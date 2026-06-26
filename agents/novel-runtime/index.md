Updated: 2026-06-27

# Novel Runtime

`botmux_novel` 是小说创作 Agent Team 的本地 P0 运行时，用标准库 Python 实现从一句灵感到首章定稿、门禁、归档和 run trace 的闭环。

## 职责

- 提供 CLI 入口 `python -m botmux_novel run`。
- 提供开书资产入口 `python -m botmux_novel foundation`，不生成正文。
- 提供真实项目启动包入口 `python -m botmux_novel novel-bootstrap`，串联 foundation、wiki bundle、llmwiki dry-run sync plan、MCP config 和 human approval package。
- 提供章节生产入口 `python -m botmux_novel chapter`，从已有 `foundation.json` 继续生成章节，不重新规划 Story Bible。
- 提供本地 wiki 审核包入口 `python -m botmux_novel wiki-bundle`，不调用 llmwiki。
- 提供 gated llmwiki 本地 workspace 同步入口 `python -m botmux_novel llmwiki-sync`，把已审批 Markdown bundle 写入 llmwiki source-of-truth 文件树，并可选运行 `llmwiki reindex`。
- 提供项目级 MCP 配置生成入口 `python -m botmux_novel llmwiki-mcp-config`，输出 Codex TOML、标准 MCP JSON、角色绑定和 humanGate 策略，不改全局配置。
- 提供连续章节样例入口 `python -m botmux_novel series`，默认生成 5 章并统计 Phase 3 质量指标。
- 提供本地就绪检查入口 `python -m botmux_novel readiness`，检查 BotMux 配置、workflow validate、workflow 模板绑定、workspace 身份、llmwiki 可用性、可选 bootstrap smoke、series smoke 和 approved llmwiki sync smoke。
- 提供 BotMux 资产同步入口 `python -m botmux_novel botmux-assets`，用于同步 workflow 模板和三个小说 bot 的 workspace `AGENTS.md`。
- 配套版本化 BotMux workflow：`workflows/novel-story-foundation.workflow.json` 和 `workflows/novel-chapter-production.workflow.json`，用于三 bot 协作、humanGate 和归档计划。
- 在本地小说项目目录中创建方案文档约定的文件工作区。
- 串行编排 6 个 MVP Agent：总导演、章纲、正文写手、编辑、一致性检查、归档记忆。
- 产出关系图、场景设定、文风档案和伏笔台账，给后续 Story Bible / llmwiki 同步使用。
- 记录每次 run 的 JSON trace 和 SQLite run 表。

## 边界

- 当前运行时使用确定性本地 Agent，不调用真实 LLM，也不连接外部 BotMux 服务。
- 当前覆盖单项目的开书和连续章节 smoke；已用 20 章本地稳定性基线验证归档和 prior context 持续传递。真实模型 provider、Web UI 和向量检索属于后续迭代。
- 输出是本地 Markdown/YAML/JSON/SQLite 文件，不涉及生产发布、云同步或多用户权限。
- `novel-bootstrap` 会写项目内 wiki 审核包、审批包和 dry-run 计划，但不会执行 approved sync、不会覆盖外部 llmwiki workspace，也不会修改 Codex/BotMux 全局配置。
- `wiki-bundle` 写本地 `wiki/novels/{project_slug}/` Markdown 页面包，用于人工审核或后续 gated llmwiki 写入。
- `llmwiki-sync` 只同步本地 Markdown workspace，不安装 llmwiki，不调用 MCP `create/edit/append`，也不绕过 `--approve` 门禁。
- `llmwiki-mcp-config` 只生成配置片段；MCP 工具 ACL 不由片段强制执行，角色边界仍由身份文档和 workflow gate 约束。
- `series` 是本地确定性 smoke 和指标采样，不代表真实模型文学质量，也不能替代人类 Story Bible 审批。
- `readiness` 不写 BotMux 配置；它只读本机状态并返回 `ready`、`ready_with_warnings` 或 `blocked`。
- BotMux workflow 只生成候选包和计划；项目文件或 llmwiki 写入必须走单独 gated 节点或人工确认。
- `botmux-assets` 默认 dry-run；只有传 `--write` 才会写入 `~/.botmux`，覆盖已有 workspace `AGENTS.md` 前会保留 `.bak-<timestamp>` 备份。

## 主流程

### Foundation

1. `NovelRuntime.foundation` 校验 `NovelFoundationRequest` 并创建工作区目录。
2. `DirectorAgent` 生成项目状态、故事圣经、题材、世界观、角色、人物关系、场景设定、文风档案和首章目标。
3. 运行 schema 必填字段校验并写入开书资产。
4. 写入 `runs/{run_id}/foundation.json`、trace 和 SQLite run 表。
5. 不写 `manuscript/draft|revised|final`。

### Novel Bootstrap

