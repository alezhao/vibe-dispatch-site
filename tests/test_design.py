"""里程碑 F：视觉设计（开发者工具风 · 深色 · 自托管字体）。

验收：uv run --no-sync python -m pytest -q
对应 docs/UAT.md 的 F-1 … F-10。只检查可机器判定的部分；观感由 dev lead 按 F-12 人工复核。
"""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from bs4 import BeautifulSoup

from tests.conftest import PAGES, ROOT

TOKENS = [
    "--color-bg",
    "--color-surface",
    "--color-fg",
    "--color-muted",
    "--color-accent",
    "--color-border",
    "--font-sans",
    "--font-mono",
    "--radius",
]


# ---------- CSS 解析辅助（够用即可，不追求完整语法） ----------


def _css(dist: Path) -> str:
    text = (dist / "static" / "style.css").read_text(encoding="utf-8")
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


def _blocks(css: str) -> list[tuple[str, str]]:
    """扁平化的 (selector, body) 列表；@media 内部的规则也展开。"""
    out: list[tuple[str, str]] = []
    depth_stack: list[str] = []
    buf = ""
    i = 0
    while i < len(css):
        ch = css[i]
        if ch == "{":
            depth_stack.append(buf.strip())
            buf = ""
        elif ch == "}":
            selector = depth_stack.pop() if depth_stack else ""
            if selector and not selector.startswith("@"):
                out.append((selector, buf))
            buf = ""
        else:
            buf += ch
        i += 1
    return out


def _rule(css: str, selector: str) -> str:
    bodies = [body for sel, body in _blocks(css) if selector in [s.strip() for s in sel.split(",")]]
    assert bodies, f"缺少 `{selector}` 规则"
    return "\n".join(bodies)


def _root_tokens(css: str) -> dict[str, str]:
    root = _rule(css, ":root")
    return {m.group(1): m.group(2).strip() for m in re.finditer(r"(--[\w-]+)\s*:\s*([^;]+);", root)}


def _hex_to_rgb(value: str) -> tuple[float, float, float]:
    m = re.fullmatch(r"#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})", value.strip())
    assert m, f"颜色 token 需用 #rgb / #rrggbb 十六进制写法便于校验，得到 {value!r}"
    h = m.group(1)
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i : i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]


