from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from botmux_novel import BotmuxAssetSyncRequest, BotmuxAssetSyncer, NovelReadinessChecker, NovelReadinessRequest
from botmux_novel.readiness import EXPECTED_NOVEL_BOTS, simulate_workflow_contract, validate_workflow_bindings


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
            self.assertEqual(checks["workflow_contract_smoke"].status, "pass")
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
                {
                    "botmux_assets",
                    "bot_configs",
                    "workflow_validate",
                    "workflow_bindings",
                    "workflow_contract_smoke",
                    "llmwiki",
                },
            )

    def test_bot_config_check_rejects_unexpected_working_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            botmux_home = root / ".botmux"
            install_temp_botmux(botmux_home)

            wrong_dir = root / "wrong-director-workspace"
            wrong_dir.mkdir()
            (wrong_dir / "AGENTS.md").write_text("# Wrong Workspace\n", encoding="utf-8")
            bots_path = botmux_home / "bots.json"
            bots = json.loads(bots_path.read_text(encoding="utf-8"))
            director_app_id = EXPECTED_NOVEL_BOTS["Novel-Director-Curator"]
            for bot in bots:
                if bot.get("larkAppId") == director_app_id:
                    bot["workingDir"] = str(wrong_dir)
            bots_path.write_text(json.dumps(bots, ensure_ascii=False, indent=2), encoding="utf-8")

            check = NovelReadinessChecker()._check_bot_configs(botmux_home=botmux_home)

            self.assertEqual(check.status, "fail")
            self.assertIn("Novel-Director-Curator", check.data["mismatched_working_dirs"])
            director = check.data["matched"]["Novel-Director-Curator"]
            self.assertFalse(director["workingDirMatchesExpected"])
            self.assertTrue(director["workingDirExists"])
            self.assertTrue(director["agentsExists"])

    def test_bot_config_check_rejects_missing_workspace_agents(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            botmux_home = root / ".botmux"
            install_temp_botmux(botmux_home)
            agents_path = botmux_home / "workspace" / "Novel-Continuity-Validator" / "AGENTS.md"
            agents_path.unlink()

            check = NovelReadinessChecker()._check_bot_configs(botmux_home=botmux_home)

            self.assertEqual(check.status, "fail")
            self.assertIn("Novel-Continuity-Validator", check.data["missing_workspace_agents"])
            validator = check.data["matched"]["Novel-Continuity-Validator"]
            self.assertTrue(validator["workingDirMatchesExpected"])
            self.assertTrue(validator["workingDirExists"])
            self.assertFalse(validator["agentsExists"])

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

    def test_workflow_contract_smoke_rejects_missing_required_property_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workflow_path = Path(tmpdir) / "bad-contract.workflow.json"
            workflow_path.write_text(
                json.dumps(
                    {
                        "workflowId": "bad-contract",
                        "params": {"projectSlug": {"type": "string", "required": True}},
                        "nodes": {
                            "source": {
                                "type": "subagent",
                                "prompt": "${params.projectSlug}",
                                "outputSchema": {
                                    "type": "object",
                                    "required": ["preview", "handoff"],
                                    "properties": {"preview": {"type": "string"}},
                                },
                            },
                            "consumer": {
                                "type": "subagent",
                                "depends": ["source"],
                                "prompt": "${source.output.preview}",
                                "outputSchema": {
                                    "type": "object",
                                    "required": ["preview", "handoff"],
                                    "properties": {
                                        "preview": {"type": "string"},
                                        "handoff": {"type": "string"},
                                    },
                                },
                            },
                        },
                    }
                ),
                encoding="utf-8",
            )

            result = simulate_workflow_contract(workflow_path)

            messages = [error["message"] for error in result["errors"]]
            self.assertIn("Required output field has no property schema: handoff", messages)
            self.assertIn("Missing required synthetic output field: handoff", messages)

    def test_workflow_contract_smoke_reports_dependency_cycles(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workflow_path = Path(tmpdir) / "cycle.workflow.json"
            workflow_path.write_text(
                json.dumps(
                    {
                        "workflowId": "cycle",
                        "params": {"projectSlug": {"type": "string", "required": True}},
                        "nodes": {
                            "first": {
                                "type": "subagent",
                                "depends": ["second"],
                                "prompt": "${params.projectSlug}",
                                "outputSchema": {
                                    "type": "object",
                                    "required": ["preview"],
                                    "properties": {"preview": {"type": "string"}},
                                },
                            },
                            "second": {
                                "type": "subagent",
                                "depends": ["first"],
                                "prompt": "${params.projectSlug}",
                                "outputSchema": {
                                    "type": "object",
                                    "required": ["preview"],
                                    "properties": {"preview": {"type": "string"}},
                                },
                            },
                        },
                    }
                ),
                encoding="utf-8",
            )

            result = simulate_workflow_contract(workflow_path)

            messages = [error["message"] for error in result["errors"]]
            self.assertIn("Workflow dependency cycle detected: first -> second -> first", messages)

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

    def test_llmwiki_smoke_runs_approved_sync_lint_and_reindex(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            botmux_home = root / ".botmux"
            fake_botmux = root / "botmux"
            fake_llmwiki = root / "llmwiki"
            install_temp_botmux(botmux_home)
            write_fake_botmux(fake_botmux)
            write_fake_llmwiki(fake_llmwiki)

            result = NovelReadinessChecker().check(
                NovelReadinessRequest(
                    repo_path=REPO_ROOT,
                    botmux_home=botmux_home,
                    botmux_bin=fake_botmux,
                    llmwiki_bin=str(fake_llmwiki),
                    run_llmwiki_smoke=True,
                )
            )

            checks = {check.name: check for check in result.checks}
            self.assertEqual(result.status, "ready")
            self.assertEqual(checks["llmwiki"].status, "pass")
            self.assertEqual(checks["llmwiki_smoke"].status, "pass")
            self.assertEqual(checks["llmwiki_smoke"].data["sync_status"], "completed")
            self.assertEqual(checks["llmwiki_smoke"].data["chapter_id"], "ch-001")
            self.assertTrue(checks["llmwiki_smoke"].data["target_overview_exists"])
            self.assertTrue(checks["llmwiki_smoke"].data["target_chapter_archive_exists"])
            self.assertTrue(checks["llmwiki_smoke"].data["target_chapter_page_exists"])
            self.assertTrue(checks["llmwiki_smoke"].data["index_exists"])
            self.assertTrue(checks["llmwiki_smoke"].data["reindex_succeeded"])
            self.assertTrue(checks["llmwiki_smoke"].data["lint_succeeded"])

    def test_bootstrap_smoke_generates_approval_package_without_workspace_writes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            botmux_home = root / ".botmux"
            fake_botmux = root / "botmux"
            fake_llmwiki = root / "llmwiki"
            install_temp_botmux(botmux_home)
            write_fake_botmux(fake_botmux)
            write_fake_llmwiki(fake_llmwiki)

            result = NovelReadinessChecker().check(
                NovelReadinessRequest(
                    repo_path=REPO_ROOT,
                    botmux_home=botmux_home,
                    botmux_bin=fake_botmux,
                    llmwiki_bin=str(fake_llmwiki),
                    run_bootstrap_smoke=True,
                )
            )

            checks = {check.name: check for check in result.checks}
            self.assertEqual(result.status, "ready")
            self.assertEqual(checks["bootstrap_smoke"].status, "pass")
            self.assertEqual(checks["bootstrap_smoke"].data["llmwiki_sync_status"], "planned")
            self.assertTrue(checks["bootstrap_smoke"].data["approval_package_exists"])
            self.assertTrue(checks["bootstrap_smoke"].data["approval_package_json_exists"])
            self.assertEqual(checks["bootstrap_smoke"].data["approval_check_status"], "ready")
            self.assertIn("apply_dry_run", checks["bootstrap_smoke"].data["approval_check_names"])
            self.assertIn("chapter", checks["bootstrap_smoke"].data["chapter_start_command"])
            self.assertIn("--foundation-json", checks["bootstrap_smoke"].data["chapter_start_command"])
            self.assertIn("novel-chapter-production", checks["bootstrap_smoke"].data["chapter_workflow_command"])
            self.assertTrue(
                any(item.startswith("storyBible=") for item in checks["bootstrap_smoke"].data["chapter_workflow_command"])
            )
            self.assertEqual(checks["bootstrap_smoke"].data["chapter_start_result"]["status"], "completed")
            self.assertTrue(checks["bootstrap_smoke"].data["chapter_start_result"]["final_path_exists"])
            self.assertTrue(checks["bootstrap_smoke"].data["chapter_start_result"]["knowledge_handoff_valid"])
            self.assertFalse(checks["bootstrap_smoke"].data["target_overview_exists"])

    def test_approval_apply_smoke_runs_init_write_lint_and_reindex(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            botmux_home = root / ".botmux"
            fake_botmux = root / "botmux"
            fake_llmwiki = root / "llmwiki"
            install_temp_botmux(botmux_home)
            write_fake_botmux(fake_botmux)
            write_fake_llmwiki(fake_llmwiki)

            result = NovelReadinessChecker().check(
                NovelReadinessRequest(
                    repo_path=REPO_ROOT,
                    botmux_home=botmux_home,
                    botmux_bin=fake_botmux,
                    llmwiki_bin=str(fake_llmwiki),
                    run_approval_apply_smoke=True,
                )
            )

            checks = {check.name: check for check in result.checks}
            self.assertEqual(result.status, "ready")
            self.assertEqual(checks["approval_apply_smoke"].status, "pass")
            self.assertEqual(checks["approval_apply_smoke"].data["decision_status"], "recorded")
            self.assertEqual(checks["approval_apply_smoke"].data["apply_status"], "completed")
            self.assertTrue(checks["approval_apply_smoke"].data["approved"])
            self.assertTrue(checks["approval_apply_smoke"].data["target_overview_exists"])
            self.assertTrue(checks["approval_apply_smoke"].data["index_exists"])
            self.assertTrue(checks["approval_apply_smoke"].data["reindex_succeeded"])
            self.assertTrue(checks["approval_apply_smoke"].data["lint_succeeded"])

    def test_cli_readiness_can_run_llmwiki_smoke(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            botmux_home = root / ".botmux"
            fake_botmux = root / "botmux"
            fake_llmwiki = root / "llmwiki"
            install_temp_botmux(botmux_home)
            write_fake_botmux(fake_botmux)
            write_fake_llmwiki(fake_llmwiki)

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
                    str(fake_llmwiki),
                    "--llmwiki-smoke",
                ],
                check=True,
                text=True,
                capture_output=True,
            )

            payload = json.loads(completed.stdout)
            self.assertEqual(payload["status"], "ready")
            checks = {check["name"]: check for check in payload["checks"]}
            self.assertEqual(checks["llmwiki_smoke"]["status"], "pass")
            self.assertTrue(checks["llmwiki_smoke"]["data"]["lint_succeeded"])
            self.assertTrue(checks["llmwiki_smoke"]["data"]["target_chapter_archive_exists"])
            self.assertTrue(checks["llmwiki_smoke"]["data"]["target_chapter_page_exists"])

    def test_cli_readiness_can_run_bootstrap_smoke(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            botmux_home = root / ".botmux"
            fake_botmux = root / "botmux"
            fake_llmwiki = root / "llmwiki"
            install_temp_botmux(botmux_home)
            write_fake_botmux(fake_botmux)
            write_fake_llmwiki(fake_llmwiki)

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
                    str(fake_llmwiki),
                    "--bootstrap-smoke",
                ],
                check=True,
                text=True,
                capture_output=True,
            )

            payload = json.loads(completed.stdout)
            self.assertEqual(payload["status"], "ready")
            checks = {check["name"]: check for check in payload["checks"]}
            self.assertEqual(checks["bootstrap_smoke"]["status"], "pass")
            self.assertIn("novel-chapter-production", checks["bootstrap_smoke"]["data"]["chapter_workflow_command"])
            self.assertFalse(checks["bootstrap_smoke"]["data"]["target_overview_exists"])

    def test_cli_readiness_can_run_approval_apply_smoke(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            botmux_home = root / ".botmux"
            fake_botmux = root / "botmux"
            fake_llmwiki = root / "llmwiki"
            install_temp_botmux(botmux_home)
            write_fake_botmux(fake_botmux)
            write_fake_llmwiki(fake_llmwiki)

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
                    str(fake_llmwiki),
                    "--approval-apply-smoke",
                ],
                check=True,
                text=True,
                capture_output=True,
            )

            payload = json.loads(completed.stdout)
            self.assertEqual(payload["status"], "ready")
            checks = {check["name"]: check for check in payload["checks"]}
            self.assertEqual(checks["approval_apply_smoke"]["status"], "pass")
            self.assertTrue(checks["approval_apply_smoke"]["data"]["target_overview_exists"])
            self.assertTrue(checks["approval_apply_smoke"]["data"]["lint_succeeded"])

    def test_cli_readiness_can_run_workflow_import_smoke(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            botmux_home = root / ".botmux"
            fake_botmux = root / "botmux"
            fake_llmwiki = root / "llmwiki"
            install_temp_botmux(botmux_home)
            write_fake_botmux(fake_botmux)
            write_fake_llmwiki(fake_llmwiki)

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
                    str(fake_llmwiki),
                    "--workflow-import-smoke",
                ],
                check=True,
                text=True,
                capture_output=True,
            )

            payload = json.loads(completed.stdout)
            self.assertEqual(payload["status"], "ready")
            checks = {check["name"]: check for check in payload["checks"]}
            self.assertEqual(checks["workflow_import_smoke"]["status"], "pass")
            self.assertEqual(checks["workflow_import_smoke"]["data"]["approval_check_status"], "ready")
            self.assertIn("apply_dry_run", checks["workflow_import_smoke"]["data"]["approval_check_names"])
            self.assertIn("chapter_smoke", checks["workflow_import_smoke"]["data"]["approval_check_names"])
            self.assertFalse(checks["workflow_import_smoke"]["data"]["target_overview_exists"])

    def test_cli_readiness_can_run_chapter_import_smoke(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            botmux_home = root / ".botmux"
            fake_botmux = root / "botmux"
            fake_llmwiki = root / "llmwiki"
            install_temp_botmux(botmux_home)
            write_fake_botmux(fake_botmux)
            write_fake_llmwiki(fake_llmwiki)

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
                    str(fake_llmwiki),
                    "--chapter-import-smoke",
                ],
                check=True,
                text=True,
                capture_output=True,
            )

            payload = json.loads(completed.stdout)
            self.assertEqual(payload["status"], "ready")
            checks = {check["name"]: check for check in payload["checks"]}
            self.assertEqual(checks["chapter_import_smoke"]["status"], "pass")
            self.assertEqual(checks["chapter_import_smoke"]["data"]["result_status"], "completed")
            self.assertTrue(checks["chapter_import_smoke"]["data"]["final_path_exists"])
            self.assertTrue(checks["chapter_import_smoke"]["data"]["archive_path_exists"])
            self.assertTrue(checks["chapter_import_smoke"]["data"]["next_command_path_exists"])
            self.assertTrue(checks["chapter_import_smoke"]["data"]["knowledge_handoff_valid"])


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


def write_fake_llmwiki(path: Path) -> None:
    path.write_text(
        "#!/bin/sh\n"
        "if [ \"$1\" = \"--help\" ]; then\n"
        "  echo \"usage: llmwiki\"\n"
        "  exit 0\n"
        "fi\n"
        "if [ \"$1\" = \"init\" ]; then\n"
        "  mkdir -p \"$2/.llmwiki\" \"$2/wiki\"\n"
        "  : > \"$2/.llmwiki/index.db\"\n"
        "  echo \"initialized $2\"\n"
        "  exit 0\n"
        "fi\n"
        "if [ \"$1\" = \"reindex\" ]; then\n"
        "  test -f \"$2/.llmwiki/index.db\" || exit 3\n"
        "  echo \"reindexed $2\"\n"
        "  exit 0\n"
        "fi\n"
        "if [ \"$1\" = \"lint\" ]; then\n"
        "  echo \"linted $2\"\n"
        "  exit 0\n"
        "fi\n"
        "echo \"unexpected llmwiki command\" >&2\n"
        "exit 1\n",
        encoding="utf-8",
    )
    path.chmod(0o755)


if __name__ == "__main__":
    unittest.main()
