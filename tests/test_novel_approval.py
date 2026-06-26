from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from botmux_novel import (
    NovelApprovalApplier,
    NovelApprovalApplyRequest,
    NovelApprovalDecider,
    NovelApprovalDecisionRequest,
    NovelBootstrapper,
    NovelBootstrapRequest,
)


class NovelApprovalApplyTest(unittest.TestCase):
    def test_approval_apply_dry_run_reads_package_without_workspace_writes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            project = root / "novel-project"
            workspace = root / "llmwiki-workspace"
            fake_llmwiki = write_fake_llmwiki(root / "llmwiki")
            bootstrap = NovelBootstrapper().bootstrap(
                NovelBootstrapRequest(
                    project_path=project,
                    title="影钟旧案",
                    inspiration="少年在旧书楼发现父亲旧案残页。",
                    project_slug="shadow-clock-case",
                    workspace_path=workspace,
                    llmwiki_bin=str(fake_llmwiki),
                )
            )

            result = NovelApprovalApplier().apply(
                NovelApprovalApplyRequest(approval_package_path=bootstrap.approval_package_json_path)
            )

            self.assertEqual(result.status, "planned")
            self.assertFalse(result.approved)
            self.assertEqual(result.llmwiki_sync.status, "planned")
            self.assertFalse((workspace / "wiki/novels/shadow-clock-case/overview.md").exists())

    def test_approval_apply_with_approve_copies_pages_and_reindexes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            project = root / "novel-project"
            workspace = root / "llmwiki-workspace"
            fake_llmwiki = write_fake_llmwiki(root / "llmwiki")
            bootstrap = NovelBootstrapper().bootstrap(
                NovelBootstrapRequest(
                    project_path=project,
                    title="影钟旧案",
                    inspiration="少年在旧书楼发现父亲旧案残页。",
                    project_slug="shadow-clock-case",
                    workspace_path=workspace,
                    llmwiki_bin=str(fake_llmwiki),
                )
            )

            result = NovelApprovalApplier().apply(
                NovelApprovalApplyRequest(
                    approval_package_path=bootstrap.approval_package_json_path,
                    approve=True,
                )
            )

            self.assertEqual(result.status, "completed_with_warnings")
            self.assertTrue(result.approved)
            self.assertTrue((workspace / "wiki/novels/shadow-clock-case/overview.md").exists())
            self.assertTrue(any(command.status == "succeeded" for command in result.init_commands))
            self.assertTrue(command_succeeded(result.llmwiki_sync.commands, "reindex"))
            self.assertTrue(command_succeeded(result.llmwiki_sync.commands, "lint"))
            self.assertTrue(any("humanGate" in warning for warning in result.warnings))

    def test_approval_decision_records_approve_before_apply(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            project = root / "novel-project"
            workspace = root / "llmwiki-workspace"
            fake_llmwiki = write_fake_llmwiki(root / "llmwiki")
            bootstrap = NovelBootstrapper().bootstrap(
                NovelBootstrapRequest(
                    project_path=project,
                    title="影钟旧案",
                    inspiration="少年在旧书楼发现父亲旧案残页。",
                    project_slug="shadow-clock-case",
                    workspace_path=workspace,
                    llmwiki_bin=str(fake_llmwiki),
                )
            )

            decision = NovelApprovalDecider().record(
                NovelApprovalDecisionRequest(
                    approval_package_path=bootstrap.approval_package_json_path,
                    decision="approve",
                    reviewer="director",
                    notes="Story Bible and wiki bundle approved.",
                )
            )
            payload = json.loads(bootstrap.approval_package_json_path.read_text(encoding="utf-8"))

            self.assertEqual(decision.status, "recorded")
            self.assertTrue(decision.markdown_updated)
            self.assertEqual(decision.approval_package_markdown_path, bootstrap.approval_package_path)
            self.assertEqual(payload["human_gate"]["decision"], "approve")
            self.assertEqual(payload["human_gate"]["reviewer"], "director")
            self.assertEqual(payload["human_gate"]["notes"], "Story Bible and wiki bundle approved.")
            self.assertEqual(len(payload["human_gate"]["decision_history"]), 1)
            package_markdown = bootstrap.approval_package_path.read_text(encoding="utf-8")
            self.assertIn("Decision: `approve`", package_markdown)

            result = NovelApprovalApplier().apply(
                NovelApprovalApplyRequest(
                    approval_package_path=bootstrap.approval_package_json_path,
                    approve=True,
                )
            )

            self.assertEqual(result.status, "completed")
            self.assertEqual(result.warnings, [])
            self.assertTrue((workspace / "wiki/novels/shadow-clock-case/overview.md").exists())
            self.assertTrue(command_succeeded(result.llmwiki_sync.commands, "reindex"))
            self.assertTrue(command_succeeded(result.llmwiki_sync.commands, "lint"))

    def test_approval_apply_refuses_recorded_request_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            project = root / "novel-project"
            workspace = root / "llmwiki-workspace"
            fake_llmwiki = write_fake_llmwiki(root / "llmwiki")
            bootstrap = NovelBootstrapper().bootstrap(
                NovelBootstrapRequest(
                    project_path=project,
                    title="影钟旧案",
                    inspiration="少年在旧书楼发现父亲旧案残页。",
                    project_slug="shadow-clock-case",
                    workspace_path=workspace,
                    llmwiki_bin=str(fake_llmwiki),
                )
            )
            NovelApprovalDecider().record(
                NovelApprovalDecisionRequest(
                    approval_package_path=bootstrap.approval_package_json_path,
                    decision="request_changes",
                    reviewer="director",
                    notes="Relationship pressure needs revision.",
                )
            )

            with self.assertRaises(ValueError):
                NovelApprovalApplier().apply(
                    NovelApprovalApplyRequest(
                        approval_package_path=bootstrap.approval_package_json_path,
                        approve=True,
                    )
                )
            self.assertFalse((workspace / "wiki/novels/shadow-clock-case/overview.md").exists())

    def test_cli_approval_apply_uses_real_entrypoint(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            project = root / "cli-novel-project"
            workspace = root / "cli-llmwiki-workspace"
            fake_llmwiki = write_fake_llmwiki(root / "llmwiki")
            bootstrap = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "botmux_novel",
                    "novel-bootstrap",
                    "--project",
                    str(project),
                    "--title",
                    "影钟旧案",
                    "--inspiration",
                    "少年在旧书楼发现父亲旧案残页。",
                    "--project-slug",
                    "shadow-clock-case",
                    "--workspace",
                    str(workspace),
                    "--llmwiki-bin",
                    str(fake_llmwiki),
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            bootstrap_payload = json.loads(bootstrap.stdout)

            decision = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "botmux_novel",
                    "approval-decision",
                    "--approval-package",
                    bootstrap_payload["approval_package_json_path"],
                    "--decision",
                    "approve",
                    "--reviewer",
                    "director",
                    "--notes",
                    "Approved for CLI smoke.",
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            decision_payload = json.loads(decision.stdout)
            self.assertEqual(decision_payload["status"], "recorded")
            self.assertTrue(decision_payload["markdown_updated"])

            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "botmux_novel",
                    "approval-apply",
                    "--approval-package",
                    bootstrap_payload["approval_package_json_path"],
                    "--approve",
                ],
                check=True,
                text=True,
                capture_output=True,
            )

            payload = json.loads(completed.stdout)
            self.assertEqual(payload["status"], "completed")
            self.assertTrue(payload["approved"])
            self.assertTrue(any(command["status"] == "succeeded" for command in payload["init_commands"]))
            self.assertTrue(json_command_succeeded(payload["llmwiki_sync"]["commands"], "reindex"))
            self.assertTrue(json_command_succeeded(payload["llmwiki_sync"]["commands"], "lint"))
            self.assertTrue((workspace / "wiki/novels/shadow-clock-case/overview.md").exists())


def command_succeeded(commands: list, operation: str) -> bool:
    return any(
        command.status == "succeeded"
        and len(command.command) >= 2
        and command.command[1] == operation
        for command in commands
    )


def json_command_succeeded(commands: list, operation: str) -> bool:
    return any(
        command["status"] == "succeeded"
        and len(command["command"]) >= 2
        and command["command"][1] == operation
        for command in commands
    )


def write_fake_llmwiki(path: Path) -> Path:
    path.write_text(
        "#!/bin/sh\n"
        "if [ \"$1\" = \"--help\" ]; then\n"
        "  echo \"usage: llmwiki\"\n"
        "  exit 0\n"
        "fi\n"
        "if [ \"$1\" = \"reindex\" ]; then\n"
        "  echo \"reindexed $2\"\n"
        "  exit 0\n"
        "fi\n"
        "if [ \"$1\" = \"lint\" ]; then\n"
        "  echo \"linted $2\"\n"
        "  exit 0\n"
        "fi\n"
        "exit 0\n",
        encoding="utf-8",
    )
    path.chmod(0o755)
    return path


if __name__ == "__main__":
    unittest.main()
