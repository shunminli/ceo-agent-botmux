# Novel llmwiki Local Install

Installed `lucasastorian/llmwiki` locally for the novel production environment.

## Local Paths

- Repository copy: `/Users/xiaochen/.local/opt/llmwiki`
- PATH wrapper: `/Users/xiaochen/.local/bin/llmwiki`
- Python runtime: `/Users/xiaochen/.local/opt/llmwiki/.venv/bin/python`
- Installed commit: `542561d`

The installed CLI entrypoint is pinned to the venv Python so both the PATH wrapper and `llmwiki mcp-config` output can run without using the system Python 3.9.

## Verification

- `llmwiki --help` works.
- `llmwiki init`, `llmwiki mcp-config`, and `llmwiki reindex` work on a temporary local workspace.
- `llmwiki serve` starts both the local API and web server on a temporary workspace and is terminated after the smoke check.
- `python3 -m botmux_novel readiness --series-smoke --smoke-chapter-count 20` now returns `ready`.

This is a local environment setup. The repository still does not auto-install llmwiki or call MCP write tools without a humanGate-approved write plan.
