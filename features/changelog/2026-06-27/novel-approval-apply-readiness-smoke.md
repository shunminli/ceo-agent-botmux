# Novel Approval Apply Readiness Smoke

Added optional readiness coverage for the humanGate apply path:

```bash
python3 -m botmux_novel readiness --approval-apply-smoke
```

The smoke creates a temporary bootstrap package, then runs approved `approval-apply` against a separate temporary llmwiki workspace. It verifies:

- The approval package can be consumed.
- The workspace is initialized automatically when reindex is requested.
- Approved wiki pages are copied into the target workspace.
- Reindex succeeds.

`approval-apply --approve` now initializes a missing llmwiki index before syncing when reindex is enabled. This makes the preferred approval command in `approval-package.md` executable on a fresh workspace after human review.
