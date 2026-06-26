from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from .llmwiki_sync import LlmwikiSyncRequest, LlmwikiSyncResult, LlmwikiSyncer


@dataclass(frozen=True)
class NovelApprovalApplyRequest:
    approval_package_path: Path
    approve: bool = False
    backup: bool = True
    llmwiki_bin: Optional[str] = None
    reindex: bool = True


@dataclass(frozen=True)
class NovelApprovalApplyResult:
    status: str
    approved: bool
    approval_package_path: Path
    project_path: Path
    project_slug: str
    workspace_path: Path
    llmwiki_sync: LlmwikiSyncResult
    warnings: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "approved": self.approved,
            "approval_package_path": str(self.approval_package_path),
            "project_path": str(self.project_path),
            "project_slug": self.project_slug,
            "workspace_path": str(self.workspace_path),
            "llmwiki_sync": self.llmwiki_sync.to_dict(),
            "warnings": self.warnings,
        }


class NovelApprovalApplier:
    def __init__(self) -> None:
        self.llmwiki_syncer = LlmwikiSyncer()

    def apply(self, request: NovelApprovalApplyRequest) -> NovelApprovalApplyResult:
        approval_package_path = request.approval_package_path.expanduser().resolve()
        payload = load_approval_package(approval_package_path)
        project_path = Path(payload["project"]["project_path"]).expanduser().resolve()
        project_slug = str(payload["project"]["project_slug"])
        workspace_path = Path(payload["project"]["llmwiki_workspace_path"]).expanduser().resolve()
        approved_command = payload.get("human_gate", {}).get("approved_write_command", [])
        llmwiki_bin = request.llmwiki_bin or command_option(approved_command, "--llmwiki-bin") or "llmwiki"

        warnings: List[str] = []
        decision = payload.get("human_gate", {}).get("decision")
        if request.approve and decision != "approve":
            warnings.append(
                "approval package decision is not set to `approve`; treating explicit --approve as the humanGate signal"
            )

        sync_result = self.llmwiki_syncer.sync(
            LlmwikiSyncRequest(
                project_path=project_path,
                project_slug=project_slug,
                workspace_path=workspace_path,
                approve=request.approve,
                backup=request.backup,
                llmwiki_bin=llmwiki_bin,
                reindex=request.reindex,
            )
        )
        status = sync_result.status if sync_result.status != "completed" or not warnings else "completed_with_warnings"
        return NovelApprovalApplyResult(
            status=status,
            approved=request.approve,
            approval_package_path=approval_package_path,
            project_path=project_path,
            project_slug=project_slug,
            workspace_path=workspace_path,
            llmwiki_sync=sync_result,
            warnings=[*warnings, *sync_result.warnings],
        )


def load_approval_package(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise ValueError(f"approval package does not exist: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("status") != "ready_for_human_review":
        raise ValueError("approval package status must be ready_for_human_review")
    project = payload.get("project")
    if not isinstance(project, dict):
        raise ValueError("approval package missing project object")
    for key in ["project_path", "project_slug", "llmwiki_workspace_path"]:
        if not project.get(key):
            raise ValueError(f"approval package project missing {key}")
    return payload


def command_option(command: Any, option: str) -> Optional[str]:
    if not isinstance(command, list):
        return None
    for index, value in enumerate(command[:-1]):
        if value == option:
            return str(command[index + 1])
    return None
