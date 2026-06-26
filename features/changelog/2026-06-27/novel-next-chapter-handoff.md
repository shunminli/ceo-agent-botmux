# Novel Next Chapter Handoff

Added a chapter-to-chapter handoff artifact for foundation-based chapter runs:

```text
runs/{chapter_run_id}/next-chapter-command.json
runs/{chapter_run_id}/next-chapter-command.md
```

Behavior:

- Writes a suggested next chapter number and chapter goal after a completed chapter archive.
- Includes source refs for the current run summary and `runs/archive-{chapter}.json`.
- Emits a ready-to-review `python3 -m botmux_novel chapter` command with `--foundation-json`.
- Adds a `NextChapterHandoff` trace step so the handoff is observable in run history.
- Reuses the same deterministic chapter goal templates as `series`, avoiding duplicated goal text.

This reduces manual path and context assembly after each chapter while preserving human control over the next chapter goal.
