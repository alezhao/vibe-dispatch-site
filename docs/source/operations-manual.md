# vibe-dispatch 操作手册

面向日常使用：怎么在自己的 git 项目上开 worktree、把任务派到沙箱、复核、合并、出问题怎么办。
命令参数以 `vibe <子命令> --help` 为准；设计理由见 `README.md` 与 `docs/architecture.md`，这里不重复。

---

## 0. 心智模型（30 秒）

```
你的本机仓库 ──worktree──▶ 任务分支 ──push──▶ GitHub ──clone──▶ 沙箱：agent 编码 + 跑验收
      ▲                                                                  │
      └── fetch 回收 ◀── 本机独立 clone 再跑一遍验收 ◀── push 产物 ◀────────┘
      │
      └── 你看 diff → vibe merge：在 GitHub 上开 PR 并合并进基线 → 本机基线自动快进跟上
```

- 一个任务 = 一个描述 + 一个仓库 + 一个新分支 + 一条**能机器判定的验收命令**。
- 沙箱里过一次、本机再过一次，两跑都绿才让你复核；合并永远是人按的。
- 服务是常驻进程（`vibe serve`），CLI 只是它的 HTTP 客户端，先起服务再敲别的。

---

## 1. 一次性准备

### 1.1 服务主机

```bash
cd ~/wsl/cc-projects/e2b
source .venv/bin/activate            # 或 pip install -e ".[dev]"

# 真实 ACA 模式需要：
export VIBE_COPILOT_TARBALL=/path/to/copilot-api-src.tgz   # 网关源码包，缺了服务拒绝启动
export VIBE_ACA_IMAGE=0197d2d4-ccf5-4e84-a3cf-622db9061619 # 已预热本项目依赖的私有镜像（可选，快很多）
export VIBE_FIX_ROUNDS=3      # 沙箱内验收没过时交回 agent 修的轮数（可选，默认 3）
export VIBE_MAX_ATTEMPTS=5    # 修复轮用完或沙箱之外失败时带反馈整链重跑的次数（可选，默认 5）
export VIBE_WORKERS=3         # 同时推进的任务数（可选，默认 3）；每个都要占一个沙箱
export VIBE_ACA_DISK_SIZE=40Gi                             # 用私有镜像时不小于镜像尺寸

vibe serve                            # 前台常驻；另开一个终端敲其余命令
# macOS 笔记本：caffeinate -i vibe serve —— 机器一睡，沙箱轮询断、本机复跑停、
# ACA 沙箱因空闲被挂起，醒来后全是「基础设施故障」，连续三次就熔断（2026-09-14 夜）
```

只想练手：`vibe serve --demo`，假沙箱、不花钱、几秒出结果，命令用法完全一样。

### 1.2 目标 git 项目（本机 worktree 模式）

在**你想被改的那个仓库**里做三件事：

```bash
cd /path/to/your/repo
echo '.vibe/' >> .gitignore && git commit -am "ignore vibe runtime"   # worktree 会建在 <repo>/.vibe/worktrees/
git remote get-url origin          # 必须就是你将传给 -r 的 owner/name，且没有另设 pushurl
git status && git log -1 --oneline # 基线分支上想让 agent 看到的改动必须已提交（可以未 push）
```

规则：
- 输入 = 基线分支**已提交**的版本。工作区里未提交、未跟踪的文件不会进沙箱，也不会被动。
- 任务分支必须是新的：本机或远端已有同名分支、或 `.vibe/worktrees/<id>` 已存在都会被拒绝，不自动接管。
- 本机 Git 和沙箱里的 token 都要有这个仓库的 push 权限（任务分支会发布到 GitHub）。

### 1.3 想清楚两条命令

| | 作用 | 典型写法 |
|---|---|---|
| `--setup` | 验收前装依赖，在**沙箱**里跑 | `uv sync --frozen --offline --extra dev --no-install-project` |
| `--local-setup` | 同一件事在**本机复跑**时的命令；不给就沿用 `--setup` | `uv sync --frozen --extra dev --no-install-project` |
| `-a` | 验收命令，退出码 0 即通过，两侧都跑 | `uv run python -m pytest -q`、`npm test`、`go test ./...` |

沙箱里只有裸 `python3`，不写 `--setup` 就跑 pytest，得到的是 `command not found`——退出码和「测试没过」长得一模一样。
不要用 `pip install --system`：命令以非 root 的 `vscode` 用户执行，往系统目录写会 `Permission denied`。

