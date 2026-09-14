# vibe-dispatch

多任务分派的 vibe coding 开发平台。

本机是 dev lead：把任务派发到一个个隔离沙箱，每个沙箱起一套完整的 vibe coding 运行时（Claude Code + copilot-api 网关），独立完成任务并推回 GitHub；本机负责复跑验收、复核，然后合并或打回。默认由沙箱开任务分支；指定 `--local-repo` 时，先在本机为任务创建 Git worktree，通过 GitHub 把该分支交给沙箱，再回收到对应 worktree。沙箱之间互不可见，本机不跑 agent；真实服务当前最多同时推进两个任务。

只想知道怎么用：看 [操作手册](docs/operations-manual.md)（在自己的 git 项目上开 worktree、派发、复核、合并、排错，附端到端例子）。

## 工作流

```
queued ──dispatch──▶ running ──collect──▶ self-tested
                        │                     │
                        │              verify_locally
                        ▼                     ▼
                     failed ◀────────── awaiting-review ──merge──▶ merged
                                               │
                                            reject
                                               ▼
                                            rejected

任何尚未结束的状态 ──cancel──▶ cancelled
failed / rejected ──retry──▶ queued（沿用原 id）
```

派发之后的四步（起沙箱 → 跑 agent → 沙箱内自测并推分支 → 本机复跑）由服务端后台线程推进，一次几分钟。任务是否算完成由验收命令的退出码决定，agent 自己说完成不作数，因此 `submit` 时 `-a` 是必填的。

agent 按 TDD 工作：prompt 要求它先把任务写成会失败的测试、看到它红，再写实现让它绿，最后跑完整验收；并且明确禁止删除或弱化已有测试来让验收通过。

**失败不是终点，而是下一轮的输入。** 验收没过不会直接停下等人，而是把失败原因交回 agent 让它继续修：

- 沙箱内自测没过 → 沙箱不销毁，测试输出（不只是退出码）作为「上一轮反馈」拼进 prompt，agent 在同一棵工作树上接着修，最多 `VIBE_FIX_ROUNDS`（默认 3）轮。这是最便宜的修法：不用重开沙箱、不用重装依赖。
- 修复轮用完、沙箱已经没了（本机复跑失败）、或 agent 出手之后的基础设施失败（agent 崩、提交/推送失败）→ 带着累计的反馈整条链重跑，最多 `VIBE_MAX_ATTEMPTS`（默认 5）次。修复轮用完再来的那一次，反馈里明确要求换思路：同一条路已经走了好几遍。本机模式下起点会挪到 agent 的提交，改动不丢。
- 派发失败（clone / setup）不在回路里：agent 还没出手，那不是它能修的。

**换了沙箱不等于失忆。** 每次失败都记一条完整记录（阶段、错误、测试输出、agent 日志尾部、当时相对基线的 diff），随任务记录落盘；新沙箱起来时整份渲染成 `/home/vscode/vibe-history.md` 放进去，prompt 要求 agent 开工前先读，并且「同一种做法失败过不止一次就换一种思路」。没有这一步，新沙箱里的 agent 只知道「上次没过」，不知道上次试的是哪条路——所谓重试就退化成从头再撞一次。

两个预算都用完才是 `failed`。`vibe show` 里能看到「第几次尝试、沙箱内已修几轮」、逐条失败记录和交给 agent 的反馈全文；Paperclip 的 issue 时间线上每次自动修复也各有一条评论。

三个不成功的终点分得很清楚，因为它们的后续处理完全不同：

- `failed` 是**机器判定**不通过——测试挂了、分支推送失败、本机复跑没过——而且自动修复预算已经用完。它不算终态，人工 `retry` 能从它出去，并给一份新的自动预算。
- `rejected` 是**人判定**不合格——dev lead 看过产出，认为改法不对。测试全绿也可能被打回，通常要改任务描述再派一次，所以 `reject` 的理由是必填的。
- `cancelled` 是**用户主动叫停**，任务根本没跑完。失败是结果，取消是决定：混在一起，日后看板上就分不清「跑挂了多少」和「自己撤了多少」。

