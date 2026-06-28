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
            project = Path(tmpdir) / "sanguo-daily-strategy-resources"
            result = NovelProjectInitializer().initialize(
                NovelProjectInitRequest(
                    project_path=project,
                    project_slug="sanguo-daily-strategy-resources",
                    title="三国：每日战略资源，只能建设辖区",
                    inspiration="主角穿到三国边地小县，系统每日发放战略资源，但只能建设当前官职辖区。",
                    genre="三国历史脑洞 / 系统种田 / 领地经营 / 争霸",
                    target_length="长篇连载，约150万字",
                    mode="lean",
                )
            )

            self.assertEqual(result.status, "initialized")
            self.assertTrue((project / "publish/fanqie/chapters").is_dir())
            self.assertTrue((project / "comms/handoffs/README.md").exists())
            self.assertTrue((project / "wiki/llmwiki-workspace").is_dir())
            self.assertTrue((project / ".gitignore").exists())
            self.assertIn("runs/", (project / ".gitignore").read_text(encoding="utf-8"))
            self.assertIn("sanguo-daily-strategy-resources", (project / "project.yaml").read_text(encoding="utf-8"))

    def test_fanqie_export_writes_plain_text_chapters_and_book(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir) / "novel"
            final_dir = project / "manuscript/final"
            final_dir.mkdir(parents=True)
            (final_dir / "ch-001.md").write_text(
                "# 第一章 粮仓三日\n\n他在**县仓**里看见[战略粮册](wiki://grain)。\n\n> 粮不能出县。\n",
                encoding="utf-8",
            )
            (final_dir / "ch-002.md").write_text(
                "豪强的车辙压过县衙前街。\n\n```json\n{\"note\":\"remove\"}\n```\n\n他合上账册。\n",
                encoding="utf-8",
            )

            result = FanqieExporter().export(FanqieExportRequest(project_path=project, title="三国：每日战略资源，只能建设辖区"))

            self.assertEqual(result.status, "completed")
            self.assertEqual(len(result.chapters), 2)
            first_text = result.chapters[0].output_path.read_text(encoding="utf-8")
            self.assertIn("第一章 粮仓三日", first_text)
            self.assertIn("县仓", first_text)
            self.assertIn("战略粮册", first_text)
            self.assertNotIn("**", first_text)
            self.assertNotIn("wiki://", first_text)
            second_text = result.chapters[1].output_path.read_text(encoding="utf-8")
            self.assertTrue(second_text.startswith("第002章"))
            self.assertNotIn("json", second_text)
            book_text = result.book_path.read_text(encoding="utf-8")
            self.assertIn("第一章 粮仓三日", book_text)
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
                    "sanguo-daily-strategy-resources",
                    "--title",
                    "三国：每日战略资源，只能建设辖区",
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
            (final_dir / "ch-001.md").write_text("第一章 粮仓三日\n\n县仓里多出三千石粮。", encoding="utf-8")
            export = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "botmux_novel",
                    "fanqie-export",
                    "--project",
                    str(project),
                    "--title",
                    "三国：每日战略资源，只能建设辖区",
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
