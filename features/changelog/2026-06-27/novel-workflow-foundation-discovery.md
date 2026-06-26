# Novel Workflow Foundation Discovery

## Change

- Default foundation discovery now includes both local `runs/foundation-*/foundation.json` and imported `runs/workflow-foundation-*/foundation.json` files.
- `python3 -m botmux_novel chapter` and `wiki-bundle` can continue from a `workflow-foundation-import` result without requiring `--foundation-json`.
- `chapter-workflow-import` now discovers the project foundation for generated local continuation and knowledge handoff commands when the caller omits `--foundation-json`.

## Impact

- The real BotMux opening workflow path can flow into local chapter smoke, chapter imports, and wiki bundle review commands without manual path reconstruction.
