# -*- coding: utf-8 -*-
r"""网页服务自检：不碰 AutoCAD，也不需要先有图纸。

    .venv\Scripts\python.exe tools\preflight.py

会用一张内置的小电缆表跑完整链路（上传 → 汇总 → 下载 → 校验），
服务没在运行时自动临时拉起，结束后自动关闭。
"""
from __future__ import annotations

import io
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

HDR = {"cable_id": "电缆号", "start": "起 点", "end": "终  点", "wire_numbers": "线          号",
       "required_cores": "需用芯数", "spec": "电缆型号", "selected_cores": "选用芯数",
       "core_section": "每芯截面", "length": "长度(m)", "remark": "备     注"}
X = {"cable_id": 0.0, "start": 1842.6, "end": 3708.5, "wire_numbers": 9352.3,
     "required_cores": 17051.6, "spec": 19050.0, "selected_cores": 21072.0,
     "core_section": 23065.8, "length": 25082.5, "remark": 31788.8}


def build_tsv() -> bytes:
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
    ])
    table(320000.0, [
        {"cable_id": "UK1", "spec": "YJV-0.6/1kV", "selected_cores": "2", "core_section": "2.5", "length": "25"},
    ])
    for label, x in [("电缆号", 0.0), ("起 点", 1842.6), ("终  点", 3708.5), ("最大需要容量", 5907.8)]:
        add(640000.0 + x, 0.0, label)
    add(640000.0, -1275.0, "X1")
    return ("\n".join(lines) + "\n").encode("utf-8")


def post(base: str, payload: bytes, filename: str = "sel.tsv"):
    boundary = "----pf" + uuid.uuid4().hex
    body = io.BytesIO()

    def w(x):
        body.write(x.encode("utf-8") if isinstance(x, str) else x)

    w(f"--{boundary}\r\n")
    w(f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n\r\n')
    w(payload)
    w(f"\r\n--{boundary}--\r\n")
    req = urllib.request.Request(base + "/api/summarize", data=body.getvalue(),
                                headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            return exc.code, json.loads(exc.read().decode("utf-8"))
        except Exception:
            return exc.code, {}


def probe(base: str):
    try:
        with urllib.request.urlopen(base + "/api/health", timeout=5) as r:
            info = json.loads(r.read().decode())
            return info.get("ok") is True, f"schema={info.get('schema_version')}"
    except Exception as exc:
        return False, str(exc)[:60]


def main() -> int:
    results = []

    def check(ok, name, hint=""):
        results.append((ok, name, hint))
        return ok

    base = "http://127.0.0.1:8100"
    print("=" * 66)
    print("电缆汇总 · 网页服务自检")
    print("=" * 66)

    check((PROJECT / "core" / "aggregate.py").exists(), "汇总内核存在", "缺少 core/aggregate.py")
    check((PROJECT / "app" / "server.py").exists(), "服务代码存在", "缺少 app/server.py")
    check((PROJECT / "app" / "static" / "index.html").exists(), "前端页面存在", "缺少 app/static/index.html")

    reachable, detail = probe(base)
    started = None
    if not reachable:
        print("  服务未运行，正在自动启动…")
        log = PROJECT / "logs" / "server.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        started = subprocess.Popen([sys.executable, "-m", "app.server", "--port", "8100"],
                                   cwd=str(PROJECT), stdout=log.open("w", encoding="utf-8"),
                                   stderr=subprocess.STDOUT)
        for _ in range(40):
            time.sleep(0.7)
            reachable, detail = probe(base)
            if reachable:
                break
    check(reachable, f"服务可启动并响应 {base}", detail)

    if reachable:
        status, home = 200, ""
        try:
            with urllib.request.urlopen(base + "/", timeout=10) as r:
                status = r.status
                home = r.read(200).decode("utf-8", "ignore")
        except Exception as exc:
            detail = str(exc)[:60]
        check(status == 200 and "<html" in home.lower(), "首页可打开", detail)

        code, data = post(base, build_tsv())
        check(code == 200 and data.get("valid") is True, "TSV 上传可汇总", json.dumps(data)[:120])
        meta = data.get("metadata", {}) if code == 200 else {}
        check(meta.get("total_quantity") == 3, f"汇总数量正确（合计={meta.get('total_quantity')}）",
              "预期 3：K1/K2 合并 2 + UK1 1")
        check(meta.get("recognised_tables") == 2, "负荷表未被当成电缆表",
              f"识别到 {meta.get('recognised_tables')} 张")

        if code == 200 and data.get("ticket"):
            try:
                with urllib.request.urlopen(f"{base}/api/download?id={data['ticket']}", timeout=60) as r:
                    blob = r.read()
                check(len(blob) > 4000 and blob[:2] == b"PK", "下载到有效 xlsx", f"{len(blob)} 字节")
            except Exception as exc:
                check(False, "下载到有效 xlsx", str(exc)[:80])

        code2, _ = post(base, b"not a dxf at all", "fake.dxf")
        check(code2 == 415, "错误内容被拒绝", f"返回 {code2}，预期 415")

    if started is not None:
        started.terminate()
        try:
            started.wait(timeout=10)
        except subprocess.TimeoutExpired:
            started.kill()

    print()
    failed = 0
    for ok, name, hint in results:
        print(f"  [{'OK  ' if ok else '失败'}] {name}")
        if not ok:
            failed += 1
            if hint:
                print(f"         → {hint}")
    print()
    if failed == 0:
        print("全部通过。双击 启动服务.bat 后，浏览器打开 http://<本机IP>:8100 即可上传。")
    else:
        print(f"有 {failed} 项未通过，请按 → 提示处理后重跑。")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
