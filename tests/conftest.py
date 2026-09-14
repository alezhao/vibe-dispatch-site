"""共享 fixture：构建一次站点，把产物解析成 BeautifulSoup 供各测试断言。

构建入口约定为 ``portal.build.build(out_dir: Path) -> None``。
``portal`` 尚未实现时这里会以 ModuleNotFoundError 失败——这是预期的红。
"""

from __future__ import annotations

from pathlib import Path

import pytest
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent

# 站点的全部页面（不含扩展名）。构建必须恰好生成这些 HTML 文件。
PAGES = ["index", "quickstart", "cli", "workflow"]

# 任务状态与转换，来自 vibe-dispatch README 的工作流图。
STATES = [
    "queued",
    "running",
    "self-tested",
    "awaiting-review",
    "merged",
    "failed",
    "rejected",
    "cancelled",
]
TRANSITIONS = [
    "dispatch",
    "collect",
    "verify_locally",
    "merge",
    "reject",
    "cancel",
    "retry",
]

GITHUB_REPO_URL = "https://github.com/alezhao/vibe-dispatch"


def read_page(dist: Path, name: str) -> BeautifulSoup:
    html = (dist / f"{name}.html").read_text(encoding="utf-8")
    return BeautifulSoup(html, "html.parser")


@pytest.fixture(scope="session")
def dist(tmp_path_factory: pytest.TempPathFactory) -> Path:
    from portal.build import build

    out = tmp_path_factory.mktemp("dist")
    build(out)
    return out


@pytest.fixture(scope="session")
def pages(dist: Path) -> dict[str, BeautifulSoup]:
    return {name: read_page(dist, name) for name in PAGES}


def code_texts(soup: BeautifulSoup) -> set[str]:
    """页面中所有 <code> 元素的文本（去首尾空白）。"""
    return {c.get_text(strip=True) for c in soup.find_all("code")}