**为什么是两条。** 两个环境本来就不一样：沙箱用预热镜像、有完整缓存，`--offline` 在那里既快又稳；本机复跑却是**每次新建的干净 clone**，只能靠宿主机的 `uv` 缓存，而那份缓存里有没有 lock 里的每一个 wheel 没人保证（2026-09-14 事故：沙箱绿、本机 `Failed to download aiohttp… Network connectivity is disabled`，三个并发任务全部「假绿」后失败）。所以本机那条不带 `--offline`：有缓存用缓存、没有才下载。只给一条 `--setup` 也行，但那就得是两边都能跑的写法（去掉 `--offline`）。

顺带一句：服务进程继承的 `UV_CACHE_DIR` / `PIP_CACHE_DIR` 若指向一个空目录（从沙箱化终端里启动服务就会这样），本机复跑同样全红。这个现在由启动自检拦住，见 1.4。

### 1.4 启动自检与 `vibe doctor`

`vibe serve` 起服务前先做一遍基础设施自检，有 ✗ 就拒绝启动并打印怎么修：git / gh / uv 在不在、缓存目录变量是否指向空目录、`gh auth status`、Azure 凭据能否取到 token。这些几秒钟能查出来的事，2026-09-14 是烧了五个沙箱、两小时之后才从失败日志里反推出来的。确要带病启动（比如只想查历史）：`VIBE_SKIP_DOCTOR=1`。

随时也可以手动跑：

```bash
vibe doctor --repo owner/name          # 宿主检查 + 仓库可达性，几秒
vibe doctor --sandbox                  # 再真起一个沙箱、跑一条命令、销毁，约 1 分钟
vibe doctor --sandbox --long           # 再跑一条 150s 的命令，验证 exec 扛得过数据面掐连接，约 3.5 分钟
```

改了 `provider/aca.py`、换了镜像、或者 Azure 侧有变动之后，跑一次 `--sandbox --long` 再派任务。

---

## 2. 场景 A：单任务端到端（本机 worktree 模式）

以本仓库自己为例，让 agent 给 `format_duration` 补小时级格式。

### 2.1 派发

```bash
vibe submit "vibe_dispatch/cli.py 的 format_duration 目前只支持到分钟：3600 秒应输出 '1h0m'，3661 秒输出 '1h1m'，小于一小时保持现状。补齐单元测试并让全部测试通过。" \
  -r alezhao/vibe-dispatch -b feat/duration-hours --base main \
  --local-repo ~/wsl/cc-projects/e2b \
  --setup "uv sync --frozen --extra dev --no-install-project" \
  -a "uv run --no-sync python -m pytest -q"
```

返回一个任务 id（下文用前缀 `6f64` 代指）。此刻发生了什么：

1. 在 `~/wsl/cc-projects/e2b/.vibe/worktrees/6f64…` 从 `main` 的当前提交建 worktree 和分支 `feat/duration-hours`；
2. 把分支 push 到 GitHub；
3. 起沙箱，沙箱 clone GitHub、检出该分支、核对 `source_sha`，agent 开始干活。

**写描述的要点**：说清「改哪个文件/函数」「期望的输入输出」「验收标准」。agent 会忠实实现你写的东西——上次 E2E 里描述写了 `"1h00m"` 而实现是 `"1h0m"`，agent 照写，测试当然红；那是任务规格错误，不是系统故障。
不确定命令是否写对：先加 `--no-start`，检查无误后 `vibe run 6f64`。派发一开始就计费。

### 2.2 观察

```bash
vibe ls -w                # 持续刷新；状态：queued → running → self-tested → awaiting-review
vibe show 6f64            # 详情：worktree 路径、source_sha / commit_sha / local_head_sha、两跑结论一行（✓ exit 0）
vibe logs 6f64            # 该任务的详细日志全文：阶段计时、agent 每个动作、验收输出、失败全文
vibe logs 6f64 -f         # 跟随，任务停下自动退出；-n 50 只看末尾 50 行
vibe show 6f64 -l         # 网关实际调用的模型（确认是 gpt-6-astra 而非静默换模型）
```

