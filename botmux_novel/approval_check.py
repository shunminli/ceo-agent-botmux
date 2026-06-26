from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .approval import NovelApprovalApplier, NovelApprovalApplyRequest


@dataclass(frozen=True)
class ApprovalPackageCheck:
    name: str
    status: str
    summary: str
    data: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "summary": self.summary,
            "data": self.data,
        }


@dataclass(frozen=True)
class NovelApprovalCheckRequest:
    approval_package_path: Path
    run_apply_dry_run: bool = False
    run_chapter_smoke: bool = False


@dataclass(frozen=True)
class NovelApprovalCheckResult:
    status: str
    approval_package_path: Path
    checks: List[ApprovalPackageCheck]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "approval_package_path": str(self.approval_package_path),
            "checks": [check.to_dict() for check in self.checks],
        }


class NovelApprovalPackageChecker:
    def check(self, request: NovelApprovalCheckRequest) -> NovelApprovalCheckResult:
        approval_package_path = request.approval_package_path.expanduser().resolve()
        checks: List[ApprovalPackageCheck] = []
        payload, payload_check = load_package_payload(approval_package_path)
        checks.append(payload_check)
        if payload is None:
            return NovelApprovalCheckResult(
                status=aggregate_check_status(checks),
                approval_package_path=approval_package_path,
                checks=checks,
            )

        checks.append(check_review_materials(payload))
        checks.append(check_human_gate(payload, approval_package_path))
        checks.append(check_llmwiki_preview(payload))
        checks.append(check_mcp_policy(payload))
        checks.append(check_next_actions(payload))
        checks.append(check_workspace_target(payload))
        if request.run_apply_dry_run:
            checks.append(check_apply_dry_run(approval_package_path))
        if request.run_chapter_smoke:
            checks.append(check_chapter_smoke(payload))

        return NovelApprovalCheckResult(
            status=aggregate_check_status(checks),
            approval_package_path=approval_package_path,
            checks=checks,
        )


