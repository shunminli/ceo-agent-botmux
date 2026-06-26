Updated: 2026-06-27

# Novel Workflow Foundation Import

Added a bridge from real BotMux `novel-story-foundation` workflow output into the local gated novel production chain.

New command:

```bash
python3 -m botmux_novel workflow-foundation-import \
  --workflow-result /path/to/novel-story-foundation-result.json \
  --project /path/to/novel-project \
  --project-slug shadow-clock-case
```

The importer:

- Extracts and validates `story_bible_package` and `wiki_sync_plan` node outputs.
- Converts the approved Story Bible package into local `foundation.json` assets.
- Preserves the raw workflow result and normalized node outputs under `runs/{workflow_foundation_run_id}/`.
- Reuses the existing wiki bundle, dry-run llmwiki sync plan, MCP config, and approval package path.
- Keeps llmwiki writes gated behind `approval-check`, `approval-decision`, and `approval-apply --approve`.

Readiness now has `--workflow-import-smoke`, which imports a synthetic BotMux result and runs `approval-check --apply-dry-run --chapter-smoke` without approved llmwiki writes.
