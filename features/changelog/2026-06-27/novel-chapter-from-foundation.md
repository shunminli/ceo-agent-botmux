Date: 2026-06-27

# Novel Chapter From Foundation

## Summary

Added a local chapter production entrypoint:

```bash
python3 -m botmux_novel chapter \
  --project /tmp/novel-demo \
  --chapter-number 1

python3 -m botmux_novel chapter \
  --project /tmp/novel-demo \
  --chapter-number 2 \
  --chapter-goal "让林烬用半张残页验证巡夜钟异常，并把妹妹影子证词转成下一章追查目标。"
```

## Coverage

- Reads an explicit `foundation.json`, or the latest local `runs/foundation-*/foundation.json` / imported `runs/workflow-foundation-*/foundation.json`.
- Updates the current chapter id and approved chapter objective without replanning the Story Bible.
- Defaults `chapter_goal` from `foundation.json` `chapter_goal.objective` when the request omits `--chapter-goal`, so an approved opening foundation can drive the first chapter without manual copy/paste.
- Reuses the existing chapter state machine for blueprint, context pack, draft, review, revision, final, archive, trace, and SQLite run records.
- Writes `runs/{chapter_run_id}/source-foundation.json` to make the chapter run's Story Bible source auditable.

## Boundary

This is a local smoke path for Phase 2. It does not run the BotMux multi-bot workflow, does not call llmwiki, and does not bypass the real workflow humanGate for production use.