1. `NovelBootstrapper` 先运行 `foundation`，生成开书设定和 `foundation.json`。
2. 运行 `wiki-bundle`，导出 `wiki/novels/{project_slug}/` 审核页面。
3. 运行未审批的 `llmwiki-sync`，只生成 sync plan；即使命令中带 planned reindex，也不会执行 reindex 或覆盖外部 workspace。
4. 运行 `llmwiki-mcp-config`，生成项目级 MCP JSON、Codex TOML 和三角色绑定策略。
5. 写入 `runs/{bootstrap_run_id}/approval-package.json` 和 `approval-package.md`，列出 humanGate 必审项、页面清单、批准后写入命令和下一步。

### Chapter Run

1. `NovelRuntime.run` 校验 `NovelRunRequest` 并创建工作区目录；该入口会从标题和灵感重新生成本地 P0 计划。
2. `DirectorAgent` 生成项目状态、故事圣经、题材、世界观、角色、人物关系、场景设定、文风档案和首章目标。
3. `BlueprintAgent` 生成章节蓝图和场景卡。
4. `ContextPackBuilder` 组装章节上下文包。
5. `DraftWriterAgent` 生成草稿。
6. `ConsistencyAgent` 执行 Gate 0-4，发现 P2 文风问题时进入修订。
7. `EditorAgent` 去除模板化表达并保留剧情事实。
8. `ConsistencyAgent` 复核通过后由总导演批准定稿。
9. `ArchiveMemoryAgent` 写入事实、时间线、带 id/status 的伏笔台账、角色状态和冲突记录。
10. `NovelWorkspace.record_run` 写入 SQLite run 表和 artifact 索引。

### Chapter From Foundation

1. `NovelRuntime.chapter` 读取显式 `foundation.json`，或使用项目中最新的 `runs/foundation-*/foundation.json`。
2. 用请求中的 `chapter_number` 和 `chapter_goal` 更新当前章节目标。
3. 读取早于当前章节的 `runs/archive-{chapter}.json`，汇总事实、时间线、伏笔、角色状态和连续性问题为 `prior_context`。
4. 写入当前 Story Bible / characters / settings / outline 资产快照，并在 `runs/{run_id}/source-foundation.json` 记录本次来源。
5. 写入 `runs/{run_id}/prior-context.json`，并把前章归档注入 `context-pack.json` 的 `prior_context`、`facts`、`character_states`、`foreshadowing` 和 `source_refs`。
6. 复用章节状态机完成蓝图、上下文包、草稿、审稿、修订、定稿、归档、trace 和 SQLite run 记录。
7. 不重新调用 `DirectorAgent.plan_project`，避免批准后的 Story Bible 被灵感重规划覆盖。

### Wiki Bundle

1. `NovelRuntime.wiki_bundle` 读取显式 `foundation.json`，或使用项目中最新的 `runs/foundation-*/foundation.json`。
2. 运行 schema 必填字段校验。
3. 写入本地 `wiki/novels/{project_slug}/` Markdown 页面包。
4. 不调用 llmwiki、不创建远端页面、不覆盖外部知识库。

### llmwiki Sync

1. `LlmwikiSyncer` 读取已存在的 `wiki/novels/{project_slug}/` Markdown 审核包。
2. 未传 `--approve` 时只写 `runs/llmwiki-sync-{project_slug}-{timestamp}.json` 计划，不复制页面。
3. 传 `--approve` 后把页面同步到 `--workspace/wiki/novels/{project_slug}/`；默认 workspace 是项目目录。
4. 覆盖已有目标页前保留 `.bak-{timestamp}` 备份，除非传 `--no-backup`。
5. 传 `--reindex` 且本机有 `llmwiki` 时运行 `llmwiki reindex <workspace>`；没有 llmwiki 时同步文件并返回 warning。

### llmwiki MCP Config

1. `NovelLlmwikiMcpConfigBuilder` 校验 `project_slug`、workspace 路径和 MCP server name。
2. 解析 `llmwiki` 可执行文件；缺失时返回 `ready_with_warnings`，仍输出可检查的配置片段。
3. 输出标准 `mcpServers` JSON，命令形状为 `llmwiki mcp <workspace>`。
4. 输出 Codex `[mcp_servers.<server>]` TOML 片段，适合人工加入 bot harness 配置。
5. 输出角色绑定策略：Director 接入读写但写入必须 humanGate，Validator 接入只读，Creative 不直接接入 llmwiki MCP。

### Series

1. `NovelSeriesRunner` 先运行 `foundation`，再按章节号连续调用 `chapter`。
2. 默认 `chapter_count=5`，每章使用可追踪的本地目标文本；第 2 章以后通过 prior archive 自动继承前文上下文。
3. 章节完成后运行 `wiki-bundle`，可选运行 `llmwiki-sync` 生成计划或执行本地 workspace 同步。
4. 写入 `runs/{series_run_id}/series-metrics.json`，包含完成章数、P0/P1 数量、修订轮次、归档完整率、prior context 覆盖率和用户修改点。
5. 当前回归基线覆盖 20 章样例，要求 20/20 完成、P0/P1 为 0、归档完整率 1.0、prior context 覆盖率 1.0。

