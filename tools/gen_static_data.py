"""把后端的内容库 / 字表 / 默认参数导出成前端可内嵌的 JS 模块。

静态版（无 Python 服务）跑在浏览器里，读不到 charsets.py 和 data/charsets.json，
所以构建前把这些数据烘焙成一份 static-data.js。数据同源，不会出现两份内容库。

用法：python tools/gen_static_data.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app import charsets, difficulty  # noqa: E402
from app.main import GRID_LABELS, VERSION, library_with_levels  # noqa: E402
from app.schemas import SheetParams  # noqa: E402


def main() -> None:
    sets = charsets.load()
    freq = sets.get("freq3500", {}).get("chars", "") or sets.get("freq1000", {}).get("chars", "")

    data = {
        "version": VERSION,
        "defaults": SheetParams().model_dump(),
        "grids": [{"id": k, "name": v} for k, v in GRID_LABELS.items()],
        "page_sizes": [
            {"id": "A4", "name": "A4  210×297mm"},
            {"id": "A5", "name": "A5  148×210mm"},
            {"id": "B5", "name": "B5  176×250mm"},
        ],
        "charsets": [
            {"id": s["id"], "name": s["name"], "desc": s["desc"],
             "count": s["count"], "chars": sets.get(s["id"], {}).get("chars", "")}
            for s in charsets.list_sets()
        ],
        "library": library_with_levels(),
        "library_flat": [
            {"id": x["id"], "title": x["title"], "author": x["author"],
             "category": x["category"], "era": x["era"],
             "text": x["text"], "note": x["note"],
             "level": x["level"], "chars": x["chars"]}
            for x in difficulty._library_scores()
        ],
        "freq": freq,
    }

    # JSON 里中文不转义，便于人工核对；用 JSON.parse 包一层避免 JS 解析 Unicode 分隔符出问题
    body = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    out = ROOT / "frontend" / "src" / "static-data.js"
    out.write_text(
        "// 由 tools/gen_static_data.py 自动生成，请勿手工编辑。\n"
        "// 静态版（无服务端）用这份快照，数据源仍是 backend/app/charsets.py。\n"
        f"export const STATIC = {body}\n",
        encoding="utf-8",
    )
    print(f"已生成 {out.relative_to(ROOT)}（{out.stat().st_size / 1024:.1f} KB）")
    print(f"  字表 {len(data['charsets'])} 张 / 文库 {len(data['library'])} 类 "
          f"{len(data['library_flat'])} 篇 / 常用字 {len(freq)} 字")


if __name__ == "__main__":
    main()
