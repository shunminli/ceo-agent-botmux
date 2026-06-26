Updated: 2026-06-27

# Novel Approval Schema Type Checks

Extended the local schema validator beyond required-field checks for approval packages.

`approval-package.schema.json` now guards both required paths and basic JSON types through:

- `novel-bootstrap` before writing approval packages.
- `approval-check` before semantic package checks.
- `approval-decision` before recording humanGate decisions.
- `approval-apply` before dry-run or approved llmwiki sync.

The validator remains dependency-free and supports the schema subset used in this repository: `object`, `array`, `string`, `number`, `integer`, `boolean`, `null`, and simple union types.

This catches malformed package shapes such as stringified command fields where arrays are required.
