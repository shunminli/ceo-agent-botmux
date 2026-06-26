from __future__ import annotations

import json
import shlex
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from .llmwiki_sync import LlmwikiSyncRequest, LlmwikiSyncResult, LlmwikiSyncer
from .mcp_config import NovelLlmwikiMcpConfigBuilder, NovelLlmwikiMcpConfigRequest, NovelLlmwikiMcpConfigResult
from .runtime import NovelFoundationRequest, NovelFoundationResult, NovelRuntime, NovelWikiBundleResult, NovelWikiBundleRequest
from .schema_validation import validate_schema
from .workspace import utc_now


@dataclass(frozen=True)
class NovelBootstrapRequest:
    project_path: Path
    title: str
    inspiration: str
    project_slug: str
    workspace_path: Optional[Path] = None
    chapter_number: int = 1
    mode: str = "lean"
    word_target: int = 1200
    llmwiki_bin: str = "llmwiki"


@dataclass(frozen=True)
class NovelBootstrapResult:
    run_id: str
    status: str
    project_path: Path
    project_slug: str
    workspace_path: Path
    foundation: NovelFoundationResult
    wiki_bundle: NovelWikiBundleResult
    llmwiki_sync: LlmwikiSyncResult
    mcp_config: NovelLlmwikiMcpConfigResult
    approval_package_path: Path
    approval_package_json_path: Path
    artifacts: List[Path]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "status": self.status,
            "project_path": str(self.project_path),
            "project_slug": self.project_slug,
            "workspace_path": str(self.workspace_path),
            "foundation": self.foundation.to_dict(),
            "wiki_bundle": self.wiki_bundle.to_dict(),
            "llmwiki_sync": self.llmwiki_sync.to_dict(),
            "mcp_config": self.mcp_config.to_dict(),
            "approval_package_path": str(self.approval_package_path),
            "approval_package_json_path": str(self.approval_package_json_path),
            "artifacts": [str(path) for path in self.artifacts],
        }


@dataclass(frozen=True)
class ApprovalPackageWriteResult:
    payload: Dict[str, Any]
    approval_package_path: Path
    approval_package_json_path: Path


class NovelBootstrapper:
    def __init__(self) -> None:
        self.runtime = NovelRuntime()
        self.llmwiki_syncer = LlmwikiSyncer()
        self.mcp_config_builder = NovelLlmwikiMcpConfigBuilder()

    def bootstrap(self, request: NovelBootstrapRequest) -> NovelBootstrapResult:
        project_path = request.project_path.expanduser().resolve()
        workspace_path = (
            request.workspace_path.expanduser().resolve()
            if request.workspace_path is not None
            else project_path
        )
        started_at = utc_now()
        run_id = f"bootstrap-{started_at.replace(':', '').replace('-', '')}-{uuid.uuid4().hex[:8]}"

        foundation = self.runtime.foundation(
            NovelFoundationRequest(
                project_path=project_path,
                title=request.title,
                inspiration=request.inspiration,
                chapter_number=request.chapter_number,
                mode=request.mode,
                word_target=request.word_target,
            )
        )
        wiki_bundle = self.runtime.wiki_bundle(
            NovelWikiBundleRequest(
                project_path=project_path,
                project_slug=request.project_slug,
                foundation_path=foundation.foundation_path,
            )
        )
        llmwiki_sync = self.llmwiki_syncer.sync(
            LlmwikiSyncRequest(
                project_path=project_path,
                project_slug=request.project_slug,
                workspace_path=workspace_path,
                approve=False,
                llmwiki_bin=request.llmwiki_bin,
                reindex=True,
                lint=True,
            )
        )
        mcp_config = self.mcp_config_builder.build(
            NovelLlmwikiMcpConfigRequest(
                workspace_path=workspace_path,
                project_slug=request.project_slug,
                llmwiki_bin=request.llmwiki_bin,
            )
        )

        run_dir = project_path / "runs" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        approval_package = write_approval_package(
            request=request,
            run_id=run_id,
            foundation=foundation,
            wiki_bundle=wiki_bundle,
            llmwiki_sync=llmwiki_sync,
            mcp_config=mcp_config,
            run_dir=run_dir,
        )

        artifacts = [
            foundation.foundation_path,
            wiki_bundle.bundle_path,
            llmwiki_sync.plan_path,
            approval_package.approval_package_json_path,
            approval_package.approval_package_path,
        ]
        status = "ready" if mcp_config.status == "ready" else "ready_with_warnings"
        return NovelBootstrapResult(
            run_id=run_id,
            status=status,
            project_path=project_path,
            project_slug=wiki_bundle.project_slug,
            workspace_path=workspace_path,
            foundation=foundation,
            wiki_bundle=wiki_bundle,
            llmwiki_sync=llmwiki_sync,
            mcp_config=mcp_config,
            approval_package_path=approval_package.approval_package_path,
            approval_package_json_path=approval_package.approval_package_json_path,
            artifacts=artifacts,
        )


