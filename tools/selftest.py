"""功能自检：每个可调参数都真跑一遍，看它是否真的改变了输出。

用法（项目根目录）：
    python tools/selftest.py             # 参数矩阵 + 规则断言
    python tools/selftest.py -v          # 附带每个用例的指纹
    python tools/selftest.py --api       # 额外跑接口冒烟（需 httpx）

判定不看代码里写没写，而是渲染前后比像素指纹 + 结构指纹
（画布尺寸 / 页数 / 字数 / 缺字 / 借用字）。指纹完全一致即视为无效参数。
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app import fonts  # noqa: E402
from app.layout import NO_END, NO_START, normalize, to_traditional, wrap  # noqa: E402
from app.render import Sheet, missing_report  # noqa: E402
from app.schemas import SheetParams  # noqa: E402

VERBOSE = "-v" in sys.argv or "--verbose" in sys.argv
WITH_API = "--api" in sys.argv

BASE = dict(
    title="静夜思",
    text="床前明月光，疑是地上霜。举头望明月，低头思故乡。",
    font_id="tk",
    font_fallback=True,
    grid="tian",
    page_size="A4",
    cell_mm=17.0,
    font_ratio=0.84,
    columns=10,
    rows=12,
    auto_rows=False,
    margin_mm=14.0,
    mode="rotate",
    demo_cells=1,
    trace_cells=2,
    repeat=True,
    cycle_demo=1,
    cycle_trace=1,
    cycle_blank=2,
    trace_style="gray",
    trace_opacity=0.35,
    grid_color="#d94a4a",
    font_color="#1f1f1f",
    show_header=True,
    dpi=150,          # 自检不需要 300dpi，速度快四倍
    keep_punct=True,
    traditional=False,
    line_break_rule=True,
    break_at_punct=True,
)

failed: list[str] = []


def fingerprint(**over) -> tuple:
    params = SheetParams(**{**BASE, **over})
    sheet = Sheet(params)
    page = sheet.render_page(0)
    digest = hashlib.sha1(page.tobytes()).hexdigest()[:12]
    missing, borrowed = missing_report(params)
    return (digest, page.size, len(sheet.pages), sheet.char_count,
            tuple(missing), tuple(borrowed))


CASES: list[tuple[str, dict, str]] = [
    # (说明, 参数覆盖, 至少要动的地方：pixels / meta / both)
    ("标题 title", {"title": "望庐山瀑布"}, "pixels"),
    ("正文 text", {"text": "白日依山尽，黄河入海流。"}, "both"),
    ("格型 米字格", {"grid": "mi"}, "pixels"),
    ("格型 九宫格", {"grid": "jiugong"}, "pixels"),
    ("格型 回宫格", {"grid": "huigong"}, "pixels"),
    ("格型 空白格", {"grid": "blank"}, "pixels"),
    ("格型 竖线格", {"grid": "vertical"}, "pixels"),
    ("格型 横线格", {"grid": "line"}, "pixels"),
    ("纸张 A5", {"page_size": "A5"}, "both"),
    ("纸张 B5", {"page_size": "B5"}, "both"),
    ("格子边长 22mm", {"cell_mm": 22.0}, "both"),
    ("字号比 60%", {"font_ratio": 0.6}, "pixels"),
    ("每行字数 12", {"columns": 12}, "both"),
    ("每页行数 16", {"rows": 16}, "both"),
    ("页边距 25mm", {"margin_mm": 25.0}, "pixels"),
    ("自动铺满整页", {"auto_rows": True}, "both"),
    ("模式 全示范", {"mode": "demo"}, "both"),
    ("模式 全描红", {"mode": "trace"}, "both"),
    ("模式 行内三段", {"mode": "mixed"}, "both"),
    ("行内三段 不重复", {"mode": "mixed", "repeat": False}, "both"),
    ("示范格数 2", {"mode": "mixed", "demo_cells": 2}, "both"),
    ("描红格数 4", {"mode": "mixed", "trace_cells": 4}, "both"),
    ("循环 示范行 2", {"cycle_demo": 2}, "both"),
    ("循环 描红行 2", {"cycle_trace": 2}, "both"),
    ("循环 空白行 0", {"cycle_blank": 0}, "both"),
    ("描红 空心", {"trace_style": "outline"}, "pixels"),
    ("描红 点阵", {"trace_style": "dot"}, "pixels"),
    ("描红浓度 70%", {"trace_opacity": 0.7}, "pixels"),
    ("格线颜色", {"grid_color": "#2f6fb0"}, "pixels"),
    ("字色", {"font_color": "#7a2f1f"}, "pixels"),
    ("隐藏页眉", {"show_header": False}, "pixels"),
    ("导出 dpi 300", {"dpi": 300}, "both"),
    ("保留标点 关", {"keep_punct": False}, "both"),
    ("转繁体", {"traditional": True}, "both"),
    ("避头尾禁则 关", {"line_break_rule": False,
                       "text": "春眠不觉晓处处闻啼鸟夜来风雨声花落知多少。"}, "both"),
    ("按标点断句 关", {"break_at_punct": False}, "both"),
]


def check(name: str, fn) -> None:
    """跑一条断言，失败记进 failed"""
    try:
        ok, detail = fn()
    except Exception as exc:                      # noqa: BLE001
        ok, detail = False, f"报错 {type(exc).__name__}: {exc}"
    print(f"{name:<26}{'通过' if ok else '未通过':<8}{detail}")
    if not ok:
        failed.append(name)


def matrix() -> None:
    font_list = fonts.list_fonts()
    if len(font_list) < 2:
        print("！可用字体不足 2 款，跳过字库切换用例")
    else:
        other = next(f["id"] for f in font_list if f["id"] != BASE["font_id"])
        CASES.insert(2, (f"字库切换 {other}", {"font_id": other}, "pixels"))

    base = fingerprint()
    print(f"基线：{base[1][0]}×{base[1][1]}px，{base[2]} 页，{base[3]} 格，指纹 {base[0]}\n")
    print(f"{'用例':<26}{'结果':<8}{'像素 / 结构'}")
    print("-" * 64)

    for name, over, expect in CASES:
        try:
            got = fingerprint(**over)
        except Exception as exc:                  # noqa: BLE001
            print(f"{name:<26}{'报错':<8}{exc}")
            failed.append(name)
            continue

        pixel_changed = got[0] != base[0] or got[1] != base[1]
        meta_changed = (got[2], got[3], got[4], got[5]) != (base[2], base[3], base[4], base[5])
        ok = {"pixels": pixel_changed, "meta": meta_changed,
              "both": pixel_changed or meta_changed}[expect]

        print(f"{name:<26}{'通过' if ok else '未生效':<8}"
              f"{'像素变' if pixel_changed else '像素同'} / {'结构变' if meta_changed else '结构同'}")
        if VERBOSE:
            print(f"    {got[0]} {got[1]} 页{got[2]} 格{got[3]} "
                  f"缺{''.join(got[4]) or '无'} 借{''.join(got[5]) or '无'}")
        if not ok:
            failed.append(name)
    print()


def rules() -> None:
    """规则类断言：不只看参数有没有生效，还要看结果对不对。"""
    print(f"{'规则断言':<26}{'结果':<8}{'说明'}")
    print("-" * 64)

    check("简繁：头发发热",
          lambda: (to_traditional("头发发热") == "頭髮發熱", to_traditional("头发发热")))
    check("简繁：量词不误转",
          lambda: (to_traditional("一公里，千里之行") == "一公里，千里之行",
                   to_traditional("一公里，千里之行")))
    check("标点：全角半角一起剔",
          lambda: (normalize("春眠，不觉晓。OK? yes", keep_punct=False) == "春眠不觉晓OKyes",
                   repr(normalize("春眠，不觉晓。OK? yes", keep_punct=False))))
    check("标点：保留时不丢",
          lambda: ("，" in normalize("春眠，不觉晓。", keep_punct=True),
                   repr(normalize("春眠，不觉晓。", keep_punct=True))))

    # 避头：任何格数下，行首都不能是标点（除非整行只有一个字）
    sample = "春眠不觉晓，处处闻啼鸟。夜来风雨声，花落知多少？（孟浩然）"
    bad: list[str] = []
    for cols in range(2, 13):
        for line in wrap(sample, cols, rule=True):
            if len(line) > 1 and line[0] in NO_START:
                bad.append(f"cols={cols} «{line}»")
    check("避头：标点不上行首", lambda: (not bad, "；".join(bad[:3]) or "2–12 格全部合规"))

    # 避尾：行尾不能悬着开引号 / 左括号
    bad_end: list[str] = []
    for cols in range(2, 13):
        for line in wrap("春眠（不觉）晓说：“你好”吧", cols, rule=True):
            if line[-1] in NO_END:
                bad_end.append(f"cols={cols} «{line}»")
    check("避尾：开引号不悬行尾", lambda: (not bad_end, "；".join(bad_end[:3]) or "全部合规"))

    # 关掉禁则时必须真的不同，否则开关是假的
    check("禁则开关有区别",
          lambda: (wrap(sample, 5, True) != wrap(sample, 5, False),
                   f"开 {wrap(sample, 5, True)} / 关 {wrap(sample, 5, False)}"))

    # 转繁体后实际要画的是繁体字，缺字检查得跟着走
    def trad_missing():
        p = SheetParams(title="", text="床前明月光", font_id="sys-stxingka",
                        traditional=True, dpi=150)
        missing, borrowed = missing_report(p)
        return ("牀" in "".join(missing + borrowed), f"缺/借 {''.join(missing + borrowed)}")

    check("繁体缺字也检查", trad_missing)

    def fallback():
        p = SheetParams(title="", text="龘靐齉", font_id="sys-stxingka",
                        font_fallback=True, dpi=150)
        s = Sheet(p)
        s.render_page(0)
        return (bool(s.borrowed or s.missing), f"借 {''.join(s.borrowed) or '无'}")

    check("缺字回退", fallback)

    def no_fallback():
        p = SheetParams(title="", text="龘靐齉", font_id="sys-stxingka",
                        font_fallback=False, dpi=150)
        s = Sheet(p)
        s.render_page(0)
        return (len(s.missing) > 0, f"缺 {''.join(s.missing) or '无'}")

    check("关回退时如实报缺字", no_fallback)


def api() -> None:
    """接口冒烟：需要 httpx（pip install httpx）"""
    print(f"\n{'接口冒烟':<26}{'结果':<8}{'说明'}")
    print("-" * 64)
    try:
        import io
        import zipfile

        from fastapi.testclient import TestClient
        from pypdf import PdfReader

        from app.main import app
    except ImportError as exc:
        print(f"{'跳过':<26}{'缺依赖':<8}{exc}")
        return

    c = TestClient(app)
    P = dict(BASE)

    def one(name, fn):
        try:
            ok, detail = fn()
        except Exception as exc:                  # noqa: BLE001
            ok, detail = False, f"报错 {type(exc).__name__}: {exc}"
        print(f"{name:<26}{'通过' if ok else '未通过':<8}{detail}")
        if not ok:
            failed.append(name)

    one("/api/health", lambda: (c.get("/api/health").json() == {"ok": True}, "ok"))

    def meta():
        d = c.get("/api/meta").json()
        caps = d.get("capabilities", {})
        return (bool(d["fonts"]) and len(d["charsets"]) == 4 and "traditional" in caps,
                f"{len(d['fonts'])} 字体 / {len(d['charsets'])} 字表 / 繁体={caps.get('traditional')}")

    one("/api/meta", meta)
    one("/api/fonts/tk/sample",
        lambda: (c.get("/api/fonts/tk/sample").headers["content-type"] == "image/png", "PNG"))
    one("/api/charset/freq3500",
        lambda: (len(c.get("/api/charset/freq3500").json()["chars"]) == 3500, "3500 字"))
    one("/api/charset 不存在", lambda: (c.get("/api/charset/nope").status_code == 404, "404"))

    def preview():
        d = c.post("/api/preview", json={"params": P, "page": 0}).json()
        return (d["image"].startswith("data:image/png;base64,") and d["pages"] >= 1,
                f"{d['pages']} 页 / {d['char_count']} 格")

    one("/api/preview", preview)
    one("/api/preview full",
        lambda: (c.post("/api/preview", json={"params": P, "page": 0, "full": True})
                 .json()["image"].startswith("data:image/png;base64,"), "全 dpi 预览"))

    def export_pages():
        r = c.post("/api/export", json={"params": P, "split_size": 0})
        pdf = PdfReader(io.BytesIO(r.content))
        box = pdf.pages[0].mediabox
        a4 = abs(float(box.width) - 595.28) < 1 and abs(float(box.height) - 841.89) < 1
        prev = c.post("/api/preview", json={"params": P, "page": 0}).json()["pages"]
        return (r.status_code == 200 and len(pdf.pages) == prev and a4,
                f"{len(pdf.pages)} 页 A4，与预览一致")

    one("/api/export PDF", export_pages)

    def export_300():
        r300 = c.post("/api/export", json={"params": dict(P, dpi=300), "split_size": 0})
        r150 = c.post("/api/export", json={"params": P, "split_size": 0})
        a = PdfReader(io.BytesIO(r300.content))
        b = PdfReader(io.BytesIO(r150.content))
        return (len(a.pages) == len(b.pages),
                f"150dpi {len(b.pages)} 页 / 300dpi {len(a.pages)} 页")

    one("预览与导出页数一致", export_300)

    def split():
        r = c.post("/api/export", json={"params": P, "split_size": 12})
        names = zipfile.ZipFile(io.BytesIO(r.content)).namelist()
        return (r.headers["content-type"] == "application/zip" and len(names) == 2,
                f"{len(names)} 册")

    one("/api/export 分册", split)

    def parse():
        r = c.post("/api/parse", files={"file": ("a.txt", "床前明月光".encode("gb18030"))})
        bad = c.post("/api/parse", files={"file": ("a.docx", b"xx")})
        return (r.json()["text"] == "床前明月光" and bad.status_code == 415,
                "GB18030 可读，docx 明确拒绝")

    one("/api/parse", parse)

    def upload():
        bad = c.post("/api/fonts/upload", files={"file": ("x.ttf", bytes(2000), "font/ttf")})
        dup = c.post("/api/fonts/upload",
                     files={"file": ("tk.ttf", (ROOT / "backend/fonts/tk.ttf").read_bytes(),
                                     "font/ttf")})
        return (bad.status_code == 400 and dup.status_code == 200,
                f"非中文字体 {bad.status_code}，重复上传复用 {dup.json()['font']['id']}")

    one("/api/fonts/upload", upload)

    def trad_api():
        a = c.post("/api/preview", json={"params": dict(P, traditional=True),
                                         "page": 0, "full": True}).json()
        b = c.post("/api/preview", json={"params": P, "page": 0, "full": True}).json()
        return (a["image"] != b["image"], "繁体预览与简体不同")

    one("接口层繁体生效", trad_api)


def main() -> int:
    matrix()
    rules()
    if WITH_API:
        api()
    print("-" * 64)
    if failed:
        print(f"共 {len(failed)} 项未通过：")
        for item in failed:
            print("  -", item)
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
