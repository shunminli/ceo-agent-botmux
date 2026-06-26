Date: 2026-06-26

# Novel BotMux Assets Sync

## Summary

Added a reproducible BotMux asset sync entrypoint:

```bash
python3 -m botmux_novel botmux-assets
python3 -m botmux_novel botmux-assets --write
```

## Coverage

- Syncs versioned workflow templates from `workflows/` into `~/.botmux/workflows/`.
- Generates the three novel bot workspace `AGENTS.md` files from `agents/*.identity.md`.
- Adds a BotMux workspace header and development closure principles to each generated `AGENTS.md`.
- Defaults to dry-run; `--write` is required to modify `~/.botmux`.
- Backs up changed workspace `AGENTS.md` files as `AGENTS.md.bak-<timestamp>`.

## Local State

The local BotMux environment has been synchronized. The two workflow files were already unchanged; the three novel bot workspace `AGENTS.md` files were updated with backups.

## Boundary

This command does not run a novel workflow and does not write project files or llmwiki. It only syncs local BotMux operational assets.