def write_approval_package(
    *,
    request: NovelBootstrapRequest,
    run_id: str,
    foundation: NovelFoundationResult,
    wiki_bundle: NovelWikiBundleResult,
    llmwiki_sync: LlmwikiSyncResult,
    mcp_config: NovelLlmwikiMcpConfigResult,
    run_dir: Path,
    extra_payload: Optional[Dict[str, Any]] = None,
    extra_warnings: Optional[List[str]] = None,
) -> ApprovalPackageWriteResult:
    run_dir.mkdir(parents=True, exist_ok=True)
    approval_package_json_path = run_dir / "approval-package.json"
    approval_package_path = run_dir / "approval-package.md"
    payload = approval_payload(
        request=request,
        run_id=run_id,
        foundation=foundation,
        wiki_bundle=wiki_bundle,
        llmwiki_sync=llmwiki_sync,
        mcp_config=mcp_config,
    )
    payload["human_gate"]["approval_decision_command"] = [
        "python3",
        "-m",
        "botmux_novel",
        "approval-decision",
        "--approval-package",
        str(approval_package_json_path),
        "--decision",
        "approve",
        "--reviewer",
        "human",
        "--notes",
        "Approved after reviewing approval-package.md and wiki bundle.",
    ]
    payload["human_gate"]["approval_apply_command"] = [
        "python3",
        "-m",
        "botmux_novel",
        "approval-apply",
        "--approval-package",
        str(approval_package_json_path),
        "--approve",
    ]
    payload["next_actions"]["chapter_start_command"] = [
        "python3",
        "-m",
        "botmux_novel",
        "chapter",
        "--project",
        str(foundation.project_path),
        "--chapter-number",
        str(request.chapter_number),
        "--foundation-json",
        str(foundation.foundation_path),
    ]
    payload["next_actions"]["chapter_workflow_command"] = build_chapter_workflow_command(
        request=request,
        foundation=foundation,
        project_slug=wiki_bundle.project_slug,
    )
    if extra_warnings:
        payload["llmwiki"]["warnings"].extend(extra_warnings)
    if extra_payload:
        payload.update(extra_payload)
    validate_schema("approval-package", payload)
    approval_package_json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    approval_package_path.write_text(render_approval_markdown(payload), encoding="utf-8")
    return ApprovalPackageWriteResult(
        payload=payload,
        approval_package_path=approval_package_path,
        approval_package_json_path=approval_package_json_path,
    )


