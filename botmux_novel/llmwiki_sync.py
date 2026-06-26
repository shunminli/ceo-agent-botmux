from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from .workspace import utc_now


@dataclass(frozen=True)
class LlmwikiSyncRequest:
    project_path: Path
    project_slug: str
    workspace_path: Optional[Path] = None
    approve: bool = False
    backup: bool = True
    llmwiki_bin: str = "llmwiki"
    reindex: bool = False


@dataclass(frozen=True)
class LlmwikiSyncAction:
    source_path: Path
    target_path: Path
    status: str
    backup_path: Optional[Path] = None

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "source_path": str(self.source_path),
            "target_path": str(self.target_path),
            "status": self.status,
        }
        if self.backup_path is not None:
            payload["backup_path"] = str(self.backup_path)
        return payload


@dataclass(frozen=True)
class LlmwikiCommandResult:
    command: List[str]
    status: str
    returncode: Optional[int] = None
    stdout: str = ""
    stderr: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "command": self.command,
            "status": self.status,
            "returncode": self.returncode,
            "stdout": self.stdout,
            "stderr": self.stderr,
        }


@dataclass(frozen=True)
class LlmwikiSyncResult:
    status: str
    approved: bool
    project_path: Path
    project_slug: str
    bundle_path: Path
    workspace_path: Path
    target_path: Path
    plan_path: Path
    actions: List[LlmwikiSyncAction]
    llmwiki_available: bool
    commands: List[LlmwikiCommandResult]
    warnings: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "approved": self.approved,
            "project_path": str(self.project_path),
            "project_slug": self.project_slug,
            "bundle_path": str(self.bundle_path),
            "workspace_path": str(self.workspace_path),
            "target_path": str(self.target_path),
            "plan_path": str(self.plan_path),
            "actions": [action.to_dict() for action in self.actions],
            "llmwiki_available": self.llmwiki_available,
            "commands": [command.to_dict() for command in self.commands],
            "warnings": self.warnings,
        }


class LlmwikiSyncer:
    def sync(self, request: LlmwikiSyncRequest) -> LlmwikiSyncResult:
        project_path = request.project_path.expanduser().resolve()
        project_slug = validate_project_slug(request.project_slug)
        workspace_path = (
            request.workspace_path.expanduser().resolve()
            if request.workspace_path is not None
            else project_path
        )
        bundle_path = project_path / "wiki" / "novels" / project_slug
        if not bundle_path.exists():
            raise ValueError(f"wiki bundle does not exist: {bundle_path}; run `python -m botmux_novel wiki-bundle` first")
        if not bundle_path.is_dir():
            raise ValueError(f"wiki bundle path is not a directory: {bundle_path}")

        target_path = workspace_path / "wiki" / "novels" / project_slug
        source_files = sorted(path for path in bundle_path.rglob("*") if path.is_file())
        if not source_files:
            raise ValueError(f"wiki bundle has no files: {bundle_path}")

        actions = [
            self._sync_file(
                source_path=source,
                target_path=target_path / source.relative_to(bundle_path),
                approve=request.approve,
                backup=request.backup,
            )
            for source in source_files
        ]

        warnings: List[str] = []
        commands: List[LlmwikiCommandResult] = []
        llmwiki_executable = resolve_executable(request.llmwiki_bin)
        llmwiki_available = llmwiki_executable is not None
        if request.reindex:
            if llmwiki_executable is None:
                warnings.append(f"llmwiki executable not found: {request.llmwiki_bin}; skipped reindex")
                commands.append(
                    LlmwikiCommandResult(
                        command=[request.llmwiki_bin, "reindex", str(workspace_path)],
                        status="skipped",
                    )
                )
            elif not request.approve:
                commands.append(
                    LlmwikiCommandResult(
                        command=[llmwiki_executable, "reindex", str(workspace_path)],
                        status="planned",
                    )
                )
            else:
                commands.append(run_command([llmwiki_executable, "reindex", str(workspace_path)]))

        status = result_status(approved=request.approve, commands=commands, warnings=warnings)
        plan_path = write_sync_plan(
            project_path=project_path,
            project_slug=project_slug,
            bundle_path=bundle_path,
            workspace_path=workspace_path,
            target_path=target_path,
            approved=request.approve,
            status=status,
            actions=actions,
            commands=commands,
            warnings=warnings,
        )
        return LlmwikiSyncResult(
            status=status,
            approved=request.approve,
            project_path=project_path,
            project_slug=project_slug,
            bundle_path=bundle_path,
            workspace_path=workspace_path,
            target_path=target_path,
            plan_path=plan_path,
            actions=actions,
            llmwiki_available=llmwiki_available,
            commands=commands,
            warnings=warnings,
        )

    def _sync_file(
        self,
        *,
        source_path: Path,
        target_path: Path,
        approve: bool,
        backup: bool,
    ) -> LlmwikiSyncAction:
        source_bytes = source_path.read_bytes()
        existing = target_path.read_bytes() if target_path.exists() else None
        if existing == source_bytes:
            return LlmwikiSyncAction(source_path=source_path, target_path=target_path, status="unchanged")

        if not approve:
            status = "would_update" if target_path.exists() else "would_create"
            return LlmwikiSyncAction(source_path=source_path, target_path=target_path, status=status)

        target_path.parent.mkdir(parents=True, exist_ok=True)
        backup_path = None
        if backup and target_path.exists():
            backup_path = target_path.with_name(f"{target_path.name}.bak-{timestamp_suffix()}")
            shutil.copy2(target_path, backup_path)
        shutil.copy2(source_path, target_path)
        status = "updated" if existing is not None else "created"
        return LlmwikiSyncAction(
            source_path=source_path,
            target_path=target_path,
            status=status,
            backup_path=backup_path,
        )


