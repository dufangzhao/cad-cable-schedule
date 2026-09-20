# -*- coding: utf-8 -*-
"""跨交付物一致性测试：三条路径必须算出同一个数。

插件引擎（exe）、网页服务（HTTP）、agent 内核（skill 的脚本）虽然各自打包、
各自带一份 core/aggregate.py，但汇总口径只有一份权威实现，结果必须逐类一致。

可用的输入（按存在性自动挑选，缺了就跳过对应用例）：
  1) 真实图纸的选择集 artifact（本机历史会话留下）
  2) 内置小电缆表夹具（一定有，覆盖合并/占位符/单行表/负荷表排除）
"""
from __future__ import annotations

import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import urllib.request
import uuid
from pathlib import Path

import pytest
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "deliverables" / "menu-plugin"
WEB = ROOT / "deliverables" / "web-service"
ENGINE = PLUGIN / "cad-plugin" / "cable-summary.exe"
PLUGIN_MAIN = PLUGIN / "main.py"
SKILL_CORE = Path.home() / ".dsh" / "skills" / "cad-cable-schedule" / "scripts" / "电缆汇总统计.py"
REAL_ARTIFACT = Path(
    r"C:\Users\ASUS\AppData\Local\Temp\hermes-cad\b9d82655-5d1e-41d7-8805-88e4d70645b5\drawing_structure.json"
)
VENV = ROOT / ".venv" / "Scripts" / "python.exe"
PY = str(VENV) if VENV.exists() else sys.executable

HDR = {"cable_id": "电缆号", "start": "起 点", "end": "终  点", "wire_numbers": "线          号",
       "required_cores": "需用芯数", "spec": "电缆型号", "selected_cores": "选用芯数",
       "core_section": "每芯截面", "length": "长度(m)", "remark": "备     注"}
X = {"cable_id": 0.0, "start": 1842.6, "end": 3708.5, "wire_numbers": 9352.3,
     "required_cores": 17051.6, "spec": 19050.0, "selected_cores": 21072.0,
     "core_section": 23065.8, "length": 25082.5, "remark": 31788.8}


def build_tsv() -> str:
    lines = ["handle\tlayer\tx\ty\theight\ttext"]
    n = 0

    def add(x, y, text):
        nonlocal n
        n += 1
        lines.append(f"T{n:05X}\tC-4\t{x}\t{y}\t500.0\t{text}")

    def table(ox, rows):
        for key, label in HDR.items():
            add(ox + X[key], 0.0, label)
        for i, row in enumerate(rows):
            y = -1275.0 - i * 700.0
            for key, value in row.items():
                add(ox + X[key], y + (-150.0 if key in ("cable_id", "wire_numbers") else -125.0), value)

    table(0.0, [
        {"cable_id": "K1", "spec": "KVV", "selected_cores": "4", "core_section": "1.5", "length": "13"},
        {"cable_id": "K2", "spec": "KVV", "selected_cores": "4", "core_section": "1.5", "length": "13"},
        {"cable_id": "K3", "spec": "KVV", "selected_cores": "4", "core_section": "-", "length": "-"},
    ])
    table(320000.0, [
        {"cable_id": "UK1", "spec": "YJV-0.6/1kV", "selected_cores": "2", "core_section": "2.5", "length": "25"},
    ])
    for label, x in [("电缆号", 0.0), ("起 点", 1842.6), ("终  点", 3708.5), ("最大需要容量", 5907.8)]:
        add(640000.0 + x, 0.0, label)
    add(640000.0, -1275.0, "X1")
    return "\n".join(lines) + "\n"


def rows_from_xlsx(path: Path) -> list[tuple]:
    """取「电缆汇总」表的全部数据行。

    注意：汇总表自 2026-09 起**不再有合计行**，所以是到最后一行（以前这里写的是
    range(2, max_row) 故意丢掉合计行，合计行取消后会误删最后一条数据）。
    备用电缆在独立的「备用电缆」表里，不属于正式统计，不取。
    """
    ws = load_workbook(path)["电缆汇总"]
    return [tuple(c.value for c in ws[r]) for r in range(2, ws.max_row + 1)]


def run_plugin(tsv: Path, out_dir: Path) -> list[tuple]:
    """插件引擎：优先冻结的 exe，其次 Python 入口。"""
    cmd = ([str(ENGINE)] if ENGINE.exists() else [PY, str(OFFLINE_MAIN)])
    target = out_dir / "plugin.xlsx"
    proc = subprocess.run(cmd + ["--input", str(tsv), "--output", str(target), "--quiet"],
                          capture_output=True, text=True, encoding="utf-8", timeout=300)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    return rows_from_xlsx(target)


