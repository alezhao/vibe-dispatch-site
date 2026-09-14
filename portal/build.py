"""将 Jinja2 模板与静态资源构建为门户站。"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT = Path(__file__).resolve().parent.parent
PAGES = (
    ("index", "首页"),
    ("quickstart", "快速开始"),
    ("cli", "CLI 参考"),
    ("workflow", "工作流"),
)


def build(out_dir: Path) -> None:
    """清空并重建输出目录，渲染页面并复制完整静态资源目录。"""
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    env = Environment(
        loader=FileSystemLoader(ROOT / "templates"),
        autoescape=select_autoescape(["html"]),
    )
    for name, title in PAGES:
        template = env.get_template(f"{name}.html")
        html = template.render(pages=PAGES, current_page=name, title=title)
        (out_dir / f"{name}.html").write_text(html, encoding="utf-8")

    shutil.copytree(ROOT / "static", out_dir / "static")


def main() -> None:
    parser = argparse.ArgumentParser(description="构建 vibe-dispatch 门户站")
    parser.add_argument("--out", type=Path, default=Path("dist"), help="输出目录（默认：dist）")
    args = parser.parse_args()
    build(args.out)


if __name__ == "__main__":
    main()
