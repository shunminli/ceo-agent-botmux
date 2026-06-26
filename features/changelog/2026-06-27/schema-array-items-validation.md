# Schema Array Items Validation

## Change

- The dependency-free schema validator now recursively checks `items` schemas for arrays.
- `next-chapter-command.schema.json` now declares string items for command arrays and `source_refs`.
- Tests cover item type failures such as `workflow_command[1] expected string`.

## Impact

- Handoff commands and source references cannot silently pass schema validation with non-string array elements.
- Existing schema files with `items` definitions now get the element-level validation their contracts describe.
