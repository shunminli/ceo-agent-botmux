# Novel llmwiki Sync Adapter

Added a gated local llmwiki workspace sync command:

```bash
python3 -m botmux_novel llmwiki-sync \
  --project /path/to/novel-project \
  --project-slug shadow-clock-case \
  --approve
```

## Behavior

- Reads an already generated `wiki/novels/{project_slug}/` Markdown bundle.
- Without `--approve`, writes only a local `runs/llmwiki-sync-{project_slug}-{timestamp}.json` plan.
- With `--approve`, copies approved Markdown pages into `--workspace/wiki/novels/{project_slug}/`.
- Creates `.bak-{timestamp}` backups before overwriting changed pages unless `--no-backup` is passed.
- Can optionally run `llmwiki reindex <workspace>` with `--reindex` when an llmwiki executable is available.

## Boundaries

This adapter does not install llmwiki and does not call MCP `create/edit/append`. It treats llmwiki's local Markdown workspace as the source-of-truth write target after human approval.
