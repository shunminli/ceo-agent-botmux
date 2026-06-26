Updated: 2026-06-27

# Novel Workflow Contract Smoke

Added a local synthetic contract smoke to `python3 -m botmux_novel readiness`.

The check loads both novel BotMux workflow templates and:

- Builds representative parameter values.
- Renders each node prompt in dependency order.
- Renders humanGate prompts.
- Synthesizes minimal upstream outputs that satisfy each node `outputSchema`.
- Verifies required contract fields such as `preview`, `handoff`, `data`, `open_questions`, `risks`, `wiki_refs`, and `change_declarations` can be passed downstream.
- Reports workflow dependency cycles before attempting downstream prompt rendering.

This does not replace a real BotMux run with real bots and humanGate approvals. It closes the offline validation gap where `botmux workflow run --bot-resolver echo` cannot produce the novel team output contract.