### Readiness

1. `NovelReadinessChecker` 用 `botmux-assets` dry-run 确认本机 workflow 和三个小说 bot workspace `AGENTS.md` 未漂移。
2. 读取 `~/.botmux/bots.json`，确认三个小说 bot 的 appId 和工作目录存在；不会输出 app secret。
3. 运行 `botmux workflow validate` 校验两个 workflow 模板。
4. 静态校验 workflow 模板中的 `${params.*}` 和 `${node.output.*}` 绑定，确认参数、上游节点、依赖闭包和输出字段都存在。
5. 检查 `llmwiki` 是否在 PATH 且 `llmwiki --help` 可执行；缺失或不可用是 warning，不阻断本地文件同步。
6. 传 `--bootstrap-smoke` 时在临时目录跑 `novel-bootstrap`，确认 foundation、wiki 审核包、dry-run sync plan、MCP config 和 approval package 可生成，且外部 workspace 未被写入。
7. 传 `--series-smoke` 时在临时目录跑连续章节 smoke，并检查 Phase 3 指标阈值。
8. 传 `--llmwiki-smoke` 时在临时目录生成 wiki bundle，初始化独立 llmwiki workspace，执行 approved `llmwiki-sync --reindex`，确认页面复制和索引重建可用。

### BotMux Assets

1. `python -m botmux_novel botmux-assets` 比较仓库模板和本机 BotMux 资产，不写文件。
2. `python -m botmux_novel botmux-assets --write` 同步 `workflows/*.workflow.json` 到 `~/.botmux/workflows/`。
3. 同步三个小说 bot 的 `~/.botmux/workspace/{bot}/AGENTS.md`，内容由仓库 `agents/*.identity.md` 加 BotMux workspace 说明和开发闭环原则生成。
4. 已存在且内容不同的 workspace 文件会先备份为 `AGENTS.md.bak-<timestamp>`。

## 数据模型

- `relationship-map.schema.json`：约束 `characters/relationships.json`，包含人物关系边、关系类型、压力和秘密。
- `scene-setting.schema.json`：约束 `settings/scenes.json` 中的单个场景或世界规则节点。
- `style-profile.schema.json`：约束 `settings/style-profile.json`，包含语气、规则、禁用表达和正反例。
- `foreshadowing-ledger.schema.json`：约束 `tracking/foreshadowing.yaml` 和 `runs/archive-{chapter}.json` 中的伏笔条目。

## 代码锚点

- `botmux_novel/runtime.py`：状态机、trace 和产物写入。
- `botmux_novel/bootstrap.py`：真实项目启动包、审批包、wiki dry-run sync plan 和 MCP 配置串联。
- `botmux_novel/agents.py`：确定性 MVP Agent 行为。
- `botmux_novel/workspace.py`：文件工作区、YAML 渲染和 SQLite 记录。
- `botmux_novel/cli.py`：命令行入口。
- `botmux_novel/llmwiki_sync.py`：gated llmwiki 本地 workspace 同步、备份、reindex 调用和同步计划。
- `botmux_novel/mcp_config.py`：项目级 llmwiki MCP 配置片段、Codex TOML、角色绑定和 humanGate 策略生成。
- `botmux_novel/series.py`：连续章节样例运行和质量指标采集。
- `botmux_novel/readiness.py`：小说生产本地就绪检查、workflow 绑定静态校验、可选 series smoke 和可选 llmwiki write/reindex smoke。
- `botmux_novel/botmux_assets.py`：BotMux workflow 和 workspace AGENTS 同步。
- `tests/test_botmux_assets.py`：BotMux 资产 dry-run、写入、CLI 和本机 workspace 同步测试。
- `tests/test_novel_bootstrap.py`：`novel-bootstrap` 审批包、dry-run sync 和 CLI 入口测试。
- `tests/test_novel_runtime.py`：端到端验证和门禁阻断测试。
- `tests/test_novel_workflows.py`：workflow 模板、bot id、humanGate 和本机安装副本一致性测试。
- `docs/novel-llmwiki-setup.md`：llmwiki 本地 workspace、MCP 权限和 humanGate 接入 runbook。

## BotMux Workflow

- `novel-story-foundation`：开书设定、Story Bible 候选和 wiki sync plan。
- `novel-chapter-production`：章节上下文、蓝图、草稿、验证、修订、定稿候选和 archive plan。
- 仓库模板保存在 `workflows/`；本机运行副本保存在 `/Users/xiaochen/.botmux/workflows/`。
- BotMux 离线 `workflow run --bot-resolver echo` 只回传 `echo` 字段，不模拟 `preview/handoff/data` 输出契约；不要把它当小说 workflow 端到端 smoke。
