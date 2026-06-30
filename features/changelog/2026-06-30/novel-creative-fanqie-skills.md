# Novel Creative Fanqie Skills

`Novel-Creative-Architect` now explicitly routes Fanqie writing tasks through three local Codex skills:

- `fanqie-story-engine` for proposed story engines, reader promise, core selling point, character pressure, and first-volume beats.
- `fanqie-chapter-blueprint` for chapter blueprints, scene cards, six-chapter progression packs, payoff rhythm, and next-chapter hooks.
- `fanqie-prose-polish` for chapter drafts, fact-preserving revision, de-AI cleanup, dialogue repair, and mobile readability.

These skills are installed under `~/.codex/skills/` and remain bounded by the existing BotMux novel team contract: Creative proposes, Director owns Story Bible writes, and Validator gates continuity and final readiness.

## Impact

- Creative workspace `AGENTS.md` should be regenerated with `python3 -m botmux_novel botmux-assets --write` after identity changes.
- The skills complement the existing workflow templates instead of replacing project directories or llmwiki gates.
