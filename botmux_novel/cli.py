from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional

from .approval import NovelApprovalApplier, NovelApprovalApplyRequest
from .bootstrap import NovelBootstrapper, NovelBootstrapRequest
from .botmux_assets import BotmuxAssetSyncRequest, BotmuxAssetSyncer
from .llmwiki_sync import LlmwikiSyncRequest, LlmwikiSyncer
from .mcp_config import NovelLlmwikiMcpConfigBuilder, NovelLlmwikiMcpConfigRequest
from .readiness import NovelReadinessChecker, NovelReadinessRequest
from .runtime import NovelChapterRequest, NovelFoundationRequest, NovelRunRequest, NovelRuntime, NovelWikiBundleRequest
from .series import NovelSeriesRequest, NovelSeriesRunner


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

    bootstrap_parser = subparsers.add_parser(
        "novel-bootstrap",
        help="Create an opening foundation, wiki review bundle, dry-run sync plan, MCP config, and human approval package.",
    )
    bootstrap_parser.add_argument("--project", required=True, help="Target novel project directory.")
    bootstrap_parser.add_argument("--title", required=True, help="Novel project title.")
    bootstrap_parser.add_argument("--inspiration", required=True, help="One-sentence story inspiration.")
    bootstrap_parser.add_argument("--project-slug", required=True, help="Target wiki namespace slug.")
    bootstrap_parser.add_argument("--workspace", help="llmwiki workspace directory. Defaults to --project.")
    bootstrap_parser.add_argument("--chapter-number", type=int, default=1, help="Initial chapter number for planning.")
    bootstrap_parser.add_argument("--mode", choices=["full", "lean", "solo"], default="lean", help="Agent execution mode.")
    bootstrap_parser.add_argument("--word-target", type=int, default=1200, help="Target chapter length for planning.")
    bootstrap_parser.add_argument("--llmwiki-bin", default="llmwiki", help="llmwiki executable to place in generated MCP config and planned reindex command.")

    approval_parser = subparsers.add_parser(
        "approval-apply",
        help="Apply a novel-bootstrap approval package after humanGate approval; dry-run unless --approve is passed.",
    )
    approval_parser.add_argument("--approval-package", required=True, help="Path to runs/<bootstrap_run_id>/approval-package.json.")
    approval_parser.add_argument("--approve", action="store_true", help="Apply approved wiki writes. Without this flag, only writes a fresh sync plan.")
    approval_parser.add_argument("--no-backup", action="store_true", help="Do not create .bak files before replacing target pages.")
    approval_parser.add_argument("--llmwiki-bin", help="Optional override for the llmwiki executable recorded in the approval package.")
    approval_parser.add_argument("--no-reindex", action="store_true", help="Do not run `llmwiki reindex <workspace>` after approved writes.")

    chapter_parser = subparsers.add_parser(
        "chapter",
        help="Produce one chapter from an existing foundation.json without replanning the Story Bible.",
    )
    chapter_parser.add_argument("--project", required=True, help="Target novel project directory.")
    chapter_parser.add_argument("--chapter-number", type=int, required=True, help="Chapter number to produce.")
    chapter_parser.add_argument("--chapter-goal", required=True, help="Approved chapter objective and reader promise.")
    chapter_parser.add_argument("--foundation-json", help="Optional explicit foundation.json path.")
    chapter_parser.add_argument("--mode", choices=["full", "lean", "solo"], help="Optional mode override; defaults to foundation mode.")
    chapter_parser.add_argument("--word-target", type=int, help="Optional target chapter length override.")

    wiki_parser = subparsers.add_parser(
        "wiki-bundle",
        help="Export local Markdown pages for review before llmwiki synchronization.",
    )
    wiki_parser.add_argument("--project", required=True, help="Target novel project directory.")
    wiki_parser.add_argument("--project-slug", required=True, help="Target wiki namespace slug.")
    wiki_parser.add_argument("--foundation-json", help="Optional explicit foundation.json path.")

    llmwiki_parser = subparsers.add_parser(
        "llmwiki-sync",
        help="Gate and sync an approved local wiki bundle into an llmwiki workspace.",
    )
    llmwiki_parser.add_argument("--project", required=True, help="Novel project directory containing wiki/novels/<slug>.")
    llmwiki_parser.add_argument("--project-slug", required=True, help="Target wiki namespace slug.")
    llmwiki_parser.add_argument("--workspace", help="llmwiki workspace directory. Defaults to --project.")
    llmwiki_parser.add_argument("--approve", action="store_true", help="Apply file writes. Without this flag, only writes a local sync plan.")
    llmwiki_parser.add_argument("--no-backup", action="store_true", help="Do not create .bak files before replacing target pages.")
    llmwiki_parser.add_argument("--llmwiki-bin", default="llmwiki", help="llmwiki executable to use for optional commands.")
    llmwiki_parser.add_argument("--reindex", action="store_true", help="Run `llmwiki reindex <workspace>` after approved writes when llmwiki is available.")

    mcp_parser = subparsers.add_parser(
        "llmwiki-mcp-config",
        help="Generate per-project llmwiki MCP snippets and role binding policy without editing global config.",
    )
    mcp_parser.add_argument("--workspace", required=True, help="llmwiki workspace directory for this novel project.")
    mcp_parser.add_argument("--project-slug", required=True, help="Target wiki namespace slug.")
    mcp_parser.add_argument("--server-name", help="Optional MCP server name. Defaults to llmwiki-novel-<project-slug>.")
    mcp_parser.add_argument("--llmwiki-bin", default="llmwiki", help="llmwiki executable to place in generated MCP config.")
    mcp_parser.add_argument("--codex-startup-timeout-sec", type=int, default=20, help="startup_timeout_sec for the Codex TOML snippet.")

    series_parser = subparsers.add_parser(
        "series",
        help="Run a multi-chapter local sample and emit Phase 3 quality metrics.",
    )
    series_parser.add_argument("--project", required=True, help="Target novel project directory.")
    series_parser.add_argument("--title", required=True, help="Novel project title.")
    series_parser.add_argument("--inspiration", required=True, help="One-sentence story inspiration.")
    series_parser.add_argument("--project-slug", required=True, help="Target wiki namespace slug.")
    series_parser.add_argument("--chapter-count", type=int, default=5, help="Number of chapters to generate.")
    series_parser.add_argument("--mode", choices=["full", "lean", "solo"], default="lean", help="Agent execution mode.")
    series_parser.add_argument("--word-target", type=int, default=1200, help="Target chapter length.")
    series_parser.add_argument("--llmwiki-sync", action="store_true", help="Also create a gated llmwiki-sync plan.")
    series_parser.add_argument("--approve-llmwiki", action="store_true", help="Apply llmwiki workspace sync after bundle export.")
    series_parser.add_argument("--llmwiki-workspace", help="llmwiki workspace directory. Defaults to --project.")
    series_parser.add_argument("--llmwiki-bin", default="llmwiki", help="llmwiki executable to use for optional commands.")
    series_parser.add_argument("--reindex", action="store_true", help="Run `llmwiki reindex <workspace>` after approved llmwiki sync.")

    readiness_parser = subparsers.add_parser(
        "readiness",
        help="Check local novel production readiness across BotMux, workflows, llmwiki, and optional series smoke.",
    )
    readiness_parser.add_argument("--repo", default=str(Path(__file__).resolve().parents[1]), help="Repository root containing agents/ and workflows/.")
    readiness_parser.add_argument("--botmux-home", default=str(Path.home() / ".botmux"), help="BotMux home directory.")
    readiness_parser.add_argument("--botmux-bin", default=str(Path.home() / ".botmux" / "bin" / "botmux"), help="BotMux executable.")
    readiness_parser.add_argument("--llmwiki-bin", default="llmwiki", help="llmwiki executable to check.")
    readiness_parser.add_argument("--bootstrap-smoke", action="store_true", help="Run a temporary novel-bootstrap smoke without approved llmwiki writes.")
    readiness_parser.add_argument("--series-smoke", action="store_true", help="Run a temporary multi-chapter series smoke.")
    readiness_parser.add_argument("--smoke-chapter-count", type=int, default=5, help="Chapter count for --series-smoke.")
    readiness_parser.add_argument(
        "--llmwiki-smoke",
        action="store_true",
        help="Run a temporary approved llmwiki workspace sync and reindex smoke.",
    )

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

    if args.command == "novel-bootstrap":
        request = NovelBootstrapRequest(
            project_path=Path(args.project).expanduser().resolve(),
            title=args.title,
            inspiration=args.inspiration,
            project_slug=args.project_slug,
            workspace_path=Path(args.workspace).expanduser().resolve() if args.workspace else None,
            chapter_number=args.chapter_number,
            mode=args.mode,
            word_target=args.word_target,
            llmwiki_bin=args.llmwiki_bin,
        )
        result = NovelBootstrapper().bootstrap(request)
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return 0 if result.status in {"ready", "ready_with_warnings"} else 2

    if args.command == "approval-apply":
        request = NovelApprovalApplyRequest(
            approval_package_path=Path(args.approval_package).expanduser().resolve(),
            approve=args.approve,
            backup=not args.no_backup,
            llmwiki_bin=args.llmwiki_bin,
            reindex=not args.no_reindex,
        )
        result = NovelApprovalApplier().apply(request)
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return 0 if result.status in {"planned", "completed", "completed_with_warnings"} else 2

    if args.command == "chapter":
        request = NovelChapterRequest(
            project_path=Path(args.project).expanduser().resolve(),
            chapter_number=args.chapter_number,
            chapter_goal=args.chapter_goal,
            foundation_path=Path(args.foundation_json).expanduser().resolve() if args.foundation_json else None,
            mode=args.mode,
            word_target=args.word_target,
        )
        result = NovelRuntime().chapter(request)
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

    if args.command == "llmwiki-sync":
        request = LlmwikiSyncRequest(
            project_path=Path(args.project).expanduser().resolve(),
            project_slug=args.project_slug,
            workspace_path=Path(args.workspace).expanduser().resolve() if args.workspace else None,
            approve=args.approve,
            backup=not args.no_backup,
            llmwiki_bin=args.llmwiki_bin,
            reindex=args.reindex,
        )
        result = LlmwikiSyncer().sync(request)
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return 0 if result.status in {"planned", "completed", "completed_with_warnings"} else 2

    if args.command == "llmwiki-mcp-config":
        request = NovelLlmwikiMcpConfigRequest(
            workspace_path=Path(args.workspace).expanduser().resolve(),
            project_slug=args.project_slug,
            server_name=args.server_name,
            llmwiki_bin=args.llmwiki_bin,
            codex_startup_timeout_sec=args.codex_startup_timeout_sec,
        )
        result = NovelLlmwikiMcpConfigBuilder().build(request)
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return 0 if result.status in {"ready", "ready_with_warnings"} else 2

    if args.command == "series":
        request = NovelSeriesRequest(
            project_path=Path(args.project).expanduser().resolve(),
            title=args.title,
            inspiration=args.inspiration,
            project_slug=args.project_slug,
            chapter_count=args.chapter_count,
            mode=args.mode,
            word_target=args.word_target,
            llmwiki_sync=args.llmwiki_sync,
            approve_llmwiki=args.approve_llmwiki,
            llmwiki_workspace_path=Path(args.llmwiki_workspace).expanduser().resolve() if args.llmwiki_workspace else None,
            llmwiki_bin=args.llmwiki_bin,
            reindex=args.reindex,
        )
        result = NovelSeriesRunner().run(request)
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return 0 if result.status == "completed" else 2

    if args.command == "readiness":
        request = NovelReadinessRequest(
            repo_path=Path(args.repo).expanduser().resolve(),
            botmux_home=Path(args.botmux_home).expanduser().resolve(),
            botmux_bin=Path(args.botmux_bin).expanduser(),
            llmwiki_bin=args.llmwiki_bin,
            run_bootstrap_smoke=args.bootstrap_smoke,
            run_series_smoke=args.series_smoke,
            smoke_chapter_count=args.smoke_chapter_count,
            run_llmwiki_smoke=args.llmwiki_smoke,
        )
        result = NovelReadinessChecker().check(request)
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return 0 if result.status in {"ready", "ready_with_warnings"} else 2

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
