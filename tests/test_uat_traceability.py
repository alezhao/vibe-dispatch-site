"""UAT 清单与单元测试的双向追溯。

docs/UAT.md 里每条 `auto` 条目引用的测试必须存在；tests/ 里每个测试函数都必须
被某条 UAT 条目引用。任何一边多出来或漏掉都算失败——这样清单不会烂掉，
测试也不会没有对应的验收场景。
"""

from __future__ import annotations

import ast
import re

from tests.conftest import ROOT

UAT = ROOT / "docs" / "UAT.md"
TESTS = ROOT / "tests"
REF = re.compile(r"`(test_[a-z0-9_]+\.py)::(test_[a-z0-9_]+)`")


def uat_references() -> set[tuple[str, str]]:
    return set(REF.findall(UAT.read_text(encoding="utf-8")))


def defined_tests() -> set[tuple[str, str]]:
    found: set[tuple[str, str]] = set()
    for path in sorted(TESTS.glob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                found.add((path.name, node.name))
    return found


def test_uat_document_exists_with_every_milestone() -> None:
    text = UAT.read_text(encoding="utf-8")
    for milestone in "ABCDEF":
        assert re.search(rf"^## 里程碑 {milestone}[：:]", text, re.M), f"UAT.md 缺少里程碑 {milestone}"


def test_every_uat_reference_points_at_a_real_test() -> None:
    missing = sorted(uat_references() - defined_tests())
    assert not missing, f"UAT.md 引用了不存在的测试：{missing}"


def test_every_test_is_covered_by_a_uat_item() -> None:
    orphans = sorted(defined_tests() - uat_references())
    assert not orphans, f"这些测试没有对应的 UAT 条目，请补进 docs/UAT.md：{orphans}"


def test_uat_ids_are_unique() -> None:
    ids = re.findall(r"^\| ([A-F]-\d+) \|", UAT.read_text(encoding="utf-8"), re.M)
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    assert not dupes, f"UAT ID 重复：{dupes}"
