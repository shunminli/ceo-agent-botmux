# Novel Role Operating Principles

## Context

Recent novel production work exposed recurring risks: role outputs could follow process templates while missing the user's real objective, Creative could over-trust a connected but unusable Doubao app state, and "remember this principle" requests needed a clearer boundary between role rules, project memory, canon, and one-off task notes.

## Change Summary

- `Novel-Director-Curator` now has an explicit first-principles decision rule: start from user goal, reader experience, hard constraints, source of truth, success criteria, and the smallest effective path before applying process templates.
- For Fanqie novel projects, `Novel-Director-Curator` now treats reader satisfaction and "shuangwen" payoff as the first creative test: process correctness, setting consistency, and workflow completeness must serve reader pleasure, commercial click-through, completion, and platform fit.
- `Novel-Creative-Architect` and `Novel-Continuity-Validator` now carry the same Fanqie shuangwen-first operating rule in their role identities: Creative must build toward clear pressure, satisfying counteraction, visible reward, credible cost, and hooks; Validator must fail or revise logically correct chapters when reader pleasure and follow-through are weak.
- `Novel-Creative-Architect` now prefers direct `botmux_doubao` CDP calls for Creative Assist work, requires real `status` and `ask` evidence before declaring Doubao CLI usable, and keeps OpenCLI app mode as a fallback.
- Creative and Validator role identities now require "principle deposition" classification before claiming something is remembered or writing it into longer-lived project artifacts.
- `Novel-Director-Curator` now has a Human Review Delivery Gate: any user review or approval request must send the unified review document as a file attachment, include necessary candidate/comparison materials, and pass an explicit attachment/impact/approval-text checklist; paths or summaries alone are not considered a completed review delivery.

## Impact Surface

- Novel planning, delegation, review, and handoff behavior.
- Human review and approval delivery in BotMux/Lark topics.
- Creative Assist Tool usage through `botmux_doubao`.
- Future updates to role identity source files and generated workspace `AGENTS.md` files.

## Notes / Compatibility

Single-novel canon, project facts, chapter prohibitions, and publish artifacts still belong in each novel project directory rather than this repository's shared role identities.

## Related Docs

- `agents/novel-director-curator.identity.md`
- `agents/novel-creative-architect.identity.md`
- `agents/novel-continuity-validator.identity.md`
