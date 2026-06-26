from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Set, Tuple

from .approval import (
    NovelApprovalApplier,
    NovelApprovalApplyRequest,
    NovelApprovalDecider,
    NovelApprovalDecisionRequest,
)
from .bootstrap import NovelBootstrapRequest, NovelBootstrapper
from .botmux_assets import BotmuxAssetSyncRequest, BotmuxAssetSyncer
from .llmwiki_sync import LlmwikiSyncRequest, LlmwikiSyncer
from .runtime import NovelFoundationRequest, NovelRuntime, NovelWikiBundleRequest
from .series import NovelSeriesRequest, NovelSeriesRunner


EXPECTED_NOVEL_BOTS = {
    "Novel-Director-Curator": "cli_aab42d6152f89be8",
    "Novel-Creative-Architect": "cli_aab42e1c87385bfc",
    "Novel-Continuity-Validator": "cli_aab42e443bf89bde",
}

WORKFLOW_FILES = [
    "novel-story-foundation.workflow.json",
    "novel-chapter-production.workflow.json",
]

TEMPLATE_REF_PATTERN = re.compile(r"\$\{([^}]+)\}")


@dataclass(frozen=True)
class NovelReadinessRequest:
    repo_path: Path
    botmux_home: Path = Path.home() / ".botmux"
    botmux_bin: Path = Path.home() / ".botmux" / "bin" / "botmux"
    llmwiki_bin: str = "llmwiki"
    run_series_smoke: bool = False
    smoke_chapter_count: int = 5
    run_llmwiki_smoke: bool = False
    run_bootstrap_smoke: bool = False
    run_approval_apply_smoke: bool = False


@dataclass(frozen=True)
class ReadinessCheck:
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
class NovelReadinessResult:
    status: str
    repo_path: Path
    botmux_home: Path
    checks: List[ReadinessCheck]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "repo_path": str(self.repo_path),
            "botmux_home": str(self.botmux_home),
            "checks": [check.to_dict() for check in self.checks],
        }


