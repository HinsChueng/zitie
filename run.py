"""一键启动：托管已构建的前端 + 后端 API，单端口对外。

用法：
    python run.py                 # 默认 127.0.0.1:8000，自动开浏览器
    python run.py --port 9000
    PORT=8080 python run.py       # 云平台注入 PORT 时自动绑 0.0.0.0、不开浏览器

构建前端（产物落在 backend/web）：
    cd frontend && npm install && npm run build
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
    env_port = os.environ.get("PORT")
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=int(env_port) if env_port else 8000)
    # 云平台上必须监听 0.0.0.0 才能被反向代理访问
    parser.add_argument("--host", default="0.0.0.0" if env_port else "127.0.0.1")
    parser.add_argument("--no-browser", action="store_true", default=bool(env_port))
    args = parser.parse_args()

    if not (BACKEND / "web" / "index.html").exists():
        print("提示：未找到 backend/web，先执行 cd frontend && npm install && npm run build")

    import uvicorn

    from app.main import app

    url = f"http://{args.host}:{args.port}"
    if not args.no_browser:
        threading.Timer(1.2, lambda: webbrowser.open(f"http://127.0.0.1:{args.port}")).start()

    print(f"字帖工坊已启动：{url}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
