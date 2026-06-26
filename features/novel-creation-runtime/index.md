Updated: 2026-06-27

# Novel Creation Runtime

## 能力

用户可以通过 CLI 输入小说标题和一句灵感，系统会在本地项目目录中生成首章创作工作区，并完成章纲、上下文包、草稿、审稿、修订、定稿、状态归档和运行记录。

BotMux workflow 已提供 3 bot 协作入口；仓库模板与本机全局安装副本保持一致：

- `workflows/novel-story-foundation.workflow.json`
- `workflows/novel-chapter-production.workflow.json`
- `/Users/xiaochen/.botmux/workflows/novel-story-foundation.workflow.json`
- `/Users/xiaochen/.botmux/workflows/novel-chapter-production.workflow.json`

## 触发方式

```bash
python3 -m botmux_novel foundation \
  --project /tmp/novel-demo \
  --title 影钟旧案 \
  --inspiration "一个背负旧案污名的少年，在巡夜钟声中发现妹妹影子会说真话。"

python3 -m botmux_novel novel-bootstrap \
  --project /tmp/novel-demo \
  --title 影钟旧案 \
  --inspiration "一个背负旧案污名的少年，在巡夜钟声中发现妹妹影子会说真话。" \
  --project-slug shadow-clock-case

python3 -m botmux_novel workflow-foundation-import \
  --workflow-result /tmp/novel-story-foundation-result.json \
  --project /tmp/novel-demo \
  --project-slug shadow-clock-case

python3 -m botmux_novel approval-decision \
  --approval-package /tmp/novel-demo/runs/<bootstrap-run-id>/approval-package.json \
  --decision approve \
  --reviewer human \
  --notes "Approved after reviewing approval-package.md and wiki bundle."

python3 -m botmux_novel approval-check \
  --approval-package /tmp/novel-demo/runs/<bootstrap-run-id>/approval-package.json \
  --apply-dry-run

python3 -m botmux_novel approval-apply \
  --approval-package /tmp/novel-demo/runs/<bootstrap-run-id>/approval-package.json \
  --approve

python3 -m botmux_novel wiki-bundle \
  --project /tmp/novel-demo \
  --project-slug shadow-clock-case

python3 -m botmux_novel llmwiki-sync \
  --project /tmp/novel-demo \
  --project-slug shadow-clock-case \
  --approve \
  --reindex \
  --lint

python3 -m botmux_novel wiki-lint \
  --workspace /tmp/novel-demo

python3 -m botmux_novel llmwiki-mcp-config \
  --workspace /tmp/novel-demo \
  --project-slug shadow-clock-case

python3 -m botmux_novel chapter \
  --project /tmp/novel-demo \
  --chapter-number 1

python3 -m botmux_novel chapter \
  --project /tmp/novel-demo \
  --chapter-number 2 \
  --chapter-goal "让林烬用半张残页验证巡夜钟异常，并把妹妹影子证词转成下一章追查目标。"

python3 -m botmux_novel chapter-workflow-import \
  --workflow-result /tmp/novel-chapter-production-result.json \
  --project /tmp/novel-demo

python3 -m botmux_novel series \
  --project /tmp/novel-series-demo \
  --title 影钟旧案 \
  --inspiration "一个背负旧案污名的少年，在巡夜钟声中发现妹妹影子会说真话。" \
  --project-slug shadow-clock-case \
  --chapter-count 5

python3 -m botmux_novel run \
  --project /tmp/novel-demo \
  --title 影钟旧案 \
  --inspiration "一个背负旧案污名的少年，在巡夜钟声中发现妹妹影子会说真话。"

python3 -m botmux_novel botmux-assets
python3 -m botmux_novel botmux-assets --write
python3 -m botmux_novel readiness --bootstrap-smoke
python3 -m botmux_novel readiness --approval-apply-smoke
python3 -m botmux_novel readiness --workflow-import-smoke
python3 -m botmux_novel readiness --chapter-import-smoke
python3 -m botmux_novel readiness --series-smoke
python3 -m botmux_novel readiness --series-smoke --smoke-chapter-count 20
python3 -m botmux_novel readiness --bootstrap-smoke --workflow-import-smoke --chapter-import-smoke --approval-apply-smoke --series-smoke --smoke-chapter-count 20 --llmwiki-smoke

/Users/xiaochen/.botmux/bin/botmux workflow run novel-chapter-production \
  --param projectSlug=shadow-clock-case \
  --param title=影钟旧案 \
  --param storyBible="已批准的 Story Bible 或 foundation handoff" \
  --param chapterNumber=1 \
  --param chapterGoal=用旧书楼残页引出主角秘密能力并埋下巡夜钟伏笔
```

## 主要产物

