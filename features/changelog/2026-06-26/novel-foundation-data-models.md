Date: 2026-06-26

# Novel Foundation Data Models

## Summary

The local novel runtime now emits structured foundation assets for the minimal novel agent team:

- `characters/relationships.json`
- `settings/scenes.json`
- `settings/style-profile.json`
- `tracking/foreshadowing.yaml` with stable `id` and `status` fields

## Schemas

Added required-field schemas for:

- `relationship-map.schema.json`
- `scene-setting.schema.json`
- `style-profile.schema.json`
- `foreshadowing-ledger.schema.json`

These schemas keep the P0 runtime aligned with the Story Bible / llmwiki sync plan without adding dependencies or changing the CLI contract.
