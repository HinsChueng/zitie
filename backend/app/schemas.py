"""请求 / 响应模型"""
from typing import Literal

from pydantic import BaseModel, Field

GridKind = Literal["tian", "mi", "jiugong", "huigong", "blank", "vertical", "line"]
TraceStyle = Literal["gray", "outline", "dot"]
Mode = Literal["demo", "trace", "mixed", "rotate"]
PageSize = Literal["A4", "A5", "B5"]


class SheetParams(BaseModel):
    """一张字帖的全部参数，前端所有控件最终都落到这里"""

    # 内容
    title: str = ""
    text: str = ""
    font_id: str = "tk"
    font_fallback: bool = True   # 所选字体缺字时，自动借用其他字体补上

    # 版式
    grid: GridKind = "tian"
    page_size: PageSize = "A4"
    cell_mm: float = Field(17.0, ge=8, le=40)
    font_ratio: float = Field(0.84, ge=0.4, le=1.0)
    columns: int = Field(10, ge=1, le=20)
    rows: int = Field(12, ge=1, le=26)
    auto_rows: bool = True       # 按页面高度自动决定每页行数
    margin_mm: float = Field(14.0, ge=0, le=45)

    # 练习模式
    mode: Mode = "rotate"
    demo_cells: int = Field(1, ge=0, le=10)
    trace_cells: int = Field(2, ge=0, le=10)
    repeat: bool = True          # mixed 模式下：单字重复整行
    cycle_demo: int = Field(1, ge=1, le=4)
    cycle_trace: int = Field(1, ge=1, le=4)
    cycle_blank: int = Field(2, ge=0, le=6)

    # 描红样式
    trace_style: TraceStyle = "gray"
    trace_opacity: float = Field(0.35, ge=0.04, le=0.9)

    # 外观
    grid_color: str = "#d94a4a"
    font_color: str = "#1f1f1f"
    show_header: bool = True
    dpi: int = Field(300, ge=150, le=600)

    # 文本处理
    keep_punct: bool = True
    traditional: bool = False
    line_break_rule: bool = True
    break_at_punct: bool = True


class PreviewRequest(BaseModel):
    params: SheetParams
    page: int = 0
    full: bool = False       # True 时按导出 dpi 渲染，用于打印


class PreviewResponse(BaseModel):
    image: str
    pages: int
    char_count: int
    missing: list[str] = []
    warnings: list[str] = []
    font_id: str = ""


class ExportRequest(BaseModel):
    params: SheetParams
    split_size: int = Field(0, ge=0, le=2000)   # >0 时按每册字数自动分册，返回 zip
