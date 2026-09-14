"""任务 C（其一）：快速开始页。

验收：uv run --no-sync python -m pytest -q tests/test_build.py tests/test_quickstart.py tests/test_cli_page.py
"""

from __future__ import annotations

from bs4 import BeautifulSoup


def _code_blocks(soup: BeautifulSoup) -> list[str]:
    return [pre.get_text() for pre in soup.select("pre > code")]


def test_heading(pages: dict[str, BeautifulSoup]) -> None:
    page = pages["quickstart"]
    h1 = page.find("h1")
    assert h1 is not None and "快速开始" in h1.get_text()


def test_steps_are_an_ordered_list(pages: dict[str, BeautifulSoup]) -> None:
    page = pages["quickstart"]
    steps = page.select_one("ol.steps")
    assert steps is not None, "步骤用 <ol class=\"steps\">"
    items = steps.find_all("li", recursive=False)
    assert len(items) >= 4, "至少四步：安装 → 起服务 → 派发 → 观察/合并"
    for li in items:
        assert li.find("pre") is not None, "每一步都要带一个可复制的命令块"


def test_commands_appear_in_pre_code_blocks(pages: dict[str, BeautifulSoup]) -> None:
    blocks = _code_blocks(pages["quickstart"])
    joined = "\n".join(blocks)
    assert 'pip install -e ".[dev]"' in joined
    assert "vibe serve --demo" in joined
    assert "vibe submit" in joined and " -a " in joined, "派发示例必须带验收命令 -a"
    assert "vibe ls" in joined
    assert "vibe show" in joined
    assert "vibe merge" in joined


def test_setup_flag_is_explained(pages: dict[str, BeautifulSoup]) -> None:
    text = pages["quickstart"].get_text(" ", strip=True)
    assert "--setup" in text
    # 要解释「为什么」：沙箱里没有 pip/pytest，command not found 的退出码和测试失败一样
    assert "command not found" in text
    assert "沙箱" in text
