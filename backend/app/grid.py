"""格子绘制：田字、米字、九宫、回宫、空白、竖行、横线。

所有尺寸都是像素，换算在 render 层做；这里只管「给定格子和位置怎么画线」。
"""
from __future__ import annotations

import math

from PIL import ImageDraw


def dashed_line(draw: ImageDraw.ImageDraw, p1, p2, fill, width: int = 1, dash: int = 12, gap: int = 9) -> None:
    """任意方向的虚线：沿向量按 dash/gap 交替画短段。"""
    x1, y1 = p1
    x2, y2 = p2
    length = math.hypot(x2 - x1, y2 - y1)
    if length <= 0:
        return
    ux, uy = (x2 - x1) / length, (y2 - y1) / length
    d = 0.0
    while d < length:
        e = min(d + dash, length)
        draw.line([(x1 + ux * d, y1 + uy * d), (x1 + ux * e, y1 + uy * e)], fill=fill, width=width)
        d = e + gap


def _cell_marks(draw, x, y, cell, kind, color, dash, gap) -> None:
    """单个格子内部的辅助线"""
    mid_x, mid_y = x + cell / 2, y + cell / 2
    right, bottom = x + cell, y + cell

    if kind in ("tian", "mi"):
        dashed_line(draw, (mid_x, y), (mid_x, bottom), color, 1, dash, gap)
        dashed_line(draw, (x, mid_y), (right, mid_y), color, 1, dash, gap)
        if kind == "mi":
            dashed_line(draw, (x, y), (right, bottom), color, 1, dash, gap)
            dashed_line(draw, (right, y), (x, bottom), color, 1, dash, gap)

    elif kind == "jiugong":
        for k in (1, 2):
            pos = x + cell * k / 3
            dashed_line(draw, (pos, y), (pos, bottom), color, 1, dash, gap)
            pos = y + cell * k / 3
            dashed_line(draw, (x, pos), (right, pos), color, 1, dash, gap)

    elif kind == "huigong":
        inset = cell * 0.25
        draw.rectangle([x + inset, y + inset, right - inset, bottom - inset], outline=color, width=1)


def draw_grid(draw: ImageDraw.ImageDraw, x0: int, y0: int, cols: int, rows: int,
              cell: int, kind: str, color: str, line_width: int = 2) -> None:
    """整页格子。vertical / line 只画单向线，其余画满格并加内部辅助线。"""
    width, height = cols * cell, rows * cell
    dash, gap = max(8, cell // 16), max(6, cell // 22)

    if kind == "vertical":
        for i in range(cols + 1):
            x = x0 + i * cell
            draw.line([(x, y0), (x, y0 + height)], fill=color, width=line_width)
        return

    if kind == "line":
        for j in range(rows + 1):
            y = y0 + j * cell
            draw.line([(x0, y), (x0 + width, y)], fill=color, width=line_width)
        return

    # 格线（共享边只画一次）
    for i in range(cols + 1):
        x = x0 + i * cell
        draw.line([(x, y0), (x, y0 + height)], fill=color, width=line_width)
    for j in range(rows + 1):
        y = y0 + j * cell
        draw.line([(x0, y), (x0 + width, y)], fill=color, width=line_width)

    if kind == "blank":
        return

    for j in range(rows):
        for i in range(cols):
            _cell_marks(draw, x0 + i * cell, y0 + j * cell, cell, kind, color, dash, gap)
