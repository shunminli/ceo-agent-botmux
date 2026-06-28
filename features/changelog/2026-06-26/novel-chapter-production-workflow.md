Date: 2026-06-26

# Novel Chapter Production Workflow

## Summary

Added the global BotMux workflow:

- `$HOME/.botmux/workflows/novel-chapter-production.workflow.json`

The workflow keeps the minimal 3 bot organization:

- `Novel-Director-Curator`
- `Novel-Creative-Architect`
- `Novel-Continuity-Validator`

## Flow

1. `chapter_prepare`
2. `chapter_blueprint`
3. `chapter_draft`
4. `continuity_review`
5. `chapter_revision`
6. `director_approval_package`
7. `archive_plan`

`director_approval_package` has a humanGate before packaging the candidate final chapter. The workflow does not write project files or llmwiki; `archive_plan` produces a safe follow-up plan for a later gated write workflow or manual operation.
