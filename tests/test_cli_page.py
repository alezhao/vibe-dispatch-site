"""任务 C（其二）：CLI 参考页。

验收：uv run --no-sync python -m pytest -q tests/test_build.py tests/test_quickstart.py tests/test_cli_page.py
"""

from __future__ import annotations

from bs4 import BeautifulSoup

SUBCOMMANDS = [
    "doctor",
    "serve",
    "submit",
    "ls",
    "show",
    "logs",
    "run",
    "retry",
    "cancel",
    "merge",
    "reject",
    "resume",
]


def _rows(soup: BeautifulSoup) -> dict[str, str]:
    """表格每行：第一格 <code>vibe xxx</code>，第二格说明。"""
    table = soup.select_one("table.commands")
    assert table is not None, "需要 <table class=\"commands\">"
    rows: dict[str, str] = {}
    for tr in table.select("tbody tr"):
        cells = tr.find_all(["td", "th"])
        assert len(cells) >= 2, "每行至少两格：命令 / 说明"
        code = cells[0].find("code")
        assert code is not None, "命令要用 <code> 包住"
        rows[code.get_text(strip=True)] = cells[1].get_text(" ", strip=True)
    return rows


def test_heading(pages: dict[str, BeautifulSoup]) -> None:
    h1 = pages["cli"].find("h1")
    assert h1 is not None and "CLI" in h1.get_text()


def test_every_subcommand_documented(pages: dict[str, BeautifulSoup]) -> None:
    rows = _rows(pages["cli"])
    for cmd in SUBCOMMANDS:
        key = f"vibe {cmd}"
        assert key in rows, f"缺少 {key}"
        assert len(rows[key]) >= 6, f"{key} 的说明太短"


def test_reject_requires_reason_but_cancel_does_not(pages: dict[str, BeautifulSoup]) -> None:
    rows = _rows(pages["cli"])
    assert "必填" in rows["vibe reject"], "reject 的理由必填，说明里要写明"
    assert "可选" in rows["vibe cancel"], "cancel 的理由可选，说明里要写明"


def test_submit_mentions_acceptance_and_setup(pages: dict[str, BeautifulSoup]) -> None:
    rows = _rows(pages["cli"])
    assert "-a" in rows["vibe submit"]
    assert "--setup" in rows["vibe submit"]
