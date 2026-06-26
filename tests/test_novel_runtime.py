from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from botmux_novel import NovelRunRequest, NovelRuntime
from botmux_novel.agents import BlueprintAgent, ConsistencyAgent, ContextPackBuilder, DirectorAgent


class NovelRuntimeTest(unittest.TestCase):
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
