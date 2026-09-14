# vibe-dispatch-site

[vibe-dispatch](https://github.com/alezhao/vibe-dispatch) 的门户网站。

这个仓库同时是一次试跑：测试先写好提交（`tests/`），实现由 vibe-dispatch 派发到沙箱里的 agent 完成，每个任务一个 PR。任务拆分与约定见 [docs/TDD-PLAN.md](docs/TDD-PLAN.md)。

```bash
uv sync --frozen --extra dev
uv run --no-sync python -m pytest -q          # 验收
uv run --no-sync python -m portal.build --out dist
```
