Date: 2026-06-26

# Novel Wiki Bundle Export

## Summary

Added a local wiki export command:

```bash
python -m botmux_novel wiki-bundle \
  --project /tmp/novel-demo \
  --project-slug shadow-clock-case
```

The command reads a local `foundation.json` and writes a reviewable Markdown bundle under:

```text
wiki/novels/{project_slug}/
```

## Boundary

This is not a direct llmwiki write adapter. It does not call external APIs, create remote pages, or mutate llmwiki. The bundle is intended for human review or a later gated write workflow.
