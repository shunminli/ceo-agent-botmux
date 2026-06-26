# Novel Chapter Workflow Prior Context Handoff

## Change

- `chapter-workflow-import` next-chapter handoff now carries the imported chapter archive into the next BotMux workflow command.
- The generated `workflow_command` includes `chapterGoal`, `priorContext`, `wordTarget`, and `mode`.
- When `--foundation-json` is supplied, the local runtime handoff command also includes `--chapter-goal` so it does not repeat the foundation's initial chapter goal.

## Impact

- Real `novel-chapter-production` continuation can start from the previous chapter's facts, timeline, foreshadowing, character state, and continuity issues without manual parameter reconstruction.
- The handoff remains reviewable in `runs/{workflow_chapter_run_id}/next-chapter-command.md|json` before any follow-up workflow is launched.
