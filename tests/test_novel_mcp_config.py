from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from botmux_novel import NovelLlmwikiMcpConfigBuilder, NovelLlmwikiMcpConfigRequest


class NovelLlmwikiMcpConfigTest(unittest.TestCase):
    def test_mcp_config_generates_codex_and_role_bound_snippets(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            workspace = root / "novel-workspace"
            workspace.mkdir()
            fake_llmwiki = root / "llmwiki"
            fake_llmwiki.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            fake_llmwiki.chmod(0o755)

            result = NovelLlmwikiMcpConfigBuilder().build(
                NovelLlmwikiMcpConfigRequest(
                    workspace_path=workspace,
                    project_slug="shadow-clock-case",
                    llmwiki_bin=str(fake_llmwiki),
                )
            )

            self.assertEqual(result.status, "ready")
            self.assertEqual(result.server_name, "llmwiki-novel-shadow-clock-case")
            self.assertEqual(
                result.mcp_json["mcpServers"][result.server_name],
                {"command": str(fake_llmwiki.resolve()), "args": ["mcp", str(workspace.resolve())]},
            )
            self.assertIn("[mcp_servers.llmwiki-novel-shadow-clock-case]", result.codex_toml)
            self.assertIn(f'command = "{fake_llmwiki.resolve()}"', result.codex_toml)
            self.assertIn(f'args = ["mcp", "{workspace.resolve()}"]', result.codex_toml)

            bindings = {binding["bot"]: binding for binding in result.role_bindings}
            self.assertTrue(bindings["Novel-Director-Curator"]["configure_mcp_server"])
            self.assertIn("create", bindings["Novel-Director-Curator"]["allowed_llmwiki_tools"])
            self.assertFalse(bindings["Novel-Creative-Architect"]["configure_mcp_server"])
            self.assertEqual(bindings["Novel-Creative-Architect"]["allowed_llmwiki_tools"], [])
            self.assertTrue(bindings["Novel-Continuity-Validator"]["configure_mcp_server"])
            self.assertNotIn("edit", bindings["Novel-Continuity-Validator"]["allowed_llmwiki_tools"])
            self.assertIn("humanGate approval", result.human_gate_policy["required_before_writes"])

    def test_mcp_config_returns_warning_when_llmwiki_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = NovelLlmwikiMcpConfigBuilder().build(
                NovelLlmwikiMcpConfigRequest(
                    workspace_path=Path(tmpdir) / "novel-workspace",
                    project_slug="shadow-clock-case",
                    llmwiki_bin="missing-llmwiki-for-test",
                )
            )

            self.assertEqual(result.status, "ready_with_warnings")
            self.assertFalse(result.llmwiki_available)
            self.assertEqual(result.llmwiki_command, "missing-llmwiki-for-test")
            self.assertTrue(result.warnings)

    def test_mcp_config_rejects_unsafe_server_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaisesRegex(ValueError, "server_name must use"):
                NovelLlmwikiMcpConfigBuilder().build(
                    NovelLlmwikiMcpConfigRequest(
                        workspace_path=Path(tmpdir),
                        project_slug="shadow-clock-case",
                        server_name="bad.name",
                    )
                )

    def test_cli_llmwiki_mcp_config_uses_real_entrypoint(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            workspace = root / "novel-workspace"
            workspace.mkdir()
            fake_llmwiki = root / "llmwiki"
            fake_llmwiki.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            fake_llmwiki.chmod(0o755)

            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "botmux_novel",
                    "llmwiki-mcp-config",
                    "--workspace",
                    str(workspace),
                    "--project-slug",
                    "shadow-clock-case",
                    "--llmwiki-bin",
                    str(fake_llmwiki),
                ],
                check=True,
                text=True,
                capture_output=True,
            )

            payload = json.loads(completed.stdout)
            self.assertEqual(payload["status"], "ready")
            self.assertEqual(payload["server_name"], "llmwiki-novel-shadow-clock-case")
            self.assertEqual(payload["mcp_json"]["mcpServers"][payload["server_name"]]["args"], ["mcp", str(workspace.resolve())])
            self.assertIn("[mcp_servers.llmwiki-novel-shadow-clock-case]", payload["codex_toml"])


if __name__ == "__main__":
    unittest.main()
