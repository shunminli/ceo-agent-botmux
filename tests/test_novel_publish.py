import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from botmux_novel.fanqie_export import FanqieExportRequest, FanqieExporter
from botmux_novel.project_template import NovelProjectInitializer, NovelProjectInitRequest


class NovelPublishTests(unittest.TestCase):
    def test_project_init_creates_independent_project_layout(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir) / "shadow-clock-case"
            result = NovelProjectInitializer().initialize(
                NovelProjectInitRequest(
                    project_path=project,
                    project_slug="shadow-clock-case",
                    title="影钟旧案",
                    inspiration="一个背负旧案污名的少年，在巡夜钟声中发现妹妹影子会说真话。",
                    genre="东方悬疑奇幻",
                    target_length="长篇",
                    mode="lean",
                )
            )

            self.assertEqual(result.status, "initialized")
            self.assertTrue((project / "publish/fanqie/chapters").is_dir())
            self.assertTrue((project / "comms/handoffs/README.md").exists())
            self.assertTrue((project / "wiki/llmwiki-workspace").is_dir())
            self.assertTrue((project / ".gitignore").exists())
            self.assertIn("runs/", (project / ".gitignore").read_text(encoding="utf-8"))
            self.assertIn("shadow-clock-case", (project / "project.yaml").read_text(encoding="utf-8"))

    def test_fanqie_export_writes_plain_text_chapters_and_book(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir) / "novel"
            final_dir = project / "manuscript/final"
            final_dir.mkdir(parents=True)
            (final_dir / "ch-001.md").write_text(
                "# 第一章 夜钟回声\n\n他在**钟楼**里看见[半张残页](wiki://clock-page)。\n\n> 影子先开口。\n",
                encoding="utf-8",
            )
            (final_dir / "ch-002.md").write_text(
                "巡夜人的灯火照过旧巷。\n\n```json\n{\"note\":\"remove\"}\n```\n\n他合上残页。\n",
                encoding="utf-8",
            )

            result = FanqieExporter().export(FanqieExportRequest(project_path=project, title="影钟旧案"))

            self.assertEqual(result.status, "completed")
            self.assertEqual(len(result.chapters), 2)
            first_text = result.chapters[0].output_path.read_text(encoding="utf-8")
            self.assertIn("第一章 夜钟回声", first_text)
            self.assertIn("钟楼", first_text)
            self.assertIn("半张残页", first_text)
            self.assertNotIn("**", first_text)
            self.assertNotIn("wiki://", first_text)
            second_text = result.chapters[1].output_path.read_text(encoding="utf-8")
            self.assertTrue(second_text.startswith("第002章"))
            self.assertNotIn("json", second_text)
            book_text = result.book_path.read_text(encoding="utf-8")
            self.assertIn("第一章 夜钟回声", book_text)
            self.assertIn("第002章", book_text)
            checklist = result.checklist_path.read_text(encoding="utf-8")
            self.assertIn("pending", checklist)
            self.assertIn("Character Count", checklist)

    def test_cli_project_init_and_fanqie_export_use_real_entrypoints(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir) / "cli-novel"
            init = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "botmux_novel",
                    "project-init",
                    "--project",
                    str(project),
                    "--project-slug",
                    "shadow-clock-case",
                    "--title",
                    "影钟旧案",
                    "--mode",
                    "lean",
                ],
                check=False,
                text=True,
                capture_output=True,
            )
            self.assertEqual(init.returncode, 0, init.stderr)
            init_payload = json.loads(init.stdout)
            self.assertEqual(init_payload["status"], "initialized")

            final_dir = project / "manuscript/final"
            final_dir.mkdir(parents=True, exist_ok=True)
            (final_dir / "ch-001.md").write_text("第一章 夜钟回声\n\n钟楼里传来第三声回响。", encoding="utf-8")
            export = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "botmux_novel",
                    "fanqie-export",
                    "--project",
                    str(project),
                    "--title",
                    "影钟旧案",
                ],
                check=False,
                text=True,
                capture_output=True,
            )
            self.assertEqual(export.returncode, 0, export.stderr)
            export_payload = json.loads(export.stdout)
            self.assertEqual(export_payload["status"], "completed")
            self.assertTrue(Path(export_payload["book_path"]).exists())


if __name__ == "__main__":
    unittest.main()
