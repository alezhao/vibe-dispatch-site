# 验收清单（UAT）

每个里程碑一组验收条目。每条写清**用户视角的场景**与**判定标准**，并标明验证方式：

- `auto`：由 `tests/` 里的单元测试自动判定，「测试」列给出 `文件::函数`。`tests/test_uat_traceability.py` 会检查本表与测试一一对应：表里引用的测试必须存在；`tests/` 里的每个测试函数都必须出现在本表里。
- `manual`：dev lead 复核时人工执行，结果记在对应 Paperclip issue 的评论里。

任务只有在其全部 `auto` 条目变绿（沙箱 + 本机各跑一次）、`manual` 条目由人确认后才能合并。

状态图例：✅ 已通过并合并 · 🔴 测试已写、实现未做 · ⬜ 手动条目待复核

## 清单自身（跨里程碑）

| ID | 场景 | 判定标准 | 方式 | 测试 |
|---|---|---|---|---|
| X-1 | dev lead 查验收清单 | 本文对 A–F 每个里程碑都有一节 | auto | `test_uat_traceability.py::test_uat_document_exists_with_every_milestone` |
| X-2 | dev lead 查某条目怎么验 | 表中引用的每个 `文件::函数` 都真实存在 | auto | `test_uat_traceability.py::test_every_uat_reference_points_at_a_real_test` |
| X-3 | dev lead 查某个测试为何存在 | `tests/` 里每个测试函数都被至少一条 UAT 引用 | auto | `test_uat_traceability.py::test_every_test_is_covered_by_a_uat_item` |
| X-4 | 引用 UAT 编号 | 编号全局唯一 | auto | `test_uat_traceability.py::test_uat_ids_are_unique` |

---

## 里程碑 A：构建管线 + 基础布局（VIB-7 ✅）

| ID | 场景 | 判定标准 | 方式 | 测试 |
|---|---|---|---|---|
| A-1 | 维护者运行构建 | 产物含 `index.html` `quickstart.html` `cli.html` `workflow.html` 与非空 `static/style.css` | auto | `test_build.py::test_build_generates_every_page_and_stylesheet` |
| A-2 | 维护者反复构建 | 输出目录被清空重建，上次残留文件消失；两次产物逐字节一致 | auto | `test_build.py::test_rebuild_is_clean_and_idempotent` |
| A-3 | 维护者在命令行构建 | `python -m portal.build --out DIR` 退出码 0 并生成 `index.html` | auto | `test_build.py::test_module_cli_builds_into_given_dir` |
| A-4 | 访客打开任一页 | `<!doctype html>`、`lang="zh-CN"`、`charset=utf-8`、viewport、`<title>` 含 vibe-dispatch、引用 `static/style.css` | auto | `test_build.py::test_page_skeleton` |
| A-5 | 访客在任一页找导航 | 每页有 `<nav>` 链到全部四页，当前页用 `aria-current="page"` 标出且只标一个 | auto | `test_build.py::test_shared_nav_links_every_page` |
| A-6 | 访客想看源码 | 每页页脚有指向 `https://github.com/alezhao/vibe-dispatch` 的链接 | auto | `test_build.py::test_footer_links_to_project_repo` |
| A-7 | 访客点击站内任何链接 | 所有相对链接 / 样式 / 图片 / 脚本引用都能在产物中找到对应文件，不出现 404 | auto | `test_build.py::test_internal_links_resolve_to_built_files` |
| A-8 | 页面作者要写页面私有样式 | `templates/base.html` 提供 `{% block head %}` 与 `{% block content %}` | auto | `test_build.py::test_base_template_exposes_head_block` |
| A-9 | 维护者从任意目录构建 | `static/` 整树（含嵌套目录、空目录、二进制）复制到产物；源里删掉的文件重建后也消失 | auto | `test_build_assets.py::test_build_copies_static_tree_from_any_working_directory` |
| A-10 | 访客打开任一页 | 有 `<h1>`：首页恰为 `vibe-dispatch`，其余页含「快速开始」「CLI 参考」「工作流」 | auto | `test_build_assets.py::test_page_has_placeholder_heading` |

## 里程碑 B：首页（VIB-8 ✅）

| ID | 场景 | 判定标准 | 方式 | 测试 |
|---|---|---|---|---|
| B-1 | 访客首次进站 | 唯一的 `<h1>` 为 `vibe-dispatch`，`.tagline` 为「多任务分派的 vibe coding 开发平台」 | auto | `test_home.py::test_hero_title_and_tagline` |
| B-2 | 访客想知道它能做什么 | ≥3 张 `.feature` 卡片，各有标题与说明文字，整体覆盖「双跑验收」「自动修复」「worktree」 | auto | `test_home.py::test_feature_cards_cover_core_selling_points` |
| B-3 | 访客想了解任务状态 | `#states` 区块用 `<code>` 列出全部 8 个状态 | auto | `test_home.py::test_state_overview_lists_every_state` |
| B-4 | 访客想上手 | `a.cta` 指向 `quickstart.html`；正文有 GitHub 仓库链接 | auto | `test_home.py::test_calls_to_action` |