- `project.yaml`：项目状态、模式、当前章节和质量阈值。
- `story.md`、`settings/*`、`characters/*`、`outline/*`：开书资产和章节蓝图。
- `characters/relationships.json`：人物关系图，包含冲突边、信息边、情感边和秘密压力。
- `settings/scenes.json`、`settings/style-profile.json`：场景设定、世界规则功能和文风规则档案。
- `manuscript/draft|revised|final/ch-001.md`：首章草稿、修订稿和定稿。
- `tracking/facts.yaml`、`timeline.yaml`、`foreshadowing.yaml`、`character-state.yaml`、`continuity-issues.yaml`：章节归档状态；伏笔台账包含 id、状态、埋设章节、回收计划和风险等级。
- `runs/{run_id}/trace.json` 和 `runs/runs.sqlite`：可观察 run 记录和可查询索引。
- `runs/{foundation_run_id}/foundation.json`：`foundation` 子命令生成的开书设定包。
- `runs/{workflow_foundation_run_id}/workflow-result-source.json|workflow-node-outputs.json|foundation.json`：`workflow-foundation-import` 保存的 BotMux workflow 原始结果、节点输出和规范化 Story Bible 来源。
- `runs/{bootstrap_run_id}/approval-package.md|json`：`novel-bootstrap` 子命令生成的 Story Bible/wiki/MCP 人工审批包，包含审批记录、approved apply 和首章启动命令。
- `approval-decision` JSON：审批决策记录结果，包含 decision、reviewer、notes、decided_at 和审批包路径。
- `approval-check` JSON：审批包机器校验结果，包含审核材料、humanGate 命令、llmwiki 预览、MCP 策略、workspace target、可选 dry-run apply 和 chapter smoke 检查。
- `approval-apply` JSON：审批包执行结果，包含是否 approved、实际 `llmwiki-sync` 状态、warnings 和产物路径。
- `runs/{chapter_run_id}/source-foundation.json`：`chapter` 子命令使用的 Story Bible 来源快照。
- `runs/{chapter_run_id}/prior-context.json`：`chapter` 子命令自动汇总的前文章节归档上下文。
- `runs/{chapter_run_id}/next-chapter-command.md|json`：从 foundation 生产的章节完成后生成的下一章 handoff，包含建议目标、来源引用和可审阅执行的命令。
- `runs/{workflow_chapter_run_id}/workflow-result-source.json|workflow-node-outputs.json|summary.md|next-chapter-command.md|json`：`chapter-workflow-import` 保存的章节 workflow 原始结果、节点输出、导入摘要和下一章 handoff；下一章 BotMux 命令包含归档摘要 `priorContext`、章节目标、目标字数和模式。
- `runs/archive-{chapter}.json`：本地章节归档快照；可由 deterministic `chapter` 或通过 humanGate 的章节 workflow 导入生成。
- `runs/llmwiki-sync-{project_slug}-{timestamp}.json`：`llmwiki-sync` 子命令生成的写入门禁计划、影响面、回滚计划和命令结果。
- `wiki-lint` JSON：本地 wiki Markdown 结构 lint 结果，包含 checked files 和 issues。
- `llmwiki-mcp-config` JSON：项目级 MCP server 片段、Codex TOML、角色绑定策略和 humanGate 规则。
- `runs/{series_run_id}/series-metrics.json`：`series` 子命令生成的连续章节质量指标。
- `wiki/novels/{project_slug}/*.md`：`wiki-bundle` 子命令生成的本地 llmwiki 写入前审核包；有章节归档时还包含 `chapter-archive.md`、`timeline.md`、`character-state.md` 和 `chapters/{chapter}.md`。
- `workflows/*.workflow.json`：版本化的 BotMux 三 bot 协作模板，测试会校验输出契约、人类门禁和本机安装副本一致性。
- `schemas/approval-package.schema.json`：审批包必填字段和基础类型契约，覆盖项目元数据、审核材料、humanGate 命令、llmwiki preview、MCP 策略和下一步命令。
- `~/.botmux/workspace/{Novel-*}/AGENTS.md`：由 `botmux-assets --write` 从仓库身份文档生成的运行态 workspace 指令。
- `readiness` JSON：本机小说生产环境的 BotMux、bot workspace 身份绑定、workflow validate、workflow 绑定、workflow 合成契约、llmwiki、可选 bootstrap smoke、workflow import smoke、chapter import smoke、approval apply smoke、series smoke 和可选 approved llmwiki sync smoke 检查结果；bootstrap smoke 和 workflow import smoke 会执行审批包里的首章启动命令。

## 规则与状态

