from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Set, Tuple

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
            self._check_llmwiki(llmwiki_bin=request.llmwiki_bin),
        ]
        if request.run_bootstrap_smoke:
            checks.append(self._check_bootstrap_smoke(llmwiki_bin=request.llmwiki_bin))
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
                        "Novel bootstrap smoke generated foundation, wiki review bundle, dry-run sync plan, MCP config, and approval package."
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
                    )
                )
                target_overview = workspace_path / "wiki" / "novels" / project_slug / "overview.md"
                index_path = workspace_path / ".llmwiki" / "index.db"
                reindex_succeeded = any(command.status == "succeeded" for command in sync_result.commands)
                passed = (
                    sync_result.status == "completed"
                    and sync_result.llmwiki_available
                    and reindex_succeeded
                    and target_overview.exists()
                    and index_path.exists()
                )
                return ReadinessCheck(
                    name="llmwiki_smoke",
                    status="pass" if passed else "fail",
                    summary=(
                        "Approved llmwiki sync smoke copied wiki pages and reindexed a temporary workspace."
                        if passed
                        else "Approved llmwiki sync smoke did not meet expected write/reindex checks."
                    ),
                    data={
                        "llmwiki_bin": executable,
                        "project_path": str(project_path),
                        "workspace_path": str(workspace_path),
                        "bundle_path": str(wiki_bundle.bundle_path),
                        "target_overview_exists": target_overview.exists(),
                        "index_exists": index_path.exists(),
                        "sync_status": sync_result.status,
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


def command_payload(completed: subprocess.CompletedProcess[str]) -> Dict[str, Any]:
    return {
        "args": list(completed.args) if isinstance(completed.args, list) else completed.args,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


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