**日志分两层。** `vibe serve` 的终端是服务日志：一行一事件、每行带任务 id 和标题——「`[6f64a1b2] 把时长显示改成小时 · 编码 完成（151s）`」——扫一眼知道每条流水线在哪，不夹任何正文。细节全在任务日志 `.vibe/logs/<id>.log`（`vibe logs`；`vibe show` 和 Paperclip 评论都给出路径）：登记全文、派发各子阶段计时、agent 每个动作、验收命令完整输出、每次失败的完整原因和交给 agent 的反馈、沙箱释放前抓下的网关日志。2026-09-14 之前这些全打在服务日志里，几个任务并发就是几百 KB 交织的文本，谁也读不了。

`running` 的任务在 `ls` 里多一行灰字、`show` 里多一行「最近动作」：agent 此刻在读哪个文件、跑哪条命令、说了什么，带上「多久以前」。这是从 agent 的流式输出实时渲染的，几秒刷一次。一个任务安静了五分钟以上，不用等它超时——`vibe logs -f` 看它卡在哪条命令上。

真实模式一个任务大约 2 分钟：派发 30–50s（预热镜像）、编码 40s 左右、沙箱验收几秒、本机复跑几秒。

### 2.3 复核

```bash
vibe show 6f64 -d         # 三点 diff（base...head），只看这个任务引入的改动
# 或者直接在 worktree 里用你熟悉的工具
cd ~/wsl/cc-projects/e2b/.vibe/worktrees/6f64*/ && git log --oneline main..HEAD && git diff main...HEAD
```

看的是**改法对不对**，不是测试绿不绿——绿只说明跑通了。

### 2.4 合并或打回

```bash
vibe merge 6f64                         # 在 GitHub 为任务分支开 PR 并合并进 main；本机 main 随后快进到合并结果
vibe reject 6f64 -m "没有覆盖 0 秒和负数"   # 打回，理由必填；之后 vibe retry 6f64 沿用原 id 重跑
vibe retry 6f64 -m "别改 api.py，问题在 cli.py"  # 重跑说明随反馈交给 agent；Paperclip 里写 `/retry 说明` 同效
```

合并发生在 GitHub：`vibe merge` 用 `gh` 为任务分支开一个 PR（标题取描述首行，正文含全文、验收命令和已验收提交），随即合并它，PR 链接记在任务上（`vibe show` 可见）。只合并已验收的那个提交——分支在 GitHub 上又多了提交时会被拒绝，没复核过的东西进不了基线。

合并成功后服务把本机 `main` 从 origin 快进过来，你的主目录干净且检出 `main` 时工作区一并更新；主目录有未提交改动、或本机 `main` 有 origin 没有的提交时不动本机，任务仍是 `merged`，`vibe show` 里留一句原因，你自己 `git pull` 即可。

合并失败（GitHub 判定有冲突）时任务留在 `awaiting-review`，PR 保持打开，`vibe show` 里有原因和 PR 链接。因为只合并已验收的提交，解决冲突意味着分支要多一个新提交，它没被双跑过——所以要么 `vibe reject -m 冲突` 后 `vibe retry` 让 agent 在当前基线上重做并重新验收，要么你在 PR 页面自己解决并手工合并（这时任务记录不会自动变 `merged`，可以 `vibe cancel` 收尾）。网络类失败直接再 `vibe merge`，会复用同一个 PR。

### 2.5 清理（都不会自动做）

```bash
cd ~/wsl/cc-projects/e2b
git worktree remove .vibe/worktrees/6f64…      # 或 git worktree prune
git branch -D feat/duration-hours
git push origin --delete feat/duration-hours   # 远端任务分支
```

不自动删是刻意的：失败/打回的 worktree 里常有值得看的半成品。

---

## 3. 场景 B：两个任务并行

同一基线，不同分支，互不干扰：

```bash
vibe submit "…补小时级格式…"       -r alezhao/vibe-dispatch -b feat/duration-hours --base main --local-repo ~/wsl/cc-projects/e2b --setup "uv sync --frozen --extra dev --no-install-project" -a "uv run --no-sync python -m pytest -q"
vibe submit "…Task 契约的边界测试…" -r alezhao/vibe-dispatch -b test/task-contract  --base main --local-repo ~/wsl/cc-projects/e2b --setup "uv sync --frozen --extra dev --no-install-project" -a "uv run --no-sync python -m pytest -q"
vibe ls -w
```

- 两个沙箱同时跑，两个 worktree 各自从同一个 `source_sha` 出发。
- 先 `merge` 哪个都行：各开各的 PR，第二个合并时基线已前进也没关系，只要不冲突。真冲突由 GitHub 判定、保留 `awaiting-review`、不碰基线，处理方式见 2.4。
- 一个任务的 GitHub 操作挂了（网络抖动）不会拖住另一个：远端调用在锁外、带 180s 硬超时。

