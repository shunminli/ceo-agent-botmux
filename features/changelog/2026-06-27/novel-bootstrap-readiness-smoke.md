# Novel Bootstrap Readiness Smoke

Added optional readiness coverage for the project bootstrap entry point:

```bash
python3 -m botmux_novel readiness --bootstrap-smoke
```

The smoke creates a temporary project and separate temporary llmwiki workspace, then verifies:

- `novel-bootstrap` completes.
- `foundation.json` exists.
- The local wiki review bundle exists.
- `llmwiki-sync` remains a dry-run plan.
- The external workspace is not populated before approval.
- `approval-package.md` and `.json` exist.
- MCP config generation succeeds or reports warnings.

This makes the real-project start path part of local readiness without bypassing humanGate.
