"""任务 A 的补充约定：完整静态资源复制与占位标题。"""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from tests.conftest import ROOT, read_page


def test_build_copies_static_tree_from_any_working_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from portal.build import build

    out = tmp_path / "nested" / "out"
    monkeypatch.chdir(tmp_path)
    with TemporaryDirectory(prefix="test-assets-", dir=ROOT / "static") as directory:
        assets = Path(directory)
        (assets / "nested").mkdir()
        (assets / "empty").mkdir()
        payload = b"\x00\xff\x80static asset\n"
        (assets / "nested" / "asset.bin").write_bytes(payload)

        assert build(out) is None
        copied = out / "static" / assets.name
        assert (copied / "nested" / "asset.bin").read_bytes() == payload
        assert (copied / "empty").is_dir()

    build(out)
    assert not copied.exists(), "重建应移除源目录已删除的嵌套静态资源"


@pytest.mark.parametrize(
    ("name", "heading"),
    [
        ("index", "vibe-dispatch"),
        ("quickstart", "快速开始"),
        ("cli", "CLI 参考"),
        ("workflow", "工作流"),
    ],
)
def test_page_has_placeholder_heading(dist: Path, name: str, heading: str) -> None:
    title = read_page(dist, name).find("h1")
    assert title is not None
    if name == "index":
        assert title.get_text(strip=True) == heading
    else:
        assert heading in title.get_text(strip=True)
