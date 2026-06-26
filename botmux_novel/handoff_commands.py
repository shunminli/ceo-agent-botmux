from __future__ import annotations

import shlex
from pathlib import Path
from typing import Any, Dict, List, Optional


def build_chapter_knowledge_handoff(
    *,
    project_path: Path,
    project_slug: str,
    foundation_path: Optional[Any] = None,
    workspace_path: Optional[Any] = None,
) -> Dict[str, Any]:
    wiki_bundle_command = build_wiki_bundle_command(
        project_path=project_path,
        project_slug=project_slug,
        foundation_path=foundation_path,
    )
    sync_plan_command = build_llmwiki_sync_command(
        project_path=project_path,
        project_slug=project_slug,
        workspace_path=workspace_path,
        approve=False,
    )
    approved_sync_command = build_llmwiki_sync_command(
        project_path=project_path,
        project_slug=project_slug,
        workspace_path=workspace_path,
        approve=True,
    )
    return {
        "wiki_bundle_command": wiki_bundle_command,
        "wiki_bundle_command_text": shlex.join(wiki_bundle_command),
        "llmwiki_sync_plan_command": sync_plan_command,
        "llmwiki_sync_plan_command_text": shlex.join(sync_plan_command),
        "approved_llmwiki_sync_command": approved_sync_command,
        "approved_llmwiki_sync_command_text": shlex.join(approved_sync_command),
        "human_gate": (
            "Review the regenerated wiki bundle and dry-run sync plan before running the "
            "approved llmwiki sync command."
        ),
    }


def build_wiki_bundle_command(
    *,
    project_path: Path,
    project_slug: str,
    foundation_path: Optional[Any] = None,
) -> List[str]:
    command = [
        "python3",
        "-m",
        "botmux_novel",
        "wiki-bundle",
        "--project",
        str(project_path),
        "--project-slug",
        project_slug,
    ]
    if foundation_path:
        command.extend(["--foundation-json", str(foundation_path)])
    return command


def build_llmwiki_sync_command(
    *,
    project_path: Path,
    project_slug: str,
    workspace_path: Optional[Any] = None,
    approve: bool = False,
) -> List[str]:
    command = [
        "python3",
        "-m",
        "botmux_novel",
        "llmwiki-sync",
        "--project",
        str(project_path),
        "--project-slug",
        project_slug,
    ]
    if workspace_path:
        command.extend(["--workspace", str(workspace_path)])
    if approve:
        command.append("--approve")
    command.extend(["--reindex", "--lint"])
    return command
