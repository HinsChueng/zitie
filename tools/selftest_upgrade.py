"""升级功能自检：新增参数是否真的改变输出 + 新接口冒烟。

用法（项目根目录）：
    python tools/selftest_upgrade.py          # 渲染指纹 + 规则断言
    python tools/selftest_upgrade.py --api    # 追加接口冒烟（需 pip install httpx）

判定沿用主自检的思路：不看代码里写没写，只看渲染指纹与结构是否变化。
"""
from __future__ import annotations

import hashlib
import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from PIL import Image  # noqa: E402
from app import charsets  # noqa: E402
from app.render import Sheet, parse_page_range  # noqa: E402
from app.schemas import SheetParams  # noqa: E402

WITH_API = "--api" in sys.argv
failed: list[str] = []

BASE = dict(
    title="静夜思",
    text="床前明月光，疑是地上霜。举头望明月，低头思故乡。",
    font_id="tk", font_fallback=True, grid="tian", page_size="A4",
    cell_mm=17.0, font_ratio=0.84, columns=10, rows=12, auto_rows=False,
    margin_mm=14.0, mode="rotate", demo_cells=1, trace_cells=2, repeat=True,
    cycle_demo=1, cycle_trace=1, cycle_blank=2, copy_blank=1,
    trace_style="gray", trace_opacity=0.35, grid_color="#d94a4a",
    font_color="#1f1f1f", paper_color="#FFFFFF", show_header=True, dpi=150,
    keep_punct=True, traditional=False, line_break_rule=True, break_at_punct=True,
)


def fingerprint(**over) -> tuple:
    params = SheetParams(**{**BASE, **over})
    sheet = Sheet(params)
    img = sheet.render_page(0)
    return (hashlib.sha1(img.tobytes()).hexdigest()[:12], len(sheet.pages),
            sheet.char_count, img.getpixel((2, 2)))


def report(label: str, ok: bool, detail: str = "") -> None:
    print(f"{label:<28}{'通过' if ok else '失败':<8}{detail}")
    if not ok:
        failed.append(label)


print("新增参数：渲染指纹必须与基准不同")
print("-" * 64)
base_fp = fingerprint()
CASES: list[tuple[str, dict]] = [
    ("格型 四线三格", {"grid": "pinyin4"}),
    ("格型 作文格", {"grid": "composition"}),
    ("格型 控笔格", {"grid": "control"}),
    ("模式 对临", {"mode": "copy"}),
    ("对临 空白行 3", {"mode": "copy", "copy_blank": 3}),
    ("纸色 碑帖黑底", {"paper_color": "#1B1A18", "font_color": "#F2EDE3",
                       "grid_color": "#8C8577"}),
    ("方向 竖排", {"direction": "vertical"}),
    ("模式 渐隐", {"mode": "fade"}),
    ("模式 生字卡", {"mode": "card"}),
    ("生字卡 每字 4 格", {"mode": "card", "card_cells": 4, "card_trace": 1}),
]
for label, over in CASES:
    fp = fingerprint(**over)
    report(label, fp != base_fp, f"{base_fp[:3]} → {fp[:3]}")

print("\n规则断言")
print("-" * 64)

# 选页解析
checks = [
    ("选页 空串=全部", parse_page_range("", 5) == [0, 1, 2, 3, 4]),
    ("选页 1-2,4", parse_page_range("1-2,4", 6) == [0, 1, 3]),
    ("选页 去重保序", parse_page_range("3,1,3", 4) == [2, 0]),
    ("选页 中文逗号", parse_page_range("1，3", 4) == [0, 2]),
]
for label, ok in checks:
    report(label, ok)

for bad in ("0", "9", "3-1", "abc", "1-", ""):
    if bad == "":
        continue
    try:
        parse_page_range(bad, 5)
        report(f"非法页码应报错 {bad}", False)
    except ValueError:
        report(f"非法页码应报错 {bad}", True)

# 内容库
groups = charsets.list_library()
items = [it for g in groups for it in g["items"]]
report("内容库 分组齐全", len(groups) == 11 and {"先秦史传", "史记", "诸子散文",
       "古文名篇", "唐诗", "宋词", "蒙学", "成语", "现代散文", "现代诗歌",
       "现代杂文"} <= {g["name"] for g in groups}, f"{len(groups)} 类 / {len(items)} 篇")
report("内容库 按古今两级分类",
       {g["era"] for g in groups} == {"古代", "现代"} and
       all(it.get("era") == g["era"] for g in groups for it in g["items"]) and
       sum(1 for it in items if it["era"] == "古代") >= 30 and
       sum(1 for it in items if it["era"] == "现代") >= 10,
       f"古代 {sum(1 for it in items if it['era'] == '古代')} 篇 / "
       f"现代 {sum(1 for it in items if it['era'] == '现代')} 篇")
