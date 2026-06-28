from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from botmux_novel import BotmuxAssetSyncRequest, BotmuxAssetSyncer
from botmux_novel.botmux_assets import ROLE_IDENTITIES, render_workspace_agents


REPO_ROOT = Path(__file__).resolve().parents[1]
INSTALLED_BOTMUX_HOME = Path.home() / ".botmux"


class BotmuxAssetSyncTest(unittest.TestCase):
    def test_dry_run_reports_expected_targets_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            botmux_home = Path(tmpdir) / ".botmux"

            result = BotmuxAssetSyncer().sync(
                BotmuxAssetSyncRequest(repo_path=REPO_ROOT, botmux_home=botmux_home, write=False)
            )

            self.assertEqual(result.status, "planned")
            self.assertEqual(len(result.actions), 5)
            self.assertEqual({action.status for action in result.actions}, {"would_create"})
            self.assertFalse((botmux_home / "workflows/novel-story-foundation.workflow.json").exists())
            self.assertFalse((botmux_home / "workspace/Novel-Director-Curator/AGENTS.md").exists())

    def test_write_syncs_workflows_and_workspace_agents_to_temp_home(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            botmux_home = Path(tmpdir) / ".botmux"

            result = BotmuxAssetSyncer().sync(
                BotmuxAssetSyncRequest(repo_path=REPO_ROOT, botmux_home=botmux_home, write=True)
            )

            self.assertEqual(result.status, "completed")
            self.assertEqual(len(result.actions), 5)
            self.assertEqual({action.status for action in result.actions}, {"created"})
            self.assertTrue((botmux_home / "workflows/novel-story-foundation.workflow.json").exists())
            self.assertTrue((botmux_home / "workflows/novel-chapter-production.workflow.json").exists())

            director_agents = (botmux_home / "workspace/Novel-Director-Curator/AGENTS.md").read_text(encoding="utf-8")
            self.assertIn("Novel-Director-Curator Workspace Instructions", director_agents)
            self.assertIn("Canonical Identity", director_agents)
            self.assertIn("开发闭环原则", director_agents)
            self.assertIn("novel-director-curator.identity.md", director_agents)
            self.assertIn("Project working directory", director_agents)

            unchanged = BotmuxAssetSyncer().sync(
                BotmuxAssetSyncRequest(repo_path=REPO_ROOT, botmux_home=botmux_home, write=True)
            )
            self.assertEqual({action.status for action in unchanged.actions}, {"unchanged"})

    def test_cli_botmux_assets_uses_real_entrypoint(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            botmux_home = Path(tmpdir) / ".botmux"
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "botmux_novel",
                    "botmux-assets",
                    "--repo",
                    str(REPO_ROOT),
                    "--botmux-home",
                    str(botmux_home),
                    "--write",
                    "--no-backup",
                ],
                check=True,
                text=True,
                capture_output=True,
            )

            payload = json.loads(completed.stdout)
            self.assertEqual(payload["status"], "completed")
            self.assertTrue(payload["write"])
            self.assertEqual(len(payload["actions"]), 5)
            self.assertTrue((botmux_home / "workspace/Novel-Continuity-Validator/AGENTS.md").exists())

    def test_installed_workspace_agents_match_generated_when_available(self) -> None:
        for role_name, identity_filename in ROLE_IDENTITIES.items():
            with self.subTest(role_name=role_name):
                installed_path = INSTALLED_BOTMUX_HOME / "workspace" / role_name / "AGENTS.md"
                if not installed_path.exists():
                    self.skipTest(f"installed workspace AGENTS missing: {installed_path}")
                expected = render_workspace_agents(
                    role_name=role_name,
                    identity_path=REPO_ROOT / "agents" / identity_filename,
                )
                self.assertEqual(installed_path.read_text(encoding="utf-8"), expected)


if __name__ == "__main__":
    unittest.main()
