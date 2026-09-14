"""任务 B：首页内容。

验收：uv run --no-sync python -m pytest -q tests/test_build.py tests/test_home.py
"""

from __future__ import annotations

from bs4 import BeautifulSoup

from tests.conftest import GITHUB_REPO_URL, STATES, code_texts

TAGLINE = "多任务分派的 vibe coding 开发平台"


def test_hero_title_and_tagline(pages: dict[str, BeautifulSoup]) -> None:
    home = pages["index"]
    h1s = home.find_all("h1")
    assert len(h1s) == 1, "首页只应有一个 h1"
    assert h1s[0].get_text(strip=True) == "vibe-dispatch"

    tagline = home.select_one(".tagline")
    assert tagline is not None, "需要 .tagline 元素承载一句话定位"
    assert TAGLINE in tagline.get_text()


def test_feature_cards_cover_core_selling_points(pages: dict[str, BeautifulSoup]) -> None:
    home = pages["index"]
    cards = home.select(".feature")
    assert len(cards) >= 3, "至少三张 .feature 卡片"

    for card in cards:
        heading = card.find(["h2", "h3"])
        assert heading is not None and heading.get_text(strip=True), "每张卡片要有标题"
        body = card.get_text(" ", strip=True)
        assert len(body) > len(heading.get_text(strip=True)) + 10, "卡片要有说明文字"

    combined = " ".join(c.get_text(" ", strip=True) for c in cards)
    for keyword in ("双跑验收", "自动修复", "worktree"):
        assert keyword in combined, f"特性卡片应覆盖「{keyword}」"


def test_state_overview_lists_every_state(pages: dict[str, BeautifulSoup]) -> None:
    home = pages["index"]
    section = home.find(id="states")
    assert section is not None, "需要 id=\"states\" 的状态一览区块"
    codes = code_texts(section)
    missing = [s for s in STATES if s not in codes]
    assert not missing, f"状态一览缺少 {missing}（每个状态用 <code> 标出）"


def test_calls_to_action(pages: dict[str, BeautifulSoup]) -> None:
    home = pages["index"]
    cta = home.select("a.cta[href]")
    assert cta, "需要 a.cta 行动按钮"
    hrefs = {a["href"] for a in cta}
    assert "quickstart.html" in hrefs, "主 CTA 应指向 quickstart.html"

    main = home.find("main") or home
    repo_links = [a for a in main.find_all("a", href=True) if a["href"] == GITHUB_REPO_URL]
    assert repo_links, "正文中应有指向 GitHub 仓库的链接"
