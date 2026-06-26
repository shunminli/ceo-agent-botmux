from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from botmux_novel import (
    LlmwikiSyncRequest,
    LlmwikiSyncer,
    NovelChapterRequest,
    NovelFoundationRequest,
    NovelRunRequest,
    NovelRuntime,
    NovelSeriesRequest,
    NovelSeriesRunner,
    NovelWikiBundleRequest,
)
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

    def test_chapter_uses_existing_foundation_without_replanning_story_bible(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir) / "chapter-from-foundation"
            foundation = NovelRuntime().foundation(
                NovelFoundationRequest(
                    project_path=project,
                    title="影钟旧案",
                    inspiration="一个背负旧案污名的少年，在巡夜钟声中发现妹妹影子会说真话。",
                )
            )

            result = NovelRuntime().chapter(
                NovelChapterRequest(
                    project_path=project,
                    chapter_number=2,
                    chapter_goal="让林烬用半张残页验证巡夜钟异常，并把妹妹影子证词转成下一章追查目标。",
                    foundation_path=foundation.foundation_path,
                )
            )

            self.assertEqual(result.status, "completed")
            self.assertEqual(result.chapter_id, "ch-002")
            self.assertTrue((project / "manuscript/final/ch-002.md").exists())
            self.assertTrue((project / f"runs/{result.run_id}/source-foundation.json").exists())
            self.assertTrue((project / "tracking/facts.yaml").exists())
            trace = json.loads(result.trace_path.read_text(encoding="utf-8"))
            self.assertEqual(trace["steps"][0]["stage"], "LoadFoundation")
            self.assertIn("foundation_path", trace["request"])
            self.assertEqual(trace["request"]["chapter_goal"], "让林烬用半张残页验证巡夜钟异常，并把妹妹影子证词转成下一章追查目标。")

    def test_chapter_loads_prior_archive_context_for_next_chapter(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir) / "chapter-continuity"
            runtime = NovelRuntime()
            foundation = runtime.foundation(
                NovelFoundationRequest(
                    project_path=project,
                    title="影钟旧案",
                    inspiration="一个背负旧案污名的少年，在巡夜钟声中发现妹妹影子会说真话。",
                )
            )
            first_chapter = runtime.chapter(
                NovelChapterRequest(
                    project_path=project,
                    chapter_number=1,
                    chapter_goal="用旧书楼残页引出主角秘密能力并埋下巡夜钟伏笔。",
                    foundation_path=foundation.foundation_path,
                )
            )
            self.assertEqual(first_chapter.status, "completed")

            second_chapter = runtime.chapter(
                NovelChapterRequest(
                    project_path=project,
                    chapter_number=2,
                    chapter_goal="让林烬用半张残页验证巡夜钟异常，并把妹妹影子证词转成下一章追查目标。",
                    foundation_path=foundation.foundation_path,
                )
            )

            prior_context_path = project / f"runs/{second_chapter.run_id}/prior-context.json"
            context_pack_path = project / f"runs/{second_chapter.run_id}/context-pack.json"
            self.assertTrue(prior_context_path.exists())
            self.assertTrue(context_pack_path.exists())

            prior_context = json.loads(prior_context_path.read_text(encoding="utf-8"))
            self.assertEqual(prior_context["source_chapters"], ["ch-001"])
            self.assertTrue(any("玄衣巡使影子" in fact["fact"] for fact in prior_context["facts"]))
            self.assertTrue(all(item["source_archive"] == "runs/archive-ch-001.json" for item in prior_context["facts"]))

            context_pack = json.loads(context_pack_path.read_text(encoding="utf-8"))
            self.assertIn("archive:ch-001", context_pack["source_refs"])
            self.assertIn("ch-001", context_pack["prior_context"]["source_chapters"])
            self.assertTrue(any("妹妹的影子" in fact for fact in context_pack["facts"]))

            trace = json.loads(second_chapter.trace_path.read_text(encoding="utf-8"))
            self.assertEqual([step["stage"] for step in trace["steps"][:3]], ["LoadFoundation", "LoadPriorContext", "Plan"])

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

    def test_cli_chapter_uses_real_entrypoint(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir) / "cli-chapter"
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
                    "chapter",
                    "--project",
                    str(project),
                    "--chapter-number",
                    "2",
                    "--chapter-goal",
                    "让林烬用半张残页验证巡夜钟异常，并把妹妹影子证词转成下一章追查目标。",
                    "--foundation-json",
                    foundation_payload["foundation_path"],
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            payload = json.loads(completed.stdout)
            self.assertEqual(payload["status"], "completed")
            self.assertEqual(payload["chapter_id"], "ch-002")
            self.assertTrue(Path(payload["final_path"]).exists())

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

    def test_llmwiki_sync_dry_run_writes_plan_without_workspace_copy(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir) / "llmwiki-project"
            workspace = Path(tmpdir) / "llmwiki-workspace"
            runtime = NovelRuntime()
            foundation = runtime.foundation(
                NovelFoundationRequest(
                    project_path=project,
                    title="影钟旧案",
                    inspiration="少年在旧书楼发现父亲旧案残页。",
                )
            )
            runtime.wiki_bundle(
                NovelWikiBundleRequest(
                    project_path=project,
                    project_slug="shadow-clock-case",
                    foundation_path=foundation.foundation_path,
                )
            )

            result = LlmwikiSyncer().sync(
                LlmwikiSyncRequest(
                    project_path=project,
                    project_slug="shadow-clock-case",
                    workspace_path=workspace,
                    approve=False,
                )
            )

            self.assertEqual(result.status, "planned")
            self.assertFalse(result.approved)
            self.assertTrue(result.plan_path.exists())
            self.assertFalse((workspace / "wiki/novels/shadow-clock-case/overview.md").exists())
            self.assertIn("would_create", {action.status for action in result.actions})
            plan = json.loads(result.plan_path.read_text(encoding="utf-8"))
            self.assertFalse(plan["approved"])
            self.assertEqual(plan["preview"]["target_namespace"], "/wiki/novels/shadow-clock-case/")

    def test_llmwiki_sync_approved_copies_bundle_and_backs_up_changed_pages(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir) / "llmwiki-project"
            workspace = Path(tmpdir) / "llmwiki-workspace"
            runtime = NovelRuntime()
            foundation = runtime.foundation(
                NovelFoundationRequest(
                    project_path=project,
                    title="影钟旧案",
                    inspiration="少年在旧书楼发现父亲旧案残页。",
                )
            )
            runtime.wiki_bundle(
                NovelWikiBundleRequest(
                    project_path=project,
                    project_slug="shadow-clock-case",
                    foundation_path=foundation.foundation_path,
                )
            )
            target_overview = workspace / "wiki/novels/shadow-clock-case/overview.md"
            target_overview.parent.mkdir(parents=True)
            target_overview.write_text("# stale\n", encoding="utf-8")

            result = LlmwikiSyncer().sync(
                LlmwikiSyncRequest(
                    project_path=project,
                    project_slug="shadow-clock-case",
                    workspace_path=workspace,
                    approve=True,
                    llmwiki_bin="llmwiki-missing-for-test",
                    reindex=True,
                )
            )

            self.assertEqual(result.status, "completed_with_warnings")
            self.assertTrue(target_overview.read_text(encoding="utf-8").startswith("# 影钟旧案"))
            updated = [action for action in result.actions if action.target_path == target_overview.resolve()]
            self.assertEqual(len(updated), 1)
            self.assertEqual(updated[0].status, "updated")
            self.assertIsNotNone(updated[0].backup_path)
            self.assertTrue(updated[0].backup_path.exists())
            self.assertTrue(any(command.status == "skipped" for command in result.commands))

    def test_llmwiki_sync_reindex_uses_configured_llmwiki_binary(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir) / "llmwiki-project"
            workspace = Path(tmpdir) / "llmwiki-workspace"
            fake_llmwiki = Path(tmpdir) / "llmwiki"
            fake_llmwiki.write_text("#!/bin/sh\necho reindexed \"$@\"\n", encoding="utf-8")
            fake_llmwiki.chmod(0o755)
            runtime = NovelRuntime()
            foundation = runtime.foundation(
                NovelFoundationRequest(
                    project_path=project,
                    title="影钟旧案",
                    inspiration="少年在旧书楼发现父亲旧案残页。",
                )
            )
            runtime.wiki_bundle(
                NovelWikiBundleRequest(
                    project_path=project,
                    project_slug="shadow-clock-case",
                    foundation_path=foundation.foundation_path,
                )
            )

            result = LlmwikiSyncer().sync(
                LlmwikiSyncRequest(
                    project_path=project,
                    project_slug="shadow-clock-case",
                    workspace_path=workspace,
                    approve=True,
                    llmwiki_bin=str(fake_llmwiki),
                    reindex=True,
                )
            )

            self.assertEqual(result.status, "completed")
            self.assertTrue(result.llmwiki_available)
            self.assertEqual(result.commands[0].status, "succeeded")
            self.assertIn("reindexed reindex", result.commands[0].stdout)

    def test_cli_llmwiki_sync_uses_real_entrypoint(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir) / "cli-llmwiki-project"
            workspace = Path(tmpdir) / "cli-llmwiki-workspace"
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
            subprocess.run(
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
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "botmux_novel",
                    "llmwiki-sync",
                    "--project",
                    str(project),
                    "--project-slug",
                    "shadow-clock-case",
                    "--workspace",
                    str(workspace),
                    "--approve",
                    "--no-backup",
                ],
                check=True,
                text=True,
                capture_output=True,
            )

            payload = json.loads(completed.stdout)
            self.assertEqual(payload["status"], "completed")
            self.assertTrue(Path(payload["plan_path"]).exists())
            self.assertTrue((workspace / "wiki/novels/shadow-clock-case/overview.md").exists())

    def test_series_generates_five_chapters_and_quality_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir) / "series-project"

            result = NovelSeriesRunner().run(
                NovelSeriesRequest(
                    project_path=project,
                    title="影钟旧案",
                    inspiration="少年在旧书楼发现父亲旧案残页。",
                    project_slug="shadow-clock-case",
                    chapter_count=5,
                    llmwiki_sync=True,
                )
            )

            self.assertEqual(result.status, "completed")
            self.assertEqual(len(result.chapters), 5)
            self.assertTrue(result.metrics_path.exists())
            self.assertEqual(result.metrics["chapter_count"], 5)
            self.assertEqual(result.metrics["completed_chapter_count"], 5)
            self.assertEqual(result.metrics["p0_p1_issue_count"], 0)
            self.assertEqual(result.metrics["revision_rounds"], 5)
            self.assertEqual(result.metrics["archive_completion_rate"], 1.0)
            self.assertEqual(result.metrics["prior_context_rate"], 1.0)
            self.assertEqual(result.metrics["llmwiki_sync_status"], "planned")
            self.assertTrue((project / "manuscript/final/ch-005.md").exists())
            self.assertTrue((project / "runs/archive-ch-005.json").exists())

    def test_cli_series_uses_real_entrypoint(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir) / "cli-series-project"
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "botmux_novel",
                    "series",
                    "--project",
                    str(project),
                    "--title",
                    "影钟旧案",
                    "--inspiration",
                    "少年在旧书楼发现父亲旧案残页。",
                    "--project-slug",
                    "shadow-clock-case",
                    "--chapter-count",
                    "3",
                ],
                check=True,
                text=True,
                capture_output=True,
            )

            payload = json.loads(completed.stdout)
            self.assertEqual(payload["status"], "completed")
            self.assertEqual(payload["metrics"]["chapter_count"], 3)
            self.assertTrue(Path(payload["metrics_path"]).exists())
            self.assertTrue((project / "manuscript/final/ch-003.md").exists())

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
