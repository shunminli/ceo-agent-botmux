from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from botmux_novel import BotmuxAssetSyncRequest, BotmuxAssetSyncer, NovelReadinessChecker, NovelReadinessRequest
from botmux_novel.readiness import EXPECTED_NOVEL_BOTS, validate_workflow_bindings


REPO_ROOT = Path(__file__).resolve().parents[1]


class NovelReadinessTest(unittest.TestCase):
    def test_readiness_checks_temp_botmux_home_and_series_smoke(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            botmux_home = root / ".botmux"
            fake_botmux = root / "botmux"
            install_temp_botmux(botmux_home)
            write_fake_botmux(fake_botmux)

            result = NovelReadinessChecker().check(
                NovelReadinessRequest(
                    repo_path=REPO_ROOT,
                    botmux_home=botmux_home,
                    botmux_bin=fake_botmux,
                    llmwiki_bin="llmwiki-missing-for-test",
                    run_series_smoke=True,
                    smoke_chapter_count=2,
                )
            )

            self.assertEqual(result.status, "ready_with_warnings")
            checks = {check.name: check for check in result.checks}
            self.assertEqual(checks["botmux_assets"].status, "pass")
            self.assertEqual(checks["bot_configs"].status, "pass")
            self.assertEqual(checks["workflow_validate"].status, "pass")
            self.assertEqual(checks["workflow_bindings"].status, "pass")
            self.assertEqual(checks["llmwiki"].status, "warn")
            self.assertEqual(checks["series_smoke"].status, "pass")
            self.assertEqual(checks["series_smoke"].data["metrics"]["chapter_count"], 2)

    def test_cli_readiness_uses_real_entrypoint(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            botmux_home = root / ".botmux"
            fake_botmux = root / "botmux"
            install_temp_botmux(botmux_home)
            write_fake_botmux(fake_botmux)

            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "botmux_novel",
                    "readiness",
                    "--repo",
                    str(REPO_ROOT),
                    "--botmux-home",
                    str(botmux_home),
                    "--botmux-bin",
                    str(fake_botmux),
                    "--llmwiki-bin",
                    "llmwiki-missing-for-test",
                ],
                check=True,
                text=True,
                capture_output=True,
            )

            payload = json.loads(completed.stdout)
            self.assertEqual(payload["status"], "ready_with_warnings")
            self.assertEqual(
                {check["name"] for check in payload["checks"]},
                {"botmux_assets", "bot_configs", "workflow_validate", "workflow_bindings", "llmwiki"},
            )

    def test_workflow_binding_validator_rejects_unknown_refs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workflow_path = Path(tmpdir) / "bad.workflow.json"
            workflow_path.write_text(
                json.dumps(
                    {
                        "workflowId": "bad-workflow",
                        "params": {"projectSlug": {"type": "string"}},
                        "nodes": {
                            "source": {
                                "type": "subagent",
                                "prompt": "${params.projectSlug}",
                                "outputSchema": {
                                    "type": "object",
                                    "properties": {"handoff": {"type": "string"}},
                                },
                            },
                            "consumer": {
                                "type": "subagent",
                                "depends": ["source"],
                                "prompt": "${source.output.missing}\n${params.missing}\n${ghost.output.handoff}\n${unrelated.output.handoff}",
                                "outputSchema": {
                                    "type": "object",
                                    "properties": {"handoff": {"type": "string"}},
                                },
                            },
                            "unrelated": {
                                "type": "subagent",
                                "prompt": "no refs",
                                "outputSchema": {
                                    "type": "object",
                                    "properties": {"handoff": {"type": "string"}},
                                },
                            },
                        },
                    }
                ),
                encoding="utf-8",
            )

            errors = validate_workflow_bindings(workflow_path)

            messages = [error["message"] for error in errors]
            self.assertIn("Unknown output field on source: missing", messages)
            self.assertIn("Unknown workflow param: missing", messages)
            self.assertIn("Unknown upstream node: ghost", messages)
            self.assertIn("Upstream node is not in dependency closure: unrelated", messages)

    def test_llmwiki_check_requires_usable_help_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_llmwiki = Path(tmpdir) / "llmwiki"
            fake_llmwiki.write_text(
                "#!/bin/sh\n"
                "if [ \"$1\" = \"--help\" ]; then\n"
                "  echo \"usage: llmwiki\"\n"
                "  exit 0\n"
                "fi\n"
                "exit 1\n",
                encoding="utf-8",
            )
            fake_llmwiki.chmod(0o755)

            check = NovelReadinessChecker()._check_llmwiki(llmwiki_bin=str(fake_llmwiki))

            self.assertEqual(check.status, "pass")
            self.assertTrue(check.data["available"])
            self.assertTrue(check.data["usable"])


def install_temp_botmux(botmux_home: Path) -> None:
    BotmuxAssetSyncer().sync(BotmuxAssetSyncRequest(repo_path=REPO_ROOT, botmux_home=botmux_home, write=True))
    bots = []
    for role_name, app_id in EXPECTED_NOVEL_BOTS.items():
        bots.append(
            {
                "larkAppId": app_id,
                "cliId": "codex",
                "workingDir": str(botmux_home / "workspace" / role_name),
                "allowedUsers": ["test-user"],
            }
        )
    (botmux_home / "bots.json").write_text(json.dumps(bots, ensure_ascii=False, indent=2), encoding="utf-8")


def write_fake_botmux(path: Path) -> None:
    path.write_text(
        "#!/bin/sh\n"
        "if [ \"$1\" = \"workflow\" ] && [ \"$2\" = \"validate\" ]; then\n"
        "  echo \"workflow valid: $3\"\n"
        "  exit 0\n"
        "fi\n"
        "echo \"unexpected command\" >&2\n"
        "exit 1\n",
        encoding="utf-8",
    )
    path.chmod(0o755)


if __name__ == "__main__":
    unittest.main()
