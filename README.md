# CEO Agent BotMux

An AI agent team built with BotMux to coordinate coding agents through chat.

本仓库沉淀一套“一人公司”的多 Agent 协作设计：CEO Agent 负责对人接口、任务拆解和调度，Tech Design / DevOps / Validation Agent 分别承担方案设计、工程落地和质量门禁。

## Documents

- [CEO Agent](agents/ceo-agent.identity.md)
- [Tech Design Agent](agents/tech-design-agent.identity.md)
- [DevOps Agent](agents/devops-agent.identity.md)
- [Validation Agent](agents/validation-agent.identity.md)
- [Team Operating Contract](agents/team-operating-contract.md)

## Collaboration Model

用户默认只面对 CEO Agent。CEO Agent 将自然语言需求转成目标、范围、Owner、验收标准和交付顺序，再把技术方案、研发落地和独立验证分派给对应 Agent。最终由 CEO Agent 汇总交付物、验证证据、风险和待决策事项。
