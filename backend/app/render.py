"""把参数变成一页页图像，再导出成 PDF / PNG。

版面计算集中在这里：页面尺寸、边距、格子缩放、页眉页脚。
"""
from __future__ import annotations

import io
import math
import re
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


def parse_page_range(spec: str, total: int) -> list[int]:
    """把「1-2,4」解析成 0 基页索引；空串代表全部页。

    页码按书写顺序返回、自动去重，越界直接报错而不是静默截断。
    """
    if not spec or not spec.strip():
        return list(range(total))
    picked: list[int] = []
    seen: set[int] = set()
    for part in re.split(r"[,，;；\s]+", spec.strip()):
        if not part:
            continue
        m = re.fullmatch(r"(\d+)(?:\s*[-–~—]\s*(\d+))?", part)
        if not m:
            raise ValueError(f"页码写法无法识别：{part}（示例：1-2,4）")
        start = int(m.group(1))
        end = int(m.group(2)) if m.group(2) else start
        if start < 1 or end > total or start > end:
            raise ValueError(f"页码 {part} 超出范围（共 {total} 页）")
        for n in range(start, end + 1):
            if n - 1 not in seen:
                seen.add(n - 1)
                picked.append(n - 1)
    if not picked:
        raise ValueError("没有选中任何页")
    return picked


