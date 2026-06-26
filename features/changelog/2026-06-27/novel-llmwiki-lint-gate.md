Updated: 2026-06-27

# Novel llmwiki Lint Gate

Approved llmwiki writes now have an executable lint gate.

- `python3 -m botmux_novel llmwiki-sync` accepts `--lint` and records the lint command in the sync plan.
- Approved sync runs `llmwiki lint <workspace>` when `--lint` is supplied. If the installed llmwiki CLI does not expose a `lint` subcommand, lint is skipped with a warning; if lint is supported and exits non-zero, the sync result is `failed`.
- `python3 -m botmux_novel approval-apply --approve` enables lint by default alongside reindex, with `--no-lint` available for diagnosis.
- `novel-bootstrap` approval packages include `--lint` in the underlying approved write command.
- Readiness `--approval-apply-smoke` and `--llmwiki-smoke` now verify both lint and reindex succeed.

This aligns the automated path with the Director role rule that llmwiki writes must be linted after humanGate-approved changes.
