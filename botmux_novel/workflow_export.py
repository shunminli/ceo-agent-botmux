from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class NovelWorkflowRunExportRequest:
    run_id: Optional[str] = None
    run_dir: Optional[Path] = None
    runs_dir: Optional[Path] = None
    botmux_bin: Path = Path.home() / ".botmux" / "bin" / "botmux"


@dataclass(frozen=True)
class NovelWorkflowRunExportResult:
    run_id: str
    workflow_id: Optional[str]
    status: str
    run_dir: Optional[Path]
    params: Dict[str, Any]
    nodes: Dict[str, Dict[str, Any]]
    errors: List[Dict[str, Any]]
    event_count: int
    source: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "runId": self.run_id,
            "workflowId": self.workflow_id,
            "status": self.status,
            "runDir": str(self.run_dir) if self.run_dir is not None else None,
            "params": self.params,
            "nodes": self.nodes,
            "errors": self.errors,
            "eventCount": self.event_count,
            "source": self.source,
        }


class NovelWorkflowRunExporter:
    def export(self, request: NovelWorkflowRunExportRequest) -> NovelWorkflowRunExportResult:
        run_dir, events, source = load_run_events(request)
        workflow = load_workflow_json(run_dir)
        if not events and run_dir is None:
            raise ValueError("workflow run not found; pass --run-dir, --runs-dir, or a botmux-visible --run-id")
        return build_export_result(run_dir=run_dir, workflow=workflow, events=events, source=source, requested_run_id=request.run_id)


def load_run_events(request: NovelWorkflowRunExportRequest) -> Tuple[Optional[Path], List[Dict[str, Any]], str]:
    run_dir = resolve_run_dir(request)
    if run_dir is not None:
        events_path = run_dir / "events.ndjson"
        if not events_path.exists():
            raise ValueError(f"workflow events file not found: {events_path}")
        return run_dir, read_ndjson(events_path), str(events_path)

    if not request.run_id:
        raise ValueError("run_id is required when --run-dir is not provided")
    events = read_events_from_botmux_tail(request.botmux_bin, request.run_id)
    inferred_run_dir = infer_run_dir_from_events(events)
    return inferred_run_dir, events, f"{request.botmux_bin} workflow tail {request.run_id} --json"