class NovelReadinessChecker:
    def check(self, request: NovelReadinessRequest) -> NovelReadinessResult:
        repo_path = request.repo_path.expanduser().resolve()
        botmux_home = request.botmux_home.expanduser().resolve()
        checks = [
            self._check_botmux_assets(repo_path=repo_path, botmux_home=botmux_home),
            self._check_bot_configs(botmux_home=botmux_home),
            self._check_workflows(repo_path=repo_path, botmux_bin=request.botmux_bin.expanduser()),
            self._check_workflow_bindings(repo_path=repo_path),
            self._check_workflow_contract_smoke(repo_path=repo_path),
            self._check_llmwiki(llmwiki_bin=request.llmwiki_bin),
        ]
        if request.run_bootstrap_smoke:
            checks.append(self._check_bootstrap_smoke(llmwiki_bin=request.llmwiki_bin))
        if request.run_approval_apply_smoke:
            checks.append(self._check_approval_apply_smoke(llmwiki_bin=request.llmwiki_bin))
        if request.run_series_smoke:
            checks.append(self._check_series_smoke(chapter_count=request.smoke_chapter_count))
        if request.run_llmwiki_smoke:
            checks.append(self._check_llmwiki_smoke(llmwiki_bin=request.llmwiki_bin))

        status = aggregate_status(checks)
        return NovelReadinessResult(status=status, repo_path=repo_path, botmux_home=botmux_home, checks=checks)

    def _check_botmux_assets(self, *, repo_path: Path, botmux_home: Path) -> ReadinessCheck:
        try:
            result = BotmuxAssetSyncer().sync(
                BotmuxAssetSyncRequest(repo_path=repo_path, botmux_home=botmux_home, write=False)
            )
        except Exception as exc:
            return ReadinessCheck(
                name="botmux_assets",
                status="fail",
                summary=f"BotMux asset dry-run failed: {exc}",
                data={},
            )
        statuses = {action.status for action in result.actions}
        status = "pass" if statuses == {"unchanged"} else "fail"
        summary = "BotMux workflows and workspace AGENTS are installed and unchanged." if status == "pass" else "BotMux assets need synchronization."
        return ReadinessCheck(
            name="botmux_assets",
            status=status,
            summary=summary,
            data={"actions": [action.to_dict() for action in result.actions]},
        )

    def _check_bot_configs(self, *, botmux_home: Path) -> ReadinessCheck:
        bots_path = botmux_home / "bots.json"
        if not bots_path.exists():
            return ReadinessCheck(
                name="bot_configs",
                status="fail",
                summary=f"Missing BotMux bots.json: {bots_path}",
                data={"expected_bots": EXPECTED_NOVEL_BOTS},
            )
        try:
            bots = json.loads(bots_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            return ReadinessCheck(
                name="bot_configs",
                status="fail",
                summary=f"Invalid bots.json: {exc}",
                data={},
            )

        matched: Dict[str, Dict[str, Any]] = {}
        missing: List[str] = []
        for role_name, app_id in EXPECTED_NOVEL_BOTS.items():
            config = next((bot for bot in bots if bot.get("larkAppId") == app_id), None)
            if config is None:
                missing.append(role_name)
                continue
            working_dir = Path(str(config.get("workingDir", ""))).expanduser()
            matched[role_name] = {
                "larkAppId": app_id,
                "cliId": config.get("cliId"),
                "workingDir": str(working_dir),
                "workingDirExists": working_dir.exists(),
            }

        missing_dirs = [role for role, data in matched.items() if not data["workingDirExists"]]
        status = "pass" if not missing and not missing_dirs else "fail"
        summary = "Novel bot configs are present and workspace directories exist." if status == "pass" else "Novel bot configs are incomplete."
        return ReadinessCheck(
            name="bot_configs",
            status=status,
            summary=summary,
            data={"matched": matched, "missing": missing, "missing_working_dirs": missing_dirs},
        )

    def _check_workflows(self, *, repo_path: Path, botmux_bin: Path) -> ReadinessCheck:
        if not botmux_bin.exists():
            return ReadinessCheck(
                name="workflow_validate",
                status="fail",
                summary=f"Missing BotMux executable: {botmux_bin}",
                data={},
            )

        commands = []
        failures = []
        for filename in WORKFLOW_FILES:
            workflow_path = repo_path / "workflows" / filename
            completed = subprocess.run(
                [str(botmux_bin), "workflow", "validate", str(workflow_path)],
                text=True,
                capture_output=True,
                check=False,
            )
            command_result = {
                "workflow": filename,
                "returncode": completed.returncode,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
            }
            commands.append(command_result)
            if completed.returncode != 0:
                failures.append(filename)

        status = "pass" if not failures else "fail"
        summary = "BotMux workflow templates validate." if status == "pass" else "BotMux workflow validation failed."
        return ReadinessCheck(
            name="workflow_validate",
            status=status,
            summary=summary,
            data={"commands": commands, "failures": failures},
        )

    def _check_workflow_bindings(self, *, repo_path: Path) -> ReadinessCheck:
        files = []
        failures = []
        for filename in WORKFLOW_FILES:
            workflow_path = repo_path / "workflows" / filename
            errors = validate_workflow_bindings(workflow_path)
            files.append(
                {
                    "workflow": filename,
                    "path": str(workflow_path),
                    "error_count": len(errors),
                    "errors": errors,
                }
            )
            failures.extend(errors)

        status = "pass" if not failures else "fail"
        summary = (
            "Novel workflow template bindings resolve to declared params and upstream output fields."
            if status == "pass"
            else f"Novel workflow template bindings failed with {len(failures)} error(s)."
        )
        return ReadinessCheck(
            name="workflow_bindings",
            status=status,
            summary=summary,
            data={"files": files, "failure_count": len(failures)},
        )

    def _check_workflow_contract_smoke(self, *, repo_path: Path) -> ReadinessCheck:
        files = []
        failures = []
        for filename in WORKFLOW_FILES:
            workflow_path = repo_path / "workflows" / filename
            result = simulate_workflow_contract(workflow_path)
            files.append(result)
            failures.extend(result["errors"])

        status = "pass" if not failures else "fail"
        summary = (
            "Novel workflow prompts render with synthetic contract outputs."
            if status == "pass"
            else f"Novel workflow contract smoke failed with {len(failures)} error(s)."
        )
        return ReadinessCheck(
            name="workflow_contract_smoke",
            status=status,
            summary=summary,
            data={"files": files, "failure_count": len(failures)},
        )

    def _check_llmwiki(self, *, llmwiki_bin: str) -> ReadinessCheck:
        executable = resolve_executable(llmwiki_bin)
        if executable is None:
            return ReadinessCheck(
                name="llmwiki",
                status="warn",
                summary=f"llmwiki executable not found: {llmwiki_bin}; llmwiki-sync can still write local Markdown but reindex is skipped.",
                data={"llmwiki_bin": llmwiki_bin, "available": False},
            )
        try:
            completed = subprocess.run(
                [executable, "--help"],
                text=True,
                capture_output=True,
                check=False,
                timeout=15,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return ReadinessCheck(
                name="llmwiki",
                status="warn",
                summary=f"llmwiki executable is present but did not respond to --help: {exc}",
                data={"llmwiki_bin": executable, "available": True, "usable": False},
            )
        if completed.returncode != 0:
            return ReadinessCheck(
                name="llmwiki",
                status="warn",
                summary=f"llmwiki executable is present but --help failed with exit code {completed.returncode}.",
                data={
                    "llmwiki_bin": executable,
                    "available": True,
                    "usable": False,
                    "returncode": completed.returncode,
                    "stderr": completed.stderr,
                },
            )
        return ReadinessCheck(
            name="llmwiki",
            status="pass",
            summary="llmwiki executable is available and responds to --help.",
            data={"llmwiki_bin": executable, "available": True, "usable": True},
        )

    def _check_series_smoke(self, *, chapter_count: int) -> ReadinessCheck:
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                project_path = Path(tmpdir) / "readiness-series"
                result = NovelSeriesRunner().run(
                    NovelSeriesRequest(
                        project_path=project_path,
                        title="影钟旧案",
                        inspiration="退役巡夜人在旧书楼发现父亲旧案残页，必须在巡城司清查前保护妹妹身份并找出篡改真相的人。",
                        project_slug="shadow-clock-case",
                        chapter_count=chapter_count,
                        llmwiki_sync=True,
                    )
                )
        except Exception as exc:
            return ReadinessCheck(
                name="series_smoke",
                status="fail",
                summary=f"Series smoke failed: {exc}",
                data={"chapter_count": chapter_count},
            )

        metrics = result.metrics
        passed = (
            result.status == "completed"
            and metrics.get("chapter_count") == chapter_count
            and metrics.get("completed_chapter_count") == chapter_count
            and metrics.get("p0_p1_issue_count") == 0
            and metrics.get("archive_completion_rate") == 1.0
            and metrics.get("prior_context_rate") == 1.0
        )
        return ReadinessCheck(
            name="series_smoke",
            status="pass" if passed else "fail",
            summary="Series smoke completed with expected metrics." if passed else "Series smoke metrics did not meet readiness thresholds.",
            data={"result_status": result.status, "metrics": metrics},
        )

    def _check_bootstrap_smoke(self, *, llmwiki_bin: str) -> ReadinessCheck:
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                root = Path(tmpdir)
                project_path = root / "readiness-bootstrap-project"
                workspace_path = root / "readiness-bootstrap-workspace"
                project_slug = "shadow-clock-case"
                result = NovelBootstrapper().bootstrap(
                    NovelBootstrapRequest(
                        project_path=project_path,
                        title="影钟旧案",
                        inspiration="退役巡夜人在旧书楼发现父亲旧案残页，必须在巡城司清查前保护妹妹身份并找出篡改真相的人。",
                        project_slug=project_slug,
                        workspace_path=workspace_path,
                        llmwiki_bin=llmwiki_bin,
                    )
                )

                wiki_overview = result.wiki_bundle.bundle_path / "overview.md"
                target_overview = workspace_path / "wiki" / "novels" / project_slug / "overview.md"
                package_payload = json.loads(result.approval_package_json_path.read_text(encoding="utf-8"))
                chapter_start_command = package_payload.get("next_actions", {}).get("chapter_start_command", [])
                chapter_start_result: Dict[str, Any] = {
                    "returncode": None,
                    "status": None,
                    "chapter_id": None,
                    "final_path_exists": False,
                }
                if chapter_start_command:
                    completed = subprocess.run(
                        [str(item) for item in chapter_start_command],
                        text=True,
                        capture_output=True,
                        check=False,
                        cwd=Path(__file__).resolve().parents[1],
                    )
                    chapter_start_result["returncode"] = completed.returncode
                    if completed.returncode == 0:
                        chapter_payload = json.loads(completed.stdout)
                        final_path = Path(chapter_payload["final_path"])
                        chapter_start_result.update(
                            {
                                "status": chapter_payload.get("status"),
                                "chapter_id": chapter_payload.get("chapter_id"),
                                "final_path_exists": final_path.exists(),
                            }
                        )
                passed = (
                    result.status in {"ready", "ready_with_warnings"}
                    and result.foundation.foundation_path.exists()
                    and wiki_overview.exists()
                    and result.llmwiki_sync.status == "planned"
                    and not result.llmwiki_sync.approved
                    and result.llmwiki_sync.plan_path.exists()
                    and result.approval_package_path.exists()
                    and result.approval_package_json_path.exists()
                    and not target_overview.exists()
                    and package_payload.get("status") == "ready_for_human_review"
                    and "chapter" in chapter_start_command
                    and "--foundation-json" in chapter_start_command
                    and chapter_start_result["returncode"] == 0
                    and chapter_start_result["status"] == "completed"
                    and chapter_start_result["final_path_exists"]
                )
                if not passed:
                    status = "fail"
                elif result.status == "ready_with_warnings":
                    status = "warn"
                else:
                    status = "pass"
                return ReadinessCheck(
                    name="bootstrap_smoke",
                    status=status,
                    summary=(
                        "Novel bootstrap smoke generated the approval package and verified its opening chapter command."
                        if passed
                        else "Novel bootstrap smoke did not meet readiness checks."
                    ),
                    data={
                        "result_status": result.status,
                        "project_path": str(project_path),
                        "workspace_path": str(workspace_path),
                        "foundation_path_exists": result.foundation.foundation_path.exists(),
                        "wiki_overview_exists": wiki_overview.exists(),
                        "approval_package_exists": result.approval_package_path.exists(),
                        "approval_package_json_exists": result.approval_package_json_path.exists(),
                        "target_overview_exists": target_overview.exists(),
                        "chapter_start_command": chapter_start_command,
                        "chapter_start_result": chapter_start_result,
                        "llmwiki_sync_status": result.llmwiki_sync.status,
                        "mcp_config_status": result.mcp_config.status,
                        "warnings": result.mcp_config.warnings + result.llmwiki_sync.warnings,
                    },
                )
        except Exception as exc:
            return ReadinessCheck(
                name="bootstrap_smoke",
                status="fail",
                summary=f"Novel bootstrap smoke failed: {exc}",
                data={"llmwiki_bin": llmwiki_bin},
            )

    def _check_approval_apply_smoke(self, *, llmwiki_bin: str) -> ReadinessCheck:
        executable = resolve_executable(llmwiki_bin)
        if executable is None:
            return ReadinessCheck(
                name="approval_apply_smoke",
                status="fail",
                summary=f"Approval apply smoke requires an llmwiki executable but none was found: {llmwiki_bin}",
                data={"llmwiki_bin": llmwiki_bin},
            )

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                root = Path(tmpdir)
                project_path = root / "readiness-approval-project"
                workspace_path = root / "readiness-approval-workspace"
                project_slug = "shadow-clock-case"
                bootstrap_result = NovelBootstrapper().bootstrap(
                    NovelBootstrapRequest(
                        project_path=project_path,
                        title="影钟旧案",
                        inspiration="退役巡夜人在旧书楼发现父亲旧案残页，必须在巡城司清查前保护妹妹身份并找出篡改真相的人。",
                        project_slug=project_slug,
                        workspace_path=workspace_path,
                        llmwiki_bin=executable,
                    )
                )
                decision_result = NovelApprovalDecider().record(
                    NovelApprovalDecisionRequest(
                        approval_package_path=bootstrap_result.approval_package_json_path,
                        decision="approve",
                        reviewer="readiness-smoke",
                        notes="Readiness smoke approval for temporary workspace sync.",
                    )
                )
                apply_result = NovelApprovalApplier().apply(
                    NovelApprovalApplyRequest(
                        approval_package_path=bootstrap_result.approval_package_json_path,
                        approve=True,
                    )
                )
                target_overview = workspace_path / "wiki" / "novels" / project_slug / "overview.md"
                index_path = workspace_path / ".llmwiki" / "index.db"
                init_succeeded = any(command.status == "succeeded" for command in apply_result.init_commands)
                reindex_succeeded = llmwiki_command_succeeded(apply_result.llmwiki_sync.commands, "reindex")
                lint_status = llmwiki_command_status(apply_result.llmwiki_sync.commands, "lint")
                lint_succeeded = lint_status == "succeeded"
                lint_skipped = lint_status == "skipped"
                passed = (
                    apply_result.status in {"completed", "completed_with_warnings"}
                    and apply_result.approved
                    and init_succeeded
                    and reindex_succeeded
                    and (lint_succeeded or lint_skipped)
                    and target_overview.exists()
                    and index_path.exists()
                )
                check_status = "pass" if passed and lint_succeeded else "warn" if passed else "fail"
                return ReadinessCheck(
                    name="approval_apply_smoke",
                    status=check_status,
                    summary=(
                        "Approval apply smoke initialized a temporary workspace, applied approved wiki pages, linted it, and reindexed it."
                        if passed and lint_succeeded
                        else "Approval apply smoke initialized a temporary workspace, applied approved wiki pages, and reindexed it; llmwiki lint is unavailable in this executable."
                        if passed
                        else "Approval apply smoke did not meet expected init/write/lint/reindex checks."
                    ),
                    data={
                        "llmwiki_bin": executable,
                        "project_path": str(project_path),
                        "workspace_path": str(workspace_path),
                        "approval_package_path": str(bootstrap_result.approval_package_json_path),
                        "decision_status": decision_result.status,
                        "apply_status": apply_result.status,
                        "approved": apply_result.approved,
                        "target_overview_exists": target_overview.exists(),
                        "index_exists": index_path.exists(),
                        "reindex_succeeded": reindex_succeeded,
                        "lint_succeeded": lint_succeeded,
                        "lint_status": lint_status,
                        "init_commands": [command.to_dict() for command in apply_result.init_commands],
                        "sync_commands": [command.to_dict() for command in apply_result.llmwiki_sync.commands],
                        "warnings": apply_result.warnings,
                    },
                )
        except Exception as exc:
            return ReadinessCheck(
                name="approval_apply_smoke",
                status="fail",
                summary=f"Approval apply smoke failed: {exc}",
                data={"llmwiki_bin": executable},
            )

    def _check_llmwiki_smoke(self, *, llmwiki_bin: str) -> ReadinessCheck:
        executable = resolve_executable(llmwiki_bin)
        if executable is None:
            return ReadinessCheck(
                name="llmwiki_smoke",
                status="fail",
                summary=f"llmwiki smoke requires an executable but none was found: {llmwiki_bin}",
                data={"llmwiki_bin": llmwiki_bin},
            )

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                root = Path(tmpdir)
                project_path = root / "readiness-llmwiki-project"
                workspace_path = root / "readiness-llmwiki-workspace"
                project_slug = "shadow-clock-case"
                runtime = NovelRuntime()
                foundation = runtime.foundation(
                    NovelFoundationRequest(
                        project_path=project_path,
                        title="影钟旧案",
                        inspiration="退役巡夜人在旧书楼发现父亲旧案残页，必须在巡城司清查前保护妹妹身份并找出篡改真相的人。",
                    )
                )
                wiki_bundle = runtime.wiki_bundle(
                    NovelWikiBundleRequest(
                        project_path=project_path,
                        project_slug=project_slug,
                        foundation_path=foundation.foundation_path,
                    )
                )
                init_result = subprocess.run(
                    [executable, "init", str(workspace_path)],
                    text=True,
                    capture_output=True,
                    check=False,
                    timeout=30,
                )
                if init_result.returncode != 0:
                    return ReadinessCheck(
                        name="llmwiki_smoke",
                        status="fail",
                        summary=f"llmwiki init failed with exit code {init_result.returncode}.",
                        data={
                            "llmwiki_bin": executable,
                            "init": command_payload(init_result),
                            "project_path": str(project_path),
                            "workspace_path": str(workspace_path),
                        },
                    )

                sync_result = LlmwikiSyncer().sync(
                    LlmwikiSyncRequest(
                        project_path=project_path,
                        project_slug=project_slug,
                        workspace_path=workspace_path,
                        approve=True,
                        llmwiki_bin=executable,
                        reindex=True,
                        lint=True,
                    )
                )
                target_overview = workspace_path / "wiki" / "novels" / project_slug / "overview.md"
                index_path = workspace_path / ".llmwiki" / "index.db"
                reindex_succeeded = llmwiki_command_succeeded(sync_result.commands, "reindex")
                lint_status = llmwiki_command_status(sync_result.commands, "lint")
                lint_succeeded = lint_status == "succeeded"
                lint_skipped = lint_status == "skipped"
                passed = (
                    sync_result.status in {"completed", "completed_with_warnings"}
                    and sync_result.llmwiki_available
                    and reindex_succeeded
                    and (lint_succeeded or lint_skipped)
                    and target_overview.exists()
                    and index_path.exists()
                )
                check_status = "pass" if passed and lint_succeeded else "warn" if passed else "fail"
                return ReadinessCheck(
                    name="llmwiki_smoke",
                    status=check_status,
                    summary=(
                        "Approved llmwiki sync smoke copied wiki pages, linted them, and reindexed a temporary workspace."
                        if passed and lint_succeeded
                        else "Approved llmwiki sync smoke copied wiki pages and reindexed a temporary workspace; llmwiki lint is unavailable in this executable."
                        if passed
                        else "Approved llmwiki sync smoke did not meet expected write/lint/reindex checks."
                    ),
                    data={
                        "llmwiki_bin": executable,
                        "project_path": str(project_path),
                        "workspace_path": str(workspace_path),
                        "bundle_path": str(wiki_bundle.bundle_path),
                        "target_overview_exists": target_overview.exists(),
                        "index_exists": index_path.exists(),
                        "sync_status": sync_result.status,
                        "reindex_succeeded": reindex_succeeded,
                        "lint_succeeded": lint_succeeded,
                        "lint_status": lint_status,
                        "commands": [command.to_dict() for command in sync_result.commands],
                        "actions": [action.to_dict() for action in sync_result.actions],
                    },
                )
        except Exception as exc:
            return ReadinessCheck(
                name="llmwiki_smoke",
                status="fail",
                summary=f"llmwiki smoke failed: {exc}",
                data={"llmwiki_bin": executable},
            )


def aggregate_status(checks: List[ReadinessCheck]) -> str:
    if any(check.status == "fail" for check in checks):
        return "blocked"
    if any(check.status == "warn" for check in checks):
        return "ready_with_warnings"
    return "ready"


def resolve_executable(command: str) -> Optional[str]:
    expanded = Path(command).expanduser()
    if expanded.parent != Path(".") and expanded.exists():
        return str(expanded.resolve())
    return shutil.which(command)


def llmwiki_command_succeeded(commands: List[Any], operation: str) -> bool:
    return llmwiki_command_status(commands, operation) == "succeeded"


def llmwiki_command_status(commands: List[Any], operation: str) -> Optional[str]:
    for command in commands:
        if command_matches_operation(command.command, operation):
            return command.status
    return None


def command_matches_operation(command: List[str], operation: str) -> bool:
    if len(command) >= 2 and command[1] == operation:
        return True
    if operation == "lint" and "wiki-lint" in command:
        return True
    return False


def command_payload(completed: subprocess.CompletedProcess[str]) -> Dict[str, Any]:
    return {
        "args": list(completed.args) if isinstance(completed.args, list) else completed.args,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def simulate_workflow_contract(workflow_path: Path) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "workflow": workflow_path.name,
        "path": str(workflow_path),
        "node_count": 0,
        "rendered_nodes": [],
        "human_gate_nodes": [],
        "errors": [],
    }
    if not workflow_path.exists():
        result["errors"].append({"node": "", "message": f"Missing workflow file: {workflow_path}"})
        return result
    try:
        workflow = json.loads(workflow_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        result["errors"].append({"node": "", "message": f"Invalid workflow JSON: {exc}"})
        return result

    params = workflow.get("params", {})
    nodes = workflow.get("nodes", {})
    if not isinstance(params, dict):
        result["errors"].append({"node": "", "message": "Workflow params must be an object."})
        return result
    if not isinstance(nodes, dict):
        result["errors"].append({"node": "", "message": "Workflow nodes must be an object."})
        return result

    result["node_count"] = len(nodes)
    sample_params = synthetic_params(params)
    ordered_nodes, order_errors = workflow_order(nodes)
    result["errors"].extend({"node": node_id, "message": message} for node_id, message in order_errors)

    outputs: Dict[str, Dict[str, Any]] = {}
    for node_id in ordered_nodes:
        node_config = nodes.get(node_id)
        if not isinstance(node_config, dict):
            result["errors"].append({"node": node_id, "message": "Node config must be an object."})
            continue
        missing_dependencies = [dependency_id for dependency_id in workflow_depends(node_config) if dependency_id not in outputs]
        if missing_dependencies:
            result["errors"].append(
                {
                    "node": node_id,
                    "message": f"Dependencies not rendered before node: {', '.join(missing_dependencies)}",
                }
            )
            continue

        node_errors: List[str] = []
        rendered_prompt = render_template_text(
            str(node_config.get("prompt", "")),
            params=sample_params,
            outputs=outputs,
            errors=node_errors,
        )
        if not rendered_prompt.strip():
            node_errors.append("Rendered prompt is empty.")
        if "${" in rendered_prompt:
            node_errors.append("Rendered prompt still contains template markers.")

        human_gate = node_config.get("humanGate")
        rendered_human_gate = ""
        if isinstance(human_gate, dict):
            rendered_human_gate = render_template_text(
                str(human_gate.get("prompt", "")),
                params=sample_params,
                outputs=outputs,
                errors=node_errors,
            )
            if not rendered_human_gate.strip():
                node_errors.append("HumanGate prompt is empty.")
            if "${" in rendered_human_gate:
                node_errors.append("HumanGate prompt still contains template markers.")
            result["human_gate_nodes"].append(node_id)

        output = synthetic_output_for_schema(node_config.get("outputSchema", {}), node_id=node_id, errors=node_errors)
        node_errors.extend(validate_synthetic_output(node_config.get("outputSchema", {}), output))
        if node_errors:
            result["errors"].extend({"node": node_id, "message": message} for message in node_errors)

        outputs[node_id] = output
        result["rendered_nodes"].append(
            {
                "node": node_id,
                "prompt_length": len(rendered_prompt),
                "human_gate_prompt_length": len(rendered_human_gate),
                "output_fields": sorted(output.keys()),
            }
        )
    return result


def synthetic_params(params: Dict[str, Any]) -> Dict[str, Any]:
    values: Dict[str, Any] = {}
    defaults = {
        "projectSlug": "shadow-clock-case",
        "title": "影钟旧案",
        "inspiration": "一个背负旧案污名的少年，在巡夜钟声中发现妹妹影子会说真话。",
        "storyBible": "已批准的 Story Bible 合成输入。",
        "chapterGoal": "用旧书楼残页引出主角秘密能力并埋下巡夜钟伏笔。",
        "priorContext": "前文章节事实、角色状态、时间线和伏笔摘要。",
        "genre": "悬疑奇幻",
        "targetLength": "长篇",
        "mode": "lean",
    }
    for name, config in params.items():
        if isinstance(config, dict) and "default" in config:
            values[name] = config["default"]
        elif name in defaults:
            values[name] = defaults[name]
        elif isinstance(config, dict) and config.get("type") == "number":
            values[name] = 1
        elif isinstance(config, dict) and config.get("type") == "boolean":
            values[name] = False
        else:
            values[name] = f"synthetic-{name}"
    return values


def workflow_order(nodes: Dict[str, Any]) -> Tuple[List[str], List[Tuple[str, str]]]:
    ordered: List[str] = []
    temporary: Set[str] = set()
    permanent: Set[str] = set()
    stack: List[str] = []
    errors: List[Tuple[str, str]] = []

    def visit(node_id: str) -> None:
        if node_id in permanent:
            return
        if node_id in temporary:
            cycle_start = stack.index(node_id) if node_id in stack else 0
            cycle_path = stack[cycle_start:] + [node_id]
            errors.append((node_id, f"Workflow dependency cycle detected: {' -> '.join(cycle_path)}"))
            return
        temporary.add(node_id)
        stack.append(node_id)
        node_config = nodes.get(node_id)
        for dependency_id in workflow_depends(node_config):
            if dependency_id in nodes:
                visit(dependency_id)
        stack.pop()
        temporary.remove(node_id)
        permanent.add(node_id)
        ordered.append(node_id)

    for node_id in nodes:
        visit(str(node_id))
    return ordered, errors


def render_template_text(
    text: str,
    *,
    params: Dict[str, Any],
    outputs: Dict[str, Dict[str, Any]],
    errors: List[str],
) -> str:
    def replace(match: re.Match[str]) -> str:
        expression = match.group(1).strip()
        parts = expression.split(".")
        if len(parts) == 2 and parts[0] == "params":
            if parts[1] not in params:
                errors.append(f"Unknown synthetic param: {parts[1]}")
                return match.group(0)
            return str(params[parts[1]])
        if len(parts) == 3 and parts[1] == "output":
            output = outputs.get(parts[0])
            if output is None:
                errors.append(f"Unknown synthetic upstream output: {parts[0]}")
                return match.group(0)
            if parts[2] not in output:
                errors.append(f"Unknown synthetic output field on {parts[0]}: {parts[2]}")
                return match.group(0)
            return stringify_template_value(output[parts[2]])
        errors.append(f"Unsupported synthetic template expression: {expression}")
        return match.group(0)

    return TEMPLATE_REF_PATTERN.sub(replace, text)


def stringify_template_value(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def synthetic_output_for_schema(schema: Any, *, node_id: str, errors: List[str]) -> Dict[str, Any]:
    if not isinstance(schema, dict):
        errors.append("Output schema must be an object.")
        return {}
    properties = schema.get("properties", {})
    required = schema.get("required", [])
    if not isinstance(properties, dict):
        errors.append("Output schema properties must be an object.")
        return {}
    if not isinstance(required, list):
        errors.append("Output schema required must be an array.")
        return {}
    output: Dict[str, Any] = {}
    for field in required:
        field_name = str(field)
        field_schema = properties.get(field_name)
        if not isinstance(field_schema, dict):
            errors.append(f"Required output field has no property schema: {field_name}")
            continue
        output[field_name] = synthetic_value_for_schema(field_schema, node_id=node_id, field_name=field_name)
    return output


def synthetic_value_for_schema(schema: Dict[str, Any], *, node_id: str, field_name: str) -> Any:
    field_type = schema.get("type")
    if field_type == "string":
        return f"{node_id}.{field_name}.synthetic"
    if field_type == "array":
        return []
    if field_type == "object":
        return {"node": node_id, "field": field_name, "synthetic": True}
    if field_type == "number":
        return 1
    if field_type == "integer":
        return 1
    if field_type == "boolean":
        return False
    return f"{node_id}.{field_name}.synthetic"


def validate_synthetic_output(schema: Any, output: Dict[str, Any]) -> List[str]:
    if not isinstance(schema, dict):
        return ["Output schema must be an object."]
    properties = schema.get("properties", {})
    required = schema.get("required", [])
    if not isinstance(properties, dict) or not isinstance(required, list):
        return ["Output schema properties/required are malformed."]
    errors: List[str] = []
    for field in required:
        field_name = str(field)
        if field_name not in output:
            errors.append(f"Missing required synthetic output field: {field_name}")
            continue
        expected_type = properties.get(field_name, {}).get("type") if isinstance(properties.get(field_name), dict) else None
        if expected_type and not value_matches_json_type(output[field_name], expected_type):
            errors.append(f"Synthetic output field has wrong type: {field_name}")
    return errors


def value_matches_json_type(value: Any, expected_type: str) -> bool:
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "array":
        return isinstance(value, list)
    if expected_type == "object":
        return isinstance(value, dict)
    if expected_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "boolean":
        return isinstance(value, bool)
    return True


def validate_workflow_bindings(workflow_path: Path) -> List[Dict[str, str]]:
    if not workflow_path.exists():
        return [
            {
                "workflow": workflow_path.name,
                "node": "",
                "location": "",
                "expression": "",
                "message": f"Missing workflow file: {workflow_path}",
            }
        ]

    try:
        workflow = json.loads(workflow_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [
            {
                "workflow": workflow_path.name,
                "node": "",
                "location": "",
                "expression": "",
                "message": f"Invalid workflow JSON: {exc}",
            }
        ]

    workflow_id = str(workflow.get("workflowId", workflow_path.name))
    params = workflow.get("params", {})
    nodes = workflow.get("nodes", {})
    if not isinstance(params, dict):
        return [
            {
                "workflow": workflow_id,
                "node": "",
                "location": "params",
                "expression": "",
                "message": "Workflow params must be an object.",
            }
        ]
    if not isinstance(nodes, dict):
        return [
            {
                "workflow": workflow_id,
                "node": "",
                "location": "nodes",
                "expression": "",
                "message": "Workflow nodes must be an object.",
            }
        ]

    errors: List[Dict[str, str]] = []
    for node_id, node_config in nodes.items():
        if not isinstance(node_config, dict):
            continue
        dependency_ids = dependency_closure(nodes, node_id)
        for location, text in iter_template_strings(node_config, ""):
            for expression in scan_template_refs(text):
                message = validate_template_ref(
                    expression=expression,
                    current_node=node_id,
                    params=params,
                    nodes=nodes,
                    dependency_ids=dependency_ids,
                )
                if message:
                    errors.append(
                        {
                            "workflow": workflow_id,
                            "node": node_id,
                            "location": location,
                            "expression": expression,
                            "message": message,
                        }
                    )

    return errors


def scan_template_refs(text: str) -> List[str]:
    return [match.group(1).strip() for match in TEMPLATE_REF_PATTERN.finditer(text)]


def iter_template_strings(value: Any, path: str) -> Iterator[Tuple[str, str]]:
    if isinstance(value, str):
        if "${" in value:
            yield path or "$", value
        return

    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            yield from iter_template_strings(child, child_path)
        return

    if isinstance(value, list):
        for index, child in enumerate(value):
            child_path = f"{path}[{index}]"
            yield from iter_template_strings(child, child_path)


def validate_template_ref(
    *,
    expression: str,
    current_node: str,
    params: Dict[str, Any],
    nodes: Dict[str, Any],
    dependency_ids: Set[str],
) -> Optional[str]:
    parts = expression.split(".")
    if len(parts) == 2 and parts[0] == "params":
        param_name = parts[1]
        if param_name not in params:
            return f"Unknown workflow param: {param_name}"
        return None

    if len(parts) == 3 and parts[1] == "output":
        upstream_node = parts[0]
        field_name = parts[2]
        if upstream_node == current_node:
            return "Node prompt cannot reference its own output."
        upstream_config = nodes.get(upstream_node)
        if not isinstance(upstream_config, dict):
            return f"Unknown upstream node: {upstream_node}"
        if upstream_node not in dependency_ids:
            return f"Upstream node is not in dependency closure: {upstream_node}"
        output_schema = upstream_config.get("outputSchema", {})
        properties = output_schema.get("properties", {}) if isinstance(output_schema, dict) else {}
        if not isinstance(properties, dict) or field_name not in properties:
            return f"Unknown output field on {upstream_node}: {field_name}"
        return None

    return "Unsupported template expression; expected params.<name> or <node>.output.<field>."


def dependency_closure(nodes: Dict[str, Any], node_id: str) -> Set[str]:
    visited: Set[str] = set()
    node_config = nodes.get(node_id, {})
    stack = workflow_depends(node_config)
    while stack:
        dependency_id = str(stack.pop())
        if dependency_id in visited:
            continue
        visited.add(dependency_id)
        dependency_config = nodes.get(dependency_id)
        stack.extend(workflow_depends(dependency_config))
    return visited


def workflow_depends(node_config: Any) -> List[str]:
    if not isinstance(node_config, dict):
        return []
    depends = node_config.get("depends", [])
    if not isinstance(depends, list):
        return []
    return [str(dependency_id) for dependency_id in depends]
