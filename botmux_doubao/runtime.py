from __future__ import annotations

import os
import shlex
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence


PROVIDER_AUTO = "auto"
PROVIDER_OPENCLI_APP = "opencli-app"
PROVIDER_OPENCLI_WEB = "opencli-web"
PROVIDER_DOUBAO_CLI = "doubao-cli"

SUPPORTED_PROVIDERS = [
    PROVIDER_AUTO,
    PROVIDER_OPENCLI_APP,
    PROVIDER_OPENCLI_WEB,
    PROVIDER_DOUBAO_CLI,
]

DEFAULT_DOUBAO_APP_PATH = Path("/Applications/Doubao.app")
DEFAULT_DOUBAO_APP_BINARY = DEFAULT_DOUBAO_APP_PATH / "Contents/MacOS/Doubao"


@dataclass(frozen=True)
class ProviderSpec:
    name: str
    executable: str
    ask_args: Callable[[str], List[str]]
    status_args: List[str]
    read_args: List[str]
    new_args: List[str]
    setup_hints: List[str]
    adapter: Optional[str] = None


@dataclass(frozen=True)
class DoubaoRequest:
    prompt: str
    provider: str = PROVIDER_AUTO
    runner: Optional[str] = None
    timeout_seconds: int = 180
    start_new: bool = False
    purpose: str = "general"
    opencli_adapter: Optional[str] = None


@dataclass
class DoubaoResult:
    status: str
    provider: str
    command: str
    returncode: Optional[int] = None
    prompt: Optional[str] = None
    raw_prompt: Optional[str] = None
    response: str = ""
    stdout: str = ""
    stderr: str = ""
    runner: Optional[str] = None
    adapter: Optional[str] = None
    setup_hints: List[str] = field(default_factory=list)
    diagnostics: Dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, object]:
        return {
            "status": self.status,
            "provider": self.provider,
            "command": self.command,
            "returncode": self.returncode,
            "runner": self.runner,
            "adapter": self.adapter,
            "prompt": self.prompt,
            "raw_prompt": self.raw_prompt,
            "response": self.response,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "setup_hints": self.setup_hints,
            "diagnostics": self.diagnostics,
        }