`merged`、`rejected`、`cancelled` 是终态，之后任何状态转换都被丢弃。这不是洁癖：叫停时后台线程可能还卡在某个阶段里，它随后那条「迟到的更新」若能改写终态，用户看到的结果就不是自己做的那个决定了。

## 本机 worktree 模式

同一个本机仓库可以给多个任务创建独立 worktree，并派发到各自的 sandbox：

```bash
vibe serve
# 另一个终端；--base 是本机存在的基线分支
vibe submit "为任务列表增加分页" -r owner/repo -b feat/pagination --base main \
    --local-repo /absolute/path/to/repo --setup "uv sync --extra dev" -a "uv run pytest -q"
vibe submit "补充 CLI 回归测试" -r owner/repo -b test/cli --base main \
    --local-repo /absolute/path/to/repo --setup "uv sync --extra dev" -a "uv run pytest -q"
```

- `submit --no-start` 只登记，不创建 worktree、不发布分支、不启动沙箱；`vibe run` 才开始派发。
- 每任务创建 `<repo>/.vibe/worktrees/<task-id>` 和独立分支。建议把 `.vibe/` 加入目标仓库的 `.gitignore`，避免把运行状态误提交。路径属于**服务主机**，CLI 会把相对路径正规化为绝对路径。
- 输入是指定**本机基线分支的已提交版本**，可以包含尚未推送的提交；原目录未提交、未跟踪的文件不会被打包或修改。任务分支会发布到 GitHub，因此基线中的提交也会被上传。
- `origin` 必须指向 `-r` 声明的 GitHub repo，不能另设 pushurl。本机 Git 和沙箱都需要相应仓库权限。任务分支必须是新的：已有同名本机/远端分支或目标目录会被拒绝，不自动接管。
- 沙箱独立 clone GitHub，检出本机发布的任务分支并核对 `source_sha`；没有共享目录、没有共享 `.git`，也不使用 bundle。
- 沙箱自测通过并推回后，本机 fetch 产物，在对应 worktree 中快进到精确 `commit_sha`；随后在独立临时 clone 中复跑相同验收。工作区被修改、切换分支、增加提交或远端 HEAD 与记录不符时拒绝覆盖。
- `vibe show <id>` 显示 worktree 路径、SHA 和 PR 链接，`show -d` 查看固定 SHA 的本机 diff。复核后 `vibe merge` **在 GitHub 上为任务分支开 PR 并合并进基线**，随后把本机基线从 origin 快进过来；本机基线不干净或有 origin 没有的提交时不动它，任务仍记为 `merged` 并留下原因。GitHub 判定冲突时保留待复核状态、PR 保持打开，基线不变。
- 失败、取消、打回和合并后均保留 worktree 与任务分支，供你检查和自行清理。本机模式 `retry` 复用受校验的工作区与分支，不删除远端分支、不清空已有改动；本机/远端偏离记录时须先人工处理。

不指定 `--local-repo` 的任务保持原有 GitHub 模式：沙箱从远端基线开分支，本机临时浅克隆验收，diff 走 GitHub API，merge 同样是开 PR 并合并。

## 双跑验收

沙箱内自测通过只证明「在那个环境里能过」。平台记录这次产物的 `commit_sha` 和基线的 `base_sha`；本机会**重新克隆并检出同一个提交**到临时目录（GitHub 模式浅克隆远端，本机 worktree 模式独立克隆已回收的本机仓库），**复跑同一条验收命令**，两跑都过才进入待复核，跑完目录即删。两侧都用 Bash，并启用 `pipefail`，避免管道中间失败被最后一个命令掩盖。

复核 diff 使用记录中的两端 SHA，合并也使用已经验收的 `commit_sha`，不跟随分支后来新增的提交。旧任务若没有记录 SHA，不能直接合并，需要打回后重新执行。注意：这保证产物身份一致，但不等于验证过产物与最新主干组合后的全部行为。

