# Novel Story Workflow Command

## Change

- Added `python3 -m botmux_novel workflow-foundation-command`.
- The command outputs reviewable JSON with `params`, `command`, and shell-safe `command_text` for `botmux workflow run novel-story-foundation`.
- Added tests for the command builder and real CLI entrypoint.

## Impact

- Real three-bot story foundation runs no longer require manually assembling BotMux `--param` arguments.
- The opening workflow path is now explicit: generate command, run it after review, export the run with `workflow-export`, then import with `workflow-foundation-import`.