def load_package_payload(path: Path) -> Tuple[Optional[Dict[str, Any]], ApprovalPackageCheck]:
    if not path.exists():
        return None, ApprovalPackageCheck(
            name="package_json",
            status="fail",
            summary=f"Approval package does not exist: {path}",
            data={},
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return None, ApprovalPackageCheck(
            name="package_json",
            status="fail",
            summary=f"Approval package is invalid JSON: {exc}",
            data={"path": str(path)},
        )

    errors = []
    for key in ["status", "project", "review_materials", "human_gate", "llmwiki", "next_actions"]:
        if key not in payload:
            errors.append(f"Missing top-level field: {key}")
    if payload.get("status") != "ready_for_human_review":
        errors.append("Package status must be ready_for_human_review.")
    markdown_path = path.with_suffix(".md")
    status = "pass" if not errors and markdown_path.exists() else "warn" if not errors else "fail"
    summary = (
        "Approval package JSON and Markdown are present."
        if status == "pass"
        else "Approval package JSON is present but sibling Markdown is missing."
        if status == "warn"
        else "Approval package JSON shape is invalid."
    )
    return payload, ApprovalPackageCheck(
        name="package_json",
        status=status,
        summary=summary,
        data={"path": str(path), "markdown_path": str(markdown_path), "errors": errors},
    )


def check_review_materials(payload: Dict[str, Any]) -> ApprovalPackageCheck:
    project = payload.get("project", {})
    materials = payload.get("review_materials", {})
    plan_payload = read_json_path(materials.get("llmwiki_sync_plan"))
    path_checks = {
        "project_path": path_exists(project.get("project_path"), expected_type="dir"),
        "foundation_json": path_exists(materials.get("foundation_json"), expected_type="file"),
        "story_markdown": path_exists(materials.get("story_markdown"), expected_type="file"),
        "wiki_bundle": path_exists(materials.get("wiki_bundle"), expected_type="dir"),
        "llmwiki_sync_plan": path_exists(materials.get("llmwiki_sync_plan"), expected_type="file"),
    }
    errors = [f"Missing or invalid review material: {name}" for name, ok in path_checks.items() if not ok]
    if path_checks["llmwiki_sync_plan"] and plan_payload is None:
        errors.append("llmwiki sync plan must be valid JSON.")

    page_errors: List[str] = []
    bundle_path = path_from(materials.get("wiki_bundle"))
    if bundle_path is not None and bundle_path.exists() and bundle_path.is_dir():
        actual_pages = bundle_pages(bundle_path)
        if "overview.md" not in actual_pages:
            page_errors.append("Wiki bundle is missing overview.md.")
        plan_pages = plan_preview_pages(plan_payload)
        if plan_pages and actual_pages != plan_pages:
            page_errors.append("Wiki bundle pages do not match llmwiki sync plan preview pages.")
        if plan_payload is not None:
            expected_count = plan_payload.get("preview", {}).get("page_count")
            if expected_count != len(actual_pages):
                page_errors.append("llmwiki sync plan page_count does not match wiki bundle files.")
    errors.extend(page_errors)

    status = "pass" if not errors else "fail"
    return ApprovalPackageCheck(
        name="review_materials",
        status=status,
        summary=(
            "Approval review materials exist and wiki bundle matches the sync plan."
            if status == "pass"
            else "Approval review materials are incomplete or inconsistent."
        ),
        data={
            "path_checks": path_checks,
            "errors": errors,
            "page_count": len(bundle_pages(bundle_path)) if bundle_path and bundle_path.exists() else 0,
        },
    )


def check_human_gate(payload: Dict[str, Any], approval_package_path: Path) -> ApprovalPackageCheck:
    human_gate = payload.get("human_gate", {})
    errors = []
    decision = human_gate.get("decision")
    if decision not in {"approve|request_changes|reject", "approve", "request_changes", "reject"}:
        errors.append("human_gate.decision must be the placeholder or a recorded decision.")
    if not isinstance(human_gate.get("must_review"), list) or not human_gate.get("must_review"):
        errors.append("human_gate.must_review must be a non-empty array.")

    approved_write = human_gate.get("approved_write_command")
    decision_command = human_gate.get("approval_decision_command")
    apply_command = human_gate.get("approval_apply_command")
    if not command_contains(approved_write, "llmwiki-sync"):
        errors.append("approved_write_command must call llmwiki-sync.")
    for option in ["--project", "--project-slug", "--workspace", "--approve", "--reindex", "--lint"]:
        if not command_has(approved_write, option):
            errors.append(f"approved_write_command missing {option}.")
    if not command_contains(decision_command, "approval-decision"):
        errors.append("approval_decision_command must call approval-decision.")
    if command_option(decision_command, "--approval-package") != str(approval_package_path):
        errors.append("approval_decision_command must point at this approval package.")
    if command_option(decision_command, "--decision") != "approve":
        errors.append("approval_decision_command should record approve.")
    if not command_contains(apply_command, "approval-apply"):
        errors.append("approval_apply_command must call approval-apply.")
    if command_option(apply_command, "--approval-package") != str(approval_package_path):
        errors.append("approval_apply_command must point at this approval package.")
    if not command_has(apply_command, "--approve"):
        errors.append("approval_apply_command must require --approve.")

    status = "pass" if not errors else "fail"
    return ApprovalPackageCheck(
        name="human_gate",
        status=status,
        summary=(
            "HumanGate commands and review checklist are complete."
            if status == "pass"
            else "HumanGate commands or review checklist are incomplete."
        ),
        data={"decision": decision, "errors": errors},
    )


def check_llmwiki_preview(payload: Dict[str, Any]) -> ApprovalPackageCheck:
    llmwiki = payload.get("llmwiki", {})
    preview = llmwiki.get("preview", {})
    errors = []
    if llmwiki.get("sync_status") != "planned":
        errors.append("llmwiki.sync_status must be planned before human approval.")
    if llmwiki.get("approved") is not False:
        errors.append("llmwiki.approved must be false in the approval package.")
    if not preview.get("target_namespace"):
        errors.append("llmwiki.preview.target_namespace is required.")
    pages = preview.get("pages")
    if not isinstance(pages, list) or not pages:
        errors.append("llmwiki.preview.pages must be a non-empty array.")
    if preview.get("page_count") != (len(pages) if isinstance(pages, list) else None):
        errors.append("llmwiki.preview.page_count must match pages length.")
    status = "pass" if not errors else "fail"
    return ApprovalPackageCheck(
        name="llmwiki_preview",
        status=status,
        summary=(
            "llmwiki preview is a planned, unapproved sync with page coverage."
            if status == "pass"
            else "llmwiki preview is incomplete or already approved."
        ),
        data={"errors": errors, "preview": preview},
    )


def check_mcp_policy(payload: Dict[str, Any]) -> ApprovalPackageCheck:
    mcp_config = payload.get("llmwiki", {}).get("mcp_config", {})
    bindings = {
        binding.get("bot"): binding
        for binding in mcp_config.get("role_bindings", [])
        if isinstance(binding, dict)
    }
    errors = []
    director = bindings.get("Novel-Director-Curator")
    creative = bindings.get("Novel-Creative-Architect")
    validator = bindings.get("Novel-Continuity-Validator")
    if not director or not director.get("configure_mcp_server"):
        errors.append("Director must be configured for the llmwiki MCP server.")
    if creative is None or creative.get("configure_mcp_server"):
        errors.append("Creative Architect must not be configured for direct llmwiki MCP access.")
    if not validator or not validator.get("configure_mcp_server"):
        errors.append("Validator must be configured for read-only llmwiki MCP access.")
    validator_tools = set(validator.get("allowed_llmwiki_tools", [])) if isinstance(validator, dict) else set()
    if validator_tools.intersection({"create", "edit", "append"}):
        errors.append("Validator must not have write llmwiki tools.")
    status = "pass" if not errors else "fail"
    return ApprovalPackageCheck(
        name="mcp_policy",
        status=status,
        summary=(
            "MCP role binding policy matches the three-bot write/read boundaries."
            if status == "pass"
            else "MCP role binding policy violates the three-bot boundaries."
        ),
        data={"errors": errors, "bots": sorted(bindings.keys())},
    )


def check_next_actions(payload: Dict[str, Any]) -> ApprovalPackageCheck:
    command = payload.get("next_actions", {}).get("chapter_start_command")
    materials = payload.get("review_materials", {})
    project = payload.get("project", {})
    errors = []
    if not command_contains(command, "chapter"):
        errors.append("chapter_start_command must call chapter.")
    if command_option(command, "--project") != project.get("project_path"):
        errors.append("chapter_start_command must target the approval package project path.")
    if not command_option(command, "--chapter-number"):
        errors.append("chapter_start_command must include --chapter-number.")
    if command_option(command, "--foundation-json") != materials.get("foundation_json"):
        errors.append("chapter_start_command must use the reviewed foundation JSON.")
    status = "pass" if not errors else "fail"
    return ApprovalPackageCheck(
        name="next_actions",
        status=status,
        summary=(
            "Next chapter start command is present and uses the reviewed foundation."
            if status == "pass"
            else "Next chapter start command is incomplete."
        ),
        data={"errors": errors, "chapter_start_command": command if isinstance(command, list) else []},
    )


def check_workspace_target(payload: Dict[str, Any]) -> ApprovalPackageCheck:
    project_path = path_from(payload.get("project", {}).get("project_path"))
    workspace_path = path_from(payload.get("project", {}).get("llmwiki_workspace_path"))
    project_slug = payload.get("project", {}).get("project_slug")
    target_path = workspace_path / "wiki" / "novels" / str(project_slug) if workspace_path else None
    target_files = sorted(str(path.relative_to(target_path)) for path in target_path.rglob("*") if path.is_file()) if target_path and target_path.exists() else []
    external_workspace = project_path is not None and workspace_path is not None and project_path != workspace_path
    status = "warn" if external_workspace and target_files else "pass"
    return ApprovalPackageCheck(
        name="workspace_target",
        status=status,
        summary=(
            "External llmwiki target namespace already has files; approved apply may update existing pages."
            if status == "warn"
            else "No unexpected pre-approval external workspace writes detected."
        ),
        data={
            "target_path": str(target_path) if target_path else None,
            "external_workspace": external_workspace,
            "target_file_count": len(target_files),
            "target_files": target_files,
        },
    )


def check_apply_dry_run(approval_package_path: Path) -> ApprovalPackageCheck:
    try:
        result = NovelApprovalApplier().apply(
            NovelApprovalApplyRequest(approval_package_path=approval_package_path, approve=False)
        )
    except Exception as exc:
        return ApprovalPackageCheck(
            name="apply_dry_run",
            status="fail",
            summary=f"approval-apply dry-run failed: {exc}",
            data={},
        )
    action_statuses = {action.status for action in result.llmwiki_sync.actions}
    passed = result.status == "planned" and not result.approved and not action_statuses.intersection({"created", "updated"})
    return ApprovalPackageCheck(
        name="apply_dry_run",
        status="pass" if passed else "fail",
        summary=(
            "approval-apply dry-run can consume the package without approved writes."
            if passed
            else "approval-apply dry-run did not remain in planned mode."
        ),
        data=result.to_dict(),
    )


def check_chapter_smoke(payload: Dict[str, Any]) -> ApprovalPackageCheck:
    command = payload.get("next_actions", {}).get("chapter_start_command")
    if not isinstance(command, list) or not command:
        return ApprovalPackageCheck(
            name="chapter_smoke",
            status="fail",
            summary="Missing chapter_start_command.",
            data={},
        )
    try:
        completed = subprocess.run(
            [str(item) for item in command],
            text=True,
            capture_output=True,
            check=False,
            timeout=60,
            cwd=Path(__file__).resolve().parents[1],
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return ApprovalPackageCheck(
            name="chapter_smoke",
            status="fail",
            summary=f"chapter_start_command failed to run: {exc}",
            data={"command": command},
        )

    data: Dict[str, Any] = {
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }
    if completed.returncode == 0:
        try:
            chapter_payload = json.loads(completed.stdout)
        except json.JSONDecodeError:
            chapter_payload = {}
        data["chapter_status"] = chapter_payload.get("status")
        data["chapter_id"] = chapter_payload.get("chapter_id")
        final_path = Path(str(chapter_payload.get("final_path", "")))
        data["final_path_exists"] = final_path.exists()
    passed = (
        completed.returncode == 0
        and data.get("chapter_status") == "completed"
        and data.get("final_path_exists") is True
    )
    return ApprovalPackageCheck(
        name="chapter_smoke",
        status="pass" if passed else "fail",
        summary=(
            "chapter_start_command produced a completed chapter."
            if passed
            else "chapter_start_command did not produce a completed chapter."
        ),
        data=data,
    )


def aggregate_check_status(checks: List[ApprovalPackageCheck]) -> str:
    if any(check.status == "fail" for check in checks):
        return "blocked"
    if any(check.status == "warn" for check in checks):
        return "ready_with_warnings"
    return "ready"


def path_from(value: Any) -> Optional[Path]:
    if not isinstance(value, str) or not value:
        return None
    return Path(value).expanduser().resolve()


def path_exists(value: Any, *, expected_type: str) -> bool:
    path = path_from(value)
    if path is None or not path.exists():
        return False
    if expected_type == "file":
        return path.is_file()
    if expected_type == "dir":
        return path.is_dir()
    return True


def read_json_path(value: Any) -> Optional[Dict[str, Any]]:
    path = path_from(value)
    if path is None or not path.exists() or not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def bundle_pages(bundle_path: Optional[Path]) -> List[str]:
    if bundle_path is None or not bundle_path.exists() or not bundle_path.is_dir():
        return []
    return sorted(str(path.relative_to(bundle_path)) for path in bundle_path.rglob("*.md"))


def plan_preview_pages(plan_payload: Optional[Dict[str, Any]]) -> List[str]:
    if plan_payload is None:
        return []
    pages = plan_payload.get("preview", {}).get("pages", [])
    return sorted(str(page) for page in pages) if isinstance(pages, list) else []


def command_contains(command: Any, token: str) -> bool:
    return isinstance(command, list) and token in [str(item) for item in command]


def command_has(command: Any, token: str) -> bool:
    return command_contains(command, token)


def command_option(command: Any, option: str) -> Optional[str]:
    if not isinstance(command, list):
        return None
    values = [str(item) for item in command]
    for index, value in enumerate(values[:-1]):
        if value == option:
            return values[index + 1]
    return None
