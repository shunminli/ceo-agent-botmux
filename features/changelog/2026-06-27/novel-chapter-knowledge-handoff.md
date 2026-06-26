# Novel Chapter Knowledge Handoff

## Change

- Chapter completion handoffs now include `knowledge_handoff` commands.
- The handoff provides a reviewable `wiki-bundle` command, a dry-run `llmwiki-sync --reindex --lint` plan command, and a humanGate-only approved sync command.
- Both local `python3 -m botmux_novel chapter` runs and `chapter-workflow-import` outputs emit the same knowledge handoff shape.
- Readiness bootstrap and chapter-import smoke checks verify the knowledge handoff exists and that the dry-run sync command does not include `--approve`.

## Impact

- After a chapter is archived, the next operator can update the wiki review bundle and generate the llmwiki sync plan without reconstructing commands manually.
- Long-term llmwiki writes remain gated; the approved sync command is present for review but is not run automatically.
