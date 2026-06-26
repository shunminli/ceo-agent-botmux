# Novel Series Metrics

Added a local Phase 3 series runner:

```bash
python3 -m botmux_novel series \
  --project /tmp/novel-series-demo \
  --title 影钟旧案 \
  --inspiration "一个背负旧案污名的少年，在巡夜钟声中发现妹妹影子会说真话。" \
  --project-slug shadow-clock-case \
  --chapter-count 5
```

## Behavior

- Runs foundation once, then produces consecutive chapters from the approved foundation.
- Uses prior archive context for chapter 2 and later.
- Exports the wiki bundle after the chapter run.
- Optionally runs gated `llmwiki-sync`.
- Writes `runs/{series_run_id}/series-metrics.json`.

## Metrics

- Completed chapter count.
- P0/P1 issue count and full issue severity counts.
- Review decision counts.
- Revision rounds.
- Archive completion rate.
- Prior context coverage rate.
- User modification points, fixed at 0 for local deterministic smoke.
