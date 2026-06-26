Date: 2026-06-26

# Novel llmwiki Runbook

## Summary

Added `docs/novel-llmwiki-setup.md` to document how the local novel `wiki-bundle` should be connected to `lucasastorian/llmwiki`.

## Coverage

- Recommended using one novel project directory as the llmwiki workspace.
- Documented `foundation`, `wiki-bundle`, `llmwiki open`, and `llmwiki mcp-config` setup order.
- Captured role-specific llmwiki permissions for Director, Creative Architect, and Continuity Validator.
- Defined humanGate write requirements, lint expectations, rollback requirements, and prohibited writes.

## Boundary

The repository still does not install llmwiki or call llmwiki write tools directly. First real writes require user approval of the Story Bible and wiki page list.
