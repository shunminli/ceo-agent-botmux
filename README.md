# CEO Agent BotMux

An AI agent team built with BotMux to coordinate coding agents through chat.

本仓库沉淀一套“一人公司”的多 Agent 协作设计：CEO Agent 负责对人接口、任务拆解和调度，Tech Design / DevOps / Validation Agent 分别承担方案设计、工程落地和质量门禁。

## Documents

- [CEO Agent](agents/ceo-agent.identity.md)
- [Tech Design Agent](agents/tech-design-agent.identity.md)
- [DevOps Agent](agents/devops-agent.identity.md)
- [Validation Agent](agents/validation-agent.identity.md)
- [Team Operating Contract](agents/team-operating-contract.md)
- [小说创作 Agent Team 技术方案](docs/novel-creation-agent-team-tech-plan.md)
- [Novel Runtime 逻辑记忆](agents/novel-runtime/index.md)
- [Novel Creation Runtime 功能记忆](features/novel-creation-runtime/index.md)

## Local Novel Runtime

P0 已提供一个标准库 Python CLI，用于验证小说创作 Agent Team 的本地闭环：从一句灵感生成首章章纲、上下文包、草稿、审稿、修订、定稿、状态归档、JSON trace 和 SQLite run 记录。

```bash
python3 -m botmux_novel run \
  --project /tmp/novel-demo \
  --title 影钟旧案 \
  --inspiration "一个背负旧案污名的少年，在巡夜钟声中发现妹妹影子会说真话。"
```

验证入口：

```bash
python3 -m unittest discover -s tests -v
```

## Collaboration Model

用户默认只面对 CEO Agent。CEO Agent 将自然语言需求转成目标、范围、Owner、验收标准和交付顺序，再把技术方案、研发落地和独立验证分派给对应 Agent。最终由 CEO Agent 汇总交付物、验证证据、风险和待决策事项。
