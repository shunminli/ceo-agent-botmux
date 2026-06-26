from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from botmux_novel import NovelFoundationRequest, NovelRunRequest, NovelRuntime, NovelWikiBundleRequest
from botmux_novel.agents import BlueprintAgent, ConsistencyAgent, ContextPackBuilder, DirectorAgent


class NovelRuntimeTest(unittest.TestCase):
    def test_foundation_creates_opening_assets_without_manuscript(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir) / "foundation-novel"
            result = NovelRuntime().foundation(
                NovelFoundationRequest(
                    project_path=project,
                    title="影钟旧案",
                    inspiration="一个背负旧案污名的少年，在巡夜钟声中发现妹妹影子会说真话。",
                )
            )

            self.assertEqual(result.status, "completed")
            self.assertTrue((project / "story.md").exists())
            self.assertTrue((project / "characters/relationships.json").exists())
            self.assertTrue((project / "settings/scenes.json").exists())
            self.assertTrue((project / "settings/style-profile.json").exists())
            self.assertTrue(result.foundation_path.exists())
            self.assertTrue(result.trace_path.exists())
            self.assertTrue(result.sqlite_path.exists())
            self.assertFalse((project / "manuscript/draft/ch-001.md").exists())
            self.assertFalse((project / "manuscript/final/ch-001.md").exists())

            trace = json.loads(result.trace_path.read_text(encoding="utf-8"))
            self.assertEqual(trace["status"], "completed")
            self.assertEqual([step["stage"] for step in trace["steps"]], ["Foundation"])

    def test_wiki_bundle_exports_reviewable_markdown_from_foundation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir) / "wiki-novel"
            foundation = NovelRuntime().foundation(
                NovelFoundationRequest(
                    project_path=project,
                    title="影钟旧案",
                    inspiration="一个背负旧案污名的少年，在巡夜钟声中发现妹妹影子会说真话。",
                )
            )

            result = NovelRuntime().wiki_bundle(
                NovelWikiBundleRequest(
                    project_path=project,
                    project_slug="shadow-clock-case",
                    foundation_path=foundation.foundation_path,
                )
            )

            self.assertEqual(result.status, "completed")
            self.assertTrue((result.bundle_path / "overview.md").exists())
            self.assertTrue((result.bundle_path / "story-bible.md").exists())
            self.assertTrue((result.bundle_path / "characters/protagonist.md").exists())
            self.assertTrue((result.bundle_path / "relationships.md").exists())
            self.assertTrue((result.bundle_path / "world-scenes.md").exists())
            self.assertTrue((result.bundle_path / "sync-plan.md").exists())
            sync_plan = (result.bundle_path / "sync-plan.md").read_text(encoding="utf-8")
            self.assertIn("/wiki/novels/shadow-clock-case/", sync_plan)

    def test_wiki_bundle_rejects_unsafe_project_slug(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir) / "wiki-novel"
            foundation = NovelRuntime().foundation(
                NovelFoundationRequest(
                    project_path=project,
                    title="影钟旧案",
                    inspiration="一个背负旧案污名的少年，在巡夜钟声中发现妹妹影子会说真话。",
                )
            )

            with self.assertRaisesRegex(ValueError, "project_slug must use"):
                NovelRuntime().wiki_bundle(
                    NovelWikiBundleRequest(
                        project_path=project,
                        project_slug="../escape",
                        foundation_path=foundation.foundation_path,
                    )
                )

    def test_runtime_creates_full_chapter_workspace_and_trace(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir) / "demo-novel"
            result = NovelRuntime().run(
                NovelRunRequest(
                    project_path=project,
                    title="影钟旧案",
                    inspiration="一个背负旧案污名的少年，在巡夜钟声中发现妹妹影子会说真话。",
                )
            )

            self.assertEqual(result.status, "completed")
            self.assertTrue((project / "project.yaml").exists())
            self.assertTrue((project / "characters/relationships.json").exists())
            self.assertTrue((project / "settings/scenes.json").exists())
            self.assertTrue((project / "settings/style-profile.json").exists())
            self.assertTrue((project / "outline/chapter-blueprints/ch-001.json").exists())
            self.assertTrue((project / "manuscript/draft/ch-001.md").exists())
            self.assertTrue((project / "manuscript/revised/ch-001.md").exists())
            self.assertTrue((project / "manuscript/final/ch-001.md").exists())
            self.assertTrue((project / "tracking/facts.yaml").exists())
            self.assertTrue((project / "tracking/foreshadowing.yaml").exists())
            self.assertTrue((project / "tracking/character-state.yaml").exists())
            self.assertTrue(result.sqlite_path.exists())

            final_text = (project / "manuscript/final/ch-001.md").read_text(encoding="utf-8")
            self.assertIn("旧书楼", final_text)
            self.assertIn("巡夜钟", final_text)
            self.assertIn("妹妹", final_text)
            self.assertNotIn("感到无比震惊", final_text)

            relationships = json.loads((project / "characters/relationships.json").read_text(encoding="utf-8"))
            self.assertGreaterEqual(len(relationships["edges"]), 3)
            self.assertTrue(any(edge["type"] == "conflict" for edge in relationships["edges"]))

            scene_settings = json.loads((project / "settings/scenes.json").read_text(encoding="utf-8"))
            self.assertTrue(any(scene["id"] == "patrol-bell" for scene in scene_settings["scene_settings"]))

            style_profile = json.loads((project / "settings/style-profile.json").read_text(encoding="utf-8"))
            self.assertIn("感到无比震惊", style_profile["forbidden_expressions"])

            archive = json.loads((project / "runs/archive-ch-001.json").read_text(encoding="utf-8"))
            self.assertTrue(all("id" in item and item["status"] == "open" for item in archive["foreshadowing"]))

            trace = json.loads(result.trace_path.read_text(encoding="utf-8"))
            self.assertEqual(trace["status"], "completed")
            self.assertEqual([step["stage"] for step in trace["steps"]], [
                "Intake",
                "Plan",
                "RetrieveContext",
                "Generate",
                "Review",
                "Revise",
                "Review",
                "Approve",
                "Archive",
            ])
            self.assertTrue(trace["artifacts"])
            self.assertIn("runs/runs.sqlite", trace["artifacts"])

            with sqlite3.connect(result.sqlite_path) as connection:
                row = connection.execute("SELECT status, chapter_id FROM runs WHERE run_id = ?", (result.run_id,)).fetchone()
            self.assertEqual(row, ("completed", "ch-001"))

    def test_cli_run_uses_real_entrypoint(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir) / "cli-novel"
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "botmux_novel",
                    "run",
                    "--project",
                    str(project),
                    "--title",
                    "影钟旧案",
                    "--inspiration",
                    "少年在旧书楼发现父亲旧案残页。",
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            payload = json.loads(completed.stdout)
            self.assertEqual(payload["status"], "completed")
            self.assertTrue(Path(payload["final_path"]).exists())
            self.assertTrue(Path(payload["trace_path"]).exists())

    def test_cli_foundation_uses_real_entrypoint(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir) / "cli-foundation"
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "botmux_novel",
                    "foundation",
                    "--project",
                    str(project),
                    "--title",
                    "影钟旧案",
                    "--inspiration",
                    "少年在旧书楼发现父亲旧案残页。",
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            payload = json.loads(completed.stdout)
            self.assertEqual(payload["status"], "completed")
            self.assertTrue(Path(payload["foundation_path"]).exists())
            self.assertTrue((project / "characters/relationships.json").exists())
            self.assertFalse((project / "manuscript/final/ch-001.md").exists())

    def test_cli_wiki_bundle_uses_real_entrypoint(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir) / "cli-wiki"
            foundation = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "botmux_novel",
                    "foundation",
                    "--project",
                    str(project),
                    "--title",
                    "影钟旧案",
                    "--inspiration",
                    "少年在旧书楼发现父亲旧案残页。",
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            foundation_payload = json.loads(foundation.stdout)
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "botmux_novel",
                    "wiki-bundle",
                    "--project",
                    str(project),
                    "--project-slug",
                    "shadow-clock-case",
                    "--foundation-json",
                    foundation_payload["foundation_path"],
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            payload = json.loads(completed.stdout)
            bundle_path = Path(payload["bundle_path"])
            self.assertEqual(payload["status"], "completed")
            self.assertTrue((bundle_path / "overview.md").exists())
            self.assertTrue((bundle_path / "chapter-index.md").exists())

    def test_gate_blocks_missing_required_context(self) -> None:
        plan = DirectorAgent().plan_project(
            title="影钟旧案",
            inspiration="少年发现旧案残页。",
            mode="lean",
            chapter_number=1,
            word_target=1200,
        ).data
        blueprint = BlueprintAgent().generate(plan).data
        context = ContextPackBuilder().build(plan, blueprint).data

        review = ConsistencyAgent().review("这一章没有关键素材。", blueprint, context).data

        self.assertEqual(review["decision"], "block")
        self.assertTrue(any(issue["severity"] == "P1" for issue in review["issues"]))


if __name__ == "__main__":
    unittest.main()
