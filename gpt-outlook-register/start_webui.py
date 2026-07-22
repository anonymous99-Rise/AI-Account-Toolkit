#!/usr/bin/env python3
"""WebUI 一键启动脚本：装依赖 → 跑 uvicorn。

用法：
    python start_webui.py             # 默认 127.0.0.1:8765
    python start_webui.py --port 9000 # 自定义端口
    python start_webui.py --host 0.0.0.0 --port 8765  # 内网监听
"""
from __future__ import annotations

import argparse
import os
import sys
import webbrowser
from pathlib import Path

# Windows 控制台 GBK 编码兼容：强制 UTF-8 输出
if sys.platform.startswith("win"):
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1", help="监听地址 (默认 127.0.0.1)")
    ap.add_argument("--port", type=int, default=8765, help="监听端口 (默认 8765)")
    ap.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    ap.add_argument("--reload", action="store_true", help="开发模式 (代码改动自动重启)")
    args = ap.parse_args()

    # 确保依赖装了
    try:
        import fastapi  # noqa: F401
        import uvicorn  # noqa: F401
    except ImportError:
        print("[!] 缺少依赖，正在安装 fastapi / uvicorn ...")
        import subprocess
        subprocess.check_call([
            sys.executable, "-m", "pip", "install",
            "fastapi", "uvicorn[standard]", "pydantic>=2",
        ])
        import fastapi  # noqa: F401
        import uvicorn  # noqa: F401

    sys.path.insert(0, str(ROOT))
    import uvicorn

    url = f"http://{args.host if args.host != '0.0.0.0' else '127.0.0.1'}:{args.port}/"
    print(f"\n🔔 团子喵 WebUI 启动中...")
    print(f"   访问: {url}\n")

    if not args.no_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass

    uvicorn.run(
        "webui.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()
