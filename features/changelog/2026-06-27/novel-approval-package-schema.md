Updated: 2026-06-27

# Novel Approval Package Schema

Added `schemas/approval-package.schema.json` and recursive required-field validation in `botmux_novel.schema_validation`.

`python3 -m botmux_novel approval-check` now validates the approval package against this schema before running its semantic checks. This catches missing nested fields such as:

- `project.project_path`
- `review_materials.foundation_json`
- `human_gate.approval_apply_command`
- `llmwiki.preview.pages`
- `llmwiki.mcp_config.role_bindings`
- `next_actions.chapter_start_command`

The schema is intentionally dependency-free. It now enforces the repository's stable `required` contracts and basic JSON types. Semantic checks still verify command wiring, file existence, MCP role boundaries, planned llmwiki state, and optional dry-run/chapter smoke behavior.
