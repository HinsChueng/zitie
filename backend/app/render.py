"""把参数变成一页页图像，再导出成 PDF。

版面计算集中在这里：页面尺寸、边距、格子缩放、页眉页脚。
"""
from __future__ import annotations

import io
import math
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from . import fonts
from .glyphs import GlyphFactory, hex_to_rgb
from .grid import draw_grid
from .layout import Slot, compose_rows, paginate, to_traditional
from .schemas import SheetParams

PAGE_MM = {"A4": (210.0, 297.0), "A5": (148.0, 210.0), "B5": (176.0, 250.0)}


def mm2px(mm: float, dpi: int) -> int:
    return max(1, int(round(mm / 25.4 * dpi)))


@dataclass
class Sheet:
    params: SheetParams
    rows: list[list[Slot | None]] = field(default_factory=list)
    pages: list[list[list[Slot | None]]] = field(default_factory=list)
    cell: int = 0
    x0: int = 0
    y0: int = 0
    page_w: int = 0
    page_h: int = 0
    warnings: list[str] = field(default_factory=list)
    char_count: int = 0
    missing: list[str] = field(default_factory=list)
    borrowed: list[str] = field(default_factory=list)   # 主字体缺、靠备用字体补上的字

    def __post_init__(self) -> None:
        self._prepare()

    # ---------- 版面 ----------
    def _prepare(self) -> None:
        p = self.params
        pw_mm, ph_mm = PAGE_MM[p.page_size]
        self.page_w = mm2px(pw_mm, p.dpi)
        self.page_h = mm2px(ph_mm, p.dpi)

        margin = mm2px(p.margin_mm, p.dpi)
        header = mm2px(9, p.dpi) if p.show_header else 0

        cell = mm2px(p.cell_mm, p.dpi)
        avail_w = self.page_w - 2 * margin
        avail_h = self.page_h - 2 * margin - header

        # 1) 先按宽度决定格子能否放下
        max_by_w = max(1, avail_w // p.columns)
        shrunk = False
        if cell > max_by_w:
            cell, shrunk = max_by_w, True

        # 2) 自动行数：按高度铺满整页，不留一大片空白
        rows = p.rows
        if p.auto_rows:
            rows = max(1, min(26, avail_h // cell))

        # 3) 行数过多导致高度不够时再缩格子
        if rows * cell > avail_h:
            limit = avail_h // rows
            if limit < mm2px(8, p.dpi):
                self.warnings.append("格子太多，已超出页面可容纳范围，建议减少行数或列数")
            elif not shrunk:
                self.warnings.append(
                    f"{p.columns} 列 × {rows} 行放不下 {p.cell_mm:g}mm 的格子，已自动缩放到"
                    f"{limit / p.dpi * 25.4:.1f}mm"
                )
            cell, shrunk = max(1, limit), True

        if shrunk and not any("自动缩放" in w for w in self.warnings):
            self.warnings.append(f"格子已自动缩放到 {cell / p.dpi * 25.4:.1f}mm 以适应页面")

        self.cell = cell
        if rows != p.rows:
            # 后续编排与分页都以实际行数为准
            p = p.model_copy(update={"rows": rows})
            self.params = p

        grid_w, grid_h = cell * p.columns, cell * rows
        self.x0 = (self.page_w - grid_w) // 2
        # 字帖习惯是网格顶到页眉下方，不做垂直居中，避免上方空一大片
        top = margin + header
        self.y0 = top + mm2px(3, p.dpi)

        self.rows = compose_rows(p)
        self.pages = paginate(self.rows, p.rows)
        self.char_count = sum(1 for row in self.rows for s in row if s)

    # ---------- 绘制 ----------
    def _header_font(self, size: int, chars: list[str]) -> ImageFont.FreeTypeFont | None:
        """页眉用小字号，按字体链挑一款能把这一串字符写全的"""
        paths = fonts.chain(self.params.font_id) if self.params.font_fallback \
            else [fonts.resolve(self.params.font_id)]
        needed = [ch for ch in chars if not ch.isspace()]
        fallback = None
        for path in paths:
            try:
                font = ImageFont.truetype(str(path), size)
            except Exception:
                continue
            if fallback is None:
                fallback = font
            if all(font.getmask(ch).getbbox() is not None for ch in needed):
                return font
        return fallback

    def _header(self, draw: ImageDraw.ImageDraw, page_idx: int, total: int) -> None:
        if not self.params.show_header:
            return
        size = mm2px(4.6, self.params.dpi)
        color = "#6b6b6b"
        top = mm2px(self.params.margin_mm, self.params.dpi)
        base_y = top + size // 2

        # 标题和页码分开挑字体：行楷类字库常常没有数字和半角符号
        if self.params.title:
            font = self._header_font(size, list(self.params.title))
            if font is not None:
                draw.text((self.x0, base_y), self.params.title, font=font, fill=color, anchor="lm")

        label = f"第 {page_idx + 1} 页 / 共 {total} 页"
        font = self._header_font(size, list(label))
        if font is not None:
            draw.text((self.x0 + self.cell * self.params.columns, base_y), label,
                      font=font, fill=color, anchor="rm")

    def render_page(self, index: int, downscale_to: int | None = None) -> Image.Image:
        p = self.params
        img = Image.new("RGB", (self.page_w, self.page_h), "white")
        draw = ImageDraw.Draw(img)

        draw_grid(draw, self.x0, self.y0, p.columns, p.rows, self.cell,
                  p.grid, p.grid_color, max(1, self.cell // 60))

        font_paths = fonts.chain(p.font_id) if p.font_fallback else [fonts.resolve(p.font_id)]
        glyphs = GlyphFactory([str(x) for x in font_paths], self.cell, p.font_ratio,
                              p.font_color, p.trace_opacity)

        for r, row in enumerate(self.pages[index]):
            for c, slot in enumerate(row):
                if slot is None:
                    continue
                # slot.style 只有 demo / trace 两种语义，
                # trace 具体画成浅灰、空心还是点阵，由 params.trace_style 决定
                style = "demo" if slot.style == "demo" else p.trace_style
                rendered = glyphs.render(slot.char, style)
                if rendered is None:
                    continue
                layer, mask = rendered
                img.paste(layer, (self.x0 + c * self.cell, self.y0 + r * self.cell), mask)

        self.missing = sorted(glyphs.missing)
        self.borrowed = sorted(glyphs.fallback)
        self._header(draw, index, len(self.pages))

        if downscale_to and img.width > downscale_to:
            ratio = downscale_to / img.width
            img = img.resize((downscale_to, int(img.height * ratio)), Image.LANCZOS)
        return img

    def preview_png(self, index: int, width: int = 820) -> bytes:
        img = self.render_page(max(0, min(index, len(self.pages) - 1)), downscale_to=width)
        buf = io.BytesIO()
        img.save(buf, "PNG", optimize=True)
        return buf.getvalue()

    # ---------- 导出 ----------
    def export_pdf(self, out: Path) -> Path:
        """逐页落成单页 PDF 后用 pypdf 合并，避免几十页图像同时驻留内存"""
        from pypdf import PdfWriter

        out.parent.mkdir(parents=True, exist_ok=True)
        writer = PdfWriter()
        with tempfile.TemporaryDirectory() as tmp:
            for i in range(len(self.pages)):
                page = self.render_page(i)
                piece = Path(tmp) / f"{i:04d}.pdf"
                page.save(piece, "PDF", resolution=self.params.dpi)
                page.close()
                with open(piece, "rb") as fh:
                    writer.append(fh)
        with open(out, "wb") as fh:
            writer.write(fh)
        return out


def _cmap_of(path: Path) -> set[int]:
    try:
        from fontTools.ttLib import TTFont

        font = TTFont(str(path), fontNumber=0, lazy=True)
        try:
            return set(font.getBestCmap())
        finally:
            font.close()
    except Exception:
        return set()


def missing_report(params: SheetParams) -> tuple[list[str], list[str]]:
    """返回 (谁都画不出来的字, 只有主字体画不出来的字)。

    第二个列表只用于提示“这几个字用了备用字体”，不算错误。
    注意：转繁体后实际要画的是繁体字，所以检查也要按转换后的文本走，
    否则「牀 / 頭 / 鄉」这些字缺字形时不会报警。
    """
    title, text = params.title, params.text
    if params.traditional:
        title, text = to_traditional(title), to_traditional(text)

    primary = fonts.resolve(params.font_id)
    paths = fonts.chain(params.font_id) if params.font_fallback else [primary]
    primary_cmap = _cmap_of(primary)
    cmaps = [primary_cmap] if len(paths) == 1 else [_cmap_of(p) for p in paths]

    seen: set[str] = set()
    missing: list[str] = []
    borrowed: list[str] = []

    for ch in title + text:
        if ch in seen or ch.isspace():
            continue
        seen.add(ch)
        if not any(ord(ch) in cmap for cmap in cmaps):
            missing.append(ch)
        elif ord(ch) not in primary_cmap:
            borrowed.append(ch)
    return missing, borrowed


def scan_missing(params: SheetParams) -> list[str]:
    """只检查字形是否存在，不渲染页面——用于提前提示缺字"""
    return missing_report(params)[0]


def volume_text(text: str, size: int) -> list[str]:
    return [text[i:i + size] for i in range(0, len(text), size)] if size > 0 else [text]
