# Novel llmwiki MCP Config

Added a project-scoped llmwiki MCP config generator:

```bash
python3 -m botmux_novel llmwiki-mcp-config \
  --workspace /path/to/novel-project \
  --project-slug <slug>
```

The command outputs:

- Standard `mcpServers` JSON shaped like `llmwiki mcp-config`.
- Codex `[mcp_servers.<name>]` TOML snippet.
- Role binding policy for the three novel bots.
- humanGate rules for Director-owned llmwiki writes.

The generator does not edit `~/.codex/config.toml` or BotMux global config. The intended binding remains minimal: Director gets gated read/write access, Validator gets read-only access, and Creative does not directly connect to llmwiki MCP.