def run_skill_core(tsv: Path) -> list[tuple]:
    """agent 内核：直接调用 skill 侧的汇总脚本（它自己的 CLI 也走同一套代码）。"""
    src = REAL_ARTIFACT if REAL_ARTIFACT.exists() else None
    script = SKILL_CORE
    assert script.exists(), f"找不到 skill 内核：{script}"
    spec = importlib.util.spec_from_file_location("skill_core", script)
    core = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(core)
    texts = core.entities_from_tsv(tsv)
    records, candidates = core.extract_tables(texts)
    model = core.build_summary(records, {"candidate_tables": candidates})
    return [(r["spec"], r["selected_cores"], r["core_section"], r["total_length"], r["quantity"])
            for r in model["records"]]


def test_plugin_and_skill_agree(tmp_path):
    """插件引擎 exe 与 skill 内核必须给出逐类一致的结果。"""
    tsv = tmp_path / "sel.tsv"
    tsv.write_text(build_tsv(), encoding="utf-8")
    plugin = run_plugin(tsv, tmp_path)
    skill = run_skill_core(tsv)
    assert plugin == skill, f"两条路径结果不一致：\n插件={plugin}\nskill={skill}"
    assert sum(r[4] for r in plugin) == 4          # K1/K2 合并 2 + K3 1 + UK1 1
    assert len(plugin) == 3                        # 三项一致即合并：KVV/4/1.5、KVV/4/-、YJV/2/2.5


def test_web_service_agrees_with_plugin(tmp_path):
    """网页服务与插件引擎必须给出逐类一致的结果（同一份内核的两份副本）。"""
    pytest.importorskip("fastapi")
    tsv = tmp_path / "sel.tsv"
    tsv.write_text(build_tsv(), encoding="utf-8")
    plugin = run_plugin(tsv, tmp_path)

    import os
    env = dict(os.environ)
    server = subprocess.Popen([PY, "-m", "app.server", "--port", "8177"], cwd=str(WEB), env=env,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        import time
        base = "http://127.0.0.1:8177"
        for _ in range(40):
            try:
                urllib.request.urlopen(base + "/api/health", timeout=2)
                break
            except Exception:
                time.sleep(0.5)
        else:
            pytest.fail("网页服务未能启动")

        boundary = "----c" + uuid.uuid4().hex
        buf = io.BytesIO()
        buf.write(f"--{boundary}\r\n".encode())
        buf.write(f'Content-Disposition: form-data; name="file"; filename="sel.tsv"\r\n\r\n'.encode())
        buf.write(tsv.read_bytes())
        buf.write(f"\r\n--{boundary}--\r\n".encode())
        req = urllib.request.Request(base + "/api/summarize", data=buf.getvalue(),
                                     headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
        with urllib.request.urlopen(req, timeout=300) as r:
            data = json.loads(r.read().decode())
        with urllib.request.urlopen(f"{base}/api/download?id={data['ticket']}", timeout=60) as r:
            blob = r.read()
        web_xlsx = tmp_path / "web.xlsx"
        web_xlsx.write_bytes(blob)
        assert rows_from_xlsx(web_xlsx) == plugin, "网页服务与插件引擎结果不一致"
    finally:
        server.terminate()
        try:
            server.wait(timeout=15)
        except subprocess.TimeoutExpired:
            server.kill()


@pytest.mark.skipif(not REAL_ARTIFACT.exists(), reason="本机没有真实选择集 artifact")
def test_real_drawing_matches_known_numbers(tmp_path):
    """真实图纸回归：exe、skill 内核两条路径都要得到 49 类 / 145 根。"""
    sys.path.insert(0, str(ROOT))
    if not SKILL_CORE.exists():
        pytest.skip("找不到 skill 内核")
    spec = importlib.util.spec_from_file_location("skill_core2", SKILL_CORE)
    core = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(core)

    texts = core.entities_from_artifact(core.load_artifact(REAL_ARTIFACT))
    tsv = tmp_path / "real.tsv"
    core.write_tsv(texts, tsv)

    model = core.build_summary(core.extract_tables(texts)[0], {})
    assert model["metadata"]["summary_row_count"] == 11, "新口径：三项合并后 11 类"
    assert model["metadata"]["total_quantity"] == 145
    assert model["metadata"]["total_length"] == 1279

    plugin = run_plugin(tsv, tmp_path)
    assert sum(r[4] for r in plugin) == 145, "插件引擎与 skill 内核在真实图纸上不一致"
    assert len(plugin) == 11, "新口径下真实图纸应为 11 类"
