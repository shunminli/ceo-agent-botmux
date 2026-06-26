# Novel llmwiki Smoke Chapter Archive

## Change

- `python3 -m botmux_novel readiness --llmwiki-smoke` now creates a temporary first chapter before exporting and syncing the wiki bundle.
- The smoke checks that the approved llmwiki workspace contains both the Story Bible pages and chapter archive pages.
- The readiness payload now reports `chapter_id`, `target_chapter_archive_exists`, and `target_chapter_page_exists`.

## Verification Impact

- Approved llmwiki sync smoke now covers `chapter-archive.md` and `chapters/ch-001.md`, not only the foundation-only 12-page bundle.
- Lint and reindex remain part of the same smoke gate.
