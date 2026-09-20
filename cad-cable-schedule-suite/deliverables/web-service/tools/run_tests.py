# -*- coding: utf-8 -*-
r"""一键跑测试：先拉起服务，跑完自动关掉。

    .venv\Scripts\python.exe tools\run_tests.py

要点：
- 总是启动**全新**的服务进程。复用已在运行的服务会加载旧版内核，
  造成"测试通过但实际还是老结果"的假象。
- 服务日志写入 logs/server.log，不混进测试输出（uvicorn 的 stderr 会被
  PowerShell 当成原生命令错误，污染退出码判断）。
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
PORT = 8100
URL = f"http://127.0.0.1:{PORT}"
LOG = PROJECT / "logs" / "server.log"


def wait_ready(timeout: float = 40.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{URL}/api/health", timeout=2) as r:
                if r.status == 200:
                    return True
        except (urllib.error.URLError, OSError):
            time.sleep(0.6)
    return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-server", action="store_true", help="复用已在运行的服务")
    args = parser.parse_args()

    server = None
    logfile = None
    if not args.no_server:
        try:
            with urllib.request.urlopen(f"{URL}/api/health", timeout=2):
                print(f"{URL} 已有服务在运行，请先停止它（或加 --no-server 复用）。", file=sys.stderr)
                return 2
        except (urllib.error.URLError, OSError):
            pass
        LOG.parent.mkdir(parents=True, exist_ok=True)
        logfile = LOG.open("w", encoding="utf-8")
        print(f"启动服务 {URL}（日志：{LOG}）…")
        server = subprocess.Popen([sys.executable, "-m", "app.server", "--port", str(PORT)],
                                  cwd=str(PROJECT), stdout=logfile, stderr=subprocess.STDOUT)
        if not wait_ready():
            print("服务未能在 40 秒内就绪，见日志。", file=sys.stderr)
            server.terminate()
            return 2
    try:
        code = subprocess.call([sys.executable, "-m", "pytest", str(PROJECT / "tests"), "-q"],
                               cwd=str(PROJECT))
    finally:
        if server:
            server.terminate()
            try:
                server.wait(timeout=15)
            except subprocess.TimeoutExpired:
                server.kill()
        if logfile:
            logfile.close()
        print("服务已停止。")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
