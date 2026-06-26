from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from .runtime import (
    DEFAULT_DOUBAO_APP_BINARY,
    PROVIDER_AUTO,
    SUPPORTED_PROVIDERS,
    DoubaoRequest,
    DoubaoResult,
    DoubaoRuntime,
)

PURPOSES = ["general", "creative", "dialogue", "rewrite"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Wrap Doubao Desktop/Web automation runners behind a stable local CLI."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    ask_parser = subparsers.add_parser("ask", help="Send a prompt to Doubao and print the reply.")
    add_runner_args(ask_parser)
    ask_parser.add_argument("prompt", nargs="?", help="Prompt text. Use '-' to read from stdin.")
    ask_parser.add_argument("--prompt-file", help="Read prompt text from a UTF-8 file.")
    ask_parser.add_argument("--purpose", choices=PURPOSES, default="general", help="Optional prompt preset.")
    ask_parser.add_argument("--new", action="store_true", help="Start a new conversation before asking.")
    ask_parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")

    read_parser = subparsers.add_parser("read", help="Read the latest Doubao assistant reply.")
    add_runner_args(read_parser)
    read_parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")

    status_parser = subparsers.add_parser("status", help="Check runner availability and login/CDP status.")
    add_runner_args(status_parser)
    status_parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")

    launch_parser = subparsers.add_parser(
        "launch",
        help="Launch Doubao Desktop with remote debugging enabled for the OpenCLI app adapter.",
    )
    launch_parser.add_argument("--port", type=int, default=9225, help="CDP remote debugging port.")
    launch_parser.add_argument(
        "--app-binary",
        default=str(DEFAULT_DOUBAO_APP_BINARY),
        help="Path to the Doubao desktop executable.",
    )
    launch_parser.add_argument("--dry-run", action="store_true", help="Print the launch command without running it.")
    launch_parser.add_argument(
        "--relaunch",
        action="store_true",
        help="Quit an existing Doubao app instance before launching with the CDP port.",
    )
    launch_parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")

    return parser


def add_runner_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--provider",
        choices=SUPPORTED_PROVIDERS,
        default=PROVIDER_AUTO,
        help="Automation runner provider.",
    )
    parser.add_argument("--runner", help="Override executable path, useful for wrappers or tests.")
    parser.add_argument("--opencli-adapter", help="Override OpenCLI adapter name, e.g. doubao-app.")
    parser.add_argument("--timeout", type=int, default=180, help="Command timeout in seconds.")


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    runtime = DoubaoRuntime()

    try:
        if args.command == "ask":
            prompt = _read_prompt(args, parser)
            result = runtime.ask(
                DoubaoRequest(
                    prompt=prompt,
                    provider=args.provider,
                    runner=args.runner,
                    timeout_seconds=args.timeout,
                    start_new=args.new,
                    purpose=args.purpose,
                    opencli_adapter=args.opencli_adapter,
                )
            )
            return _emit(result, args.json)

        if args.command == "read":
            result = runtime.read(
                provider=args.provider,
                runner=args.runner,
                timeout_seconds=args.timeout,
                opencli_adapter=args.opencli_adapter,
            )
            return _emit(result, args.json)

        if args.command == "status":
            result = runtime.status(
                provider=args.provider,
                runner=args.runner,
                timeout_seconds=args.timeout,
                opencli_adapter=args.opencli_adapter,
            )
            return _emit(result, args.json)

        if args.command == "launch":
            result = runtime.launch_desktop(
                port=args.port,
                app_binary=Path(args.app_binary).expanduser(),
                dry_run=args.dry_run,
                relaunch=args.relaunch,
            )
            return _emit(result, args.json)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    parser.error(f"unknown command: {args.command}")
    return 2


def _read_prompt(args: argparse.Namespace, parser: argparse.ArgumentParser) -> str:
    if args.prompt_file:
        prompt = Path(args.prompt_file).expanduser().read_text(encoding="utf-8")
    elif args.prompt == "-":
        prompt = sys.stdin.read()
    elif args.prompt:
        prompt = args.prompt
    else:
        parser.error("ask requires a prompt, --prompt-file, or '-' for stdin")
    prompt = prompt.strip()
    if not prompt:
        parser.error("prompt cannot be empty")
    return prompt


def _emit(result: DoubaoResult, as_json: bool) -> int:
    if as_json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    elif result.status == "completed":
        print(result.response or result.stdout)
    else:
        _print_failure(result)

    if result.status == "completed":
        return 0
    if result.status in {"missing_runner", "missing_app"}:
        return 127
    if result.status == "timeout":
        return 124
    return result.returncode if result.returncode is not None else 1


def _print_failure(result: DoubaoResult) -> None:
    print(f"{result.command} failed: {result.status}", file=sys.stderr)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    if result.setup_hints:
        print("Setup hints:", file=sys.stderr)
        for hint in result.setup_hints:
            print(f"- {hint}", file=sys.stderr)
