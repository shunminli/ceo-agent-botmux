# Novel Next Chapter Command Schema

## Change

- Added `schemas/next-chapter-command.schema.json`.
- Local `chapter` and `chapter-workflow-import` now validate next-chapter handoffs before writing `runs/{run_id}/next-chapter-command.json`.
- Tests cover successful handoff schema validation for both production paths and nested required-field failures for `knowledge_handoff`.

## Impact

- The next chapter handoff, BotMux workflow command, `priorContext`, source refs, and wiki sync handoff commands are now guarded by the same dependency-free schema validator used for approval packages.
- Malformed continuation artifacts fail at write time instead of reaching a later operator or workflow step.
