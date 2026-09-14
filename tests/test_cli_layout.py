"""F-12 人工反馈回归：行内命令不折行，表格溢出限于自身容器。"""

from __future__ import annotations

import re
from pathlib import Path

from bs4 import BeautifulSoup

from tests.test_design import _css, _rule


def _property(css: str, selector: str, name: str) -> str:
    values = re.findall(rf"\b{re.escape(name)}\s*:\s*([^;]+);", _rule(css, selector))
    assert values, f"{selector} 缺少 {name} 声明"
    return values[-1].strip()


def test_inline_code_does_not_wrap(dist: Path) -> None:
    css = _css(dist)
    assert _property(css, "code", "white-space") == "nowrap", "行内命令与参数不能拆行"
    assert _property(css, "pre code", "white-space") == "pre", "多行代码块仍须保留换行与缩进"


def test_command_column_does_not_wrap(dist: Path, pages: dict[str, BeautifulSoup]) -> None:
    table = pages["cli"].select_one("table.commands")
    assert table is not None
    first_cells = [row.find(["th", "td"]) for row in table.select("tr")]
    assert first_cells and all(cell.name == "th" for cell in first_cells)
    assert _property(_css(dist), ".commands th:first-child", "white-space") == "nowrap"


def test_commands_scroll_inside_wrapper(dist: Path, pages: dict[str, BeautifulSoup]) -> None:
    table = pages["cli"].select_one(".table-scroll > table.commands")
    assert table is not None, "CLI 表格需要独立的横向滚动容器"
    assert table.parent.get("tabindex") == "0", "键盘用户应能聚焦滚动容器"
    css = _css(dist)
    assert _property(css, ".table-scroll", "overflow-x") == "auto"
    assert _property(css, ".table-scroll", "max-width") == "100%"
    assert _property(css, ".commands", "table-layout") == "auto", "列宽须容纳不折行代码，不能溢出固定单元格"