report("内容库 含史记与左传名篇",
       {"史记", "先秦史传"} <= {g["name"] for g in groups} and
       any("曹刿" in it["title"] for it in items) and
       any("项羽" in it["title"] or "陈涉" in it["title"] for it in items))
report("内容库 含现代名篇",
       any(it["era"] == "现代" and "朱自清" in it["author"] for it in items) and
       any(it["era"] == "现代" and "鲁迅" in it["author"] for it in items) and
       any(g["name"] == "现代诗歌" and g["era"] == "现代" for g in groups))
report("内容库 全文非空", all(it["text"].strip() and it["count"] > 0 for it in items))
report("内容库 节选篇幅适合一页字帖", all(20 <= len(it["text"]) <= 120 for it in items),
       f"{min(len(it['text']) for it in items)}–{max(len(it['text']) for it in items)} 字")
report("内容库 按 id 可取", charsets.get_passage(items[0]["id"]) is not None)
report("内容库 id 不重复", len({it["id"] for it in items}) == len(items))

# 对临编排：示范行 + copy_blank 个空白行
p = SheetParams(**{**BASE, "mode": "copy", "copy_blank": 2})
sheet = Sheet(p)
# 空白行在编排里就是空列表（格子由 draw_grid 整页绘制，行数据只记「写什么」）
demo_rows = sum(1 for row in sheet.rows if row)
blank_rows = sum(1 for row in sheet.rows if not row)
report("对临 行数配比", blank_rows == demo_rows * 2,
       f"示范 {demo_rows} 行 / 空白 {blank_rows} 行")

# 黑底：纸色真的落到画布上，且描红按纸色混合
dark = fingerprint(paper_color="#1B1A18", font_color="#F2EDE3", grid_color="#8C8577")
report("黑底 像素落纸色", sum(dark[3][:3]) < 120, str(dark[3]))

# ---------- v2.1：竖排 / 渐隐 / 生字卡 / 难度 ----------
from app import difficulty  # noqa: E402

vp = dict(columns=8, rows=12, cell_mm=12, auto_rows=False)
hs = Sheet(SheetParams(**{**BASE, **vp}))
vs = Sheet(SheetParams(**{**BASE, **vp, "direction": "vertical"}))
report("竖排 网格宽高互换", hs.grid_w == vs.grid_h and hs.grid_h == vs.grid_w,
       f"横 {hs.grid_w}×{hs.grid_h} / 竖 {vs.grid_w}×{vs.grid_h}")
report("竖排 编排数据不变", len(hs.rows) == len(vs.rows) and hs.char_count == vs.char_count)
report("竖排 给出标点提示", any("标点" in w for w in vs.warnings))
report("竖排 不兼容格型回退",
       Sheet(SheetParams(**{**BASE, **vp, "direction": "vertical",
                            "grid": "pinyin4"})).params.grid == "tian")

fade = Sheet(SheetParams(**{**BASE, "mode": "fade", "columns": 8, "rows": 6,
                            "auto_rows": False, "keep_punct": False}))
fimg = fade.render_page(0)
fcell = fade.cell


