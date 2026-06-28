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
- [小说 llmwiki 接入 Runbook](docs/novel-llmwiki-setup.md)
- [Novel Runtime 逻辑记忆](agents/novel-runtime/index.md)
- [Doubao CLI 逻辑记忆](agents/doubao-cli/index.md)
- [Novel Creation Runtime 功能记忆](features/novel-creation-runtime/index.md)
- [Doubao Creative Assist CLI 功能记忆](features/doubao-cli/index.md)
- [Novel Story Foundation Workflow](workflows/novel-story-foundation.workflow.json)
- [Novel Chapter Production Workflow](workflows/novel-chapter-production.workflow.json)

## Local Novel Runtime

P0 已提供一个标准库 Python CLI，用于验证小说创作 Agent Team 的本地闭环：从一句灵感生成开书设定、章节章纲、上下文包、草稿、审稿、修订、定稿、关系图、场景设定、文风档案、伏笔台账、状态归档、JSON trace 和 SQLite run 记录。连续章节会读取前章 `runs/archive-*.json` 并生成 `prior-context.json`；从 foundation 或章节 workflow 导入生产的章节还会生成 `runs/{run_id}/next-chapter-command.md|json`，用于审阅并启动下一章，真实 BotMux 命令会携带前章归档 `priorContext`。该 handoff 也包含重新生成 wiki 审核包、创建 dry-run llmwiki sync 计划和 humanGate 后 approved sync 的命令。

真实项目优先从 `novel-bootstrap` 生成的 `approval-package.md|json` 继续；审批包会给出审批记录、approved apply、本地首章 smoke 命令和真实 BotMux 首章 workflow 命令，避免手工拼路径。

```bash
python3 -m botmux_novel project-init \
  --project /tmp/novel-demo \
  --project-slug shadow-clock-case \
  --title 影钟旧案 \
  --inspiration "一个背负旧案污名的少年，在巡夜钟声中发现妹妹影子会说真话。" \
  --genre 东方悬疑奇幻 \
  --target-length 长篇

python3 -m botmux_novel foundation \
  --project /tmp/novel-demo \
  --title 影钟旧案 \
  --inspiration "一个背负旧案污名的少年，在巡夜钟声中发现妹妹影子会说真话。"

python3 -m botmux_novel novel-bootstrap \
  --project /tmp/novel-demo \
  --title 影钟旧案 \
  --inspiration "一个背负旧案污名的少年，在巡夜钟声中发现妹妹影子会说真话。" \
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

python3 -m botmux_novel fanqie-export \
  --project /tmp/novel-demo \
  --title 影钟旧案

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

python3 -m botmux_novel workflow-foundation-command \
  --project-slug shadow-clock-case \
  --title 影钟旧案 \
  --inspiration "一个背负旧案污名的少年，在巡夜钟声中发现妹妹影子会说真话。" \
  --genre 东方悬疑奇幻 \
  --target-length 长篇

python3 -m botmux_novel workflow-export \
  --run-id <botmux-run-id> \
  > /tmp/novel-story-foundation-result.json
```

BotMux workflow 模板已纳入仓库，并同步安装到本机 BotMux 全局目录：

```bash
python3 -m botmux_novel botmux-assets
python3 -m botmux_novel botmux-assets --write
$HOME/.botmux/bin/botmux workflow validate workflows/novel-story-foundation.workflow.json
$HOME/.botmux/bin/botmux workflow validate workflows/novel-chapter-production.workflow.json

python3 -m botmux_novel readiness --bootstrap-smoke
python3 -m botmux_novel readiness --approval-apply-smoke
python3 -m botmux_novel readiness --series-smoke
```

真实 BotMux 开书 run 可先用 `workflow-foundation-command` 生成启动命令；run 完成后，再用 `workflow-export` 从 run 事件和 blobs 导出 JSON，交给 `workflow-foundation-import` 或 `chapter-workflow-import`。`workflow run --bot-resolver echo` 只适合调试 BotMux 调度，不会产出小说节点的 `preview/handoff/data` 合约。

小说正文项目应使用独立目录，例如 `$HOME/NovelProjects/{project_slug}`。本仓库只管理工具链、workflow、schema 和 bot 身份；单本小说的 `bible/`、`manuscript/final/`、`publish/fanqie/`、`tracking/` 和 `comms/decisions/` 可放在小说目录自己的私有 git 中。`runs/`、bot 原始日志、`wiki/llmwiki-workspace/` 和临时索引默认本地管理，不纳入 git。

`fanqie-export` 从 `manuscript/final/ch-*.md` 生成番茄后台友好的 UTF-8 纯文本产物：`publish/fanqie/chapters/*.txt`、`publish/fanqie/book.txt` 和 `publish/fanqie/upload-checklist.md`。该命令不调用番茄后台 API，不自动发布章节。

验证入口：

```bash
python3 -m unittest discover -s tests -v
python3 -m botmux_novel readiness --bootstrap-smoke --approval-apply-smoke --series-smoke
python3 -m botmux_novel readiness --bootstrap-smoke --approval-apply-smoke --series-smoke --smoke-chapter-count 20 --llmwiki-smoke
```

`readiness` 默认会同时执行 workflow 绑定静态校验和本地合成契约 smoke，确认两个 BotMux workflow 的 prompt 能按依赖顺序渲染，并且每个节点都能传递 `preview/handoff/data` 等统一输出字段。传 `--llmwiki-smoke` 时会在临时项目生成一章归档，再验证 Story Bible 页面和章节归档页都能 approved sync、lint 和 reindex。

`approval-check` 默认只读校验 `novel-bootstrap` 审批包；它会检查审核材料、humanGate 命令、llmwiki 预览、MCP 角色策略、本地首章命令和真实 BotMux 首章 workflow 命令，传 `--apply-dry-run` 时额外验证审批包能被 `approval-apply` 以 dry-run 消费且不会执行 approved writes。

## Local Doubao CLI

本仓库提供一个轻量豆包包装层，用于把豆包桌面端或网页版自动化 runner 暴露成稳定 CLI。桌面端推荐直接 CDP provider `cdp-app`；它使用本机 Node 连接已登录的 Doubao Desktop，不需要额外 npm 依赖：

```bash
python3 -m botmux_doubao launch --dry-run
python3 -m botmux_doubao launch --app-binary <path-to-doubao-binary>
export DOUBAO_CDP_ENDPOINT=http://127.0.0.1:9225

python3 -m botmux_doubao ask \
  --provider cdp-app \
  --purpose creative \
  "给这个主角生成三个可选内心冲突。"
```

如果豆包桌面端已经在运行但没有 CDP 端口，需要先退出豆包再用上面的 remote debugging 参数重启；也可以显式运行 `python3 -m botmux_doubao launch --relaunch` 完成退出并重启。也可以用 `--provider opencli-app` 调用 OpenCLI `doubao-app` 适配器，用 `--provider opencli-web` 调用网页版适配器，此模式需要 OpenCLI Browser Bridge extension 已连接；或把 `--provider doubao-cli` 指向基于浏览器会话的第三方 `doubao-cli` runner。所有模式都只使用本机已登录的豆包桌面端或 Web 会话，不保存账号凭证。

## Collaboration Model

用户默认只面对 CEO Agent。CEO Agent 将自然语言需求转成目标、范围、Owner、验收标准和交付顺序，再把技术方案、研发落地、独立验证和实体空间选址分派给对应 Agent。最终由 CEO Agent 汇总交付物、验证证据、风险和待决策事项。
