# Novel Readiness Check

Added a local readiness command:

```bash
python3 -m botmux_novel readiness --series-smoke
```

## Checks

- BotMux workflow and workspace AGENTS assets are installed and unchanged.
- The three novel bot configs are present in `~/.botmux/bots.json`, with workspace directories available.
- Both BotMux workflow templates pass `botmux workflow validate`.
- `llmwiki` availability is reported as a warning when missing.
- Optional `--series-smoke` runs a temporary multi-chapter series and validates key Phase 3 metrics.

## Status

- `ready`: all checks pass.
- `ready_with_warnings`: required checks pass, optional capabilities such as llmwiki are missing.
- `blocked`: required BotMux config, workspace sync, workflow validation, or series smoke fails.