class DoubaoRuntime:
    def ask(self, request: DoubaoRequest) -> DoubaoResult:
        provider = self._resolve_provider(request.provider, request.runner)
        spec = self._provider_spec(provider, request.opencli_adapter)
        runner = self._resolve_runner(spec.executable, request.runner)
        prompt = self._apply_purpose(request.prompt, request.purpose)

        if not runner:
            return self._missing_runner_result("ask", spec, request, prompt)

        if request.start_new:
            new_result = self._run_command(
                [runner] + spec.new_args,
                request.timeout_seconds,
                "new",
                spec,
                request,
                prompt,
            )
            if new_result.status != "completed":
                return new_result

        return self._run_command(
            [runner] + spec.ask_args(prompt),
            request.timeout_seconds,
            "ask",
            spec,
            request,
            prompt,
        )

    def read(
        self,
        provider: str = PROVIDER_AUTO,
        runner: Optional[str] = None,
        timeout_seconds: int = 30,
        opencli_adapter: Optional[str] = None,
    ) -> DoubaoResult:
        resolved = self._resolve_provider(provider, runner)
        spec = self._provider_spec(resolved, opencli_adapter)
        runner_path = self._resolve_runner(spec.executable, runner)
        if not runner_path:
            empty_request = DoubaoRequest("", provider=provider, runner=runner, opencli_adapter=opencli_adapter)
            return self._missing_runner_result("read", spec, empty_request, "")
        return self._run_command([runner_path] + spec.read_args, timeout_seconds, "read", spec, DoubaoRequest(""), "")

    def status(
        self,
        provider: str = PROVIDER_AUTO,
        runner: Optional[str] = None,
        timeout_seconds: int = 30,
        opencli_adapter: Optional[str] = None,
    ) -> DoubaoResult:
        resolved = self._resolve_provider(provider, runner)
        spec = self._provider_spec(resolved, opencli_adapter)
        runner_path = self._resolve_runner(spec.executable, runner)
        diagnostics = self._diagnostics(spec, runner_path)
        if not runner_path:
            return DoubaoResult(
                status="missing_runner",
                provider=spec.name,
                command="status",
                runner=runner,
                adapter=spec.adapter,
                setup_hints=spec.setup_hints,
                diagnostics=diagnostics,
            )

        result = self._run_command([runner_path] + spec.status_args, timeout_seconds, "status", spec, DoubaoRequest(""))
        result.diagnostics = diagnostics
        return result

    def launch_desktop(
        self,
        port: int = 9225,
        app_binary: Path = DEFAULT_DOUBAO_APP_BINARY,
        dry_run: bool = False,
    ) -> DoubaoResult:
        command = [str(app_binary), f"--remote-debugging-port={port}"]
        diagnostics = {
            "app_binary": str(app_binary),
            "app_binary_exists": app_binary.exists(),
            "cdp_endpoint": f"http://127.0.0.1:{port}",
        }
        if dry_run:
            return DoubaoResult(
                status="completed",
                provider=PROVIDER_OPENCLI_APP,
                command="launch",
                stdout=shlex.join(command),
                diagnostics=diagnostics,
                setup_hints=[] if app_binary.exists() else ["Install Doubao Desktop or pass --app-binary."],
            )
        if not app_binary.exists():
            return DoubaoResult(
                status="missing_app",
                provider=PROVIDER_OPENCLI_APP,
                command="launch",
                diagnostics=diagnostics,
                setup_hints=[
                    "Install Doubao Desktop or pass --app-binary to the Doubao executable.",
                    "After launch, export OPENCLI_CDP_ENDPOINT=http://127.0.0.1:9225 for OpenCLI.",
                ],
            )
        process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        diagnostics["pid"] = process.pid
        return DoubaoResult(
            status="completed",
            provider=PROVIDER_OPENCLI_APP,
            command="launch",
            stdout=f"launched Doubao Desktop with pid {process.pid}",
            diagnostics=diagnostics,
            setup_hints=[f"export OPENCLI_CDP_ENDPOINT=http://127.0.0.1:{port}"],
        )

    def _run_command(
        self,
        command: Sequence[str],
        timeout_seconds: int,
        operation: str,
        spec: ProviderSpec,
        request: DoubaoRequest,
        prompt: str = "",
    ) -> DoubaoResult:
        try:
            completed = subprocess.run(
                list(command),
                text=True,
                capture_output=True,
                timeout=timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            return DoubaoResult(
                status="timeout",
                provider=spec.name,
                command=operation,
                returncode=None,
                prompt=prompt or None,
                raw_prompt=request.prompt or None,
                stdout=exc.stdout or "",
                stderr=exc.stderr or "",
                runner=command[0] if command else None,
                adapter=spec.adapter,
                setup_hints=spec.setup_hints,
            )

        stdout = completed.stdout.strip()
        stderr = completed.stderr.strip()
        return DoubaoResult(
            status="completed" if completed.returncode == 0 else "failed",
            provider=spec.name,
            command=operation,
            returncode=completed.returncode,
            prompt=prompt or None,
            raw_prompt=request.prompt or None,
            response=stdout if operation in {"ask", "read"} and completed.returncode == 0 else "",
            stdout=stdout,
            stderr=stderr,
            runner=command[0] if command else None,
            adapter=spec.adapter,
            setup_hints=[] if completed.returncode == 0 else spec.setup_hints,
        )

    def _missing_runner_result(
        self,
        operation: str,
        spec: ProviderSpec,
        request: DoubaoRequest,
        prompt: str,
    ) -> DoubaoResult:
        return DoubaoResult(
            status="missing_runner",
            provider=spec.name,
            command=operation,
            prompt=prompt or None,
            raw_prompt=request.prompt or None,
            runner=request.runner,
            adapter=spec.adapter,
            setup_hints=spec.setup_hints,
            diagnostics=self._diagnostics(spec, None),
        )

    def _resolve_provider(self, provider: str, runner: Optional[str]) -> str:
        if provider != PROVIDER_AUTO:
            return provider

        env_provider = os.environ.get("DOUBAO_CLI_PROVIDER")
        if env_provider in SUPPORTED_PROVIDERS and env_provider != PROVIDER_AUTO:
            return env_provider

        runner_name = Path(runner).name if runner else ""
        if runner_name == "doubao-cli":
            return PROVIDER_DOUBAO_CLI
        if shutil.which("opencli"):
            return PROVIDER_OPENCLI_APP
        if shutil.which("doubao-cli"):
            return PROVIDER_DOUBAO_CLI
        return PROVIDER_OPENCLI_APP

    def _resolve_runner(self, executable: str, override: Optional[str]) -> Optional[str]:
        candidate = override or executable
        if os.sep in candidate:
            path = Path(candidate).expanduser()
            return str(path) if path.exists() and os.access(path, os.X_OK) else None
        return shutil.which(candidate)

    def _provider_spec(self, provider: str, opencli_adapter: Optional[str]) -> ProviderSpec:
        if provider == PROVIDER_OPENCLI_APP:
            adapter = opencli_adapter or os.environ.get("DOUBAO_OPENCLI_ADAPTER") or "doubao-app"
            return ProviderSpec(
                name=PROVIDER_OPENCLI_APP,
                executable="opencli",
                adapter=adapter,
                ask_args=lambda prompt: [adapter, "ask", prompt],
                status_args=[adapter, "status"],
                read_args=[adapter, "read"],
                new_args=[adapter, "new"],
                setup_hints=[
                    "Install OpenCLI (`npm install -g @jackwener/opencli`, Node.js >= 20) or install OpenCLIApp, then ensure `opencli` is on PATH.",
                    "Launch Doubao Desktop with `/Applications/Doubao.app/Contents/MacOS/Doubao --remote-debugging-port=9225`.",
                    "If Doubao is already running without CDP, quit it first and relaunch with the remote debugging port.",
                    "Set `OPENCLI_CDP_ENDPOINT=http://127.0.0.1:9225` before running this wrapper.",
                ],
            )
        if provider == PROVIDER_OPENCLI_WEB:
            adapter = opencli_adapter or os.environ.get("DOUBAO_OPENCLI_ADAPTER") or "doubao"
            return ProviderSpec(
                name=PROVIDER_OPENCLI_WEB,
                executable="opencli",
                adapter=adapter,
                ask_args=lambda prompt: [adapter, "ask", prompt],
                status_args=[adapter, "status"],
                read_args=[adapter, "read"],
                new_args=[adapter, "new"],
                setup_hints=[
                    "Install OpenCLI (`npm install -g @jackwener/opencli`, Node.js >= 20) or install OpenCLIApp, then ensure `opencli` is on PATH.",
                    "Install and connect the OpenCLI Browser Bridge extension for the browser profile.",
                    "Log in to Doubao Web in the browser profile used by the OpenCLI adapter.",
                    "If your OpenCLI adapter has a different name, pass --opencli-adapter.",
                ],
            )
        if provider == PROVIDER_DOUBAO_CLI:
            return ProviderSpec(
                name=PROVIDER_DOUBAO_CLI,
                executable="doubao-cli",
                adapter=None,
                ask_args=lambda prompt: [prompt],
                status_args=["account"],
                read_args=["last"],
                new_args=["new"],
                setup_hints=[
                    "Install a browser-session based doubao-cli and ensure `doubao-cli` is on PATH.",
                    "Run `doubao-cli login --web` or the runner's supported login flow before asking.",
                ],
            )
        raise ValueError(f"unsupported provider: {provider}")

    def _apply_purpose(self, prompt: str, purpose: str) -> str:
        cleaned = prompt.strip()
        if purpose == "general":
            return cleaned
        if purpose == "creative":
            return (
                "请把以下内容当作中文小说创作候选素材生成任务。"
                "只输出可供 Codex 再整理的候选创意，不要声明为已确认事实。\n\n"
                f"{cleaned}"
            )
        if purpose == "dialogue":
            return (
                "请围绕以下要求生成多组中文小说对白候选。"
                "保持人物动机清晰，避免把新增设定写成既定事实。\n\n"
                f"{cleaned}"
            )
        if purpose == "rewrite":
            return (
                "请在不改变剧情事实、人物关系和因果顺序的前提下润色或改写以下文本。"
                "如果必须新增信息，请明确标为候选。\n\n"
                f"{cleaned}"
            )
        raise ValueError(f"unsupported purpose: {purpose}")

    def _diagnostics(self, spec: ProviderSpec, runner_path: Optional[str]) -> Dict[str, object]:
        diagnostics: Dict[str, object] = {
            "runner_found": runner_path is not None,
            "runner_path": runner_path,
        }
        if spec.name == PROVIDER_OPENCLI_APP:
            diagnostics.update(
                {
                    "doubao_app_found": DEFAULT_DOUBAO_APP_PATH.exists(),
                    "doubao_app_binary": str(DEFAULT_DOUBAO_APP_BINARY),
                    "opencli_cdp_endpoint": os.environ.get("OPENCLI_CDP_ENDPOINT"),
                }
            )
        return diagnostics