def approval_payload(
    *,
    request: NovelBootstrapRequest,
    run_id: str,
    foundation: NovelFoundationResult,
    wiki_bundle: NovelWikiBundleResult,
    llmwiki_sync: LlmwikiSyncResult,
    mcp_config: NovelLlmwikiMcpConfigResult,
) -> Dict[str, Any]:
    return {
        "run_id": run_id,
        "status": "ready_for_human_review",
        "project": {
            "title": request.title,
            "project_slug": wiki_bundle.project_slug,
            "project_path": str(foundation.project_path),
            "llmwiki_workspace_path": str(llmwiki_sync.workspace_path),
        },
        "review_materials": {
            "foundation_json": str(foundation.foundation_path),
            "story_markdown": str(foundation.story_path),
            "wiki_bundle": str(wiki_bundle.bundle_path),
            "llmwiki_sync_plan": str(llmwiki_sync.plan_path),
            "mcp_server_name": mcp_config.server_name,
        },
        "human_gate": {
            "decision": "approve|request_changes|reject",
            "must_review": [
                "Story Bible promise, core characters, relationship pressure, plot trajectory, scene rules, and forbidden reveals",
                "wiki page list and target namespace",
                "llmwiki MCP binding policy for Director and Validator",
                "rollback and lint plan before any approved write",
            ],
            "approved_write_command": [
                "python3",
                "-m",
                "botmux_novel",
                "llmwiki-sync",
                "--project",
                str(foundation.project_path),
                "--project-slug",
                wiki_bundle.project_slug,
                "--workspace",
                str(llmwiki_sync.workspace_path),
                "--llmwiki-bin",
                request.llmwiki_bin,
                "--approve",
                "--reindex",
                "--lint",
            ],
        },
        "llmwiki": {
            "sync_status": llmwiki_sync.status,
            "approved": llmwiki_sync.approved,
            "preview": sync_plan_preview(llmwiki_sync.plan_path),
            "mcp_config": mcp_config.to_dict(),
            "warnings": [*llmwiki_sync.warnings, *mcp_config.warnings],
        },
        "next_actions": {},
        "next_steps": [
            "Human reviews approval-package.md and wiki bundle pages.",
            "If approved, run approval_decision_command to record reviewer, decision, timestamp, and notes.",
            "Run approval_apply_command or let Director execute an equivalent humanGate-approved write.",
            "After llmwiki sync, configure the generated MCP server for Director and Validator only.",
            "Run chapter_workflow_command to start the real three-bot opening chapter workflow, or chapter_start_command for local runtime smoke.",
        ],
    }


def build_chapter_workflow_command(
    *,
    request: NovelBootstrapRequest,
    foundation: NovelFoundationResult,
    project_slug: str,
) -> List[str]:
    foundation_payload = json.loads(foundation.foundation_path.read_text(encoding="utf-8"))
    chapter_goal = foundation_payload.get("chapter_goal", {})
    project = foundation_payload.get("project", {})
    chapter_id = str(chapter_goal.get("chapter_id", f"ch-{request.chapter_number:03d}"))
    chapter_number = chapter_number_from_id(chapter_id, default=request.chapter_number)
    word_target = int(project.get("word_target", request.word_target))
    mode = str(project.get("mode", request.mode))
    return [
        "botmux",
        "workflow",
        "run",
        "novel-chapter-production",
        "--param",
        f"projectSlug={project_slug}",
        "--param",
        f"title={request.title}",
        "--param",
        f"storyBible={story_bible_workflow_param(foundation_payload)}",
        "--param",
        f"chapterNumber={chapter_number}",
        "--param",
        f"chapterGoal={chapter_goal.get('objective', '')}",
        "--param",
        "priorContext=无",
        "--param",
        f"wordTarget={word_target}",
        "--param",
        f"mode={mode}",
    ]


def chapter_number_from_id(chapter_id: str, *, default: int) -> int:
    prefix = "ch-"
    if chapter_id.startswith(prefix):
        suffix = chapter_id[len(prefix):]
        if suffix.isdigit():
            return int(suffix)
    return default


