# Novel Readiness Check

Added a local readiness command:

```bash
python3 -m botmux_novel readiness --series-smoke
```

## Checks

- BotMux workflow and workspace AGENTS assets are installed and unchanged.
- The three novel bot configs are present in `~/.botmux/bots.json`, with workspace directories available.
- Both BotMux workflow templates pass `botmux workflow validate`.
- Workflow template bindings are checked statically so `${params.*}` and `${node.output.*}` references must resolve to declared params, upstream dependencies, and output schema fields.
- Workflow contract smoke renders each prompt and humanGate prompt with synthetic `preview/handoff/data` outputs to catch contract regressions that `botmux workflow run --bot-resolver echo` cannot cover.
- `llmwiki` availability is reported as a warning when missing or when `llmwiki --help` cannot execute.
- Optional `--series-smoke` runs a temporary multi-chapter series and validates key Phase 3 metrics.
- Optional `--llmwiki-smoke` runs an approved temporary llmwiki workspace sync, lint, and reindex.

## Status

- `ready`: all checks pass.
- `ready_with_warnings`: required checks pass, optional capabilities such as llmwiki are missing.
- `blocked`: required BotMux config, workspace sync, workflow validation, workflow binding validation, or an explicitly requested smoke fails.
