Date: 2026-06-26

# Novel Workflow Templates

## Summary

Versioned the two BotMux novel workflow definitions in the repository:

- `workflows/novel-story-foundation.workflow.json`
- `workflows/novel-chapter-production.workflow.json`

The templates match the installed copies under `/Users/xiaochen/.botmux/workflows/`.

## Validation

Added `tests/test_novel_workflows.py` to verify:

- expected 3 bot lark app ids,
- required `novel_agent_output_v1` fields,
- humanGate placement before Story Bible and chapter approval packaging,
- matching repository and installed workflow payloads when installed copies are present.

## Boundary

These workflow templates still do not write project files or llmwiki. Long-lived writes remain gated by human approval.
