"""FastAPI 入口"""
from __future__ import annotations

import base64
import io
import re
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageDraw, ImageFont

from . import charsets, difficulty, fonts
from .layout import ALL_PUNCT, TraditionalUnavailable, traditional_available
from .render import Sheet, missing_report, parse_page_range, volume_text
from .schemas import (AnalyzeRequest, ExportRequest, PreviewRequest, PreviewResponse,
                      PrintRequest, SheetParams, ThumbRequest)

app = FastAPI(title="字帖工坊 API", version="2.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

GRID_LABELS = {
    "tian": "田字格",
    "mi": "米字格",
    "jiugong": "九宫格",
    "huigong": "回宫格",
    "blank": "空白格",
    "vertical": "竖线格",
    "line": "横线格",
    "pinyin4": "四线格",
    "composition": "作文格",
    "control": "控笔格",
}

VERSION = "2.1.0"


def safe_name(text: str, fallback: str = "字帖") -> str:
    text = re.sub(r'[\\/:*?"<>|\r\n\t]', "", (text or "").strip())
    return text[:40] or fallback


def stamp() -> str:
    return datetime.now().strftime("%Y%m%d")


def library_with_levels() -> list[dict]:
    """给内容库每篇挂上离线算出的难度星级，前端选篇时可直接看到。"""
    levels = {x["id"]: x["level"] for x in difficulty.library_levels()}
    groups = charsets.list_library()
    for group in groups:
        for item in group["items"]:
            item["level"] = levels.get(item["id"], 1)
    return groups


def preview_params(params: SheetParams) -> SheetParams:
    """预览用低 dpi 渲染再缩放，物理版式不变但快很多"""
    return params.model_copy(update={"dpi": min(params.dpi, 150)})


def build_sheet(params: SheetParams) -> Sheet:
    """构造 Sheet；转繁体缺依赖时给一句人能看懂的报错，而不是静默出简体验"""
    try:
        return Sheet(params)
    except TraditionalUnavailable as exc:
        raise HTTPException(400, str(exc)) from exc


def data_url(png: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(png).decode()


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "version": VERSION}


@app.get("/api/meta")
def meta() -> dict:
    font_list = fonts.list_fonts()
    defaults = SheetParams().model_dump()
    # 默认字体跟着实际可用的字体走，避免默认值指向一个不存在的 id
    if font_list and not any(f["id"] == defaults["font_id"] for f in font_list):
        defaults["font_id"] = font_list[0]["id"]
    return {
        "fonts": font_list,
        "charsets": charsets.list_sets(),
        "library": library_with_levels(),
        "grids": [{"id": k, "name": v} for k, v in GRID_LABELS.items()],
        "page_sizes": [
            {"id": "A4", "name": "A4  210×297mm"},
            {"id": "A5", "name": "A5  148×210mm"},
            {"id": "B5", "name": "B5  176×250mm"},
        ],
        "defaults": defaults,
        # 前端据此决定「转繁体」是否可用，避免开关点了没反应
        "capabilities": {"traditional": traditional_available(), "version": VERSION,
                         "formats": ["pdf", "png"], "modes": 7, "directions": 2},
    }


@app.post("/api/analyze")
def analyze(req: AnalyzeRequest) -> dict:
    """离线难度评估 + 篇目推荐；纯本地计算，不联网、不需要 Key。"""
    return difficulty.analyze(req.text, req.title, req.keep_punct)


@app.get("/api/fonts")
def font_list(refresh: bool = False) -> dict:
    items = fonts.list_fonts(refresh=refresh)
    return {
        "fonts": items,
        "bundled": sum(1 for f in items if f["source"] == "bundled"),
        "system": sum(1 for f in items if f["source"] == "system"),
    }


@app.post("/api/fonts/upload")
async def font_upload(file: UploadFile) -> JSONResponse:
    raw = await file.read()
    if len(raw) > 32 * 1024 * 1024:
        raise HTTPException(413, "字体文件超过 32MB")
    try:
        item = fonts.register(raw, file.filename or "custom.ttf")
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return JSONResponse({"font": item})


@app.get("/api/fonts/{font_id}/sample")
def font_sample(font_id: str, text: str = "永字", size: int = 56) -> Response:
    """把几个字用指定字体画成小图，供选择器直接看效果"""
    size = max(16, min(120, size))
    sample = (text or "永字")[:8]
    try:
        path = fonts.resolve(font_id)
        font = ImageFont.truetype(str(path), size)
    except Exception:
        raise HTTPException(400, "字体无法加载")

    canvas = Image.new("L", (size * (len(sample) + 2), size * 3), 255)
    ImageDraw.Draw(canvas).text((size, size // 2), sample, font=font, fill=0, anchor="lt")
    box = canvas.getbbox()
    if box is None:                     # 这个字体连样字都没有，退成一条横线
        canvas = Image.new("L", (size * 2, size), 255)
        ImageDraw.Draw(canvas).line([(size * 0.3, size / 2), (size * 1.7, size / 2)], fill=90, width=2)
    else:
        pad = max(2, size // 12)
        canvas = canvas.crop((max(0, box[0] - pad), max(0, box[1] - pad),
                              min(canvas.width, box[2] + pad), min(canvas.height, box[3] + pad)))

    # 白底转成透明，才能贴在任意底色的卡片上看清字形
    ink = Image.new("RGBA", canvas.size, (30, 28, 25, 0))
    ink.putalpha(canvas.point(lambda v: 255 - v))
    buf = io.BytesIO()
    ink.save(buf, "PNG", optimize=True)
    return Response(buf.getvalue(), media_type="image/png",
                    headers={"Cache-Control": "public, max-age=86400"})


@app.get("/api/charset/{key}")
def charset(key: str) -> dict:
    item = charsets.get(key)
    if not item:
        raise HTTPException(404, "字表不存在")
    return item


@app.get("/api/library")
def library() -> dict:
    """内容库：按类别分组的诗文，选一篇即用（含全文，前端不必再请求）"""
    return {"groups": library_with_levels()}


@app.get("/api/library/{key}")
def library_item(key: str) -> dict:
    item = charsets.get_passage(key)
    if not item:
        raise HTTPException(404, "篇目不存在")
    return item


@app.post("/api/preview", response_model=PreviewResponse)
def preview(req: PreviewRequest) -> PreviewResponse:
    params = preview_params(req.params) if not req.full else req.params
    sheet = build_sheet(params)
    if not sheet.pages:
        raise HTTPException(400, "没有可渲染的内容")

    page = max(0, min(req.page, len(sheet.pages) - 1))
    png = sheet.preview_png(page, width=0 if req.full else 820)
    warnings = list(sheet.warnings)

    missing, borrowed = missing_report(req.params)
    if missing:
        warnings.append(f"字体缺少 {len(missing)} 个字形，这些字不会显示：{''.join(missing[:20])}"
                        + ("…" if len(missing) > 20 else ""))
    # 标点借用备用字体是常态（不少书法字库不含标点），不必打扰用户
    borrowed_words = [c for c in borrowed if c not in ALL_PUNCT]
    if borrowed_words:
        warnings.append(f"当前字库没有 {len(borrowed_words)} 个字，已用备用字体补上："
                        f"{''.join(borrowed_words[:20])}" + ("…" if len(borrowed_words) > 20 else ""))

    return PreviewResponse(
        image=data_url(png),
        pages=len(sheet.pages),
        char_count=sheet.char_count,
        missing=missing,
        warnings=warnings,
        font_id=req.params.font_id,
    )


@app.post("/api/thumbnails")
def thumbnails(req: ThumbRequest) -> dict:
    """一次给出全部页的小图，供预览区做缩略图导航（低 dpi，超出上限截断）"""
    params = req.params.model_copy(update={"dpi": min(req.params.dpi, 96)})
    sheet = build_sheet(params)
    total = len(sheet.pages)
    count = min(total, req.limit)
    return {
        "thumbs": [data_url(sheet.page_png(i, width=req.width)) for i in range(count)],
        "total": total,
        "truncated": count < total,
    }


@app.post("/api/print")
def print_pages(req: PrintRequest) -> dict:
    """一次打印整本字帖：返回选中页的高清图，前端按 @page 分页直接送打印机。

    一次给太多页会把响应体撑爆，默认最多 30 页；超了提示改用 PDF 导出。
    """
    sheet = build_sheet(req.params)
    try:
        indices = parse_page_range(req.page_range, len(sheet.pages))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if len(indices) > req.limit:
        raise HTTPException(400, f"选中 {len(indices)} 页，超过一次打印上限 {req.limit} 页，请缩小页码范围或导出 PDF")
    return {
        "pages": [data_url(sheet.page_png(i)) for i in indices],
        "page_size": req.params.page_size,
        "total": len(sheet.pages),
    }


def _content_disposition(filename: str) -> dict:
    return {"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"}


def _export_png(sheet: Sheet, indices: list[int], base: str) -> Response:
    """单页直接给 PNG，多页按页码命名打 zip"""
    if len(indices) == 1:
        n = indices[0] + 1
        return Response(sheet.page_png(indices[0]), media_type="image/png",
                        headers=_content_disposition(f"{base}_{stamp()}_第{n}页.png"))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for i in indices:
            zf.writestr(f"{base}_第{i + 1:03d}页.png", sheet.page_png(i))
    buf.seek(0)
    return Response(buf.getvalue(), media_type="application/zip",
                    headers=_content_disposition(f"{base}_{stamp()}_共{len(indices)}页.zip"))


@app.post("/api/export")
def export(req: ExportRequest) -> Response:
    params = req.params
    if not params.text.strip():
        raise HTTPException(400, "正文为空")

    base = safe_name(params.title or params.text[:12])

    if req.split_size <= 0:
        sheet = build_sheet(params)
        try:
            indices = parse_page_range(req.page_range, len(sheet.pages))
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        if len(indices) > 200:
            raise HTTPException(400, f"共 {len(indices)} 页，超过单次导出上限 200 页，请分册或缩小页码范围")
        if req.file_format == "png":
            return _export_png(sheet, indices, base)
        with tempfile.TemporaryDirectory() as tmp:
            out = sheet.export_pdf(Path(tmp) / f"{base}.pdf", indices)
            data = out.read_bytes()
        return Response(data, media_type="application/pdf",
                        headers=_content_disposition(f"{base}_{stamp()}.pdf"))

    chunks = [c for c in volume_text(params.text, req.split_size) if c.strip()]
    if not chunks:
        raise HTTPException(400, "没有可导出的内容")
    if len(chunks) > 40:
        raise HTTPException(400, "分册数量超过 40 册，请减小每册字数")

    buf = io.BytesIO()
    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for i, chunk in enumerate(chunks, 1):
                sub = params.model_copy(update={
                    "text": chunk,
                    "title": f"{params.title} 第{i}册".strip(),
                })
                sheet = build_sheet(sub)
                out = sheet.export_pdf(Path(tmp) / f"v{i}.pdf")
                zf.write(out, f"{base}_{stamp()}_第{i}册.pdf")
    buf.seek(0)
    return Response(buf.getvalue(), media_type="application/zip",
                    headers=_content_disposition(f"{base}_{stamp()}_共{len(chunks)}册.zip"))


@app.post("/api/parse")
async def parse(file: UploadFile) -> JSONResponse:
    """上传 txt / md，直接读成正文；其他格式提示手动粘贴"""
    suffix = Path(file.filename or "").suffix.lower()
    raw = await file.read()
    if len(raw) > 5 * 1024 * 1024:
        raise HTTPException(413, "文件超过 5MB")

    if suffix in (".txt", ".md", ".csv"):
        for enc in ("utf-8-sig", "utf-8", "gb18030", "big5"):
            try:
                return JSONResponse({"text": raw.decode(enc)})
            except UnicodeDecodeError:
                continue
        raise HTTPException(400, "无法识别文件编码，请另存为 UTF-8")

    raise HTTPException(415, "目前仅支持 txt / md，其他格式请直接粘贴正文")


BACKEND_DIR = Path(__file__).resolve().parent.parent          # backend/
ROOT_DIR = BACKEND_DIR.parent                                  # 项目根

# 构建产物统一放 backend/web（跟着后端一起走，部署时不会漏）
DIST = next(
    (d for d in (BACKEND_DIR / "web", ROOT_DIR / "frontend" / "dist") if (d / "index.html").exists()),
    None,
)
if DIST is not None:
    app.mount("/", StaticFiles(directory=str(DIST), html=True), name="static")