实测（2026-09-06）：两任务派发 48s/50s、编码 38s/44s，全程约 2 分钟，两个都 merged。

---

## 4. 场景 C：验收没过怎么办

`vibe ls` 看到 `failed`，先分类：

```bash
vibe show 6f64      # 一句原因 + 两跑结论 + 失败记录列表
vibe logs 6f64      # 全文：agent 到底做了什么、测试到底输出了什么
```

看到 `failed` 时先明白一件事：它已经过了自动修复回路。验收没过会先交回 agent 修（`vibe show` 的「自动修复」行显示第几次尝试、沙箱内已修几轮；「失败记录」逐条列出每次失败的阶段与原因；「交给 agent 的反馈」面板是它每一轮拿到的摘要）。每条失败记录的全文（测试输出、agent 日志、当时的 diff）在 API 的 `attempts` 字段里，也是新沙箱开工前 agent 读到的那份历史。`failed` 意味着两个预算都用完了，agent 换着沙箱反复修不好，确实需要人看。

**每条失败记录都带一个分类**，处理方式完全不同：

| 分类 | 含义 | 编排层怎么做 |
|---|---|---|
| `agent` | 验收没过、agent 崩了、假绿——agent 该负责的 | 进 `feedback`、耗 `attempt` 预算、下一轮 agent 能读到 |
| `infra` | 沙箱创建/连接失败、clone / 装依赖失败、推送失败、数据面掐连接——agent 没出手或不是它的错 | **不进反馈、不耗 agent 预算**，用独立的 `infra_retries`（默认 3）原地重排；连续 3 个任务都栽在 infra 上就**熔断** |
| `human` | 人工 `retry -m` / `reject -m` 写的理由 | 进反馈，`attempt` 重新数 |

熔断之后 `vibe ls` 顶部出现红色横幅，`/api/health` 的 `degraded` 有值，排队中的任务不再派发（已在跑的不受影响）。这时候不要 `retry`：先 `vibe doctor --sandbox` 找到坏的那一环修好，再 `vibe resume` 放行。三个任务连续在同一处失败，几乎不可能是三个任务各自的问题。

| 现象 | 原因 | 处理 |
|---|---|---|
| 沙箱验收 `command not found` | 没写 `--setup` 或装依赖失败 | `cancel` 后带 `--setup` 重新 `submit` |
| 沙箱验收断言失败，agent 日志显示按描述实现了 | 描述里的期望值写错 | 没有改描述的接口：`cancel` 后重新 `submit`（换新分支名） |
| `sandbox 内自测失败 …，已修 N 轮；已自动尝试 M 次` | 换了 M 个沙箱、每个里修 N 轮都没过，任务本身可能超出它的能力或描述有歧义 | 看 `vibe show` 的失败记录（每次试的什么、看到什么）；`retry -m` 写清楚线索再给一份预算，或拆小任务重新 `submit` |
| 沙箱绿、本机红，错误标「疑似环境特异性假绿」并「已自动尝试 N 次」 | agent 依赖了沙箱里碰巧有的东西，且几次重跑都没改掉 | 看 diff 找隐式依赖，`retry -m` 把依赖名写进说明，agent 下一轮会看到 |
| 错误尾部有 `invalid peer certificate` / `timeout` | 网络 / 证书 | 与代码无关，直接 `retry` |
| `agent 执行异常: … RemoteDisconnected`，每次都在编码 1.5–3 分钟处死 | ACA 数据面掐断了长连接。2026-09-14 前 `exec` 直接挂在一次 `executeShellCommand` 上，超过 ~90–180s 必死；现已改为后台运行 + 轮询，理论上不再出现 | 若再见到，说明轮询本身连续 4 次都连不上——看 `vibe serve` 日志里「沙箱轮询连接中断」，多半是网络或 Azure 侧故障，`retry` 即可 |
| 本机复跑 `Network connectivity is disabled, but the requested data wasn't found in the cache` | `--setup` 带了 `--offline`，本机干净 clone 靠宿主缓存装依赖却缺 wheel；沙箱有预热镜像所以绿 | 去掉 `--offline` 重新 `submit`（见 1.3）。Paperclip 侧改 agent 的 `setupCommand` / `acceptanceCommand` |
| `merged` 但备注「本机基线未同步」 | 主目录有未提交改动，或本机 `main` 有 origin 没有的提交 | GitHub 上已合并；自己 `git pull` 即可 |
| `merge` 失败：`gh` 认证 / 权限 | 本机 `gh auth status` 未登录，或 token 没有该 repo 的写权限 | `gh auth login` 后再 `vibe merge`，复用同一个 PR |

