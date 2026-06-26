Updated: 2026-06-27

# Novel Approval Schema Enforcement

Extended `approval-package.schema.json` from a checker-only contract to a required runtime gate.

Enforcement points:

- `novel-bootstrap` validates the approval package before writing `approval-package.json` and `.md`.
- `approval-decision` validates the package before recording a humanGate decision.
- `approval-apply` validates the package before dry-run or approved llmwiki sync.

This keeps malformed packages from bypassing `approval-check` and reaching the humanGate decision or write path.
