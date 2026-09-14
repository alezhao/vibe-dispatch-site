"""任务 D：工作流页（状态机、三种结局、自动修复回路、双跑验收）。

验收：uv run --no-sync python -m pytest -q tests/test_build.py tests/test_workflow.py
"""

from __future__ import annotations

from bs4 import BeautifulSoup

from tests.conftest import STATES, TRANSITIONS, code_texts


def test_heading(pages: dict[str, BeautifulSoup]) -> None:
    h1 = pages["workflow"].find("h1")
    assert h1 is not None and "工作流" in h1.get_text()


def test_state_machine_names_every_state_and_transition(pages: dict[str, BeautifulSoup]) -> None:
    page = pages["workflow"]
    machine = page.find(id="state-machine")
    assert machine is not None, "需要 id=\"state-machine\" 区块"
    codes = code_texts(machine)
    assert not [s for s in STATES if s not in codes], "状态机区块应用 <code> 列出全部状态"
    assert not [t for t in TRANSITIONS if t not in codes], "状态机区块应用 <code> 列出全部转换"


def test_three_unsuccessful_endings_are_distinguished(pages: dict[str, BeautifulSoup]) -> None:
    page = pages["workflow"]
    for ending, hint in (
        ("failed", "机器"),
        ("rejected", "人"),
        ("cancelled", "叫停"),
    ):
        block = page.find(id=f"ending-{ending}")
        assert block is not None, f"需要 id=\"ending-{ending}\" 区块"
        text = block.get_text(" ", strip=True)
        assert len(text) >= 30, f"{ending} 的说明太短"
        assert hint in text, f"{ending} 的说明应点出关键差异（{hint}）"

    # failed 不是终态：可以 retry；merged/rejected/cancelled 是终态
    text = page.get_text(" ", strip=True)
    assert "终态" in text


def test_auto_fix_loop_documents_both_budgets(pages: dict[str, BeautifulSoup]) -> None:
    page = pages["workflow"]
    section = page.find(id="auto-fix")
    assert section is not None, "需要 id=\"auto-fix\" 区块"
    codes = code_texts(section)
    assert "VIBE_FIX_ROUNDS" in codes
    assert "VIBE_MAX_ATTEMPTS" in codes
    text = section.get_text(" ", strip=True)
    assert "3" in text and "5" in text, "要写出默认值：修复 3 轮、整链重跑 5 次"


def test_double_run_acceptance_explained(pages: dict[str, BeautifulSoup]) -> None:
    section = pages["workflow"].find(id="double-run")
    assert section is not None, "需要 id=\"double-run\" 区块"
    text = section.get_text(" ", strip=True)
    assert "沙箱" in text and "本机" in text
    assert "commit_sha" in code_texts(section)
