# Novel Chapter Archive Wiki Bundle

## Change

- `wiki-bundle` now scans local `runs/archive-*.json` files after loading the approved foundation.
- When chapter archives exist, the bundle includes `chapter-archive.md`, `timeline.md`, `character-state.md`, and `chapters/{chapter}.md`.
- Chapter archive pages include archive facts, timeline, foreshadowing, character state, continuity issues, source archive refs, and the local final manuscript when present.

## Guardrails

- Foundation-only projects keep the original base wiki bundle shape and page count.
- `wiki-bundle` still only writes local Markdown under `wiki/novels/{project_slug}/`; external llmwiki writes remain gated by `llmwiki-sync --approve`.
- The local `wiki-lint` path accepts the expanded bundle before sync.
