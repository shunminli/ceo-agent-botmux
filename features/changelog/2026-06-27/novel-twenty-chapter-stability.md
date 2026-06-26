# Novel Twenty Chapter Stability Baseline

Added a 20-chapter local stability regression for `NovelSeriesRunner`.

## Baseline

- `chapter_count`: 20
- `completed_chapter_count`: 20
- `p0_p1_issue_count`: 0
- `archive_completion_rate`: 1.0
- `prior_context_rate`: 1.0

This verifies that deterministic local chapter production can carry prior archive context, final manuscript files, and archive records across a longer run than the default 5-chapter smoke.

## Command Evidence

```bash
python3 -m botmux_novel readiness --series-smoke --smoke-chapter-count 20
```

With the local llmwiki install in place, the readiness result for this command is `ready`; BotMux assets, bot configs, workflow validation, workflow bindings, llmwiki availability, and the 20-chapter series smoke pass.

This is still a runtime stability baseline, not a real-model literary quality guarantee.
