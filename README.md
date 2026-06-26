# CEO Agent BotMux

An AI agent team built with BotMux to coordinate coding agents through chat.

本仓库沉淀一套“一人公司”的多 Agent 协作设计：CEO Agent 负责对人接口、任务拆解和调度，Tech Design / DevOps / Validation Agent 分别承担方案设计、工程落地和质量门禁，Rental Agent 负责企业厂房、仓库和办公室选址中介任务。

## Documents

- [CEO Agent](agents/ceo-agent.identity.md)
- [Tech Design Agent](agents/tech-design-agent.identity.md)
- [DevOps Agent](agents/devops-agent.identity.md)
- [Validation Agent](agents/validation-agent.identity.md)
- [Rental Agent](agents/rental-agent.identity.md)
- [Novel Director Curator](agents/novel-director-curator.identity.md)
- [Novel Creative Architect](agents/novel-creative-architect.identity.md)
- [Novel Continuity Validator](agents/novel-continuity-validator.identity.md)
- [Team Operating Contract](agents/team-operating-contract.md)
- [小说生产 Agent Team 技术方案](docs/novel-creation-agent-team-tech-plan.md)
- [Novel Runtime 逻辑记忆](agents/novel-runtime/index.md)
- [Doubao CLI 逻辑记忆](agents/doubao-cli/index.md)
- [Novel Creation Runtime 功能记忆](features/novel-creation-runtime/index.md)
- [Doubao Creative Assist CLI 功能记忆](features/doubao-cli/index.md)

## Local Novel Runtime

P0 已提供一个标准库 Python CLI，用于验证小说创作 Agent Team 的本地闭环：从一句灵感生成首章章纲、上下文包、草稿、审稿、修订、定稿、关系图、场景设定、文风档案、伏笔台账、状态归档、JSON trace 和 SQLite run 记录。

```bash
python3 -m botmux_novel foundation \
  --project /tmp/novel-demo \
  --title 影钟旧案 \
  --inspiration "一个背负旧案污名的少年，在巡夜钟声中发现妹妹影子会说真话。"

python3 -m botmux_novel run \
  --project /tmp/novel-demo \
  --title 影钟旧案 \
  --inspiration "一个背负旧案污名的少年，在巡夜钟声中发现妹妹影子会说真话。"
```

验证入口：

```bash
python3 -m unittest discover -s tests -v
```

## Local Doubao CLI

本仓库提供一个轻量豆包包装层，用于把豆包桌面端或网页版自动化 runner 暴露成稳定 CLI。默认推荐 OpenCLI 的桌面端适配器；前置 runner 可用 `npm install -g @jackwener/opencli` 安装（需要 Node.js >= 20）：

```bash
python3 -m botmux_doubao launch --dry-run
/Applications/Doubao.app/Contents/MacOS/Doubao --remote-debugging-port=9225
export OPENCLI_CDP_ENDPOINT=http://127.0.0.1:9225

python3 -m botmux_doubao ask \
  --provider opencli-app \
  --purpose creative \
  "给这个主角生成三个可选内心冲突。"
```

如果豆包桌面端已经在运行但没有 CDP 端口，需要先退出豆包再用上面的 remote debugging 参数重启；也可以显式运行 `python3 -m botmux_doubao launch --relaunch` 完成退出并重启。也可以用 `--provider opencli-web` 调用网页版适配器，此模式需要 OpenCLI Browser Bridge extension 已连接；或把 `--provider doubao-cli` 指向基于浏览器会话的第三方 `doubao-cli` runner。所有模式都只使用本机已登录的豆包桌面端或 Web 会话，不保存账号凭证。

## Collaboration Model

用户默认只面对 CEO Agent。CEO Agent 将自然语言需求转成目标、范围、Owner、验收标准和交付顺序，再把技术方案、研发落地、独立验证和实体空间选址分派给对应 Agent。最终由 CEO Agent 汇总交付物、验证证据、风险和待决策事项。
