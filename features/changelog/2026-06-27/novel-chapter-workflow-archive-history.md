# Novel Chapter Workflow Archive History

## Change

- `chapter-workflow-import` now rebuilds `project.yaml.archived_chapters` from `runs/archive-*.json`.
- Multi-chapter workflow imports preserve earlier archived chapters instead of replacing the list with only the latest chapter.

## Impact

- Project state remains consistent with local archive files after consecutive real workflow imports.
- Wiki bundle and prior-context loading already use archive files, so this aligns project status with the authoritative archive snapshots.
