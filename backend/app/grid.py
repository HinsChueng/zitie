"""格子绘制：田字、米字、九宫、回宫、空白、竖行、横线、四线三格、作文格、控笔格。

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


def _rgb(value: str) -> tuple[int, int, int]:
    value = (value or "").lstrip("#")
    if len(value) == 3:
        value = "".join(c * 2 for c in value)
    try:
        return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]
    except (ValueError, IndexError):
        return (31, 31, 31)


def _mix(color: str, ratio: float, paper_rgb: tuple[int, int, int]) -> tuple[int, int, int]:
    """把格线色按 ratio 混向纸色，得到辅助线的淡色（黑底碑帖同样成立）"""
    src = _rgb(color)
    return tuple(round(p + (c - p) * ratio) for c, p in zip(src, paper_rgb))  # type: ignore[return-value]


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


def _control_path(draw, x, y, cell, variant, color, width) -> None:
    """控笔训练的四种轨迹：波浪 / 螺旋 / 折线 / 连续环。

    轨迹只给「沿着描」的引导，不落墨，颜色比格线淡一档。
    """
    pad = cell * 0.14
    span = cell - pad * 2
    cx, cy = x + cell / 2, y + cell / 2
    points: list[tuple[float, float]] = []

    if variant == 0:                                   # 波浪线
        for i in range(97):
            t = i / 96
            points.append((x + pad + span * t, cy + math.sin(t * math.pi * 6) * span * 0.26))
    elif variant == 1:                                 # 阿基米德螺线
        for i in range(145):
            t = i / 144
            angle = t * math.pi * 7
            radius = span * 0.46 * t
            points.append((cx + math.cos(angle) * radius, cy + math.sin(angle) * radius))
    elif variant == 2:                                 # 锯齿折线
        for i in range(13):
            t = i / 12
            points.append((x + pad + span * t, cy + (span * 0.28 if i % 2 else -span * 0.28)))
    else:                                              # 横向 8 字环
        for i in range(145):
            t = i / 144 * math.pi * 2
            points.append((cx + math.sin(t) * span * 0.42, cy + math.sin(t * 2) * span * 0.24))

    draw.line(points, fill=color, width=width, joint="curve")


def draw_grid(draw: ImageDraw.ImageDraw, x0: int, y0: int, cols: int, rows: int,
              cell: int, kind: str, color: str, line_width: int = 2,
              paper_rgb: tuple[int, int, int] = (255, 255, 255)) -> None:
    """整页格子。vertical / line 只画单向线，其余画满格并加内部辅助线。"""
    width, height = cols * cell, rows * cell
    dash, gap = max(8, cell // 16), max(6, cell // 22)
    faint = _mix(color, 0.42, paper_rgb)

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

    if kind == "pinyin4":
        # 每行四条横线构成「三格」，中间两条用淡虚线，字母／拼音写在中间格
        for j in range(rows):
            top = y0 + j * cell
            for k in (1, 2):
                y = top + k * cell / 3
                dashed_line(draw, (x0, y), (x0 + width, y), faint, 1, dash, gap)
        return

    if kind == "composition":
        # 作文稿纸：只给格心点，不画十字，避免干扰整篇书写
        r = max(2, cell // 60)
        for j in range(rows):
            for i in range(cols):
                cx, cy = x0 + i * cell + cell / 2, y0 + j * cell + cell / 2
                draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=faint)
        return

    if kind == "control":
        trace = _mix(color, 0.30, paper_rgb)
        lw = max(1, cell // 90)
        for j in range(rows):
            for i in range(cols):
                _control_path(draw, x0 + i * cell, y0 + j * cell, cell,
                              (i + j * 2) % 4, trace, lw)
        return

    for j in range(rows):
        for i in range(cols):
            _cell_marks(draw, x0 + i * cell, y0 + j * cell, cell, kind, color, dash, gap)
