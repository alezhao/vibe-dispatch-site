# vibe-dispatch 门户站：TDD 计划

这是 [vibe-dispatch](https://github.com/alezhao/vibe-dispatch) 的门户网站，同时也是用 vibe-dispatch 本身派发开发的一次端到端试跑。
**测试先于实现写好并提交**（`tests/`），每个任务的目标就是让指定的测试文件变绿。agent 开工前必读本文、[`docs/UAT.md`](UAT.md) 里对应里程碑的验收条目，以及对应测试。

验收分两层：`docs/UAT.md` 是**用户视角的验收清单**（每条一个场景 + 判定标准，标注 auto / manual），`tests/` 是其中 auto 条目的**单元测试实现**；`tests/test_uat_traceability.py` 保证两者一一对应。

## 技术栈与约束

- Python ≥ 3.10，依赖只有 `jinja2`；dev 依赖 `pytest`、`beautifulsoup4`、`pyyaml`。用 `uv sync --frozen --extra dev` 安装，`uv run --no-sync python -m pytest -q …` 验收。
- 沙箱里**没有 node/npm**，不要引入任何前端构建工具。纯静态：Jinja2 模板 → HTML + 一份 CSS。
- 包名 `portal`（不能叫 `site`，与标准库冲突）。构建入口固定为：
  - `portal.build.build(out_dir: Path) -> None`：清空并重建 `out_dir`，生成 `index.html`、`quickstart.html`、`cli.html`、`workflow.html` 与 `static/style.css`。
  - `python -m portal.build --out DIR`：命令行入口，退出码 0。
- 模板放 `templates/`（`base.html` + 每页一个模板），静态资源放 `static/`，构建时整目录复制到 `dist/static/`。
- 页面语言 `zh-CN`，内容以 `docs/source/` 里的两份文档（vibe-dispatch 的 README 与操作手册）为唯一事实来源，**不要编造功能**。
- 页面私有样式写在自己模板的 `{% block head %}` 里（`<style>`），不要为此改 `static/style.css`；这样并行任务的分支不会在同一文件上冲突。

## 站点信息架构

| 页面 | 文件 | 内容 |
|---|---|---|
| 首页 | `index.html` | hero（`h1` = `vibe-dispatch`，`.tagline` = 「多任务分派的 vibe coding 开发平台」）、≥3 张 `.feature` 卡片（双跑验收 / 自动修复回路 / 本机 worktree 模式 …）、`#states` 状态一览（8 个状态用 `<code>`）、`a.cta` 指向 `quickstart.html`、正文含 GitHub 仓库链接 |
| 快速开始 | `quickstart.html` | `h1` 含「快速开始」；`ol.steps` ≥4 步，每步一个 `<pre><code>`：`pip install -e ".[dev]"` → `vibe serve --demo` → `vibe submit … -a …` → `vibe ls` / `vibe show` / `vibe merge`；解释 `--setup` 为何必填（沙箱里没有 pip/pytest，`command not found` 的退出码和测试失败一样） |
| CLI 参考 | `cli.html` | `h1` 含「CLI」；`table.commands`，`tbody` 每行 `<code>vibe xxx</code>` + 说明，覆盖 doctor / serve / submit / ls / show / logs / run / retry / cancel / merge / reject / resume；reject 说明含「必填」，cancel 说明含「可选」，submit 说明含 `-a` 与 `--setup` |
| 工作流 | `workflow.html` | `h1` 含「工作流」；`#state-machine`（全部状态与 dispatch / collect / verify_locally / merge / reject / cancel / retry 用 `<code>`）；`#ending-failed` / `#ending-rejected` / `#ending-cancelled` 三段说明（机器判定 / 人判定 / 用户叫停，并提及「终态」）；`#auto-fix`（`VIBE_FIX_ROUNDS` 默认 3、`VIBE_MAX_ATTEMPTS` 默认 5）；`#double-run`（沙箱 + 本机各跑一次，`commit_sha`） |

共用布局（`base.html`）：`<!doctype html>`、`<html lang="zh-CN">`、`<meta charset="utf-8">`、viewport、`<title>` 含 `vibe-dispatch`、`<link rel="stylesheet" href="static/style.css">`、`<nav>` 链接四个页面并用 `aria-current="page"` 标当前页、`<footer>` 含 `https://github.com/alezhao/vibe-dispatch` 链接、`{% block head %}` 与 `{% block content %}`。站内所有链接必须能在产物中找到对应文件。

## 任务拆分

| 任务 | 分支 | 测试文件 | 验收命令 | 依赖 |
|---|---|---|---|---|
| A 构建管线 + 基础布局 | `feat/build-pipeline` | `tests/test_build.py` | `uv run --no-sync python -m pytest -q tests/test_build.py` | — |
| B 首页 | `feat/home` | `tests/test_home.py` | `… tests/test_build.py tests/test_home.py` | A |
| C 快速开始 + CLI 参考 | `feat/quickstart-cli` | `tests/test_quickstart.py` `tests/test_cli_page.py` | `… tests/test_build.py tests/test_quickstart.py tests/test_cli_page.py` | A |
| D 工作流页 | `feat/workflow-page` | `tests/test_workflow.py` | `… tests/test_build.py tests/test_workflow.py` | A |
| E GitHub Pages 部署 | `feat/pages-deploy` | `tests/test_pages_workflow.py` | `uv run --no-sync python -m pytest -q tests/test_pages_workflow.py` | — |
| F 视觉设计 | `paperclip/vib-12` | `tests/test_design.py`（UAT F-1…F-11） | `uv run --no-sync python -m pytest -q`（全量：内容测试不得回退） | A–E |

F 的设计方向与约束见 `docs/UAT.md` 里程碑 F：开发者工具风、只做深色、自托管 Inter + JetBrains Mono（文件已在 `static/fonts/`）、零 JS、零外部请求、颜色全部走 `:root` token。F 可以改 `static/style.css`、`templates/base.html`、`static/fonts/`；各页模板只允许加 class 或结构包裹，不改任何文字（A–E 的内容测试会守住）。F-12 / F-13 为人工复核项。

A 先做：它要让四个页面都能生成（内容可以是占位标题，但骨架、导航、链接检查必须过）。A 合并后 B / C / D / E 并行，各自只改自己的模板（B: `templates/index.html`，C: `templates/quickstart.html` + `templates/cli.html`，D: `templates/workflow.html`，E: `.github/workflows/pages.yml`），**不改 `portal/build.py`、`templates/base.html`、`static/style.css` 和任何测试**。

## 规则

- 不得修改、删除或弱化 `tests/` 下已有测试；可以新增测试。
- 验收命令两侧（沙箱、本机）各跑一次，两次都过才进入复核。
- 内容忠于 `docs/source/`，术语与原文一致（例如「双跑验收」「自动修复」「本机 worktree」「终态」）。
