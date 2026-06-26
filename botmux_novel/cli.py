from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional

from .botmux_assets import BotmuxAssetSyncRequest, BotmuxAssetSyncer
from .runtime import NovelFoundationRequest, NovelRunRequest, NovelRuntime, NovelWikiBundleRequest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the local novel creation agent chain.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Create or continue a local novel project through one chapter.")
    run_parser.add_argument("--project", required=True, help="Target novel project directory.")
    run_parser.add_argument("--title", required=True, help="Novel project title.")
    run_parser.add_argument("--inspiration", required=True, help="One-sentence story inspiration.")
    run_parser.add_argument("--chapter-number", type=int, default=1, help="Chapter number to generate.")
    run_parser.add_argument("--mode", choices=["full", "lean", "solo"], default="lean", help="Agent execution mode.")
    run_parser.add_argument("--word-target", type=int, default=1200, help="Target chapter length.")

    foundation_parser = subparsers.add_parser(
        "foundation",
        help="Create only the opening story foundation assets without drafting a chapter.",
    )
    foundation_parser.add_argument("--project", required=True, help="Target novel project directory.")
    foundation_parser.add_argument("--title", required=True, help="Novel project title.")
    foundation_parser.add_argument("--inspiration", required=True, help="One-sentence story inspiration.")
    foundation_parser.add_argument("--chapter-number", type=int, default=1, help="Initial chapter number for planning.")
    foundation_parser.add_argument("--mode", choices=["full", "lean", "solo"], default="lean", help="Agent execution mode.")
    foundation_parser.add_argument("--word-target", type=int, default=1200, help="Target chapter length for planning.")

    wiki_parser = subparsers.add_parser(
        "wiki-bundle",
        help="Export local Markdown pages for review before llmwiki synchronization.",
    )
    wiki_parser.add_argument("--project", required=True, help="Target novel project directory.")
    wiki_parser.add_argument("--project-slug", required=True, help="Target wiki namespace slug.")
    wiki_parser.add_argument("--foundation-json", help="Optional explicit foundation.json path.")

    assets_parser = subparsers.add_parser(
        "botmux-assets",
        help="Sync versioned novel BotMux workflows and workspace AGENTS.md files.",
    )
    assets_parser.add_argument("--repo", default=str(Path(__file__).resolve().parents[1]), help="Repository root containing agents/ and workflows/.")
    assets_parser.add_argument("--botmux-home", default=str(Path.home() / ".botmux"), help="BotMux home directory.")
    assets_parser.add_argument("--write", action="store_true", help="Write files. Without this flag, only reports planned changes.")
    assets_parser.add_argument("--no-backup", action="store_true", help="Do not create .bak files before replacing existing targets.")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "run":
        request = NovelRunRequest(
            project_path=Path(args.project).expanduser().resolve(),
            title=args.title,
            inspiration=args.inspiration,
            chapter_number=args.chapter_number,
            mode=args.mode,
            word_target=args.word_target,
        )
        result = NovelRuntime().run(request)
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return 0 if result.status == "completed" else 2

    if args.command == "foundation":
        request = NovelFoundationRequest(
            project_path=Path(args.project).expanduser().resolve(),
            title=args.title,
            inspiration=args.inspiration,
            chapter_number=args.chapter_number,
            mode=args.mode,
            word_target=args.word_target,
        )
        result = NovelRuntime().foundation(request)
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return 0 if result.status == "completed" else 2

    if args.command == "wiki-bundle":
        request = NovelWikiBundleRequest(
            project_path=Path(args.project).expanduser().resolve(),
            project_slug=args.project_slug,
            foundation_path=Path(args.foundation_json).expanduser().resolve() if args.foundation_json else None,
        )
        result = NovelRuntime().wiki_bundle(request)
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return 0 if result.status == "completed" else 2

    if args.command == "botmux-assets":
        request = BotmuxAssetSyncRequest(
            repo_path=Path(args.repo).expanduser().resolve(),
            botmux_home=Path(args.botmux_home).expanduser().resolve(),
            write=args.write,
            backup=not args.no_backup,
        )
        result = BotmuxAssetSyncer().sync(request)
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return 0

    parser.error(f"unknown command: {args.command}")
    return 2