@dataclass
class Sheet:
    params: SheetParams
    rows: list[list[Slot | None]] = field(default_factory=list)
    pages: list[list[list[Slot | None]]] = field(default_factory=list)
    cell: int = 0
    x0: int = 0
    y0: int = 0
    grid_w: int = 0
    grid_h: int = 0
    page_w: int = 0
    page_h: int = 0
    warnings: list[str] = field(default_factory=list)
    char_count: int = 0
    missing: list[str] = field(default_factory=list)
    borrowed: list[str] = field(default_factory=list)   # 主字体缺、靠备用字体补上的字
    paper_rgb: tuple[int, int, int] = (255, 255, 255)

    # 渲染期缓存：一次构造字形工厂，多页复用，避免每页重新加载整条字体链
    _glyphs: GlyphFactory | None = field(default=None, repr=False)
    _missing_set: set[str] = field(default_factory=set, repr=False)
    _borrowed_set: set[str] = field(default_factory=set, repr=False)
    _header_fonts: dict = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        self._prepare()

    # ---------- 版面 ----------
    def _prepare(self) -> None:
        p = self.params
        self.paper_rgb = hex_to_rgb(p.paper_color)
        pw_mm, ph_mm = PAGE_MM[p.page_size]
        self.page_w = mm2px(pw_mm, p.dpi)
        self.page_h = mm2px(ph_mm, p.dpi)

        vertical = p.direction == "vertical"
        margin = mm2px(p.margin_mm, p.dpi)
        header = mm2px(9, p.dpi) if p.show_header else 0

        cell = mm2px(p.cell_mm, p.dpi)
        avail_w = self.page_w - 2 * margin
        avail_h = self.page_h - 2 * margin - header

        # 横排：每行字数吃宽度、每页行数吃高度；竖排两者正好互换。
        # 「行」在编排层始终表示一串字，竖排时它会被画成一竖列，数据结构不变。
        per_line = p.columns
        fixed_room = avail_h if vertical else avail_w      # 一行／一列必须装下的方向
        free_room = avail_w if vertical else avail_h       # 决定每页能排几行／几列的方向

        # 1) 先按固定方向决定格子能否放下
        limit = max(1, fixed_room // per_line)
        shrunk = False
        if cell > limit:
            cell, shrunk = limit, True

        # 2) 自动行数：按剩余方向铺满整页，不留一大片空白
        rows = p.rows
        if p.auto_rows:
            rows = max(1, min(26, free_room // cell))

        # 3) 行数过多导致剩余方向不够时再缩格子
        if rows * cell > free_room:
            limit = free_room // rows
            if limit < mm2px(8, p.dpi):
                self.warnings.append("格子太多，已超出页面可容纳范围，建议减少行数或列数")
            elif not shrunk:
                self.warnings.append(
                    f"{per_line} 字／行 × {rows} 行放不下 {p.cell_mm:g}mm 的格子，已自动缩放到"
                    f"{limit / p.dpi * 25.4:.1f}mm"
                )
            cell, shrunk = max(1, limit), True

        if shrunk and not any("自动缩放" in w for w in self.warnings):
            self.warnings.append(f"格子已自动缩放到 {cell / p.dpi * 25.4:.1f}mm 以适应页面")

        self.cell = cell
        if rows != p.rows:
            # 后续编排与分页都以实际行数（竖排即列数）为准
            p = p.model_copy(update={"rows": rows})
            self.params = p

        self.grid_w = cell * (rows if vertical else per_line)
        self.grid_h = cell * (per_line if vertical else rows)
        self.x0 = (self.page_w - self.grid_w) // 2
        # 字帖习惯是网格顶到页眉下方，不做垂直居中，避免上方空一大片
        self.y0 = margin + header + mm2px(3, p.dpi)

        # 竖排专属限制：这几种格型的辅助线是按横排设计的，硬套会画歪
        if vertical and p.grid in ("pinyin4", "composition", "control"):
            self.warnings.append("竖排下四线格／作文格／控笔格不适用，已改用田字格")
            p = p.model_copy(update={"grid": "tian"})
            self.params = p
        if vertical and p.keep_punct:
            self.warnings.append("竖排下标点仍按横排字形绘制，正式临帖建议关闭“保留标点”")

        self.rows = compose_rows(p)
        self.pages = paginate(self.rows, p.rows)
        self.char_count = sum(1 for row in self.rows for s in row if s)

    # ---------- 绘制 ----------
    def _header_font(self, size: int, chars: list[str]) -> ImageFont.FreeTypeFont | None:
        """页眉用小字号，按字体链挑一款能把这一串字符写全的"""
        key = (size, "".join(chars))
        if key in self._header_fonts:
            return self._header_fonts[key]
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
                self._header_fonts[key] = font
                return font
        self._header_fonts[key] = fallback
        return fallback

    def _header(self, draw: ImageDraw.ImageDraw, page_idx: int, total: int) -> None:
        if not self.params.show_header:
            return
        size = mm2px(4.6, self.params.dpi)
        # 黑底碑帖时页眉要反色，否则灰字看不见
        color = "#d8d2c6" if sum(self.paper_rgb) / 3 < 128 else "#6b6b6b"
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
            draw.text((self.x0 + self.grid_w, base_y), label,
                      font=font, fill=color, anchor="rm")

    def _glyph_factory(self) -> GlyphFactory:
        if self._glyphs is None:
            p = self.params
            font_paths = fonts.chain(p.font_id) if p.font_fallback else [fonts.resolve(p.font_id)]
            self._glyphs = GlyphFactory([str(x) for x in font_paths], self.cell, p.font_ratio,
                                        p.font_color, p.trace_opacity, p.paper_color)
        return self._glyphs

    def render_page(self, index: int, downscale_to: int | None = None) -> Image.Image:
        p = self.params
        vertical = p.direction == "vertical"
        img = Image.new("RGB", (self.page_w, self.page_h), self.paper_rgb)
        draw = ImageDraw.Draw(img)

        # 竖排时横向格数是「每页列数」，纵向格数是「每列字数」
        draw_grid(draw, self.x0, self.y0,
                  p.rows if vertical else p.columns,
                  p.columns if vertical else p.rows,
                  self.cell, p.grid, p.grid_color, max(1, self.cell // 60), self.paper_rgb)

        glyphs = self._glyph_factory()
        for r, row in enumerate(self.pages[index]):
            for c, slot in enumerate(row):
                if slot is None:
                    continue
                # slot.style 只有 demo / trace 两种语义，
                # trace 具体画成浅灰、空心还是点阵，由 params.trace_style 决定
                style = "demo" if slot.style == "demo" else p.trace_style
                opacity = None
                if p.mode == "fade" and slot.style == "trace" and style == "gray":
                    # 渐隐临摹：首字实心，其后沿书写方向逐格变淡，
                    # 末尾保留一点痕迹（下限 0.04），不至于突然整格空白。
                    span = max(2, p.columns)
                    t = min(1.0, max(0.0, (c - 1) / max(1, span - 2)))
                    opacity = max(0.04, p.trace_opacity * (1 - 0.88 * t))
                rendered = glyphs.render(slot.char, style, opacity)
                if rendered is None:
                    continue
                layer, mask = rendered
                if vertical:
                    # 第 0 行是最右一列，列序自右向左；c 变成自上而下的字序
                    x = self.x0 + (p.rows - 1 - r) * self.cell
                    y = self.y0 + c * self.cell
                else:
                    x = self.x0 + c * self.cell
                    y = self.y0 + r * self.cell
                img.paste(layer, (x, y), mask)

        # 多页渲染时缺字报告要累积，不能让最后一页覆盖前面几页
        self._missing_set.update(glyphs.missing)
        self._borrowed_set.update(glyphs.fallback)
        self.missing = sorted(self._missing_set)
        self.borrowed = sorted(self._borrowed_set)
        self._header(draw, index, len(self.pages))

        if downscale_to and img.width > downscale_to:
            ratio = downscale_to / img.width
            img = img.resize((downscale_to, int(img.height * ratio)), Image.LANCZOS)
        return img

    def page_png(self, index: int, width: int | None = None) -> bytes:
        """原尺寸页 PNG；width 给定时等比缩小（缩略图用）"""
        img = self.render_page(max(0, min(index, len(self.pages) - 1)), downscale_to=width)
        buf = io.BytesIO()
        img.save(buf, "PNG", optimize=True)
        data = buf.getvalue()
        img.close()
        return data

    def preview_png(self, index: int, width: int = 820) -> bytes:
        return self.page_png(index, width=width or None)

    # ---------- 导出 ----------
    def export_pdf(self, out: Path, pages: list[int] | None = None) -> Path:
        """逐页落成单页 PDF 后用 pypdf 合并，避免几十页图像同时驻留内存。

        pages 给定时只导出选中的页（顺序与传入一致）。
        """
        from pypdf import PdfWriter

        indices = list(range(len(self.pages))) if pages is None else pages
        out.parent.mkdir(parents=True, exist_ok=True)
        writer = PdfWriter()
        with tempfile.TemporaryDirectory() as tmp:
            for i in indices:
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