def story_bible_workflow_param(foundation_payload: Dict[str, Any]) -> str:
    project = foundation_payload.get("project", {})
    story = foundation_payload.get("story_bible", {})
    genre = foundation_payload.get("genre", {})
    world = foundation_payload.get("world", {})
    volume = foundation_payload.get("volume_outline", {})
    chapter_goal = foundation_payload.get("chapter_goal", {})
    characters = foundation_payload.get("characters", [])
    relationships = foundation_payload.get("relationships", {}).get("edges", [])
    scenes = foundation_payload.get("scene_settings", [])

    character_lines = [
        f"- {item.get('name', item.get('id', 'unknown'))}: {item.get('role', '')}; motivation={item.get('motivation', '')}; state={item.get('current_state', '')}"
        for item in characters
        if isinstance(item, dict)
    ]
    relationship_lines = [
        f"- {item.get('source', '')}->{item.get('target', '')}: {item.get('type', '')}; pressure={item.get('pressure', '')}"
        for item in relationships
        if isinstance(item, dict)
    ]
    scene_lines = [
        f"- {item.get('name', item.get('id', 'unknown'))}: {item.get('function', '')}"
        for item in scenes
        if isinstance(item, dict)
    ]
    sections = [
        f"Title: {project.get('title', '')}",
        f"Genre: {genre.get('primary', '')}",
        f"Theme: {story.get('theme', '')}",
        f"Inspiration: {story.get('inspiration', '')}",
        f"Core conflict: {story.get('core_conflict', '')}",
        f"Ending constraint: {story.get('ending_constraint', '')}",
        "World rules:\n" + "\n".join(f"- {item}" for item in world.get("rules", []) if item),
        "Forbidden:\n" + "\n".join(f"- {item}" for item in world.get("forbidden", []) if item),
        "Characters:\n" + "\n".join(character_lines),
        "Relationships:\n" + "\n".join(relationship_lines),
        f"Volume goal: {volume.get('goal', '')}",
        "Turning points:\n" + "\n".join(f"- {item}" for item in volume.get("turning_points", []) if item),
        "Scene settings:\n" + "\n".join(scene_lines),
        f"Opening chapter goal: {chapter_goal.get('objective', '')}",
    ]
    return "\n\n".join(section for section in sections if section.strip())


def sync_plan_preview(plan_path: Path) -> Dict[str, Any]:
    if not plan_path.exists():
        return {}
    payload = json.loads(plan_path.read_text(encoding="utf-8"))
    return {
        "target_namespace": payload.get("preview", {}).get("target_namespace"),
        "page_count": payload.get("preview", {}).get("page_count"),
        "pages": payload.get("preview", {}).get("pages", []),
        "action_summary": payload.get("preview", {}).get("action_summary", {}),
    }


def render_approval_markdown(payload: Dict[str, Any]) -> str:
    project = payload["project"]
    materials = payload["review_materials"]
    human_gate = payload["human_gate"]
    llmwiki = payload["llmwiki"]
    preview = llmwiki.get("preview", {})
    command = shlex.join(human_gate["approved_write_command"])
    decision_command = shlex.join(human_gate.get("approval_decision_command", []))
    apply_command = shlex.join(human_gate.get("approval_apply_command", []))
    chapter_start_command = shlex.join(payload.get("next_actions", {}).get("chapter_start_command", []))
    chapter_workflow_command = shlex.join(payload.get("next_actions", {}).get("chapter_workflow_command", []))
    pages = "\n".join(f"- `{page}`" for page in preview.get("pages", [])) or "- No pages found"
    must_review = "\n".join(f"- {item}" for item in human_gate["must_review"])
    next_steps = "\n".join(f"{index}. {step}" for index, step in enumerate(payload["next_steps"], start=1))
    warnings = "\n".join(f"- {warning}" for warning in llmwiki.get("warnings", [])) or "- None"
    return f"""# Novel Bootstrap Approval Package

## Project

- Title: {project["title"]}
- Project slug: `{project["project_slug"]}`
- Project path: `{project["project_path"]}`
- llmwiki workspace: `{project["llmwiki_workspace_path"]}`

## Review Materials

- Foundation JSON: `{materials["foundation_json"]}`
- Story Markdown: `{materials["story_markdown"]}`
- Wiki bundle: `{materials["wiki_bundle"]}`
- llmwiki sync plan: `{materials["llmwiki_sync_plan"]}`
- MCP server name: `{materials["mcp_server_name"]}`

## Human Gate

Decision: `{human_gate["decision"]}`

Review before approving:

{must_review}

## llmwiki Preview

- Sync status: `{llmwiki["sync_status"]}`
- Already approved: `{llmwiki["approved"]}`
- Target namespace: `{preview.get("target_namespace")}`
- Page count: `{preview.get("page_count")}`

Warnings:

{warnings}

Pages:

{pages}

Record approval decision command:

```bash
{decision_command}
```

Preferred approval apply command:

```bash
{apply_command}
```

Underlying approved write command:

```bash
{command}
```

Start opening chapter command:

```bash
{chapter_start_command}
```

Start opening chapter workflow command:

```bash
{chapter_workflow_command}
```

## Next Steps

{next_steps}
"""
