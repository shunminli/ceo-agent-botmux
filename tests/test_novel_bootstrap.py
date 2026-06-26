from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from botmux_novel import NovelBootstrapper, NovelBootstrapRequest


class NovelBootstrapTest(unittest.TestCase):
    def test_bootstrap_creates_approval_package_without_llmwiki_writes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            project = root / "novel-project"
            workspace = root / "llmwiki-workspace"
            fake_llmwiki = root / "llmwiki"
            fake_llmwiki.write_text("#!/bin/sh\necho planned \"$@\"\n", encoding="utf-8")
            fake_llmwiki.chmod(0o755)

            result = NovelBootstrapper().bootstrap(
                NovelBootstrapRequest(
                    project_path=project,
                    title="影钟旧案",
                    inspiration="一个背负旧案污名的少年，在巡夜钟声中发现妹妹影子会说真话。",
                    project_slug="shadow-clock-case",
                    workspace_path=workspace,
                    llmwiki_bin=str(fake_llmwiki),
                )
            )

            self.assertEqual(result.status, "ready")
            self.assertTrue(result.foundation.foundation_path.exists())
            self.assertTrue((result.wiki_bundle.bundle_path / "overview.md").exists())
            self.assertEqual(result.llmwiki_sync.status, "planned")
            self.assertFalse(result.llmwiki_sync.approved)
            self.assertTrue(result.llmwiki_sync.plan_path.exists())
            self.assertTrue(any(command.status == "planned" for command in result.llmwiki_sync.commands))
            self.assertFalse((workspace / "wiki/novels/shadow-clock-case/overview.md").exists())
            self.assertEqual(result.mcp_config.server_name, "llmwiki-novel-shadow-clock-case")
            self.assertTrue(result.approval_package_path.exists())
            self.assertTrue(result.approval_package_json_path.exists())

            package = json.loads(result.approval_package_json_path.read_text(encoding="utf-8"))
            self.assertEqual(package["status"], "ready_for_human_review")
            self.assertEqual(package["human_gate"]["decision"], "approve|request_changes|reject")
            self.assertIn("--approve", package["human_gate"]["approved_write_command"])
            self.assertIn("--lint", package["human_gate"]["approved_write_command"])
            self.assertIn("--llmwiki-bin", package["human_gate"]["approved_write_command"])
            self.assertIn(str(fake_llmwiki), package["human_gate"]["approved_write_command"])
            self.assertIn("approval-decision", package["human_gate"]["approval_decision_command"])
            self.assertIn("--decision", package["human_gate"]["approval_decision_command"])
            self.assertIn(str(result.approval_package_json_path), package["human_gate"]["approval_decision_command"])
            self.assertIn("approval-apply", package["human_gate"]["approval_apply_command"])
            self.assertIn(str(result.approval_package_json_path), package["human_gate"]["approval_apply_command"])
            self.assertIn("chapter", package["next_actions"]["chapter_start_command"])
            self.assertIn("--foundation-json", package["next_actions"]["chapter_start_command"])
            self.assertIn(str(result.foundation.foundation_path), package["next_actions"]["chapter_start_command"])
            self.assertEqual(package["llmwiki"]["preview"]["page_count"], 12)
            package_markdown = result.approval_package_path.read_text(encoding="utf-8")
            self.assertIn("# Novel Bootstrap Approval Package", package_markdown)
            self.assertIn("Record approval decision command", package_markdown)
            self.assertIn("Preferred approval apply command", package_markdown)
            self.assertIn("Underlying approved write command", package_markdown)
            self.assertIn("Start opening chapter command", package_markdown)

            chapter = subprocess.run(
                package["next_actions"]["chapter_start_command"],
                check=True,
                text=True,
                capture_output=True,
            )
            chapter_payload = json.loads(chapter.stdout)
            self.assertEqual(chapter_payload["status"], "completed")
            self.assertEqual(chapter_payload["chapter_id"], "ch-001")
            self.assertTrue((project / "manuscript/final/ch-001.md").exists())

    def test_cli_novel_bootstrap_uses_real_entrypoint(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            project = root / "cli-novel-project"
            workspace = root / "cli-llmwiki-workspace"
            fake_llmwiki = root / "llmwiki"
            fake_llmwiki.write_text("#!/bin/sh\necho planned \"$@\"\n", encoding="utf-8")
            fake_llmwiki.chmod(0o755)

            completed = subprocess.run(
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

            payload = json.loads(completed.stdout)
            self.assertEqual(payload["status"], "ready")
            self.assertTrue(Path(payload["approval_package_path"]).exists())
            self.assertTrue(Path(payload["approval_package_json_path"]).exists())
            self.assertFalse((workspace / "wiki/novels/shadow-clock-case/overview.md").exists())
            self.assertEqual(payload["llmwiki_sync"]["status"], "planned")


if __name__ == "__main__":
    unittest.main()
