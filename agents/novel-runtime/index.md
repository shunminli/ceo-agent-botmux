Commit: 8595e9722336d27913d3139befa1914d8db316a3

# Novel Runtime

`botmux_novel` 是小说创作 Agent Team 的本地 P0 运行时，用标准库 Python 实现从一句灵感到首章定稿、门禁、归档和 run trace 的闭环。

## 职责

- 提供 CLI 入口 `python -m botmux_novel run`。
- 在本地小说项目目录中创建方案文档约定的文件工作区。
- 串行编排 6 个 MVP Agent：总导演、章纲、正文写手、编辑、一致性检查、归档记忆。
- 记录每次 run 的 JSON trace 和 SQLite run 表。

## 边界

- 当前运行时使用确定性本地 Agent，不调用真实 LLM，也不连接外部 BotMux 服务。
- 当前只覆盖单项目、单章闭环；连续多章、真实模型 provider、Web UI 和向量检索属于后续迭代。
- 输出是本地 Markdown/YAML/JSON/SQLite 文件，不涉及生产发布、云同步或多用户权限。

## 主流程

1. `NovelRuntime.run` 校验 `NovelRunRequest` 并创建工作区目录。
2. `DirectorAgent` 生成项目状态、故事圣经、题材、世界观、角色和首章目标。
3. `BlueprintAgent` 生成章节蓝图和场景卡。
4. `ContextPackBuilder` 组装章节上下文包。
5. `DraftWriterAgent` 生成草稿。
6. `ConsistencyAgent` 执行 Gate 0-4，发现 P2 文风问题时进入修订。
7. `EditorAgent` 去除模板化表达并保留剧情事实。
8. `ConsistencyAgent` 复核通过后由总导演批准定稿。
9. `ArchiveMemoryAgent` 写入事实、时间线、伏笔、角色状态和冲突记录。
10. `NovelWorkspace.record_run` 写入 SQLite run 表和 artifact 索引。

## 代码锚点

- `botmux_novel/runtime.py`：状态机、trace 和产物写入。
- `botmux_novel/agents.py`：确定性 MVP Agent 行为。
- `botmux_novel/workspace.py`：文件工作区、YAML 渲染和 SQLite 记录。
- `botmux_novel/cli.py`：命令行入口。
- `tests/test_novel_runtime.py`：端到端验证和门禁阻断测试。
