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
            self.assertTrue(any(command.status == "succeeded" for command in result.llmwiki_sync.commands))
            self.assertTrue(any("humanGate" in warning for warning in result.warnings))

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
            self.assertEqual(payload["status"], "completed_with_warnings")
            self.assertTrue(payload["approved"])
            self.assertTrue(any(command["status"] == "succeeded" for command in payload["init_commands"]))
            self.assertTrue((workspace / "wiki/novels/shadow-clock-case/overview.md").exists())


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
        "exit 0\n",
        encoding="utf-8",
    )
    path.chmod(0o755)
    return path


if __name__ == "__main__":
    unittest.main()
