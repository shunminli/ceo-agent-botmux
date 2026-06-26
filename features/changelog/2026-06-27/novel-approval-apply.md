# Novel Approval Apply

Added a gated approval package executor:

```bash
python3 -m botmux_novel approval-apply \
  --approval-package /path/to/novel-project/runs/<bootstrap-run-id>/approval-package.json \
  --approve
```

Behavior:

- Reads the `novel-bootstrap` approval package.
- Extracts project path, project slug, llmwiki workspace, and `--llmwiki-bin`.
- Without `--approve`, writes only a fresh `llmwiki-sync` plan.
- With `--approve`, applies the reviewed wiki bundle to the target workspace and runs reindex/lint unless `--no-reindex` or `--no-lint` is passed.
- When approved reindex is requested and the target workspace has no `.llmwiki/index.db`, it runs `llmwiki init <workspace>` first.
- Preserves a warning when the approval package decision text is still the placeholder and the operator uses CLI `--approve` as the explicit humanGate signal.

This reduces path-copying mistakes after human review while keeping long-lived writes explicitly gated.
