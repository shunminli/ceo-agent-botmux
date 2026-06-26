Commit: 8595e9722336d27913d3139befa1914d8db316a3

# Local Novel Runtime

## Context

小说创作 Agent Team 方案要求 P0 先跑通本地文件制项目、6 个 MVP Agent、章节级工作流、事实快照、质量门禁和 run trace。

## Change Summary

- 新增 `botmux_novel` 标准库 Python 运行时和 CLI。
- 实现从灵感到首章定稿、修订、归档和 trace/SQLite 记录的单章闭环。
- 补充端到端测试，覆盖真实 CLI 入口、文件副作用、SQLite run 表和门禁阻断。

## Impact Surface

- 新增本地项目目录写入协议。
- 新增小说创作 P0 Agent 行为和质量门禁语义。
- README 和技术方案可引用新的 CLI 作为后续迭代入口。

## Notes / Compatibility

当前实现不依赖第三方包、不调用真实 LLM、不连接外部 BotMux 服务。后续接入真实模型时，应保持 `NovelRunRequest`、run trace 和工作区产物契约稳定。

## Related Docs

- `agents/novel-runtime/index.md`
- `features/novel-creation-runtime/index.md`
