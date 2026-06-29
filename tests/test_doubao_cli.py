from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from unittest import mock
from pathlib import Path

from botmux_doubao.runtime import DoubaoRuntime


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

    def test_ask_supports_direct_cdp_app_provider(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = self._write_fake_cdp_runner(Path(tmpdir) / "node")
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "botmux_doubao",
                    "ask",
                    "只回复固定测试串",
                    "--provider",
                    "cdp-app",
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
            self.assertEqual(payload["provider"], "cdp-app")
            self.assertEqual(payload["adapter"], "direct-cdp")
            self.assertEqual(payload["response"], "fake-cdp-reply:只回复固定测试串")
            self.assertEqual(payload["diagnostics"]["operation"], "ask")

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
        self.assertEqual(payload["provider"], "cdp-app")
        self.assertIn("open -na", payload["stdout"])
        self.assertIn("/Applications/Doubao.app", payload["stdout"])
        self.assertIn("--remote-debugging-port=9225", payload["stdout"])
        self.assertEqual(payload["diagnostics"]["app_bundle"], "/Applications/Doubao.app")

    def test_launch_relaunch_dry_run_prints_quit_then_cdp_command(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "botmux_doubao",
                "launch",
                "--dry-run",
                "--relaunch",
                "--json",
            ],
            check=True,
            text=True,
            capture_output=True,
        )

        payload = json.loads(completed.stdout)
        self.assertEqual(payload["status"], "completed")
        self.assertEqual(payload["provider"], "cdp-app")
        self.assertTrue(payload["diagnostics"]["relaunch"])
        self.assertIn("osascript", payload["stdout"])
        self.assertIn("open -na", payload["stdout"])
        self.assertIn("--remote-debugging-port=9225", payload["stdout"])

    def test_launch_custom_binary_does_not_wait_for_process_exit(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            app_binary = Path(tmpdir) / "doubao-test-app"
            app_binary.write_text(
                textwrap.dedent(
                    """\
                    #!/usr/bin/env python3
                    import time
                    time.sleep(5)
                    """
                ),
                encoding="utf-8",
            )
            app_binary.chmod(app_binary.stat().st_mode | 0o111)

            runtime = DoubaoRuntime()
            started_at = time.monotonic()
            with mock.patch.object(runtime, "_wait_for_cdp", return_value=True):
                result = runtime.launch_desktop(app_binary=app_binary)
            elapsed = time.monotonic() - started_at

            pid = result.diagnostics.get("pid")
            try:
                self.assertEqual(result.status, "completed")
                self.assertLess(elapsed, 1.0)
                self.assertEqual(result.diagnostics["launch_command"][0], str(app_binary))
                self.assertIsInstance(pid, int)
            finally:
                if isinstance(pid, int):
                    try:
                        os.kill(pid, signal.SIGTERM)
                    except ProcessLookupError:
                        pass
                for process in runtime._desktop_processes:
                    try:
                        process.wait(timeout=1)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=1)

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

    def _write_fake_cdp_runner(self, path: Path) -> Path:
        path.write_text(
            textwrap.dedent(
                """\
                #!/usr/bin/env python3
                import json
                import sys

                payload = json.load(sys.stdin)
                response = {
                    "ok": True,
                    "response": "fake-cdp-reply:" + payload.get("prompt", ""),
                    "stdout": "fake-cdp-stdout",
                    "diagnostics": {
                        "operation": payload.get("operation"),
                        "cdp_endpoint": payload.get("endpoint"),
                    },
                }
                print(json.dumps(response))
                """
            ),
            encoding="utf-8",
        )
        path.chmod(path.stat().st_mode | 0o111)
        return path


if __name__ == "__main__":
    unittest.main()
