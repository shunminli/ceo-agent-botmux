# Novel Bootstrap Chapter Workflow Command

## Change

- `novel-bootstrap` and `workflow-foundation-import` approval packages now include `next_actions.chapter_workflow_command`.
- The command starts `novel-chapter-production` with `projectSlug`, `title`, compact `storyBible`, `chapterNumber`, `chapterGoal`, `priorContext`, `wordTarget`, and `mode` derived from the approved foundation.
- `approval-package.schema.json` and `approval-check` now require and validate the BotMux chapter workflow command.

## Impact

- After Story Bible approval, operators no longer need to manually assemble the first real three-bot chapter workflow command.
- The existing `next_actions.chapter_start_command` remains available for local runtime smoke checks.