## 里程碑 C：快速开始 + CLI 参考（VIB-9 ✅）

| ID | 场景 | 判定标准 | 方式 | 测试 |
|---|---|---|---|---|
| C-1 | 访客打开快速开始 | `<h1>` 含「快速开始」 | auto | `test_quickstart.py::test_heading` |
| C-2 | 访客按步骤操作 | `ol.steps` ≥4 步，每步带一个 `<pre>` 命令块 | auto | `test_quickstart.py::test_steps_are_an_ordered_list` |
| C-3 | 访客复制命令 | 命令块里出现 `pip install -e ".[dev]"`、`vibe serve --demo`、带 `-a` 的 `vibe submit`、`vibe ls`、`vibe show`、`vibe merge` | auto | `test_quickstart.py::test_commands_appear_in_pre_code_blocks` |
| C-4 | 访客不理解为何要 `--setup` | 页面解释：沙箱里没有 pip/pytest，`command not found` 的退出码和测试失败一样 | auto | `test_quickstart.py::test_setup_flag_is_explained` |
| C-5 | 访客打开 CLI 参考 | `<h1>` 含「CLI」 | auto | `test_cli_page.py::test_heading` |
| C-6 | 访客查某个子命令 | `table.commands` 覆盖 doctor / serve / submit / ls / show / logs / run / retry / cancel / merge / reject / resume，每条说明 ≥6 字 | auto | `test_cli_page.py::test_every_subcommand_documented` |
| C-7 | 访客区分 reject 与 cancel | reject 说明含「必填」，cancel 说明含「可选」 | auto | `test_cli_page.py::test_reject_requires_reason_but_cancel_does_not` |
| C-8 | 访客查 submit 参数 | submit 说明提到 `-a` 与 `--setup` | auto | `test_cli_page.py::test_submit_mentions_acceptance_and_setup` |

## 里程碑 D：工作流页（VIB-10 ✅）

| ID | 场景 | 判定标准 | 方式 | 测试 |
|---|---|---|---|---|
| D-1 | 访客打开工作流 | `<h1>` 含「工作流」 | auto | `test_workflow.py::test_heading` |
| D-2 | 访客看状态机 | `#state-machine` 用 `<code>` 列出全部 8 个状态与 7 个转换 | auto | `test_workflow.py::test_state_machine_names_every_state_and_transition` |
| D-3 | 访客区分三种非成功结局 | `#ending-failed`（机器判定）/ `#ending-rejected`（人判定）/ `#ending-cancelled`（用户叫停）各 ≥30 字；页面提到「终态」 | auto | `test_workflow.py::test_three_unsuccessful_endings_are_distinguished` |
| D-4 | 访客想调预算 | `#auto-fix` 用 `<code>` 给出 `VIBE_FIX_ROUNDS`（默认 3）与 `VIBE_MAX_ATTEMPTS`（默认 5） | auto | `test_workflow.py::test_auto_fix_loop_documents_both_budgets` |
| D-5 | 访客想知道为何要双跑 | `#double-run` 提到沙箱与本机，`commit_sha` 用 `<code>` | auto | `test_workflow.py::test_double_run_acceptance_explained` |

## 里程碑 E：GitHub Pages 部署（VIB-11 ✅）

| ID | 场景 | 判定标准 | 方式 | 测试 |
|---|---|---|---|---|
| E-1 | 维护者推送 main | 工作流在 push main 时触发，并允许手动 `workflow_dispatch` | auto | `test_pages_workflow.py::test_triggers_on_push_to_main` |
| E-2 | 安全审阅 | permissions 仅 `contents: read`、`pages: write`、`id-token: write` | auto | `test_pages_workflow.py::test_permissions_for_pages_deploy` |
| E-3 | 维护者读工作流 | 构建用 `uv sync` 与 `python -m portal.build --out dist` | auto | `test_pages_workflow.py::test_build_steps_use_uv_and_portal_build` |
| E-4 | 维护者读工作流 | 使用官方 `actions/checkout`、`upload-pages-artifact`、`deploy-pages` | auto | `test_pages_workflow.py::test_uses_official_pages_actions` |
| E-5 | 维护者读工作流 | 上传的目录是 `dist` | auto | `test_pages_workflow.py::test_upload_points_at_dist` |
| E-6 | 维护者读工作流 | 部署 job 的 environment 为 `github-pages` | auto | `test_pages_workflow.py::test_deploy_job_has_pages_environment` |
| E-7 | 访客访问线上地址 | https://alezhao.github.io/vibe-dispatch-site/ 及四页、`static/style.css` 均 200 | manual | 合并后 `gh run list` 成功；curl 五个 URL — 2026-09-14 已确认 ✅ |

