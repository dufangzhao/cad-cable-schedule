# -*- coding: utf-8 -*-
"""CLI 输出命名逻辑回归测试（插件引擎入口 deliverables/menu-plugin/main.py）。

覆盖引擎 CLI 的输出目录 / 命名启发式：

* 输入位于系统临时目录（插件导出选择集的真实场景）→ 结果落桌面，文件名是
  '{project前缀}电缆汇总表.xlsx'，**不带输入文件的临时随机名**；
* --output-dir：结果落指定目录（文件名仍走默认规则）；
* --output-name：只自定义文件名（目录仍走默认启发式）；
* --timestamp：扩展名前插入 _yyyymmdd-HHMMSS；
* --project P：文件名加 P_ 前缀；
* 重名不覆盖（_unique 追加时间戳后缀）；
* --response：回写 SAVE_PATH= 行。

本文件只做黑盒测试：用 subprocess 调真实 CLI，不 import 引擎模块，因此
引擎内部重构不会让测试失效。

输入 TSV 由本文件手写（表头行 + 3 行数据），格式与 core/aggregate.py 的
entities_from_tsv 一致，六个制表符分隔字段：

    handle | layer | x | y | height | text

列头文字取自 HEADER_ALIASES（电缆号/电缆型号/选用芯数/每芯截面/长度），
各列按 x 网格排开、数据行 y 递减，保证 extract_tables 能识别为可汇总表。

依赖真实用户桌面：写桌面的用例在桌面缺失/不可写时 skip，用完即删本次新增的
xlsx（fixture 里做快照对比，不碰用户原有文件）。
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

# --------------------------------------------------------------------------- #
# 路径与常量
# --------------------------------------------------------------------------- #
SUITE_ROOT = Path(__file__).resolve().parent.parent
MAIN_PY = SUITE_ROOT / "deliverables" / "menu-plugin" / "main.py"   # 插件引擎入口（插件唯一源码目录）

TSV_HEADER = ["handle", "layer", "x", "y", "height", "text"]

# 列头 x 网格：电缆号 / 电缆型号 / 选用芯数 / 每芯截面 / 长度
COL_X = {"cable_id": 0.0, "spec": 60.0, "selected_cores": 120.0,
         "core_section": 180.0, "length": 240.0}
HEADER_Y = 100.0
ROW_Y = (90.0, 80.0, 70.0)
TEXT_HEIGHT = 3.0
LAYER = "电缆表"

# 默认文件名的固定部分（main.py 的默认命名规则）。
# 带 --project P 时是 "P_电缆汇总表.xlsx"；重名时 _unique 会追加 _yyyymmdd-HHMMSS。
DEFAULT_LABEL = "电缆汇总表"
DEFAULT_NAME_RE = re.compile(r"^电缆汇总表(_\d{8}-\d{6})?\.xlsx$")
TIMESTAMP_RE = re.compile(r"_\d{8}-\d{6}\.xlsx$")


# --------------------------------------------------------------------------- #
# 输入构造
# --------------------------------------------------------------------------- #
def _tsv_cell(handle, x, y, text):
    return "\t".join([handle, LAYER, repr(x), repr(y), repr(TEXT_HEIGHT), text])


def write_min_cable_tsv(path):
    """造一份最小可识别的电缆表 TSV，返回写入的路径。"""
    # 表头行必须是引擎 HEADER_ALIASES 里的中文表头文字（内部键名只是定位用）
    header_texts = ["电缆号", "电缆型号", "选用芯数", "每芯截面", "长度(m)"]
    lines = ["\t".join(TSV_HEADER)]
    n = 0
    for (name, x), text in zip(COL_X.items(), header_texts):
        n += 1
        lines.append(_tsv_cell("H%03d" % n, x, HEADER_Y, text))

    rows = [
        ("K1", "YJV-4x25", "4", "25", "12.5"),
        ("K2", "YJV-4x25", "4", "25", "8"),
        ("K3", "KVV-2x4", "2", "4", "30"),
    ]
    for row_index, row in enumerate(rows):
        y = ROW_Y[row_index]
        for (name, x), text in zip(COL_X.items(), row):
            n += 1
            lines.append(_tsv_cell("D%03d" % n, x, y, text))

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def make_temp_input(name="cblsum001.tsv"):
    """把 TSV 放到系统临时目录的子目录下，模拟插件导出选择集的场景。"""
    root = Path(tempfile.mkdtemp(prefix="cblsum-cli-test-"))
    return write_min_cable_tsv(root / name)


# --------------------------------------------------------------------------- #
# 运行引擎
# --------------------------------------------------------------------------- #
def run_engine(*args, cwd=None):
    """以 [sys.executable, deliverables/menu-plugin/main.py, ...] 跑引擎。"""
    cmd = [sys.executable, str(MAIN_PY)] + [str(a) for a in args]
    env = dict(os.environ)
    env.setdefault("CBLSUM_CWD", str(cwd or SUITE_ROOT))
    return subprocess.run(
        cmd,
        cwd=str(cwd or SUITE_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
        env=env,
    )


def assert_engine_ok(proc):
    assert proc.returncode == 0, (
        "引擎退出码 %s\n--- stdout ---\n%s\n--- stderr ---\n%s"
        % (proc.returncode, proc.stdout, proc.stderr)
    )


# --------------------------------------------------------------------------- #
# 找产出文件
# --------------------------------------------------------------------------- #
def _xlsx_in(directory):
    directory = Path(directory)
    if not directory.is_dir():
        return []
    return sorted(p for p in directory.iterdir()
                  if p.is_file() and p.suffix.lower() == ".xlsx")


def find_output(directory, prefix=""):
    """在（本测试新建的）directory 里找唯一一个以 prefix 开头的 xlsx。"""
    hits = [p for p in _xlsx_in(directory) if p.name.startswith(prefix)]
    assert len(hits) == 1, (
        "%s 里以 %r 开头的 xlsx 应恰好 1 个，实际 %s"
        % (directory, prefix, [p.name for p in hits])
    )
    return hits[0]


def desktop_dir():
    return Path.home() / "Desktop"


class DesktopGuard:
    """桌面快照守卫：只认本次运行新增的 xlsx，用完删掉。"""

    def __init__(self):
        self.desktop = desktop_dir()
        if not self.desktop.is_dir():
            pytest.skip("桌面目录不存在：%s" % self.desktop)
        probe = self.desktop / ".cblsum-write-probe.tmp"
        try:
            probe.write_text("probe", encoding="utf-8")
            probe.unlink()
        except OSError as exc:
            pytest.skip("桌面不可写：%s（%s）" % (self.desktop, exc))
        self.before = set(_xlsx_in(self.desktop))

    def new(self, prefix=""):
        """本次新增的桌面 xlsx（可按文件名前缀过滤）。"""
        return sorted(p for p in _xlsx_in(self.desktop)
                      if p not in self.before and p.name.startswith(prefix))

    def new_one(self, prefix=""):
        hits = self.new(prefix)
        assert len(hits) == 1, (
            "桌面本次应新增 1 个以 %r 开头的 xlsx，实际 %s"
            % (prefix, [p.name for p in hits])
        )
        return hits[0]

    def cleanup(self):
        for path in self.new():
            try:
                path.unlink()
            except OSError:
                pass


@pytest.fixture
def guard():
    g = DesktopGuard()
    try:
        yield g
    finally:
        g.cleanup()


# --------------------------------------------------------------------------- #
# 默认：临时输入 → 桌面
# --------------------------------------------------------------------------- #
def test_default_from_temp_lands_on_desktop_without_temp_stem(guard):
    """默认：临时输入落桌面，名字固定，不含输入文件的临时随机名。"""
    src = make_temp_input("cblsum001.tsv")
    try:
        assert "Temp" in str(src.parent) or "tmp" in str(src.parent).lower(), src.parent

        proc = run_engine("--input", str(src))
        assert_engine_ok(proc)

        out = guard.new_one()
        assert out.parent == guard.desktop, str(out)
        assert DEFAULT_LABEL in out.name, out.name
        # 就是默认名（重名时允许 _unique 的 _yyyymmdd-HHMMSS 后缀）
        assert DEFAULT_NAME_RE.match(out.name), out.name
        # 输入文件的临时随机名不得进入结果文件名
        assert src.stem not in out.name, "%r 不该出现在 %r" % (src.stem, out.name)
        assert "cblsum" not in out.name.lower(), out.name
    finally:
        shutil.rmtree(str(src.parent), ignore_errors=True)


def test_default_output_dir_option_is_used():
    """--output-dir：文件落指定目录，且目录不存在时自动创建。"""
    src = make_temp_input("cblsum002.tsv")
    root = Path(tempfile.mkdtemp(prefix="cblsum-cli-outdir-"))
    target_dir = root / "结果"
    try:
        proc = run_engine("--input", str(src), "--output-dir", str(target_dir))
        assert_engine_ok(proc)

        assert target_dir.is_dir(), "引擎应自动创建 --output-dir 指定的目录"
        out = find_output(target_dir)
        assert out.parent == target_dir
        assert DEFAULT_LABEL in out.name, out.name
        assert "cblsum" not in out.name.lower(), out.name
    finally:
        shutil.rmtree(str(src.parent), ignore_errors=True)
        shutil.rmtree(str(root), ignore_errors=True)


def test_output_name_overrides_file_name_only(guard):
    """--output-name：文件名等于给定名字，目录仍走默认启发式（桌面）。"""
    src = make_temp_input("cblsum003.tsv")
    name = "自定义结果.xlsx"
    stem = Path(name).stem
    try:
        proc = run_engine("--input", str(src), "--output-name", name)
        assert_engine_ok(proc)

        out = guard.new_one(stem)
        assert out.parent == guard.desktop
        assert out.suffix == ".xlsx", out.name
        # 同名文件已存在时 _unique 会加后缀，因此允许 stem 前缀变体
        assert out.name == name or out.name.startswith(stem + "_"), out.name
    finally:
        shutil.rmtree(str(src.parent), ignore_errors=True)


def test_output_name_without_extension_gets_xlsx():
    """--output-name 不带扩展名时按 .xlsx 处理，可与 --output-dir 组合。"""
    src = make_temp_input("cblsum004.tsv")
    root = Path(tempfile.mkdtemp(prefix="cblsum-cli-name-"))
    try:
        proc = run_engine("--input", str(src), "--output-dir", str(root),
                          "--output-name", "cable-summary")
        assert_engine_ok(proc)

        out = find_output(root, prefix="cable-summary")
        assert out.parent == root
        assert out.name == "cable-summary.xlsx" or out.stem.startswith("cable-summary_"), out.name
    finally:
        shutil.rmtree(str(src.parent), ignore_errors=True)
        shutil.rmtree(str(root), ignore_errors=True)


def test_timestamp_option_inserts_stamp_before_extension(guard):
    """--timestamp：扩展名前加 _yyyymmdd-HHMMSS。"""
    src = make_temp_input("cblsum005.tsv")
    try:
        proc = run_engine("--input", str(src), "--timestamp")
        assert_engine_ok(proc)

        out = guard.new_one()
        assert TIMESTAMP_RE.search(out.name), "文件名缺少 _yyyyMMdd-HHMMSS：%s" % out.name
        assert DEFAULT_LABEL in out.name, out.name
    finally:
        shutil.rmtree(str(src.parent), ignore_errors=True)


def test_project_option_prefixes_file_name(guard):
    """--project P：文件名以 P_ 开头。"""
    src = make_temp_input("cblsum006.tsv")
    try:
        proc = run_engine("--input", str(src), "--project", "P")
        assert_engine_ok(proc)

        out = guard.new_one("P_")
        assert out.name.startswith("P_" + DEFAULT_LABEL), out.name
        assert re.match(r"^P_电缆汇总表(_\d{8}-\d{6})?\.xlsx$", out.name), out.name
    finally:
        shutil.rmtree(str(src.parent), ignore_errors=True)


def test_project_option_applies_to_explicit_output(tmp_path):
    """--project P 对显式 --output / --output-name 同样生效。

    回归：插件把「保存为」当 --output 传下来，而那条分支原来直接采用完整路径、
    把工程/图号整个丢掉（用户："设置了工号，保存出来的文件名里没有"）。
    """
    src = make_temp_input("cblsum008.tsv")
    try:
        # ① 显式路径 + 工号 → 工号拼在文件名最前面
        d1 = tmp_path / "explicit"
        d1.mkdir()
        proc = run_engine("--input", str(src), "--output", str(d1 / "电缆汇总表.xlsx"),
                          "--project", "样例工程-V2")
        assert_engine_ok(proc)
        assert [p.name for p in _xlsx_in(d1)] == ["样例工程-V2_电缆汇总表.xlsx"], _xlsx_in(d1)

        # ② 文件名里已经带工号 → 不重复拼
        d2 = tmp_path / "already"
        d2.mkdir()
        proc = run_engine("--input", str(src), "--output", str(d2 / "样例工程-V2_电缆汇总表.xlsx"),
                          "--project", "样例工程-V2")
        assert_engine_ok(proc)
        assert [p.name for p in _xlsx_in(d2)] == ["样例工程-V2_电缆汇总表.xlsx"], _xlsx_in(d2)

        # ③ --output-name + 工号 + 时间戳：工号在前，时间戳紧贴扩展名
        d3 = tmp_path / "named"
        d3.mkdir()
        proc = run_engine("--input", str(src), "--output-dir", str(d3),
                          "--output-name", "自定义.xlsx", "--project", "A1", "--timestamp")
        assert_engine_ok(proc)
        names = [p.name for p in _xlsx_in(d3)]
        assert len(names) == 1 and re.match(r"^A1_自定义_\d{8}-\d{6}\.xlsx$", names[0]), names

        # ④ 没给工号 → 文件名原样不动
        d4 = tmp_path / "noTag"
        d4.mkdir()
        proc = run_engine("--input", str(src), "--output", str(d4 / "电缆汇总表.xlsx"))
        assert_engine_ok(proc)
        assert [p.name for p in _xlsx_in(d4)] == ["电缆汇总表.xlsx"], _xlsx_in(d4)
    finally:
        shutil.rmtree(str(src.parent), ignore_errors=True)


def test_duplicate_output_is_not_overwritten(guard):
    """重名不覆盖：第二次运行产出新文件，第一次的文件原样保留。"""
    src = make_temp_input("cblsum007.tsv")
    name = "重名测试.xlsx"
    stem = Path(name).stem
    try:
        first = run_engine("--input", str(src), "--output-name", name)
        assert_engine_ok(first)
        created = guard.new(stem)
        assert [p.name for p in created] == [name], [p.name for p in created]
        stamp = created[0].stat().st_mtime_ns
        size = created[0].stat().st_size

        second = run_engine("--input", str(src), "--output-name", name)
        assert_engine_ok(second)

        created = sorted(guard.new(stem), key=lambda p: p.stat().st_mtime_ns)
        assert len(created) == 2, [p.name for p in created]
        assert created[0].name == name, [p.name for p in created]
        assert created[0].name != created[1].name, "第二次运行不应覆盖第一次的结果"
        assert created[0].stat().st_mtime_ns == stamp, "第一次的文件被改写了"
        assert created[0].stat().st_size == size
    finally:
        shutil.rmtree(str(src.parent), ignore_errors=True)


def test_response_file_reports_save_path(guard):
    """--response：回写 SAVE_PATH= 行，且指向真实落盘文件。"""
    src = make_temp_input("cblsum008.tsv")
    response = src.parent / "response.txt"
    try:
        proc = run_engine("--input", str(src), "--response", str(response))
        assert_engine_ok(proc)

        assert response.is_file(), "引擎应写出 --response 文件：%s" % response
        raw = response.read_bytes()
        text = None
        for enc in ("utf-8-sig", "utf-8", "gbk", "cp936"):
            try:
                text = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        assert text is not None, "响应文件无法解码"

        save_lines = [ln for ln in text.splitlines() if ln.startswith("SAVE_PATH=")]
        assert len(save_lines) == 1, text
        saved = Path(save_lines[0].split("=", 1)[1].strip())
        assert saved.exists(), "SAVE_PATH 指向的文件不存在：%s" % saved
        assert saved.suffix.lower() == ".xlsx", saved.name
        assert saved.resolve().parent == guard.desktop.resolve(), str(saved)
        assert DEFAULT_NAME_RE.match(saved.name), saved.name
    finally:
        shutil.rmtree(str(src.parent), ignore_errors=True)