def validate_project_slug(project_slug: str) -> str:
    slug = project_slug.strip()
    if not slug:
        raise ValueError("project_slug is required")
    if re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,79}", slug) is None:
        raise ValueError("project_slug must use 1-80 lowercase letters, digits, hyphen, or underscore")
    return slug


def resolve_executable(command: str) -> Optional[str]:
    expanded = Path(command).expanduser()
    if expanded.parent != Path(".") and expanded.exists():
        return str(expanded.resolve())
    return shutil.which(command)


def run_command(command: List[str]) -> LlmwikiCommandResult:
    completed = subprocess.run(command, text=True, capture_output=True, check=False)
    return LlmwikiCommandResult(
        command=command,
        status="succeeded" if completed.returncode == 0 else "failed",
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def result_status(
    *,
    approved: bool,
    commands: List[LlmwikiCommandResult],
    warnings: List[str],
) -> str:
    if any(command.status == "failed" for command in commands):
        return "failed"
    if not approved:
        return "planned"
    if warnings:
        return "completed_with_warnings"
    return "completed"


def write_sync_plan(
    *,
    project_path: Path,
    project_slug: str,
    bundle_path: Path,
    workspace_path: Path,
    target_path: Path,
    approved: bool,
    status: str,
    actions: List[LlmwikiSyncAction],
    commands: List[LlmwikiCommandResult],
    warnings: List[str],
) -> Path:
    run_id = f"llmwiki-sync-{project_slug}-{timestamp_suffix()}"
    path = project_path / "runs" / f"{run_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    page_paths = [str(action.source_path.relative_to(bundle_path)) for action in actions]
    payload = {
        "run_id": run_id,
        "status": status,
        "approved": approved,
        "project_slug": project_slug,
        "bundle_path": str(bundle_path),
        "workspace_path": str(workspace_path),
        "target_path": str(target_path),
        "preview": {
            "target_namespace": f"/wiki/novels/{project_slug}/",
            "page_count": len(page_paths),
            "pages": page_paths,
            "action_summary": count_statuses(action.status for action in actions),
        },
        "impact": {
            "knowledge_layer": "local llmwiki workspace markdown pages",
            "entities": impacted_entities(page_paths),
            "source_of_truth": "approved wiki-bundle markdown",
        },
        "source_refs": [str(bundle_path.relative_to(project_path)) if bundle_path.is_relative_to(project_path) else str(bundle_path)],
        "rollback_plan": rollback_plan(actions),
        "lint_plan": {
            "markdown_bundle": "rerun `python -m botmux_novel wiki-bundle` and inspect changed pages",
            "llmwiki": "open the workspace with llmwiki MCP and run the lint tool after writes",
            "reindex": f"llmwiki reindex {workspace_path}",
        },
        "actions": [action.to_dict() for action in actions],
        "commands": [command.to_dict() for command in commands],
        "warnings": warnings,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def count_statuses(statuses: Any) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for status in statuses:
        counts[status] = counts.get(status, 0) + 1
    return counts


def impacted_entities(page_paths: List[str]) -> List[str]:
    entities: List[str] = []
    for page_path in page_paths:
        if page_path.startswith("characters/"):
            entities.append("characters")
        else:
            entities.append(Path(page_path).stem)
    return sorted(set(entities))


def rollback_plan(actions: List[LlmwikiSyncAction]) -> List[str]:
    plan: List[str] = []
    for action in actions:
        if action.status == "created":
            plan.append(f"delete {action.target_path}")
        elif action.backup_path is not None:
            plan.append(f"restore {action.backup_path} to {action.target_path}")
    if not plan:
        plan.append("no file rollback needed for planned or unchanged actions")
    return plan


def timestamp_suffix() -> str:
    return utc_now().replace(":", "").replace("-", "")
