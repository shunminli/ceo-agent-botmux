# Schema Enum Range Validation

## Change

- The dependency-free schema validator now checks `enum`, `minimum`, and `maximum` constraints.
- Runtime, workflow foundation import, and chapter workflow import now use full `validate_schema` for stable structured artifacts instead of required-field-only validation.
- Tests cover invalid `project-state.mode` and too-small `word_target` failures.

## Impact

- Declared schema constraints now protect run traces, project state, chapter blueprints, fact snapshots, foreshadowing ledger items, character state, and next-chapter handoffs at write time.
- Invalid modes, run statuses, risk labels, or target lengths fail early instead of leaking into project files.
