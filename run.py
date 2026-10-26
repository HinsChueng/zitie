"""一键启动：加载已构建的前端，启动后端并打开浏览器。

用法：
    python run.py                 # 默认 127.0.0.1:8000
    python run.py --port 9000
"""
from __future__ import annotations

import argparse
import os
import sys
import threading
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"

sys.path.insert(0, str(BACKEND))
os.chdir(BACKEND)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    if not (ROOT / "frontend" / "dist" / "index.html").exists():
        print("提示：未找到 frontend/dist，先执行 cd frontend && npm install && npm run build")

    import uvicorn

    from app.main import app

    url = f"http://{args.host}:{args.port}"
    if not args.no_browser:
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()

    print(f"字帖工坊已启动：{url}")
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
