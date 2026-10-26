"""字形渲染：把单个汉字做成 cell×cell 的蒙版，再按描红样式处理。

四种形态：
  demo  实心示范
  gray  浅灰描红（浓度可调）
  outline 空心字（只留轮廓，用于双钩廓填）
  dot   点阵字（用点描出字形，练笔顺方向）
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

from .layout import ALL_PUNCT


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    if len(value) == 3:
        value = "".join(c * 2 for c in value)
    try:
        return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]
    except ValueError:
        return (31, 31, 31)


def _blend(color: tuple[int, int, int], ratio: float, bg: int = 255) -> tuple[int, int, int]:
    """把前景色按 ratio 混向背景色（白），得到浅灰效果"""
    return tuple(round(bg - (bg - c) * ratio) for c in color)  # type: ignore[return-value]


class GlyphFactory:
    """font_paths 可以是一组字体：前面的缺字就依次往后借"""

    def __init__(self, font_paths, cell: int, ratio: float,
                 font_color: str = "#1f1f1f", opacity: float = 0.22):
        self.cell = cell
        self.color = hex_to_rgb(font_color)
        self.opacity = opacity
        size = max(8, round(cell * ratio))
        if isinstance(font_paths, (str, Path)):
            font_paths = [font_paths]

        self.fonts: list[ImageFont.FreeTypeFont] = []
        for path in font_paths:
            try:
                self.fonts.append(ImageFont.truetype(str(path), size))
            except Exception:
                continue
        if not self.fonts:
            raise RuntimeError("没有可用字体，请检查 backend/fonts 目录")

        self.font = self.fonts[0]
        self._masks: dict[tuple[str, bool], Image.Image | None] = {}
        self._styled: dict[tuple[str, str, bool], Image.Image | None] = {}
        self.missing: set[str] = set()
        self.fallback: dict[str, int] = {}      # 记录了哪些字是从第几顺位字体借来的

    # ---------- 基础蒙版 ----------
    def _mask(self, ch: str, punct: bool) -> Image.Image | None:
        """按墨迹包围盒把字形摆进格子。

        不能直接用 anchor='mm'：它对齐的是字体的行框（含上下留白），
        汉字偏上、标点会掉到格子外面。这里先测量实际落墨范围再平移对齐。
        """
        key = (ch, punct)
        if key in self._masks:
            return self._masks[key]

        cell = self.cell
        # 2 倍画布，保证平移后不会被裁掉
        big = Image.new("L", (cell * 2, cell * 2), 0)
        pen = ImageDraw.Draw(big)

        bbox = None
        for index, font in enumerate(self.fonts):
            pen.rectangle([0, 0, cell * 2, cell * 2], fill=0)
            pen.text((cell, cell), ch, font=font, fill=255, anchor="lt")
            bbox = big.getbbox()
            if bbox is not None:            # 当前字体有这个字形
                if index:
                    self.fallback[ch] = index
                break

        if bbox is None:                    # 所有字体都没有，PIL 会静默不落墨
            self.missing.add(ch)
            self._masks[key] = None
            return None

        # 标点压格子左下角，汉字居中
        tx, ty = (cell * 0.34, cell * 0.76) if punct else (cell * 0.5, cell * 0.5)
        ink_x = (bbox[0] + bbox[2]) / 2
        ink_y = (bbox[1] + bbox[3]) / 2
        left = int(round(ink_x - tx))
        top = int(round(ink_y - ty))
        tile = big.crop((left, top, left + cell, top + cell))

        self._masks[key] = tile
        return tile

    # ---------- 样式 ----------
    def _outline(self, mask: Image.Image) -> Image.Image:
        pad = max(2, self.cell // 70)
        big = Image.new("L", (mask.width + pad * 2, mask.height + pad * 2), 0)
        big.paste(mask, (pad, pad))
        eroded = big.filter(ImageFilter.MinFilter(pad * 2 + 1))
        ring = ImageChops.subtract(big, eroded)
        return ring.crop((pad, pad, pad + mask.width, pad + mask.height))

    def _dots(self, mask: Image.Image) -> Image.Image:
        # 点距约 1/30 格宽：太密看不出点，太稀看不出笔顺
        step = max(4, self.cell // 30)
        r = max(1, step // 3)
        out = Image.new("L", mask.size, 0)
        draw = ImageDraw.Draw(out)
        px = mask.load()
        for y in range(0, mask.height, step):
            for x in range(0, mask.width, step):
                if px[x, y] > 60:
                    draw.ellipse([x - r, y - r, x + r, y + r], fill=255)
        return out

    def render(self, ch: str, style: str) -> tuple[Image.Image, Image.Image] | None:
        """返回 (纯色层, 蒙版)，直接 page.paste(layer, pos, mask)"""
        punct = ch in ALL_PUNCT
        key = (ch, style, punct)
        if key in self._styled:
            cached = self._styled[key]
            if cached is None:
                return None
            mask = cached
            color = _blend(self.color, self.opacity) if style == "gray" else self.color
            return Image.new("RGB", mask.size, color), mask

        base = self._mask(ch, punct)
        if base is None:
            self._styled[key] = None
            return None

        if style == "outline":
            mask = self._outline(base)
        elif style == "dot":
            mask = self._dots(base)
        else:
            mask = base

        self._styled[key] = mask
        color = _blend(self.color, self.opacity) if style == "gray" else self.color
        return Image.new("RGB", mask.size, color), mask
