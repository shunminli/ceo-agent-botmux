# Novel Local Chapter Workflow Handoff

## Change

- Local `python3 -m botmux_novel chapter` now writes a BotMux `novel-chapter-production` workflow command into `runs/{run_id}/next-chapter-command.json|md`.
- The generated workflow command carries the next chapter goal, compact Story Bible, inferred project slug, word target, mode, and archive-derived `priorContext`.
- Shared Story Bible compression and chapter workflow command construction live in `botmux_novel/workflow_commands.py`.

## Impact

- A project can use local runtime for smoke or fallback chapters, then switch back to the real three-bot chapter workflow without manually rebuilding `priorContext`.
- The existing local runtime command remains available in the same handoff artifact.
