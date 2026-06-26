Updated: 2026-06-27

# Novel Bot Workspace Binding Readiness

Tightened the novel production readiness gate for the three BotMux story team bots.

`python3 -m botmux_novel readiness` now validates that each configured novel bot:

- Exists in `~/.botmux/bots.json` by expected Lark app id.
- Has a working directory that exists.
- Is bound to the expected `~/.botmux/workspace/{RoleName}` directory.
- Has a workspace `AGENTS.md` identity file at that bound directory.

This prevents a false-ready state where a bot exists but runs from the wrong workspace or without its role identity instructions.