def resolve_run_dir(request: NovelWorkflowRunExportRequest) -> Optional[Path]:
    if request.run_dir is not None:
        return request.run_dir.expanduser().resolve()
    if not request.run_id:
        return None

    candidates: List[Path] = []
    if request.runs_dir is not None:
        candidates.append(request.runs_dir.expanduser().resolve() / request.run_id)
    env_runs_dir = os.environ.get("BOTMUX_WORKFLOW_RUNS_DIR")
    if env_runs_dir:
        candidates.append(Path(env_runs_dir).expanduser().resolve() / request.run_id)
    botmux_home = Path.home() / ".botmux"
    candidates.extend(
        [
            botmux_home / "workflow-runs" / request.run_id,
            botmux_home / "data" / "workflow-runs" / request.run_id,
        ]
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def read_events_from_botmux_tail(botmux_bin: Path, run_id: str) -> List[Dict[str, Any]]:
    completed = subprocess.run(
        [str(botmux_bin.expanduser()), "workflow", "tail", run_id, "--json"],
        check=False,
        text=True,
        capture_output=True,
    )
    if completed.returncode != 0:
        message = completed.stderr.strip() or completed.stdout.strip() or f"botmux workflow tail failed with {completed.returncode}"
        raise ValueError(message)
    events: List[Dict[str, Any]] = []
    for line in completed.stdout.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        events.append(json.loads(stripped))
    return events


def read_ndjson(path: Path) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped:
            events.append(json.loads(stripped))
    return events


def load_workflow_json(run_dir: Optional[Path]) -> Dict[str, Any]:
    if run_dir is None:
        return {}
    workflow_path = run_dir / "workflow.json"
    if not workflow_path.exists():
        return {}
    return json.loads(workflow_path.read_text(encoding="utf-8"))


def build_export_result(
    *,
    run_dir: Optional[Path],
    workflow: Dict[str, Any],
    events: List[Dict[str, Any]],
    source: str,
    requested_run_id: Optional[str],
) -> NovelWorkflowRunExportResult:
    run_id = requested_run_id or first_text(*(event.get("runId") for event in events), default="")
    workflow_id = workflow.get("workflowId")
    params: Dict[str, Any] = {}
    nodes: Dict[str, Dict[str, Any]] = {}
    errors: List[Dict[str, Any]] = []
    activity_to_node: Dict[str, str] = {}
    status = "unknown"

    for event in events:
        event_type = event.get("type")
        payload = object_or_empty(event.get("payload"))
        if not run_id:
            run_id = first_text(event.get("runId"), default="")
        if event_type == "runCreated":
            workflow_id = first_text(workflow_id, payload.get("workflowId"), default=None)
            params_value = read_ref_payload(payload.get("inputRef"))
            if isinstance(params_value, dict):
                params = params_value
            status = "created"
        elif event_type == "runStarted":
            status = "running"
        elif event_type in {"runSucceeded", "runCompleted", "runFinished"}:
            status = "completed"
        elif event_type == "runFailed":
            status = "failed"
            errors.append(event_error(event))
        elif event_type in {"runCanceled", "runCancelled"}:
            status = "canceled"
            errors.append(event_error(event))

        node_id = first_text(payload.get("nodeId"), default=None)
        activity_id = first_text(payload.get("activityId"), default=None)
        if event_type == "attemptCreated" and node_id and activity_id:
            activity_to_node[activity_id] = node_id
            node_record(nodes, node_id)["activityId"] = activity_id
            node_record(nodes, node_id)["attemptId"] = payload.get("attemptId")
        elif event_type == "activitySucceeded" and activity_id:
            node_id = activity_to_node.get(activity_id) or node_id_from_activity_id(activity_id)
            if node_id:
                record = node_record(nodes, node_id)
                record["status"] = "succeeded"
                record["activityId"] = activity_id
                record["attemptId"] = payload.get("attemptId")
                record["output"] = read_ref_payload(payload.get("outputRef"))
        elif event_type == "activityFailed" and activity_id:
            node_id = activity_to_node.get(activity_id) or node_id_from_activity_id(activity_id)
            error = event_error(event)
            errors.append(error)
            if node_id:
                record = node_record(nodes, node_id)
                record["status"] = "failed"
                record["activityId"] = activity_id
                record["attemptId"] = payload.get("attemptId")
                record["error"] = error.get("error")
        elif event_type == "nodeSucceeded" and node_id:
            node_record(nodes, node_id)["status"] = "succeeded"
        elif event_type == "nodeFailed" and node_id:
            record = node_record(nodes, node_id)
            record["status"] = "failed"
            record["errorClass"] = payload.get("errorClass")

    if not workflow_id:
        workflow_id = first_text(workflow.get("id"), default=None)
    return NovelWorkflowRunExportResult(
        run_id=run_id,
        workflow_id=workflow_id,
        status=status,
        run_dir=run_dir,
        params=params,
        nodes=nodes,
        errors=errors,
        event_count=len(events),
        source=source,
    )


def infer_run_dir_from_events(events: List[Dict[str, Any]]) -> Optional[Path]:
    for event in events:
        payload = object_or_empty(event.get("payload"))
        for key in ("inputRef", "outputRef"):
            ref = object_or_empty(payload.get(key))
            output_path = ref.get("outputPath")
            if isinstance(output_path, str):
                path = Path(output_path).expanduser()
                if path.parent.name == "blobs":
                    return path.parent.parent.resolve()
    return None


def read_ref_payload(ref: Any) -> Any:
    ref_payload = object_or_empty(ref)
    output_path = ref_payload.get("outputPath")
    if not isinstance(output_path, str):
        return None
    path = Path(output_path).expanduser()
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def node_record(nodes: Dict[str, Dict[str, Any]], node_id: str) -> Dict[str, Any]:
    if node_id not in nodes:
        nodes[node_id] = {}
    return nodes[node_id]


def node_id_from_activity_id(activity_id: str) -> Optional[str]:
    match = re.search(r"::work::([^:]+)", activity_id)
    if match:
        return match.group(1)
    return None


def event_error(event: Dict[str, Any]) -> Dict[str, Any]:
    payload = object_or_empty(event.get("payload"))
    return {
        "eventId": event.get("eventId"),
        "type": event.get("type"),
        "nodeId": payload.get("nodeId"),
        "activityId": payload.get("activityId"),
        "error": payload.get("error"),
        "failedNodeId": payload.get("failedNodeId"),
        "rootCauseEventId": payload.get("rootCauseEventId"),
    }


def object_or_empty(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def first_text(*values: Any, default: Optional[str] = "") -> Optional[str]:
    for value in values:
        if isinstance(value, str) and value:
            return value
    return default
