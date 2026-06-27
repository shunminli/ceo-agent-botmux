from __future__ import annotations

import json
import shlex
import subprocess
import sys
import unittest

from botmux_novel.workflow_commands import build_story_foundation_workflow_command


class NovelWorkflowCommandTest(unittest.TestCase):
    def test_build_story_foundation_workflow_command(self) -> None:
        command = build_story_foundation_workflow_command(
            project_slug="shadow-clock-case",
            title="影钟旧案",
            inspiration="一个背负旧案污名的少年，在巡夜钟声中发现妹妹影子会说真话。",
            genre="东方悬疑奇幻",
            target_length="长篇",
            mode="lean",
        )

        self.assertEqual(command[:4], ["botmux", "workflow", "run", "novel-story-foundation"])
        self.assertIn("projectSlug=shadow-clock-case", command)
        self.assertIn("title=影钟旧案", command)
        self.assertIn("inspiration=一个背负旧案污名的少年，在巡夜钟声中发现妹妹影子会说真话。", command)
        self.assertIn("genre=东方悬疑奇幻", command)
        self.assertIn("targetLength=长篇", command)
        self.assertIn("mode=lean", command)

    def test_cli_workflow_foundation_command_uses_real_entrypoint(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "botmux_novel",
                "workflow-foundation-command",
                "--project-slug",
                "shadow-clock-case",
                "--title",
                "影钟旧案",
                "--inspiration",
                "一个背负旧案污名的少年，在巡夜钟声中发现妹妹影子会说真话。",
                "--genre",
                "东方悬疑奇幻",
                "--target-length",
                "长篇",
                "--mode",
                "lean",
            ],
            check=True,
            text=True,
            capture_output=True,
        )

        payload = json.loads(completed.stdout)
        self.assertEqual(payload["workflow_id"], "novel-story-foundation")
        self.assertEqual(payload["params"]["projectSlug"], "shadow-clock-case")
        self.assertEqual(payload["params"]["targetLength"], "长篇")
        self.assertEqual(payload["command"][3], "novel-story-foundation")
        self.assertEqual(shlex.split(payload["command_text"]), payload["command"])


if __name__ == "__main__":
    unittest.main()
