# Novel Approval Decision

Added a humanGate decision recorder for `novel-bootstrap` approval packages:

```bash
python3 -m botmux_novel approval-decision \
  --approval-package /path/to/novel-project/runs/<bootstrap-run-id>/approval-package.json \
  --decision approve \
  --reviewer human \
  --notes "Approved after reviewing approval-package.md and wiki bundle."
```

Behavior:

- Records `approve`, `request_changes`, or `reject` in `approval-package.json`.
- Stores reviewer, notes, timestamp, previous decision, and append-only `decision_history`.
- Re-renders sibling `approval-package.md` when present so the human-readable package shows the recorded decision.
- Keeps llmwiki writes separate; the command only updates the approval package.
- `approval-apply --approve` now refuses packages recorded as `request_changes` or `reject`.
- Readiness `--approval-apply-smoke` covers the formal path: bootstrap, decision record, approved apply, workspace init, page sync, lint, and reindex.

This makes the Story Bible/wiki write gate auditable without requiring manual JSON edits.
