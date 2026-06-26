Updated: 2026-06-27

# Novel Wiki Lint Fallback

Added a local lint entry point for novel wiki Markdown workspaces:

```bash
python3 -m botmux_novel wiki-lint --workspace /path/to/novel-project
```

The linter checks:

- `wiki/novels` exists and contains Markdown pages.
- Each novel namespace has the required Story Bible, relationship, plot, scene, foreshadowing, continuity, chapter index, and sync plan pages.
- The `characters/` directory exists and contains Markdown pages.
- Every Markdown page is UTF-8, non-empty, starts with an H1, and has no broken local Markdown links.

`llmwiki-sync --lint` now uses this local linter automatically when the installed `llmwiki` CLI does not expose a `lint` subcommand. This turns readiness back to `ready` on the current machine while preserving hard failure when local or external lint finds structural errors.
