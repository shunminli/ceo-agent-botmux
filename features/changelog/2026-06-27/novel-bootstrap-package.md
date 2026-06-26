# Novel Bootstrap Package

Added a local project bootstrap command:

```bash
python3 -m botmux_novel novel-bootstrap \
  --project /path/to/novel-project \
  --title <title> \
  --inspiration <brief> \
  --project-slug <slug>
```

The command runs the safe pre-write chain for a new novel project:

- Generates the opening foundation and `foundation.json`.
- Exports the local wiki review bundle.
- Creates a dry-run `llmwiki-sync` plan without running approved sync, reindex, or external workspace overwrites.
- Generates project-scoped llmwiki MCP config and role binding policy.
- Writes `runs/{bootstrap_run_id}/approval-package.md` and `.json` for humanGate review.
- Includes `next_actions.chapter_start_command`, a ready-to-run `python3 -m botmux_novel chapter` command that starts the opening chapter from the approved `foundation.json`.

This turns the next real project step into a single auditable entry point. It still does not approve long-lived llmwiki writes or run reindex; the approval package contains the exact gated write and opening-chapter commands to run after human review.
