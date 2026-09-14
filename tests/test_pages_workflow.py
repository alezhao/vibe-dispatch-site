"""任务 E：GitHub Pages 部署工作流。

验收：uv run --no-sync python -m pytest -q tests/test_pages_workflow.py

不依赖站点构建（不使用 dist/pages fixture），只校验 workflow 文件本身。
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from tests.conftest import ROOT

WORKFLOW = ROOT / ".github" / "workflows" / "pages.yml"


@pytest.fixture(scope="module")
def workflow() -> dict:
    assert WORKFLOW.is_file(), "缺少 .github/workflows/pages.yml"
    data = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def _steps(workflow: dict) -> list[dict]:
    steps: list[dict] = []
    for job in workflow["jobs"].values():
        steps += job.get("steps", [])
    return steps


def test_triggers_on_push_to_main(workflow: dict) -> None:
    # PyYAML 会把裸 `on:` 键解析成布尔 True
    on = workflow.get("on") or workflow.get(True)
    assert on is not None, "缺少 on: 触发器"
    push = on.get("push") if isinstance(on, dict) else None
    assert push is not None and "main" in push.get("branches", []), "应在 push main 时触发"
    assert "workflow_dispatch" in on, "应允许手动触发"


def test_permissions_for_pages_deploy(workflow: dict) -> None:
    perms = workflow.get("permissions", {})
    assert perms.get("pages") == "write"
    assert perms.get("id-token") == "write"
    assert perms.get("contents") == "read"


def test_build_steps_use_uv_and_portal_build(workflow: dict) -> None:
    runs = "\n".join(step.get("run", "") for step in _steps(workflow))
    assert "uv sync" in runs, "要用 uv sync 装依赖"
    assert "python -m portal.build" in runs and "--out dist" in runs, "要用 portal.build 构建到 dist"


def test_uses_official_pages_actions(workflow: dict) -> None:
    uses = [step.get("uses", "") for step in _steps(workflow)]
    assert any(u.startswith("actions/checkout@") for u in uses)
    assert any(u.startswith("actions/upload-pages-artifact@") for u in uses)
    assert any(u.startswith("actions/deploy-pages@") for u in uses)


def test_upload_points_at_dist(workflow: dict) -> None:
    for step in _steps(workflow):
        if step.get("uses", "").startswith("actions/upload-pages-artifact@"):
            assert step.get("with", {}).get("path") == "dist"
            return
    pytest.fail("找不到 upload-pages-artifact 步骤")


def test_deploy_job_has_pages_environment(workflow: dict) -> None:
    deploy_jobs = [
        job
        for job in workflow["jobs"].values()
        if any(s.get("uses", "").startswith("actions/deploy-pages@") for s in job.get("steps", []))
    ]
    assert deploy_jobs, "需要一个执行 deploy-pages 的 job"
    env = deploy_jobs[0].get("environment")
    name = env.get("name") if isinstance(env, dict) else env
    assert name == "github-pages"