`retry` 沿用原 id、原描述、原分支和 worktree，清掉上次的产物与 SHA，但把 `-m` 说明、上次失败原因和失败的测试输出打包成反馈交给 agent，并重置自动修复预算；`cancel` 任何状态都可用，沙箱当场释放停止计费。

---

## 5. 场景 D：不带本机仓库（GitHub 模式）

不给 `--local-repo`，一切走 GitHub：沙箱从远端基线开分支，本机临时浅克隆做复跑，`merge` 同样是开 PR 并合并；本机没有仓库副本，合并后自己 `git pull`。

```bash
vibe submit "README 增加安装章节" -r owner/repo -b docs/install -a "test -s README.md"
```

适合你本机没有这个仓库、或者仓库很大不想放本机的情况。代价是没有 worktree 可翻，只能靠 `show -d`。

---

## 6. 场景 E：用 Paperclip 看板派发与审批

不想敲命令、想在看板上管任务时，用 `integrations/paperclip-adapter`（详见其 README）。

```bash
# 终端 1：vibe 服务（真实或 --demo）
vibe serve

# 终端 2：Paperclip
cd vendor/paperclip
export PATH="$HOME/.nvm/versions/node/v24.20.0/bin:$PATH"
export PAPERCLIP_HOME=~/wsl/cc-projects/e2b/.omc/paperclip-home
export PAPERCLIP_AGENT_JWT_SECRET=<随便一串长密钥>   # 没有它 adapter 拿不到回调凭据
pnpm dev                                          # http://127.0.0.1:3100

# 首次：注册插件（之后自动加载）
curl -X POST http://127.0.0.1:3100/api/adapters/install -H 'content-type: application/json' \
  -d '{"packageName":"'"$HOME"'/wsl/cc-projects/e2b/integrations/paperclip-adapter","isLocalPath":true}'
```

UI 里：
1. **Agents → New agent**，adapter 选 `vibe_dispatch`，填 `repo`、`acceptanceCommand`、`setupCommand`、`localRepo`（服务主机上的绝对路径）。
2. **New Task** 建 issue，标题+描述就是任务描述，指派给这个 agent。
3. 几秒后 issue 评论出现「已提交 vibe-dispatch 任务 …」；agent 的 **Runs** 页有中文进度。
4. 双跑通过：issue 变 **In Review**，评论含两跑输出与 diff，**Inbox/Approvals** 出现「合并 paperclip/<issue标识>」。
5. **Approve** = 在 GitHub 开 PR 并合并，PR 链接回帖到 issue（issue → Done）；**Reject** 并写备注 = 打回。评论 `/retry` 重跑，`/status` 查状态，`/cancel` 停。

分支名固定为 `paperclip/<issue 标识小写>`（如 `paperclip/vib-7`），同一 issue 重试沿用。

---

## 7. 速查

```bash
vibe doctor [--repo owner/name] [--sandbox [--long]]
vibe serve [--demo] [--backend azure-aca-sandbox|local-docker]     # 起服务前自动做宿主自检；VIBE_SKIP_DOCTOR=1 越过
vibe submit "<描述>" -r owner/name -b <新分支> [--base main] [--local-repo /abs/path] [--setup "<沙箱装依赖>"] [--local-setup "<本机装依赖>"] -a "<验收>" [--no-start]
vibe ls [-w] [-s <状态>]
vibe show <id前缀> [-d] [-l]
vibe logs <id前缀> [-n 行数] [-f]                                     # 该任务的详细日志
vibe run | retry | cancel [-m 理由] | merge | reject -m <理由>   <id前缀>
vibe resume                                                         # 熔断后修好基础设施再放行
```

状态流转：`queued → running → self-tested → awaiting-review → merged | rejected`，任一阶段可 `cancelled`，验收不过或出错为 `failed`。

任务记录在服务工作目录 `.vibe/tasks.json`，每任务的详细日志在旁边的 `.vibe/logs/<id>.log`；worktree 在目标仓库 `.vibe/worktrees/<id>`；Paperclip 实例数据在 `$PAPERCLIP_HOME`。都不进 git。
