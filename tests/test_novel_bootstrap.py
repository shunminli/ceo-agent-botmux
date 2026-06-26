from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from botmux_novel import NovelApprovalCheckRequest, NovelApprovalPackageChecker, NovelBootstrapper, NovelBootstrapRequest
from botmux_novel.schema_validation import missing_required_fields, schema_validation_errors


class NovelBootstrapTest(unittest.TestCase):
    def test_approval_package_schema_reports_nested_required_fields(self) -> None:
        missing = missing_required_fields(
            "approval-package",
            {
                "run_id": "bootstrap-test",
                "status": "ready_for_human_review",
                "project": {},
                "review_materials": {},
                "human_gate": {},
                "llmwiki": {"preview": {}, "mcp_config": {}},
                "next_actions": {},
                "next_steps": [],
            },
        )

        self.assertIn("project.title", missing)
        self.assertIn("human_gate.approval_apply_command", missing)
        self.assertIn("llmwiki.preview.pages", missing)
        self.assertIn("next_actions.chapter_start_command", missing)

    def test_approval_package_schema_reports_type_errors(self) -> None:
        errors = schema_validation_errors(
            "approval-package",
            {
                "run_id": "bootstrap-test",
                "status": "ready_for_human_review",
                "project": {
                    "title": "影钟旧案",
                    "project_slug": "shadow-clock-case",
                    "project_path": "/tmp/project",
                    "llmwiki_workspace_path": "/tmp/workspace",
                },
                "review_materials": {
                    "foundation_json": "/tmp/project/foundation.json",
                    "story_markdown": "/tmp/project/story.md",
                    "wiki_bundle": "/tmp/project/wiki/novels/shadow-clock-case",
                    "llmwiki_sync_plan": "/tmp/project/runs/sync.json",
                    "mcp_server_name": "llmwiki-novel-shadow-clock-case",
                },
                "human_gate": {
                    "decision": "approve|request_changes|reject",
                    "must_review": [],
                    "approved_write_command": [],
                    "approval_decision_command": [],
                    "approval_apply_command": "python3 -m botmux_novel approval-apply",
                },
                "llmwiki": {
                    "sync_status": "planned",
                    "approved": "false",
                    "preview": {
                        "target_namespace": "/wiki/novels/shadow-clock-case/",
                        "page_count": 12,
                        "pages": [],
                        "action_summary": {},
                    },
                    "mcp_config": {
                        "status": "ready",
                        "project_slug": "shadow-clock-case",
                        "workspace_path": "/tmp/workspace",
                        "server_name": "llmwiki-novel-shadow-clock-case",
                        "role_bindings": [],
                        "human_gate_policy": {},
                    },
                    "warnings": [],
                },
                "next_actions": {"chapter_start_command": []},
                "next_steps": [],
            },
        )

        self.assertIn("human_gate.approval_apply_command expected array", errors)
        self.assertIn("llmwiki.approved expected boolean", errors)

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

            check = NovelApprovalPackageChecker().check(
                NovelApprovalCheckRequest(
                    approval_package_path=result.approval_package_json_path,
                    run_apply_dry_run=True,
                )
            )
            self.assertEqual(check.status, "ready")
            checks = {item.name: item for item in check.checks}
            self.assertEqual(checks["package_json"].status, "pass")
            self.assertEqual(checks["review_materials"].status, "pass")
            self.assertEqual(checks["human_gate"].status, "pass")
            self.assertEqual(checks["llmwiki_preview"].status, "pass")
            self.assertEqual(checks["mcp_policy"].status, "pass")
            self.assertEqual(checks["next_actions"].status, "pass")
            self.assertEqual(checks["workspace_target"].status, "pass")
            self.assertEqual(checks["apply_dry_run"].status, "pass")

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

            check_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "botmux_novel",
                    "approval-check",
                    "--approval-package",
                    payload["approval_package_json_path"],
                    "--apply-dry-run",
                    "--chapter-smoke",
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            check_payload = json.loads(check_completed.stdout)
            self.assertEqual(check_payload["status"], "ready")
            checks = {check["name"]: check for check in check_payload["checks"]}
            self.assertEqual(checks["apply_dry_run"]["status"], "pass")
            self.assertEqual(checks["chapter_smoke"]["status"], "pass")
            self.assertEqual(checks["chapter_smoke"]["data"]["chapter_status"], "completed")

    def test_approval_check_blocks_missing_review_material(self) -> None:
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
                    inspiration="少年在旧书楼发现父亲旧案残页。",
                    project_slug="shadow-clock-case",
                    workspace_path=workspace,
                    llmwiki_bin=str(fake_llmwiki),
                )
            )
            package = json.loads(result.approval_package_json_path.read_text(encoding="utf-8"))
            Path(package["review_materials"]["story_markdown"]).unlink()

            check = NovelApprovalPackageChecker().check(
                NovelApprovalCheckRequest(approval_package_path=result.approval_package_json_path)
            )

            self.assertEqual(check.status, "blocked")
            checks = {item.name: item for item in check.checks}
            self.assertEqual(checks["review_materials"].status, "fail")

    def test_approval_check_blocks_missing_required_nested_package_field(self) -> None:
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
                    inspiration="少年在旧书楼发现父亲旧案残页。",
                    project_slug="shadow-clock-case",
                    workspace_path=workspace,
                    llmwiki_bin=str(fake_llmwiki),
                )
            )
            package = json.loads(result.approval_package_json_path.read_text(encoding="utf-8"))
            del package["human_gate"]["approval_apply_command"]
            result.approval_package_json_path.write_text(
                json.dumps(package, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            check = NovelApprovalPackageChecker().check(
                NovelApprovalCheckRequest(approval_package_path=result.approval_package_json_path)
            )

            self.assertEqual(check.status, "blocked")
            checks = {item.name: item for item in check.checks}
            self.assertEqual(checks["package_json"].status, "fail")
            self.assertIn(
                "Missing required field: human_gate.approval_apply_command",
                checks["package_json"].data["errors"],
            )

    def test_approval_check_blocks_wrong_command_type(self) -> None:
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
                    inspiration="少年在旧书楼发现父亲旧案残页。",
                    project_slug="shadow-clock-case",
                    workspace_path=workspace,
                    llmwiki_bin=str(fake_llmwiki),
                )
            )
            package = json.loads(result.approval_package_json_path.read_text(encoding="utf-8"))
            package["human_gate"]["approval_apply_command"] = "python3 -m botmux_novel approval-apply"
            result.approval_package_json_path.write_text(
                json.dumps(package, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            check = NovelApprovalPackageChecker().check(
                NovelApprovalCheckRequest(approval_package_path=result.approval_package_json_path)
            )

            self.assertEqual(check.status, "blocked")
            checks = {item.name: item for item in check.checks}
            self.assertEqual(checks["package_json"].status, "fail")
            self.assertIn(
                "human_gate.approval_apply_command expected array",
                checks["package_json"].data["errors"],
            )


if __name__ == "__main__":
    unittest.main()
