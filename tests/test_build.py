"""任务 A：构建管线与基础布局。

验收：uv run --no-sync python -m pytest -q tests/test_build.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from tests.conftest import GITHUB_REPO_URL, PAGES, ROOT, read_page


def test_build_generates_every_page_and_stylesheet(dist: Path) -> None:
    for name in PAGES:
        assert (dist / f"{name}.html").is_file(), f"缺少 {name}.html"
    assert (dist / "static" / "style.css").is_file()
    assert (dist / "static" / "style.css").stat().st_size > 0


def test_rebuild_is_clean_and_idempotent(tmp_path: Path) -> None:
    from portal.build import build

    out = tmp_path / "out"
    build(out)
    first = {p.relative_to(out): p.read_bytes() for p in out.rglob("*") if p.is_file()}

    stale = out / "stale.html"
    stale.write_text("<p>上次构建残留</p>", encoding="utf-8")
    build(out)
    second = {p.relative_to(out): p.read_bytes() for p in out.rglob("*") if p.is_file()}

    assert not stale.exists(), "重建应清空输出目录，不留残余文件"
    assert first == second, "两次构建的产物应逐字节一致"


def test_module_cli_builds_into_given_dir(tmp_path: Path) -> None:
    out = tmp_path / "cli-out"
    proc = subprocess.run(
        [sys.executable, "-m", "portal.build", "--out", str(out)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert (out / "index.html").is_file()


@pytest.mark.parametrize("name", PAGES)
def test_page_skeleton(dist: Path, name: str) -> None:
    raw = (dist / f"{name}.html").read_text(encoding="utf-8")
    assert raw.lstrip().lower().startswith("<!doctype html>")

    soup = read_page(dist, name)
    html = soup.find("html")
    assert html is not None and html.get("lang") == "zh-CN"

    meta = soup.find("meta", attrs={"charset": True})
    assert meta is not None and meta["charset"].lower() == "utf-8"
    assert soup.find("meta", attrs={"name": "viewport"}) is not None

    title = soup.find("title")
    assert title is not None and "vibe-dispatch" in title.get_text()

    link = soup.find("link", rel="stylesheet")
    assert link is not None and link["href"].endswith("static/style.css")


@pytest.mark.parametrize("name", PAGES)
def test_shared_nav_links_every_page(dist: Path, name: str) -> None:
    soup = read_page(dist, name)
    nav = soup.find("nav")
    assert nav is not None, "每页都要有共用导航 <nav>"

    hrefs = {a["href"] for a in nav.find_all("a", href=True)}
    for target in PAGES:
        assert f"{target}.html" in hrefs, f"导航缺少 {target}.html"

    current = [a for a in nav.find_all("a", href=True) if a.get("aria-current") == "page"]
    assert len(current) == 1 and current[0]["href"] == f"{name}.html", (
        "导航需用 aria-current=\"page\" 标出当前页，且只标一个"
    )


@pytest.mark.parametrize("name", PAGES)
def test_footer_links_to_project_repo(dist: Path, name: str) -> None:
    soup = read_page(dist, name)
    footer = soup.find("footer")
    assert footer is not None
    hrefs = {a["href"] for a in footer.find_all("a", href=True)}
    assert GITHUB_REPO_URL in hrefs


@pytest.mark.parametrize("name", PAGES)
def test_internal_links_resolve_to_built_files(dist: Path, name: str) -> None:
    soup = read_page(dist, name)
    refs: list[str] = []
    refs += [a["href"] for a in soup.find_all("a", href=True)]
    refs += [l["href"] for l in soup.find_all("link", href=True)]
    refs += [i["src"] for i in soup.find_all("img", src=True)]
    refs += [s["src"] for s in soup.find_all("script", src=True)]

    page_dir = (dist / f"{name}.html").parent
    for ref in refs:
        parts = urlsplit(ref)
        if parts.scheme or parts.netloc or ref.startswith("#") or ref.startswith("mailto:"):
            continue
        path = parts.path
        if not path:
            continue
        target = (page_dir / path).resolve()
        assert target.is_file(), f"{name}.html 引用了不存在的 {ref}"


def test_base_template_exposes_head_block() -> None:
    base = ROOT / "templates" / "base.html"
    assert base.is_file(), "需要 templates/base.html 作为共用布局"
    text = base.read_text(encoding="utf-8")
    assert "{% block head %}" in text, "base.html 需提供 head block 供各页内联私有样式"
    assert "{% block content %}" in text