def _luminance(value: str) -> float:
    def lin(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (lin(c) for c in _hex_to_rgb(value))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast(a: str, b: str) -> float:
    la, lb = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


# ---------- F-1 ~ F-3：深色主题、token、对比度 ----------


def test_dark_theme_declared(dist: Path, pages: dict[str, BeautifulSoup]) -> None:
    css = _css(dist)
    root = _rule(css, ":root")
    assert re.search(r"color-scheme\s*:\s*dark\b", root), ":root 需声明 color-scheme: dark"
    for name, soup in pages.items():
        meta = soup.find("meta", attrs={"name": "color-scheme"})
        assert meta is not None and meta.get("content") == "dark", f"{name}.html 缺少 <meta name=\"color-scheme\" content=\"dark\">"
    assert _luminance(_root_tokens(css)["--color-bg"]) < 0.1, "背景色应为深色（相对亮度 < 0.1）"


def test_design_tokens_defined(dist: Path) -> None:
    tokens = _root_tokens(_css(dist))
    missing = [t for t in TOKENS if t not in tokens]
    assert not missing, f":root 缺少设计 token：{missing}"


def test_no_raw_colors_outside_tokens(dist: Path) -> None:
    css = _css(dist)
    offenders: list[str] = []
    for selector, body in _blocks(css):
        if selector == ":root":
            continue
        if re.search(r"#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(", body):
            offenders.append(selector)
    assert not offenders, f"颜色一律走 var(--…)，这些规则里有裸色值：{offenders}"


def test_contrast_ratios(dist: Path) -> None:
    tokens = _root_tokens(_css(dist))
    bg = tokens["--color-bg"]
    assert _contrast(tokens["--color-fg"], bg) >= 7, "正文与背景对比度需 ≥ 7:1"
    assert _contrast(tokens["--color-muted"], bg) >= 4.5, "次要文字与背景对比度需 ≥ 4.5:1"
    assert _contrast(tokens["--color-accent"], bg) >= 4.5, "强调色与背景对比度需 ≥ 4.5:1"


# ---------- F-4 ~ F-6：字体、预载、无外部资源 ----------


def _font_faces(css: str) -> dict[str, list[str]]:
    faces: dict[str, list[str]] = {}
    for m in re.finditer(r"@font-face\s*\{([^}]*)\}", css):
        body = m.group(1)
        fam = re.search(r"font-family\s*:\s*[\"']?([^;\"']+)[\"']?\s*;", body)
        urls = re.findall(r"url\(\s*[\"']?([^)\"']+)[\"']?\s*\)", body)
        if fam:
            faces.setdefault(fam.group(1).strip(), []).extend(urls)
    return faces


def test_self_hosted_fonts(dist: Path) -> None:
    css = _css(dist)
    faces = _font_faces(css)
    for family in ("Inter", "JetBrains Mono"):
        assert family in faces, f"缺少 @font-face {family}"
        assert faces[family], f"{family} 的 @font-face 没有 src: url()"
        for url in faces[family]:
            assert not urlsplit(url).netloc, f"字体必须自托管，不能引用 {url}"
            target = (dist / "static" / url).resolve()
            assert target.is_file() and target.suffix == ".woff2", f"{family} 引用的 {url} 不在产物中"

    tokens = _root_tokens(css)
    assert "Inter" in tokens["--font-sans"], "--font-sans 应以 Inter 打头"
    assert "JetBrains Mono" in tokens["--font-mono"], "--font-mono 应以 JetBrains Mono 打头"
    assert "var(--font-sans)" in _rule(css, "body"), "body 用 var(--font-sans)"
    code_rule = "\n".join(body for sel, body in _blocks(css) if {"code", "pre"} & {s.strip() for s in sel.split(",")})
    assert "var(--font-mono)" in code_rule, "code / pre 用 var(--font-mono)"


def test_primary_font_preloaded(dist: Path, pages: dict[str, BeautifulSoup]) -> None:
    for name, soup in pages.items():
        preloads = [
            l
            for l in soup.find_all("link", rel="preload")
            if l.get("as") == "font" and l.get("type") == "font/woff2" and l.has_attr("crossorigin")
        ]
        assert preloads, f"{name}.html 缺少字体 preload"
        hrefs = [l["href"] for l in preloads]
        assert any("Inter" in h for h in hrefs), f"{name}.html 应预载 Inter 主字体，得到 {hrefs}"
        for href in hrefs:
            assert (dist / href).is_file(), f"{name}.html 预载的 {href} 不存在"


def test_no_scripts_and_no_external_assets(dist: Path, pages: dict[str, BeautifulSoup]) -> None:
    for name, soup in pages.items():
        assert not soup.find_all("script"), f"{name}.html 不应有 <script>"
        for tag, attr in (("link", "href"), ("img", "src"), ("source", "src"), ("iframe", "src")):
            for el in soup.find_all(tag, attrs={attr: True}):
                assert not urlsplit(el[attr]).netloc, f"{name}.html 引用了外部资源 {el[attr]}"
    for url in re.findall(r"url\(\s*[\"']?([^)\"']+)[\"']?\s*\)", _css(dist)):
        assert not urlsplit(url).netloc and not url.startswith("data:"), f"style.css 引用了外部资源 {url}"


# ---------- F-7 ~ F-10：代码块、页头、焦点、响应式 ----------


def test_code_blocks_styled(dist: Path) -> None:
    css = _css(dist)
    pre = _rule(css, "pre")
    assert "var(--color-surface)" in pre, "pre 背景用 var(--color-surface)"
    assert re.search(r"\bborder(-\w+)?\s*:", pre), "pre 需要边框"
    assert "var(--radius)" in pre, "pre 圆角用 var(--radius)"
    assert re.search(r"overflow-x\s*:\s*auto", pre), "pre 需 overflow-x: auto"
    inline = "\n".join(body for sel, body in _blocks(css) if "code" in [s.strip() for s in sel.split(",")])
    assert re.search(r"background(-color)?\s*:", inline), "行内 code 需要背景色以区分正文"


def test_sticky_header_and_current_nav(dist: Path) -> None:
    css = _css(dist)
    header = _rule(css, ".site-header")
    assert re.search(r"position\s*:\s*sticky", header) and re.search(r"\btop\s*:\s*0", header), ".site-header 需 position: sticky; top: 0"
    _rule(css, 'nav a[aria-current="page"]')


def test_focus_visible_outline(dist: Path) -> None:
    css = _css(dist)
    focus = "\n".join(body for sel, body in _blocks(css) if ":focus-visible" in sel)
    assert focus, "缺少 :focus-visible 规则"
    assert re.search(r"\boutline(-\w+)?\s*:", focus), ":focus-visible 需设置 outline"


def test_responsive_layout_rules(dist: Path) -> None:
    css = _css(dist)
    assert re.search(r"@media\s*\(\s*max-width", css), "至少一个 max-width 断点"
    features = _rule(css, ".features")
    assert re.search(r"display\s*:\s*grid", features), ".features 用 grid 布局"
    assert "auto-fit" in features or "auto-fill" in features, ".features 列数需自适应（auto-fit / auto-fill + minmax）"
    assert "minmax(" in features


@pytest.mark.parametrize("name", PAGES)
def test_every_page_links_same_stylesheet_only(pages: dict[str, BeautifulSoup], name: str) -> None:
    """F 期间不得为绕过 token 检查而新增第二份样式表。"""
    sheets = [l["href"] for l in pages[name].find_all("link", rel="stylesheet")]
    assert sheets == ["static/style.css"], f"{name}.html 的样式表应只有 static/style.css，得到 {sheets}"