- 默认执行 `lean` 模式。
- `foundation` 只生成开书设定资产，不写 `manuscript/draft|revised|final`。
- `novel-bootstrap` 串联开书设定、项目内 wiki bundle、llmwiki dry-run sync plan、MCP 配置和审批包；审批包会在落盘前通过 `approval-package.schema.json` 必填字段和基础类型校验，并包含 `next_actions.chapter_start_command`，用于在审批和写入后从批准的 foundation 直接启动首章；它不会执行 approved sync、覆盖外部 llmwiki workspace 或修改全局配置。
- `workflow-foundation-import` 读取已完成的 `novel-story-foundation` workflow JSON 结果，校验 `story_bible_package` 和 `wiki_sync_plan` 输出契约，把 Story Bible 规范化成 `foundation.json`，再复用 wiki bundle、dry-run sync、MCP config 和 approval package 链路；它不执行 approved sync。
- `approval-decision` 只把 humanGate 决策写入审批包 JSON，并在同目录 `approval-package.md` 存在时重渲染 Markdown 审批包；它会先按 `approval-package.schema.json` 校验审批包，不执行 llmwiki 写入，正式批准路径应先记录 `--decision approve`。
- `approval-check` 默认只读校验审批包；它会先按 `approval-package.schema.json` 递归检查必填字段和基础类型。`--apply-dry-run` 只验证 `approval-apply` dry-run 消费路径，不执行 approved writes；`--chapter-smoke` 会执行首章命令，应用在临时 smoke 项目，不建议在未经审批的真实项目上默认运行。
- `approval-apply` 默认只重新生成同步计划；它会先按 `approval-package.schema.json` 校验审批包，只有传 `--approve` 才会按审批包写入 llmwiki workspace，并默认运行 `llmwiki reindex` 与写后 lint。若审批包已记录 `request_changes` 或 `reject`，会拒绝写入；若未记录 `approve` 但命令显式 `--approve`，会保留 warning 说明这是命令级 humanGate 信号。
- `chapter` 从本地 `foundation.json` 继续生产章节，不重新规划 Story Bible；未传 `--chapter-goal` 时自动使用 `foundation.json` 的 `chapter_goal.objective`，自动读取早于当前章节的 `runs/archive-*.json` 作为连续性上下文，并在完成后生成下一章 handoff 命令。
- `chapter-workflow-import` 读取已完成的 `novel-chapter-production` workflow JSON 结果，校验七个节点输出契约，只有 Director 决策和 archive plan 均通过时才写入本地 final、tracking、archive 和下一章 handoff；`project.yaml.archived_chapters` 会从 `runs/archive-*.json` 汇总，保留多章导入历史。下一章 handoff 会把本章事实、时间线、伏笔、人物状态和连续性问题压缩进 BotMux `priorContext` 参数。被 block 的章节只写 blocked run artifacts，不写 final，不写 llmwiki。
- `wiki-bundle` 读取本地 `foundation.json` 并写项目内 Markdown bundle；若存在 `runs/archive-*.json`，会把章节定稿、事实、时间线、伏笔和人物状态纳入章节归档页与聚合页。该命令不调用 llmwiki。
- `llmwiki-sync` 默认只生成计划；只有传 `--approve` 才把审核包复制到 llmwiki workspace。传 `--lint` 后优先运行 `llmwiki lint <workspace>`；若当前 llmwiki CLI 不支持 `lint` 子命令，则自动运行本地 `wiki-lint` fallback；若 lint 检查失败则同步结果为 `failed`。它不安装 llmwiki，不调用 MCP 写工具。
- `llmwiki-mcp-config` 只生成配置片段和角色绑定策略，不写 `~/.codex/config.toml`，默认只建议 Director 和 Validator 接入 llmwiki MCP。
- `series` 默认连续生成 5 章、导出 wiki bundle，并统计 P0/P1、修订轮次、归档完整率和 prior context 覆盖率。
- `readiness` 只读检查本机状态；缺少 llmwiki 时返回 `ready_with_warnings`，BotMux 配置、bot workingDir 与 workspace `AGENTS.md` 身份绑定、workflow validate、workflow 绑定校验、workflow 合成契约校验、workflow import smoke 或显式请求的其他 smoke 失败时返回 `blocked`。`--llmwiki-smoke` 会生成一章归档并确认章节归档页也能 approved sync、lint 和 reindex。
- `botmux-assets` 默认只报告差异；传 `--write` 后才同步本机 BotMux 资产，并为被替换的 `AGENTS.md` 创建备份。
- `novel-chapter-production` 只输出章节定稿候选包和归档计划，不直接写项目文件或 llmwiki。
- 质量门禁区分 `pass`、`revise` 和 `block`。
- P0/P1 硬约束或上下文缺失会阻断定稿。
- P2 文风问题会触发编辑 Agent 修订，并由一致性 Agent 复核。
- 归档通过后才写入最终事实、时间线、伏笔、角色状态和连续性问题。
- 关系图、场景设定、伏笔台账和文风档案都有对应 JSON Schema，运行时会在写入前做必填字段校验。

## 限制

- 当前 Agent 是确定性本地实现，不代表真实模型质量。
- 当前已验证连续 20 章本地稳定性基线：20/20 完成、P0/P1 为 0、归档完整率 1.0、prior context 覆盖率 1.0。
- 当前 YAML 写入用于本地可读产物，复杂读写和 schema migration 仍需后续迭代。
- 本机已安装 llmwiki；若其他环境未安装，`llmwiki-sync --reindex --lint` 会跳过 reindex 并返回 warning，但 lint 会走本地 `wiki-lint` fallback。若环境里的 llmwiki 版本尚未提供 CLI `lint` 子命令，fallback lint 仍会执行并纳入 readiness。

## 相关逻辑文档

- [Novel Runtime](../../agents/novel-runtime/index.md)
- [Novel llmwiki Setup Runbook](../../docs/novel-llmwiki-setup.md)
