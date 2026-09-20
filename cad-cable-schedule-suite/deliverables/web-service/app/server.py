# -*- coding: utf-8 -*-
"""电缆汇总表内网网页服务。

把 core/aggregate.py 的确定性内核套一层 HTTP 外壳，让不接触 agent 的同事也能
"上传 DXF → 下载电缆汇总表.xlsx"。

三种上传内容任选：
- DXF：在 CAD 里整图另存或 WBLOCK 选中的电缆表（含几何，体积大）
- TSV：CAD 插件导出的选择集文字清单（85 KB 量级，不泄露图纸其余内容）——推荐
- JSON：read_drawing_structure 的 artifact（agent 路径复用）

服务本身不连接 CAD、不依赖 MCP；图纸只在请求期间落在临时目录，处理完即删。
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from core import aggregate as core

MAX_UPLOAD_BYTES = 64 * 1024 * 1024
ALLOWED_SUFFIXES = {".dxf", ".tsv", ".txt", ".json"}
TICKET_TTL_SECONDS = 30 * 60          # 取件票据有效期，防临时文件堆积

app = FastAPI(title="电缆汇总表服务", version="1.0.0")
_TICKETS: dict[str, tuple[Path, str, float]] = {}


def _purge_expired() -> None:
    now = time.time()
    for key, (path, _, created) in list(_TICKETS.items()):
        if now - created > TICKET_TTL_SECONDS:
            _TICKETS.pop(key, None)
            shutil.rmtree(path.parent, ignore_errors=True)


def _sniff(suffix: str, head: str) -> str | None:
    """内容嗅探，不只信扩展名。返回 None 表示通过，否则返回错误说明。"""
    if suffix == ".dxf":
        if "SECTION" not in head and "HEADER" not in head:
            return "文件内容不像 DXF，请确认导出格式"
    elif suffix in {".tsv", ".txt"}:
        if "handle\tlayer\tx\ty\theight\ttext" not in head:
            return "TSV 表头不符合插件导出格式（应为 handle/layer/x/y/height/text）"
    elif suffix == ".json":
        if '"scan"' not in head and '"entities"' not in head:
            return "JSON 不是 read_drawing_structure artifact"
    return None


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return (Path(__file__).resolve().parent / "static" / "index.html").read_text(encoding="utf-8")


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "schema_version": core.SCHEMA_VERSION,
            "key_fields": list(core.KEY_FIELDS), "max_upload_mb": MAX_UPLOAD_BYTES // 1024 // 1024}


@app.post("/api/summarize")
async def summarize(file: UploadFile = File(...), project: str = Form(""),
                    keep_incomplete: bool = Form(False), want: str = Form("xlsx")):
    name = (file.filename or "").strip()
    suffix = Path(name).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(415, f"只接受 {'/'.join(sorted(ALLOWED_SUFFIXES))}（收到 {suffix or '无扩展名'}）")
    payload = await file.read()
    if not payload:
        raise HTTPException(422, "上传文件为空")
    if len(payload) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"文件超过 {MAX_UPLOAD_BYTES // 1024 // 1024} MB 上限")

    problem = _sniff(suffix, payload[:4096].decode("utf-8", errors="ignore"))
    if problem:
        raise HTTPException(415, problem)

    _purge_expired()
    ticket = uuid.uuid4().hex
    workdir = Path(tempfile.mkdtemp(prefix=f"cable-{ticket[:8]}-"))
    try:
        upload = workdir / f"upload{suffix}"
        upload.write_bytes(payload)
        if suffix == ".dxf":
            texts = core.entities_from_dxf(upload)
            document = name
        elif suffix in {".tsv", ".txt"}:
            texts = core.entities_from_tsv(upload)
            document = Path(name).stem
        else:
            artifact = json.loads(payload.decode("utf-8-sig"))
            core.load_artifact(upload)          # 空选择/截断在此失败关闭
            texts = core.entities_from_artifact(artifact)
            document = (artifact.get("document") or {}).get("name") or name
        if not texts:
            raise HTTPException(422, "内容里没有文字实体，无法识别电缆表")

        records, candidates = core.extract_tables(texts)
        if not [c for c in candidates if c["usable"]]:
            raise HTTPException(422, "没有识别到可汇总的电缆表（需含 电缆号/电缆型号/选用芯数/每芯截面/长度 列）")
        if not records:
            raise HTTPException(422, "识别到列表头但没有提取到电缆数据行")

        model = core.build_summary(records, {
            "source_document": document,
            "source_input": f"{suffix} 上传",
            "candidate_tables": candidates,
        }, keep_incomplete=keep_incomplete)

        if want == "json":
            out = workdir / "cable-summary.json"
            out.write_text(json.dumps(model, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
            out_name = f"{Path(name).stem}_cable-summary.json"
        else:
            tag = f"{project.strip()}_" if project.strip() else ""
            out = workdir / "deliver.xlsx"
            core.export_summary(model, out)
            out_name = f"{tag}{Path(name).stem}_电缆汇总表.xlsx"

        _TICKETS[ticket] = (out, out_name, time.time())
        return JSONResponse({
            "valid": True,
            "ticket": ticket,
            "filename": out_name,
            "metadata": model["metadata"],
            "issues": model["issues"],
            "records": model["records"],
        })
    except HTTPException:
        shutil.rmtree(workdir, ignore_errors=True)
        raise
    except (ValueError, json.JSONDecodeError) as exc:
        shutil.rmtree(workdir, ignore_errors=True)
        raise HTTPException(422, str(exc)) from exc
    except Exception as exc:
        shutil.rmtree(workdir, ignore_errors=True)
        raise HTTPException(500, f"处理失败：{exc}") from exc


@app.get("/api/download")
def download(id: str):
    entry = _TICKETS.pop(id, None)          # 一次性取件
    if not entry:
        raise HTTPException(404, "结果不存在或已过期，请重新上传")
    path, filename, _ = entry
    if not path.exists():
        raise HTTPException(404, "结果文件已清理")
    media = ("application/json" if path.suffix == ".json"
             else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    return FileResponse(path, filename=filename, media_type=media)


def _lan_ips() -> list[str]:
    """列出本机局域网 IPv4，供同事访问。用 UDP connect 探测出口网卡，不真的发包。

    过滤回环与虚拟网卡（169.254 自动私有地址、172.16-31 的 WSL/Hyper-V），
    否则会把同事引到一个连不通的地址上。
    """
    import socket

    ips: list[str] = []
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        probe.connect(("8.8.8.8", 80))
        ips.append(probe.getsockname()[0])
        probe.close()
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if ip not in ips:
                ips.append(ip)
    except OSError:
        pass
    out = []
    for ip in ips:
        if ip.startswith(("127.", "169.254.")):
            continue
        if ip.startswith("172.") and 16 <= int(ip.split(".")[1] or 0) <= 31:
            continue
        out.append(ip)
    return out


def _print_banner(host: str, port: int) -> None:
    """把访问地址打印在服务端控制台。

    这段本来放在 .bat 里，但 .bat 现在刻意保持纯 ASCII 以避开 cmd 的编码坑，
    所以中文一律由 Python 输出（本函数在 uvicorn 启动前调用）。
    """
    print("=" * 60)
    print("  电缆汇总表服务")
    print("=" * 60)
    print()
    print(f"  本机访问 : http://127.0.0.1:{port}")
    if host in ("0.0.0.0", "::"):
        for ip in _lan_ips():
            print(f"  同事访问 : http://{ip}:{port}")
    else:
        print(f"  监听地址 : http://{host}:{port}")
    print()
    print("  关掉这个窗口即停止服务。Ctrl+C 也可停止。")
    print("=" * 60)
    print()
    # 输出被重定向到文件时 Python 走块缓冲，显式 flush 才能保证地址立刻可见
    sys.stdout.flush()


def main() -> int:
    parser = argparse.ArgumentParser(description="电缆汇总表内网网页服务")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8100)
    parser.add_argument("--workers", type=int, default=1,
                        help="DXF 解析是 CPU 密集任务（约 4 秒/张），多人使用时调大")
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    _print_banner(args.host, args.port)
    import uvicorn
    uvicorn.run("app.server:app", host=args.host, port=args.port, workers=args.workers,
                log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
