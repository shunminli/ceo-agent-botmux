# Novel llmwiki Local Setup

Documented an optional local `lucasastorian/llmwiki` setup for the novel production environment.

## Local Paths

- Repository copy: `$HOME/.local/opt/llmwiki`
- PATH wrapper: `$HOME/.local/bin/llmwiki`
- Python runtime: `$HOME/.local/opt/llmwiki/.venv/bin/python`

The CLI entrypoint should be pinned to the venv Python so both the PATH wrapper and `llmwiki mcp-config` output can run without relying on the system Python.

## Verification

- `llmwiki --help` works.
- `llmwiki init`, `llmwiki mcp-config`, and `llmwiki reindex` work on a temporary local workspace.
- `llmwiki serve` starts both the local API and web server on a temporary workspace and is terminated after the smoke check.
- `python3 -m botmux_novel readiness --series-smoke --smoke-chapter-count 20` should return `ready` when the local dependencies are available.

The repository still does not auto-install llmwiki or call MCP write tools without a humanGate-approved write plan.
