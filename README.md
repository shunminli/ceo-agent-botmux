# CEO Agent BotMux

An AI agent team built with BotMux to coordinate specialist agents through chat.

本仓库沉淀“一人公司”多 Agent 协作设计和本地工具链：CEO Agent 负责对人接口、任务拆解和调度，Tech Design / DevOps / Validation Agent 分别承担方案设计、工程落地和质量门禁，Rental Agent 负责企业厂房、仓库和办公室选址中介任务。

## Repository Scope

- Agent identities and team operating contracts.
- BotMux workflow templates for novel production.
- Local `botmux_novel` runtime for deterministic smoke tests and workflow import/export.
- Local `botmux_doubao` wrapper for Doubao creative-assist calls.
- Repository memory under `agents/*/index.md`, `features/*/index.md`, and `features/changelog/*`.

The README is only the entry point. Detailed commands, examples, and historical notes belong in the linked docs and feature memory, not here.

## Key Documents

### Agent Identities

- [CEO Agent](agents/ceo-agent.identity.md)
- [Tech Design Agent](agents/tech-design-agent.identity.md)
- [DevOps Agent](agents/devops-agent.identity.md)
- [Validation Agent](agents/validation-agent.identity.md)
- [Rental Agent](agents/rental-agent.identity.md)
- [Team Operating Contract](agents/team-operating-contract.md)

### Novel Production

- [Novel Director Curator](agents/novel-director-curator.identity.md)
- [Novel Creative Architect](agents/novel-creative-architect.identity.md)
- [Novel Continuity Validator](agents/novel-continuity-validator.identity.md)
- [Novel Runtime Logic Memory](agents/novel-runtime/index.md)
- [Novel Creation Runtime Feature Memory](features/novel-creation-runtime/index.md)
- [Novel Agent Team Tech Plan](docs/novel-creation-agent-team-tech-plan.md)
- [Novel llmwiki Setup Runbook](docs/novel-llmwiki-setup.md)

### Doubao CLI

- [Doubao CLI Logic Memory](agents/doubao-cli/index.md)
- [Doubao Creative Assist CLI Feature Memory](features/doubao-cli/index.md)

### Workflows

- [Novel Story Foundation Workflow](workflows/novel-story-foundation.workflow.json)
- [Novel Chapter Production Workflow](workflows/novel-chapter-production.workflow.json)

## Validation

Run the standard test suite before handing off code changes:

```bash
python3 -m unittest discover -s tests -v
```

For novel runtime or workflow changes, also run the core readiness smoke:

```bash
python3 -m botmux_novel readiness --bootstrap-smoke --approval-apply-smoke --series-smoke
```

Use the heavier llmwiki and 20-chapter smoke only when the change affects long-run stability, llmwiki sync, or release readiness:

```bash
python3 -m botmux_novel readiness --bootstrap-smoke --approval-apply-smoke --series-smoke --smoke-chapter-count 20 --llmwiki-smoke
```

## Operating Boundaries

- Single-novel project facts do not belong in shared role identities or this README.
- Novel manuscript projects should live outside this tool repository; this repo owns shared runtime, workflow, schema, and bot identity assets.
- `fanqie-export` prepares UTF-8 text artifacts for manual upload; it does not call Fanqie APIs or publish chapters.
- Doubao integration uses the user's local logged-in desktop or web session and does not store account credentials.
- BotMux workflow templates generate candidate packages and plans; project file writes and llmwiki writes remain gated by explicit approval paths.

## Collaboration Model

Users normally interact with the CEO Agent. The CEO Agent turns natural-language requests into goals, owners, acceptance criteria, and delivery order, then coordinates specialist agents and summarizes evidence, risks, and remaining decisions.
