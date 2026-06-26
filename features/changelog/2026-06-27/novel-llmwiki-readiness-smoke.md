# Novel llmwiki Readiness Smoke

Added an optional readiness smoke:

```bash
python3 -m botmux_novel readiness --llmwiki-smoke
```

## What It Verifies

- Generates a temporary novel foundation.
- Exports a temporary `wiki/novels/{project_slug}/` Markdown bundle.
- Initializes a separate temporary llmwiki workspace.
- Runs approved `llmwiki-sync` into that workspace.
- Runs `llmwiki lint` and `llmwiki reindex` through the configured executable.
- Confirms copied wiki pages and `.llmwiki/index.db` exist.

This closes the local write/lint/reindex verification gap without touching real project files or bypassing production humanGate rules.
