from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


class DoubaoCliTest(unittest.TestCase):
    def test_ask_uses_opencli_app_runner_through_real_entrypoint(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = self._write_fake_runner(Path(tmpdir) / "opencli")
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "botmux_doubao",
                    "ask",
                    "少年和妹妹在旧书楼重逢。",
                    "--provider",
                    "opencli-app",
                    "--runner",
                    str(runner),
                    "--purpose",
                    "dialogue",
                    "--json",
                ],
                check=True,
                text=True,
                capture_output=True,
            )

            payload = json.loads(completed.stdout)
            self.assertEqual(payload["status"], "completed")
            self.assertEqual(payload["provider"], "opencli-app")
            self.assertEqual(payload["adapter"], "doubao-app")
            self.assertIn("中文小说对白候选", payload["prompt"])
            self.assertIn("少年和妹妹在旧书楼重逢", payload["response"])

    def test_ask_can_start_new_conversation_before_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = self._write_fake_runner(Path(tmpdir) / "opencli")
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "botmux_doubao",
                    "ask",
                    "生成三个桥段",
                    "--provider",
                    "opencli-app",
                    "--runner",
                    str(runner),
                    "--new",
                    "--json",
                ],
                check=True,
                text=True,
                capture_output=True,
            )

            payload = json.loads(completed.stdout)
            self.assertEqual(payload["status"], "completed")
            self.assertIn("生成三个桥段", payload["response"])

    def test_missing_runner_reports_setup_guidance(self) -> None:
        missing_runner = "/tmp/botmux-doubao-missing-runner"
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "botmux_doubao",
                "ask",
                "hello",
                "--provider",
                "opencli-app",
                "--runner",
                missing_runner,
                "--json",
            ],
            check=False,
            text=True,
            capture_output=True,
        )

        self.assertEqual(completed.returncode, 127)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["status"], "missing_runner")
        self.assertEqual(payload["runner"], missing_runner)
        self.assertTrue(any("OpenCLI" in hint for hint in payload["setup_hints"]))

    def test_status_supports_standalone_doubao_cli_provider(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = self._write_fake_runner(Path(tmpdir) / "doubao-cli")
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "botmux_doubao",
                    "status",
                    "--provider",
                    "doubao-cli",
                    "--runner",
                    str(runner),
                    "--json",
                ],
                check=True,
                text=True,
                capture_output=True,
            )

            payload = json.loads(completed.stdout)
            self.assertEqual(payload["status"], "completed")
            self.assertEqual(payload["provider"], "doubao-cli")
            self.assertTrue(payload["diagnostics"]["runner_found"])
            self.assertIn("fake-account", payload["stdout"])

    def test_launch_dry_run_prints_cdp_command(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "botmux_doubao",
                "launch",
                "--dry-run",
                "--json",
            ],
            check=True,
            text=True,
            capture_output=True,
        )

        payload = json.loads(completed.stdout)
        self.assertEqual(payload["status"], "completed")
        self.assertIn("--remote-debugging-port=9225", payload["stdout"])

    def _write_fake_runner(self, path: Path) -> Path:
        path.write_text(
            textwrap.dedent(
                """\
                #!/usr/bin/env python3
                import sys

                args = sys.argv[1:]
                if args[:2] in (["doubao-app", "status"], ["doubao", "status"]):
                    print("fake-status-ok")
                elif args[:2] in (["doubao-app", "new"], ["doubao", "new"]):
                    print("fake-new-ok")
                elif args[:2] in (["doubao-app", "read"], ["doubao", "read"]):
                    print("fake-latest-reply")
                elif args[:2] in (["doubao-app", "ask"], ["doubao", "ask"]):
                    print("fake-doubao-reply:" + args[2])
                elif args == ["account"]:
                    print("fake-account-ok")
                elif args == ["new"]:
                    print("fake-new-ok")
                elif args == ["last"]:
                    print("fake-latest-reply")
                elif args:
                    print("fake-doubao-reply:" + args[0])
                else:
                    print("unexpected args", file=sys.stderr)
                    sys.exit(2)
                """
            ),
            encoding="utf-8",
        )
        path.chmod(path.stat().st_mode | 0o111)
        return path


if __name__ == "__main__":
    unittest.main()