重新取一份而不是复用本地副本，是因为双跑的意义在于换一个环境验证——换个目录不算换环境。GitHub 模式下，本机不保留目标仓库的持久副本，合并、取 diff、删远端分支全部走 GitHub API；本机 worktree 模式则保留用户仓库和任务 worktree，在本机完成复核，合并仍在 GitHub 上以 PR 完成，之后本机基线快进跟上。两种模式的验收临时 clone 都会删除。

这一步专门用来抓环境特异性的假绿——沙箱里恰好装了某个依赖、留着上一步的构建产物、环境变量与本机不同，都会让测试在沙箱里绿、换台机器就红。只有沙箱一跑的话，这类问题要等合并进主干才暴露。

沙箱通过而本机失败的任务直接转 `failed`，错误信息里标明「疑似环境特异性假绿」。两跑的完整输出都存在任务记录里，`vibe show` 会上下并列显示。

## 看板与审批：接入 Paperclip

CLI 之外，可以把 [Paperclip](https://github.com/paperclipai/paperclip) 当作看板和审批面：把 issue 指派给一个 `vibe_dispatch` 类型的 agent，插件就会提交任务、把进展写回 issue 评论和运行日志；双跑通过后在审批箱发起「合并 paperclip/xxx」，Approve 即在 GitHub 开 PR 并合并（PR 链接回帖到 issue）、Reject 即打回。代码仍只走 GitHub，Paperclip 只看状态、日志和 diff 文本。插件在 `integrations/paperclip-adapter/`，安装与配置见其 README。

## 安装

```bash
pip install -e ".[dev]"
```

需要 Python 3.10+。真实派发还需要能访问 Azure Container Apps sandbox 的凭据，以及存在 ACA secret 里的 GitHub token；换成 `--backend local-docker` 则改用自有硬件上的 Docker daemon，见下文「沙箱后端」。只想试 CLI 的话用 `--demo`，它走假 provider 和预置数据，不碰任何云资源，也不产生费用。

### 编码模型与运行时前置条件

默认编码模型为 **`gpt-6-astra`**，与更新后的 `cc-git-copilot` 路由一致。Claude Code 仍是沙箱内的编码客户端，通过 copilot-api 调用 GPT‑6，不直接调用 Anthropic API。编码前会查询网关模型目录；目标模型不存在时明确失败，不静默换模型。

真实服务需要 copilot-api 源码包，默认路径 `/tmp/copilot-api-src.tgz`，可用 `VIBE_COPILOT_TARBALL` 指定持久路径。缺少源码包时启动失败，不再静默省略网关装配。

## CLI

```bash
vibe serve --demo                                                          # 启动常驻服务（demo 模式，假 provider + 预置任务）
vibe submit "为任务列表接口增加分页" -r alezhao/vibe-dispatch -b feat/pagination -a "pytest -q" \
            --setup "uv sync --extra dev"                                  # 派发任务
vibe ls -w                                                                 # 列出任务，-w 持续刷新，-s 按状态筛选
vibe show 1dac -d                                                          # 查看详情与双跑结果（支持 ID 前缀），-d 附上完整改动
vibe merge 1dac                                                            # 复核通过，合并到基线分支
vibe reject 1dac -m "没有覆盖空列表的情况"                                    # 打回，理由必填
vibe cancel 1dac -m "描述写错了"                                             # 叫停并释放沙箱，理由可选
vibe run 1dac                                                              # 启动一个排队中的任务（配合 --no-start）
vibe retry 1dac                                                            # 重跑失败或被打回的任务，沿用原 id
```

CLI 是常驻服务的 HTTP 客户端，不直接操作 Orchestrator：任务要跑几分钟，而 CLI 是短命进程，状态和后台执行必须留在服务端。所以先 `vibe serve`，其余命令在另一个终端敲。

几个不那么显然的选项：

- `submit --setup` 是验收前的准备命令。沙箱里只有裸 `python3`，没有 pip、没有 pytest，跑测试类验收不指定它，验收命令会以 `command not found` 告终——而那个非零退出码看上去和「测试没过」一模一样。它在**沙箱和本机两侧都会执行**：只在沙箱装依赖的话，双跑比较的就不是同一件事，本机那一跑必然红，差异全是假的。

  装依赖用 `uv sync`（建项目自己的 .venv）而不是 `uv pip install --system`：后者要往 `/usr/local/lib/python3.*/dist-packages` 写，而沙箱里的命令一律以非特权的 `vscode` 身份运行，实测报 `Permission denied (os error 13)`。验收命令相应地用 `uv run python -m pytest ...`，让它落在同一个 .venv 里。
- `submit --no-start` 只登记不派发，任务停在 `queued`，之后用 `vibe run <id>` 启动。默认行为是登记完立刻派发，因为「派发任务」在使用者眼里就是一个动作；但派发会立刻起沙箱并开始按运行时长计费，命令敲错了就只能再 `cancel` 一次。不确定的时候先 `--no-start`。
- `retry` 把失败或被打回的任务放回队列，**沿用原 id 和原任务描述**，上一次的输出与提交 SHA 会被清掉——但会先变成给 agent 的反馈：`-m` 的说明、上次的失败原因、失败的测试输出，agent 下一轮都看得到，而不是把同样的事再做一遍。人工 retry 重置自动修复预算。重跑前先释放遗留沙箱；GitHub 模式再清理旧远端分支，清理失败就不重跑，分支查询超时也不会被当成「不存在」。本机 worktree 模式则校验并复用原工作区和远端分支，不删除产物。当前没有编辑任务描述的接口，需要修改需求时请重新 `submit`。
- `merge` 失败时保留 `awaiting-review` 和验收产物，并记录错误。确认失败原因后可再次 `vibe merge`，无需重新编码。同一任务的合并、取消、打回和重试互斥；合并请求正在进行时不能用取消来假装撤回远端操作。
- `show -d/--diff` 显示分支相对基线引入的完整改动，用三点 diff（`base...head`）——两点是「两个 ref 的内容差」，会把基线上后来的提交也算进来，方向还相反，复核时满屏都是自己没改的东西。不默认显示是因为 diff 动辄几百行，会把双跑输出顶出屏幕。复核的核心其实是看改法对不对：测试变绿只说明「跑通了」，说明不了「改得对」。
- `cancel` 的理由可选，`reject` 的必填。取消常常就是「手滑了」，强制填写只会得到一堆无意义的占位文字；打回是对产出的判断，不写理由对后续毫无帮助。取消不限定来源状态——它的价值恰恰在任务正跑着的时候，沙箱当场释放，不再计费。
- `serve --backend` 选沙箱后端，默认 `azure-aca-sandbox`，另一个是 `local-docker`。

## 沙箱后端

`azure-aca-sandbox` 之外还有 `local-docker`，用自有硬件上的 Docker daemon 供应沙箱：

```bash
export VIBE_TAILNET_HOST=100.102.220.47      # 节点的 tailnet IP
vibe serve --backend local-docker
```

「local」指的是 daemon 跑在自己的机器上，**不代表连接方式是本地的**——driver 连的始终是 `tcp://<tailnet-ip>:2375`，即使 daemon 就在同一台机器上也如此。回环地址在构造时就被拒绝，这是刻意的：走 `127.0.0.1` 等于远程寻址那条代码路径从没被执行过，将来把 DGX Spark 作为 tailnet 第二个节点接进来，才发现它一直没被验证。绕远路是为了让这条路径现在就在真实网络上跑。换节点时只需改 `VIBE_TAILNET_HOST`，代码一行不动。

寻址逻辑只存在于 driver 内部，`SandboxHandle` 里不含任何地址信息——一旦 IP 泄进 handle，上层就会开始依赖它，driver 也就不再是唯一知道 tailnet 存在的地方了。

daemon 需要监听在 tailnet 地址上。正式节点应当直接配 dockerd 的原生 TCP 监听并启用 TLS 双向认证：

```bash
dockerd -H unix:///var/run/docker.sock -H tcp://<tailnet-ip>:2375 \
        --tlsverify --tlscacert=... --tlscert=... --tlskey=...
```

开发机上改 dockerd 的 systemd 单元需要 root，没有的话用 `tools/tailnet_docker_gateway.py` 顶上：它把 tailnet TCP 端口转发到 unix socket，网络形状与真实远程节点一致，且不需要提权。**它不是生产部署方式**——Docker API 等价于该主机的 root 权限，网关不带认证，只有在 tailnet 里仅自己一个节点时才勉强可接受；接入第二个节点之前必须换成上面那套带 TLS 的配置。

沙箱镜像由 `docker/sandbox.Dockerfile` 构建，内容对标 ACA 的内置 `claude` 镜像（Claude Code、Node、Bun、git/gh、python3，以及一个 uid 1000 的 `vscode` 用户），另外预构建了 copilot-api 网关：

```bash
VIBE_TAILNET_HOST=100.102.220.47 scripts/build_sandbox_image.sh
```

单独一个脚本而不是直接 `docker build`，是因为 Dockerfile 要 COPY copilot-api 的源码包，而那个包由本机打出、不在仓库里（沙箱没有私有仓库访问权限，源码只能推进去）。脚本把它放进构建上下文，构建完再清掉。镜像必须建在**跑容器的那个 daemon** 上，否则运行时找不到它。

预构建网关不是可有可无的优化：不预构建的话每开一个沙箱都要重跑 `bun install`，实测拉 232MB、耗时 44 秒（预构建后整个 provision 是 1.4 秒）。更要紧的是两个沙箱同时装等于同时拉 464MB，把出口带宽占满，GitHub 连接随之超时——一次三任务并发全军覆没就是这么来的。

跳过重建的判据是**源码摘要相符**，不是「构建产物在不在」：镜像里那份可能是旧版本，直接复用会让沙箱跑着与本机不一致的网关，而且毫无征兆。对不上就照旧完整部署，因此改了 copilot-api 忘了重建镜像只会慢一点，不会跑错版本。完整部署结束后也会写下摘要，于是把一个装配好的沙箱 commit 成镜像之后（ACA 那套 2.7 秒的 commit 工作流），下次同样能跳过。

镜像里不放任何凭据，一律运行时逐沙箱注入——镜像可被任何有权创建容器的人复用，烘进去就等于泄露。

## 模块

| 文件 | 职责 |
| --- | --- |
| `cli.py` | 终端界面，服务的 HTTP 客户端 |
| `server.py` | 装配各层组件；demo 替身与预置数据 |
| `api.py` | Orchestrator 的 HTTP 接口 |
| `executor.py` | 线程池，后台把任务从 queued 推到 awaiting-review |
| `orchestrator.py` | 状态机与流程编排，本机侧的 dev lead 控制面 |
| `task.py` | 任务模型；构造即校验 |
| `provider/__init__.py` | 沙箱后端的接口契约，把厂商 SDK 关在 driver 内 |
| `provider/aca.py` | Azure Container Apps 沙箱的生命周期管理 |
| `provider/local_docker.py` | 第二个后端：经 tailnet 连 Docker daemon 供应沙箱 |
| `runtime.py` | 在沙箱内装配 Claude Code + copilot-api |
| `agent.py` | 在沙箱内驱动编码 agent 并提交改动 |
| `shell.py` | 把沙箱内的命令降权到 vscode 用户执行 |
| `github_ops.py` | 本机侧：浅克隆复跑，以及走 GitHub API 的开 PR + 合并 / diff / 删分支 |
| `store.py` | 任务记录落盘，服务重启后接着看 |
| `credentials/__init__.py` | 凭据抽象，接口从一开始就是逐 sandbox 的 |
| `credentials/aca_secret.py` | 从 ACA sandbox group 的 secret store 取凭据 |

`shell.py` 单独成一层是因为沙箱里 `exec` 进去默认就是 root，而 Claude Code 拒绝在 root 下跳过权限确认（`--dangerously-skip-permissions` 会直接报错）。仓库操作、agent、验收命令因此一律降权到镜像自带的 `vscode` 用户（uid 1000）。命令经脚本文件传递而非拼进 `sudo -u user bash -c "..."`：后者要套多层引号，任务描述和路径里的特殊字符会直接把命令打散。

### ACA 侧的运行时镜像

ACA 没有 Dockerfile 这种构建手段，装配好的运行时只能靠 sandbox commit 固化：

```bash
python scripts/aca_image.py build --project .  # 固化运行时和本项目锁定依赖缓存，输出镜像 id
python scripts/aca_image.py list            # 列出自建镜像，标出当前启用的那个
python scripts/aca_image.py delete <id>     # 删除；拒绝删掉正在用的那个

export VIBE_ACA_IMAGE=<输出的镜像 id>
export VIBE_ACA_DISK_SIZE=40Gi              # 不小于镜像本身的尺寸
```

固化出来的镜像与 ACA 的公共镜像（`claude`、`copilot`、`python-3.12`、`node-24` 等）是平级的，只是私有——区别仅在创建沙箱时怎么引用：公共镜像用名字，私有镜像用 UUID。它托管在 sandbox group 里，不占本机空间。

镜像不会自己消失，每 build 一次多一个，所以有 `list` / `delete`——否则用几周之后没人说得清哪个在用、哪些能删。

固化后每个沙箱的装配从 9.6 秒降到 0.8 秒。收益比 local-docker 那边小得多（那边是 94 秒降到 1.5 秒），因为 ACA 沙箱在 Azure 数据中心里，出口带宽远高于开发机——同一个 `bun install`，本机 44 秒，ACA 6.5 秒。

两处纪律：

**镜像里绝不放凭据。** 装配走 `VibeRuntime.install()` 而不是 `provision()`，前者根本没有写凭据文件的代码路径——做成两个入口而不是一个布尔参数，是因为传错一个布尔值的后果是泄露凭据，而调错一个方法名会立刻报错。脚本在 commit 前还会再审计一遍，按内容而非路径判别（依赖包的文档里满是 `ghp_xxxxxxxxxxxxxxxxxxxx` 这类占位符，只看文件名分不出真假），报告时只打掩码。

**disk_size 必须给足。** commit 产出的镜像继承源沙箱的磁盘尺寸，创建时给小了会报 `InvalidRequest`（实测镜像最小 40960 MiB，给 32Gi 被拒）。内置的 `claude` 镜像不需要这个字段。

## 任务记录

任务记录写在 `<工作目录>/.vibe/tasks.json`（权限 600），每次状态变更都落盘。不是只在退出时写：服务多半是被 kill 掉或崩掉的，而那正是最需要历史的时候。

创建沙箱取得 id 后立即落盘，不必等运行时装配结束。重启时停在 `running` / `self-tested`，或处于 `queued` 但已关联沙箱的任务，会被标记为 `failed`。错误信息带上遗留沙箱 id，重试前会先清理；未关联沙箱的 `queued` 任务仍可用 `vibe run` 启动。

创建尚未返回时取消，迟到的沙箱会被释放；读取日志失败也不能阻止销毁。销毁失败保留 id 和错误信息，不能声称已经清理。任务快照写入在单个服务进程内串行化，避免并发旧快照覆盖新记录；不支持多个服务进程同时写同一份 `tasks.json`。

读取端一律容错、写入失败只记日志：历史是参考资料，任务本身才是正事，不该因为磁盘满了就把一个跑成功的任务判成失败，也不该因为文件损坏就让服务起不来。记录跟着工作目录走，一台机器上给不同仓库开服务时各自的历史不会混在一起。

## 测试

```bash
pytest -q                      # 单元测试，全部用替身，不碰云资源
pytest -m integration          # 集成测试，需要真实 Azure 资源，较慢且产生费用

# local-docker 的契约测试默认跳过，需要 tailnet 上真实可达的 daemon
VIBE_RUN_DOCKER_INTEGRATION=1 VIBE_TAILNET_HOST=100.102.220.47 pytest -q tests/test_local_docker_provider.py
```

`local-docker` 的测试分两层：寻址规则（禁止回环、换节点不改代码）不需要 Docker，跟着单元测试一起跑——那是最容易日后被「顺手改成 localhost 更方便」破坏的一条，必须有测试钉死；接口契约那部分要连真实 daemon，用与 ACA driver 同一套断言，验证两个后端对 Orchestrator 表现一致，因此默认跳过，靠 `VIBE_RUN_DOCKER_INTEGRATION=1` 显式启用。
