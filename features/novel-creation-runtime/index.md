Updated: 2026-06-26

# Novel Creation Runtime

## 能力

用户可以通过 CLI 输入小说标题和一句灵感，系统会在本地项目目录中生成首章创作工作区，并完成章纲、上下文包、草稿、审稿、修订、定稿、状态归档和运行记录。

BotMux 全局 workflow 也已提供 3 bot 协作入口：

- `/Users/xiaochen/.botmux/workflows/novel-story-foundation.workflow.json`
- `/Users/xiaochen/.botmux/workflows/novel-chapter-production.workflow.json`

## 触发方式

```bash
python3 -m botmux_novel foundation \
  --project /tmp/novel-demo \
  --title 影钟旧案 \
  --inspiration "一个背负旧案污名的少年，在巡夜钟声中发现妹妹影子会说真话。"

python3 -m botmux_novel run \
  --project /tmp/novel-demo \
  --title 影钟旧案 \
  --inspiration "一个背负旧案污名的少年，在巡夜钟声中发现妹妹影子会说真话。"

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

## 规则与状态

- 默认执行 `lean` 模式。
- `foundation` 只生成开书设定资产，不写 `manuscript/draft|revised|final`。
- `novel-chapter-production` 只输出章节定稿候选包和归档计划，不直接写项目文件或 llmwiki。
- 质量门禁区分 `pass`、`revise` 和 `block`。
- P0/P1 硬约束或上下文缺失会阻断定稿。
- P2 文风问题会触发编辑 Agent 修订，并由一致性 Agent 复核。
- 归档通过后才写入最终事实、时间线、伏笔、角色状态和连续性问题。
- 关系图、场景设定、伏笔台账和文风档案都有对应 JSON Schema，运行时会在写入前做必填字段校验。

## 限制

- 当前 Agent 是确定性本地实现，不代表真实模型质量。
- 当前只验证首章闭环，不验证连续 20 章稳定性。
- 当前 YAML 写入用于本地可读产物，复杂读写和 schema migration 仍需后续迭代。

## 相关逻辑文档

- [Novel Runtime](../../agents/novel-runtime/index.md)
