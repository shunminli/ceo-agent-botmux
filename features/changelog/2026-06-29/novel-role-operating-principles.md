# Novel Role Operating Principles

## Context

Recent novel production work exposed recurring risks: role outputs could follow process templates while missing the user's real objective, Creative could over-trust a connected but unusable Doubao app state, and "remember this principle" requests needed a clearer boundary between role rules, project memory, canon, and one-off task notes.

## Change Summary

- `Novel-Director-Curator` now has an explicit first-principles decision rule: start from user goal, reader experience, hard constraints, source of truth, success criteria, and the smallest effective path before applying process templates.
- `Novel-Creative-Architect` now prefers direct `botmux_doubao` CDP calls for Creative Assist work, requires real `status` and `ask` evidence before declaring Doubao CLI usable, and keeps OpenCLI app mode as a fallback.
- Creative and Validator role identities now require "principle deposition" classification before claiming something is remembered or writing it into longer-lived project artifacts.

## Impact Surface

- Novel planning, delegation, review, and handoff behavior.
- Creative Assist Tool usage through `botmux_doubao`.
- Future updates to role identity source files and generated workspace `AGENTS.md` files.

## Notes / Compatibility

Single-novel canon, project facts, chapter prohibitions, and publish artifacts still belong in each novel project directory rather than this repository's shared role identities.

## Related Docs

- `agents/novel-director-curator.identity.md`
- `agents/novel-creative-architect.identity.md`
- `agents/novel-continuity-validator.identity.md`
