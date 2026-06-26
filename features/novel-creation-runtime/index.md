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

python3 -m botmux_novel wiki-bundle \
  --project /tmp/novel-demo \
  --project-slug shadow-clock-case

python3 -m botmux_novel llmwiki-sync \
  --project /tmp/novel-demo \
  --project-slug shadow-clock-case \
  --approve

python3 -m botmux_novel llmwiki-mcp-config \
  --workspace /tmp/novel-demo \
  --project-slug shadow-clock-case

python3 -m botmux_novel chapter \
  --project /tmp/novel-demo \
  --chapter-number 2 \
  --chapter-goal "让林烬用半张残页验证巡夜钟异常，并把妹妹影子证词转成下一章追查目标。"

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
python3 -m botmux_novel readiness --series-smoke
python3 -m botmux_novel readiness --series-smoke --smoke-chapter-count 20
python3 -m botmux_novel readiness --llmwiki-smoke

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
- `runs/{chapter_run_id}/source-foundation.json`：`chapter` 子命令使用的 Story Bible 来源快照。
- `runs/{chapter_run_id}/prior-context.json`：`chapter` 子命令自动汇总的前文章节归档上下文。
- `runs/llmwiki-sync-{project_slug}-{timestamp}.json`：`llmwiki-sync` 子命令生成的写入门禁计划、影响面、回滚计划和命令结果。
- `llmwiki-mcp-config` JSON：项目级 MCP server 片段、Codex TOML、角色绑定策略和 humanGate 规则。
- `runs/{series_run_id}/series-metrics.json`：`series` 子命令生成的连续章节质量指标。
- `wiki/novels/{project_slug}/*.md`：`wiki-bundle` 子命令生成的本地 llmwiki 写入前审核包。
- `workflows/*.workflow.json`：版本化的 BotMux 三 bot 协作模板，测试会校验输出契约、人类门禁和本机安装副本一致性。
- `~/.botmux/workspace/{Novel-*}/AGENTS.md`：由 `botmux-assets --write` 从仓库身份文档生成的运行态 workspace 指令。
- `readiness` JSON：本机小说生产环境的 BotMux、workflow validate、workflow 绑定、llmwiki、可选 series smoke 和可选 approved llmwiki sync smoke 检查结果。

## 规则与状态

- 默认执行 `lean` 模式。
- `foundation` 只生成开书设定资产，不写 `manuscript/draft|revised|final`。
- `chapter` 从本地 `foundation.json` 继续生产章节，不重新规划 Story Bible，并自动读取早于当前章节的 `runs/archive-*.json` 作为连续性上下文。
- `wiki-bundle` 只读取本地 `foundation.json` 并写项目内 Markdown bundle，不调用 llmwiki。
- `llmwiki-sync` 默认只生成计划；只有传 `--approve` 才把审核包复制到 llmwiki workspace。它不安装 llmwiki，不调用 MCP 写工具。
- `llmwiki-mcp-config` 只生成配置片段和角色绑定策略，不写 `~/.codex/config.toml`，默认只建议 Director 和 Validator 接入 llmwiki MCP。
- `series` 默认连续生成 5 章、导出 wiki bundle，并统计 P0/P1、修订轮次、归档完整率和 prior context 覆盖率。
- `readiness` 只读检查本机状态；缺少 llmwiki 时返回 `ready_with_warnings`，BotMux 配置、workflow validate、workflow 绑定校验或显式请求的 smoke 失败时返回 `blocked`。
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
- 本机已安装 llmwiki；若其他环境未安装，`llmwiki-sync --reindex` 会跳过 reindex 并返回 warning，文件同步仍可完成。

## 相关逻辑文档

- [Novel Runtime](../../agents/novel-runtime/index.md)
- [Novel llmwiki Setup Runbook](../../docs/novel-llmwiki-setup.md)