def tile_mean(c: int) -> float:
    x, y = fade.x0 + c * fcell, fade.y0
    tile = fimg.crop((x + fcell // 4, y + fcell // 4,
                      x + fcell * 3 // 4, y + fcell * 3 // 4)).convert("L")
    data = list(tile.getdata())
    return sum(data) / len(data)


m1, m4, m7 = tile_mean(1), tile_mean(4), tile_mean(7)
report("渐隐 浓度逐格递减", m1 < m4 < m7, f"灰度 {m1:.1f} < {m4:.1f} < {m7:.1f}")

card = Sheet(SheetParams(**{**BASE, "mode": "card", "columns": 12,
                            "rows": 6, "auto_rows": False}))
styles = [s.style if s else None for s in card.rows[0][:6]]
report("生字卡 块结构", styles == ["demo", "trace", "trace", None, None, None], str(styles))

set_counts = {s["id"]: s["count"] for s in charsets.list_sets()}
report("分级字表 三档齐全",
       all(set_counts.get(k) == v for k, v in
           {"grade1": 100, "grade2": 300, "grade3": 500}.items()), str(
           {k: set_counts.get(k) for k in ("grade1", "grade2", "grade3")}))

a = difficulty.analyze(BASE["text"], "静夜思")
levels = [x["level"] for x in difficulty.library_levels()]
report("难度 星级合法", 1 <= a["level"] <= 5, f"{a['level']}★ {a['label']}")
report("难度 指标可解释", a["chars"] == 20 and 0 <= a["coverage"] <= 100
       and len(a["reasons"]) == 3)
report("难度 推荐三篇", len(a["recommend"]) == 3
       and all(x["reason"] for x in a["recommend"]))
report("难度 内容库有区分度", len(set(levels)) >= 3, str(sorted(set(levels))))
long = difficulty.analyze(BASE["text"] * 100)
report("难度 长文升档", long["level"] > a["level"], f"{a['level']}★ → {long['level']}★")
# 重复短诗篇幅再长也不该判成最高难度；真正难的是生僻字多 + 篇幅长
report("难度 高难样本可达 5 级",
       difficulty.analyze("天地玄黄宇宙洪荒" * 100)["level"] == 5)

# 多页复用字形工厂：渲染 2 页后仍是同一个实例
p2 = SheetParams(**{**BASE, "rows": 3, "auto_rows": False, "mode": "demo"})
s2 = Sheet(p2)
if len(s2.pages) < 2:
    report("多页渲染工厂复用", False, "测试文本未产生 2 页")
else:
    s2.render_page(0)
    first = s2._glyphs
    s2.render_page(1)
    report("多页渲染工厂复用", s2._glyphs is first and first is not None)

# PNG / PDF 选页
png = s2.page_png(0)
with Image.open(io.BytesIO(png)) as im:
    report("页 PNG 可解码", im.format == "PNG" and im.size == (s2.page_w, s2.page_h), str(im.size))

import tempfile  # noqa: E402
with tempfile.TemporaryDirectory() as tmp:
    out = s2.export_pdf(Path(tmp) / "sel.pdf", [0])
    from pypdf import PdfReader  # noqa: E402
    count = len(PdfReader(str(out)).pages)
    report("PDF 只导出选中页", count == 1, f"{count} 页")

if WITH_API:
    print("\n接口冒烟")
    print("-" * 64)
    try:
        from fastapi.testclient import TestClient  # noqa: E402
        from app.main import app  # noqa: E402
    except ImportError as exc:
        report("接口冒烟依赖", False, f"缺少 httpx：{exc}")
    else:
        client = TestClient(app)
        req = {"params": {**BASE, "rows": 4, "auto_rows": False, "mode": "demo"},
               "page": 0}

        r = client.get("/api/meta")
        report("GET /api/meta", r.status_code == 200 and
               any(g["id"] == "control" for g in r.json()["grids"]) and
               bool(r.json()["library"]))
        r = client.get("/api/library")
        lib_groups = r.json()["groups"] if r.status_code == 200 else []
        report("GET /api/library 返回古今分组", r.status_code == 200 and
               len(lib_groups) == 11 and
               {g.get("era") for g in lib_groups} == {"古代", "现代"} and
               all(it.get("era") for g in lib_groups for it in g["items"]))
        report("meta 含分级字表", any(c["id"] == "grade1" for c in client.get("/api/meta").json()["charsets"]))
        r = client.post("/api/analyze", json={"text": BASE["text"], "title": "静夜思"})
        report("POST /api/analyze", r.status_code == 200 and
               r.json()["level"] >= 1 and len(r.json()["recommend"]) == 3)
        r = client.post("/api/preview", json={"params": {**req["params"], "direction": "vertical"},
                                              "page": 0})
        report("竖排预览接口", r.status_code == 200 and
               r.json()["image"].startswith("data:image/png"))
        r = client.post("/api/preview", json=req)
        report("POST /api/preview", r.status_code == 200 and
               r.json()["image"].startswith("data:image/png"))
        r = client.post("/api/thumbnails", json={"params": req["params"], "width": 120, "limit": 5})
        report("POST /api/thumbnails", r.status_code == 200 and len(r.json()["thumbs"]) >= 1)
        r = client.post("/api/print", json={"params": req["params"], "page_range": "1", "limit": 5})
        report("POST /api/print", r.status_code == 200 and len(r.json()["pages"]) == 1)
        r = client.post("/api/export", json={"params": req["params"], "file_format": "png",
                                             "page_range": "1"})
        report("导出 PNG 单页", r.status_code == 200 and r.content[:4] == b"\x89PNG")
        # 造一份多页文本，才能真正走到「多页打 zip」这条分支
        many_params = {**req["params"], "text": BASE["text"] * 4, "rows": 3}
        r = client.post("/api/export", json={"params": many_params, "file_format": "png",
                                             "page_range": "1-2"})
        names: list[str] = []
        if r.status_code == 200 and r.content[:2] == b"PK":
            import zipfile  # noqa: E402
            with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
                names = zf.namelist()
        report("导出 PNG 多页 zip", len(names) == 2, f"{r.status_code} / {len(names)} 个文件")
        r = client.post("/api/export", json={"params": req["params"], "page_range": "1"})
        report("导出 PDF 选页", r.status_code == 200 and r.content[:4] == b"%PDF")
        r = client.post("/api/export", json={"params": req["params"], "page_range": "99"})
        report("越界页码返回 400", r.status_code == 400)

print("\n" + "-" * 64)
if failed:
    print(f"失败 {len(failed)} 项：{'、'.join(failed)}")
    sys.exit(1)
print("全部通过")