## 里程碑 F：视觉设计（开发者工具风 · 深色 · 自托管字体）（VIB-12 🔴）

设计方向：开发者工具风（深色为主、等宽字体点缀、代码块突出），只做深色主题，自托管 Inter（正文）与 JetBrains Mono（代码），零 JS、零外部请求。字体文件与许可证已放在 `static/fonts/`。

| ID | 场景 | 判定标准 | 方式 | 测试 |
|---|---|---|---|---|
| F-1 | 访客打开任一页 | 深色主题：`:root` 声明 `color-scheme: dark`，每页 `<meta name="color-scheme" content="dark">`，背景 token 的相对亮度 < 0.1 | auto | `test_design.py::test_dark_theme_declared` |
| F-2 | 设计师复核色板 | `:root` 定义完整 token：`--color-bg` `--color-surface` `--color-fg` `--color-muted` `--color-accent` `--color-border` `--font-sans` `--font-mono` `--radius`；`:root` 之外不得出现裸色值（`#hex` / `rgb(` / `hsl(`），一律 `var(--…)` | auto | `test_design.py::test_design_tokens_defined`、`test_design.py::test_no_raw_colors_outside_tokens` |
| F-3 | 视力较弱的访客阅读 | 对比度：正文 `--color-fg` vs `--color-bg` ≥ 7:1，`--color-muted` vs `--color-bg` ≥ 4.5:1，`--color-accent` vs `--color-bg` ≥ 4.5:1 | auto | `test_design.py::test_contrast_ratios` |
| F-4 | 访客加载页面 | 字体自托管：`@font-face` 声明 `Inter` 与 `JetBrains Mono`，`src: url()` 指向 `fonts/*.woff2` 且文件存在于产物；`--font-sans` 含 Inter、`--font-mono` 含 JetBrains Mono；`body` 用 `var(--font-sans)`，`code, pre` 用 `var(--font-mono)` | auto | `test_design.py::test_self_hosted_fonts` |
| F-5 | 访客首屏渲染 | 每页 `<link rel="preload" as="font" type="font/woff2" crossorigin>` 预载 Inter 主字体文件 | auto | `test_design.py::test_primary_font_preloaded` |
| F-6 | 隐私 / 离线访问 | 页面无 `<script>`；HTML 与 CSS 里所有 `url()` / `href` / `src` 资源都是站内相对路径（GitHub 仓库链接等 `<a>` 除外） | auto | `test_design.py::test_no_scripts_and_no_external_assets` |
| F-7 | 访客读命令 | `pre` 有独立的 surface 背景、边框、圆角，`overflow-x: auto`；行内 `code` 有背景色，与正文区分 | auto | `test_design.py::test_code_blocks_styled` |
| F-8 | 访客滚动长页面 | 页头 `.site-header` 粘性定位（`position: sticky; top: 0`），当前导航项 `nav a[aria-current="page"]` 有独立样式 | auto | `test_design.py::test_sticky_header_and_current_nav` |
| F-9 | 键盘用户 | 存在 `:focus-visible` 规则并设置 `outline` | auto | `test_design.py::test_focus_visible_outline` |
| F-10 | 访客用手机 | 至少一个 `@media (max-width: …)` 断点；首页 `.features` 为 `display: grid` 并用 `auto-fit` / `minmax` 自适应列数 | auto | `test_design.py::test_responsive_layout_rules` |
| F-11 | 内容不受影响 | A–E 全部 `auto` 条目仍绿（F 只能改 `static/style.css`、`templates/base.html`、`static/fonts/`，各页模板只允许加 class / 结构包裹，不改文字）；每页仍只引用一份 `static/style.css`，不得另开样式表绕过 token 检查 | auto | 全量 `pytest -q`；`test_design.py::test_every_page_links_same_stylesheet_only` |
| F-12 | dev lead 复核观感 | 1280px 与 390px 宽度截图：无横向滚动、导航可点、hero / 卡片 / 代码块层次清晰、字体确实为 Inter / JetBrains Mono（DevTools 检查 rendered fonts） | manual | 复核时截图贴在 VIB-12 评论 ⬜ |
| F-13 | 访客在线访问 | Pages 部署成功后线上样式生效（`static/fonts/*.woff2` 200） | manual | 合并后 curl ⬜ |
