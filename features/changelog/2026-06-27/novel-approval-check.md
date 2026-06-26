Updated: 2026-06-27

# Novel Approval Package Check

Added a machine-verifiable approval package gate:

```bash
python3 -m botmux_novel approval-check \
  --approval-package /path/to/novel-project/runs/<bootstrap-run-id>/approval-package.json \
  --apply-dry-run
```

The default check is read-only. It verifies:

- `approval-package.json` and sibling Markdown exist.
- Review materials exist: foundation JSON, story Markdown, wiki bundle, and llmwiki sync plan.
- Wiki bundle pages match the sync plan preview.
- HumanGate commands point at the current package and require approved `llmwiki-sync --approve --reindex --lint`.
- MCP role policy keeps Director as gated writer, Creative without direct llmwiki access, and Validator read-only.
- The next chapter command uses the reviewed foundation JSON.

Optional flags:

- `--apply-dry-run` verifies `approval-apply` can consume the package while staying in planned mode.
- `--chapter-smoke` runs the package chapter command and is intended for temporary smoke projects, not default real-project approval.

Readiness `--bootstrap-smoke` now uses this checker with `--apply-dry-run`, so bootstrap packages are validated as first-class launch artifacts.
