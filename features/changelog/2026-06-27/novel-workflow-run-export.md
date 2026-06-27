# Novel Workflow Run Export

## Change

- Added `python3 -m botmux_novel workflow-export`.
- The exporter reads BotMux workflow `events.ndjson`, `workflow.json`, and event blob refs, or falls back to `botmux workflow tail <runId> --json`.
- Exported JSON preserves `runId`, `workflowId`, `status`, `params`, node outputs, and failure details.

## Impact

- Real `novel-story-foundation` and `novel-chapter-production` runs can be bridged into `workflow-foundation-import` and `chapter-workflow-import` without manually assembling result JSON.
- Failed echo or contract-broken workflow runs remain inspectable because exported nodes and errors are preserved instead of hidden.
