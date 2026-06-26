# Schema Array Items Validation

## Change

- The dependency-free schema validator now recursively checks `items` schemas for arrays, including item object `required` fields.
- `next-chapter-command.schema.json` now declares string items for command arrays and `source_refs`.
- Tests cover item type failures such as `workflow_command[1] expected string` and object item required failures such as `edges[0].target`.

## Impact

- Handoff commands and source references cannot silently pass schema validation with non-string array elements.
- Existing schema files with `items` definitions now get the element-level type and required-field validation their contracts describe.
