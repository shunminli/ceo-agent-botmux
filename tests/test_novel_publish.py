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
            project = Path(tmpdir) / "qin-last-lamp"
            result = NovelProjectInitializer().initialize(
                NovelProjectInitRequest(
                    project_path=project,
                    project_slug="qin-last-lamp",
                    title="秦灯未灭",
                    inspiration="秦亡竹简预写了未来。",
                    genre="秦末历史权谋",
                    target_length="长篇连载，约30万字",
                    mode="lean",
                )
            )

            self.assertEqual(result.status, "initialized")
            self.assertTrue((project / "publish/fanqie/chapters").is_dir())
            self.assertTrue((project / "comms/handoffs/README.md").exists())
            self.assertTrue((project / "wiki/llmwiki-workspace").is_dir())
            self.assertTrue((project / ".gitignore").exists())
            self.assertIn("runs/", (project / ".gitignore").read_text(encoding="utf-8"))
            self.assertIn("qin-last-lamp", (project / "project.yaml").read_text(encoding="utf-8"))

    def test_fanqie_export_writes_plain_text_chapters_and_book(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir) / "novel"
            final_dir = project / "manuscript/final"
            final_dir.mkdir(parents=True)
            (final_dir / "ch-001.md").write_text(
                "# 第一章 灯下竹简\n\n他在**密档室**里看见[亡秦竹简](wiki://bamboo)。\n\n> 灯没有灭。\n",
                encoding="utf-8",
            )
            (final_dir / "ch-002.md").write_text(
                "赵高的车辙压过宫门。\n\n```json\n{\"note\":\"remove\"}\n```\n\n他合上竹简。\n",
                encoding="utf-8",
            )

            result = FanqieExporter().export(FanqieExportRequest(project_path=project, title="秦灯未灭"))

            self.assertEqual(result.status, "completed")
            self.assertEqual(len(result.chapters), 2)
            first_text = result.chapters[0].output_path.read_text(encoding="utf-8")
            self.assertIn("第一章 灯下竹简", first_text)
            self.assertIn("密档室", first_text)
            self.assertIn("亡秦竹简", first_text)
            self.assertNotIn("**", first_text)
            self.assertNotIn("wiki://", first_text)
            second_text = result.chapters[1].output_path.read_text(encoding="utf-8")
            self.assertTrue(second_text.startswith("第002章"))
            self.assertNotIn("json", second_text)
            book_text = result.book_path.read_text(encoding="utf-8")
            self.assertIn("第一章 灯下竹简", book_text)
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
                    "qin-last-lamp",
                    "--title",
                    "秦灯未灭",
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
            (final_dir / "ch-001.md").write_text("第一章 灯下竹简\n\n灯火照见竹简。", encoding="utf-8")
            export = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "botmux_novel",
                    "fanqie-export",
                    "--project",
                    str(project),
                    "--title",
                    "秦灯未灭",
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
