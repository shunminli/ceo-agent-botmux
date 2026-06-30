# Novel Director And Validator Fanqie Skills

`Novel-Director-Curator` and `Novel-Continuity-Validator` now have role-specific local Codex skills installed under `~/.codex/skills/`:

- `fanqie-director-curation` for Director intake, context packages, canon status classification, Story Bible candidate curation, write plans, wiki sync previews, and role routing.
- `fanqie-review-package` for one-entry human review packages, approval phrases, impact summaries, rollback paths, and final/publish/llmwiki approval boundaries.
- `fanqie-continuity-gate` for Validator P0/P1/P2/P3 review, adversarial source checks, character motivation, timeline, world rules, foreshadowing, and canon status pollution.
- `fanqie-rhythm-audit` for chapter net word counts, Fanqie serial rhythm, pressure-counteraction-payoff-hook checks, repeated mechanism fatigue, merge/split recommendations, and six-chapter progression health.

The skills are intentionally lighter than third-party web-novel toolboxes: they do not introduce an alternate project layout, do not write canon, and do not bypass Director/Creative/Validator boundaries.

## Impact

- `Novel-Director-Curator` and `Novel-Continuity-Validator` workspace `AGENTS.md` files should be regenerated with `python3 -m botmux_novel botmux-assets --write`.
- Validator remains read-only for Story Bible, llmwiki, final manuscript, and publish assets; Director still requires preview, impact surface, rollback path, and humanGate before durable writes.
