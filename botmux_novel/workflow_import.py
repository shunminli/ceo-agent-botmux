from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .bootstrap import NovelBootstrapRequest, write_approval_package
from .llmwiki_sync import LlmwikiSyncRequest, LlmwikiSyncResult, LlmwikiSyncer
from .mcp_config import NovelLlmwikiMcpConfigBuilder, NovelLlmwikiMcpConfigRequest, NovelLlmwikiMcpConfigResult
from .runtime import NovelFoundationResult, NovelRuntime, NovelWikiBundleRequest, NovelWikiBundleResult
from .schema_validation import validate_schema
from .workspace import NovelWorkspace, utc_now


REQUIRED_STORY_WORKFLOW_NODES = ["story_bible_package", "wiki_sync_plan"]
KNOWN_STORY_WORKFLOW_NODES = [
    "intake_brief",
    "context_scan",
    "creative_foundation",
    "continuity_review",
    "foundation_revision",
    "story_bible_package",
    "wiki_sync_plan",
]
AGENT_OUTPUT_FIELDS = {
    "preview": str,
    "handoff": str,
    "data": dict,
    "open_questions": list,
    "risks": list,
    "wiki_refs": list,
    "change_declarations": list,
}


@dataclass(frozen=True)
class NovelWorkflowFoundationImportRequest:
    workflow_result_path: Path
    project_path: Path
    project_slug: str
    title: Optional[str] = None
    inspiration: Optional[str] = None
    workspace_path: Optional[Path] = None
    chapter_number: int = 1
    mode: str = "lean"
    word_target: int = 1200
    llmwiki_bin: str = "llmwiki"


@dataclass(frozen=True)
class NovelWorkflowFoundationImportResult:
    run_id: str
    status: str
    project_path: Path
    project_slug: str
    workspace_path: Path
    workflow_result_path: Path
    imported_nodes: List[str]
    warnings: List[str]
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
            "workflow_result_path": str(self.workflow_result_path),
            "imported_nodes": self.imported_nodes,
            "warnings": self.warnings,
            "foundation": self.foundation.to_dict(),
            "wiki_bundle": self.wiki_bundle.to_dict(),
            "llmwiki_sync": self.llmwiki_sync.to_dict(),
            "mcp_config": self.mcp_config.to_dict(),
            "approval_package_path": str(self.approval_package_path),
            "approval_package_json_path": str(self.approval_package_json_path),
            "artifacts": [str(path) for path in self.artifacts],
        }


class NovelWorkflowFoundationImporter:
    def __init__(self) -> None:
        self.runtime = NovelRuntime()
        self.llmwiki_syncer = LlmwikiSyncer()
        self.mcp_config_builder = NovelLlmwikiMcpConfigBuilder()

    def import_foundation(self, request: NovelWorkflowFoundationImportRequest) -> NovelWorkflowFoundationImportResult:
        workflow_result_path = request.workflow_result_path.expanduser().resolve()
        project_path = request.project_path.expanduser().resolve()
        workspace_path = (
            request.workspace_path.expanduser().resolve()
            if request.workspace_path is not None
            else project_path
        )
        raw_result = load_workflow_result(workflow_result_path)
        params = workflow_params(raw_result)
        node_outputs = collect_story_workflow_outputs(raw_result)
        errors = validate_workflow_outputs(node_outputs)
        if errors:
            raise ValueError("invalid story foundation workflow result: " + "; ".join(errors))

        plan, import_warnings = workflow_outputs_to_foundation_plan(
            request=request,
            params=params,
            node_outputs=node_outputs,
            workflow_result_path=workflow_result_path,
        )
        foundation = self._write_foundation_import(
            request=request,
            project_path=project_path,
            workflow_result_path=workflow_result_path,
            raw_result=raw_result,
            node_outputs=node_outputs,
            plan=plan,
            warnings=import_warnings,
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

        started_at = utc_now()
        run_id = f"workflow-bootstrap-{started_at.replace(':', '').replace('-', '')}-{uuid.uuid4().hex[:8]}"
        run_dir = project_path / "runs" / run_id
        bootstrap_request = NovelBootstrapRequest(
            project_path=project_path,
            title=plan["project"]["title"],
            inspiration=plan["story_bible"]["inspiration"],
            project_slug=request.project_slug,
            workspace_path=workspace_path,
            chapter_number=request.chapter_number,
            mode=request.mode,
            word_target=request.word_target,
            llmwiki_bin=request.llmwiki_bin,
        )
        approval_package = write_approval_package(
            request=bootstrap_request,
            run_id=run_id,
            foundation=foundation,
            wiki_bundle=wiki_bundle,
            llmwiki_sync=llmwiki_sync,
            mcp_config=mcp_config,
            run_dir=run_dir,
            extra_payload={
                "workflow_import": {
                    "source_path": str(workflow_result_path),
                    "imported_nodes": sorted(node_outputs.keys()),
                    "story_bible_preview": node_outputs["story_bible_package"]["preview"],
                    "wiki_sync_plan_preview": node_outputs["wiki_sync_plan"]["preview"],
                    "warnings": import_warnings,
                }
            },
            extra_warnings=[f"workflow import: {warning}" for warning in import_warnings],
        )

        warnings = [*import_warnings, *llmwiki_sync.warnings, *mcp_config.warnings]
        status = "ready" if not warnings and mcp_config.status == "ready" else "ready_with_warnings"
        artifacts = [
            foundation.foundation_path,
            wiki_bundle.bundle_path,
            llmwiki_sync.plan_path,
            approval_package.approval_package_json_path,
            approval_package.approval_package_path,
        ]
        return NovelWorkflowFoundationImportResult(
            run_id=run_id,
            status=status,
            project_path=project_path,
            project_slug=wiki_bundle.project_slug,
            workspace_path=workspace_path,
            workflow_result_path=workflow_result_path,
            imported_nodes=sorted(node_outputs.keys()),
            warnings=warnings,
            foundation=foundation,
            wiki_bundle=wiki_bundle,
            llmwiki_sync=llmwiki_sync,
            mcp_config=mcp_config,
            approval_package_path=approval_package.approval_package_path,
            approval_package_json_path=approval_package.approval_package_json_path,
            artifacts=artifacts,
        )

    def _write_foundation_import(
        self,
        *,
        request: NovelWorkflowFoundationImportRequest,
        project_path: Path,
        workflow_result_path: Path,
        raw_result: Dict[str, Any],
        node_outputs: Dict[str, Dict[str, Any]],
        plan: Dict[str, Any],
        warnings: List[str],
    ) -> NovelFoundationResult:
        workspace = NovelWorkspace(project_path)
        workspace.ensure_layout()
        started_at = utc_now()
        run_id = f"workflow-foundation-{started_at.replace(':', '').replace('-', '')}-{uuid.uuid4().hex[:8]}"
        trace_payload: Dict[str, Any] = {
            "run_id": run_id,
            "started_at": started_at,
            "ended_at": None,
            "status": "running",
            "request": {
                "project_path": str(project_path),
                "workflow_result_path": str(workflow_result_path),
                "project_slug": request.project_slug,
                "chapter_number": request.chapter_number,
                "mode": request.mode,
                "word_target": request.word_target,
            },
            "steps": [
                {
                    "stage": "LoadWorkflowResult",
                    "agent": "director",
                    "status": "pass",
                    "summary": "Loaded story foundation workflow outputs.",
                    "output_keys": sorted(node_outputs.keys()),
                },
                {
                    "stage": "NormalizeFoundation",
                    "agent": "director",
                    "status": "pass" if not warnings else "warn",
                    "summary": "Converted workflow Story Bible outputs into local foundation assets.",
                    "output_keys": sorted(plan.keys()),
                },
            ],
            "artifacts": [],
        }

        bootstrap_request = NovelBootstrapRequest(
            project_path=project_path,
            title=plan["project"]["title"],
            inspiration=plan["story_bible"]["inspiration"],
            project_slug=request.project_slug,
            chapter_number=request.chapter_number,
            mode=request.mode,
            word_target=request.word_target,
            llmwiki_bin=request.llmwiki_bin,
        )
        self.runtime._validate_plan(plan)
        artifacts = self.runtime._write_project_assets(workspace, plan, bootstrap_request)
        source_path = workspace.write_json(f"runs/{run_id}/workflow-result-source.json", raw_result)
        outputs_path = workspace.write_json(f"runs/{run_id}/workflow-node-outputs.json", node_outputs)
        foundation_path = workspace.write_json(f"runs/{run_id}/foundation.json", plan)
        artifacts.extend([source_path, outputs_path, foundation_path])
        story_path = workspace.path("story.md")

        ended_at = utc_now()
        trace_payload["status"] = "completed"
        trace_payload["ended_at"] = ended_at
        for artifact in artifacts:
            trace_payload["artifacts"].append(str(artifact.relative_to(workspace.root)))
        validate_schema("run-trace", trace_payload)
        trace_path = workspace.write_json(f"runs/{run_id}/trace.json", trace_payload)
        artifacts.append(trace_path)
        sqlite_path = workspace.record_run(
            run_id=run_id,
            project_title=plan["project"]["title"],
            chapter_id=plan["chapter_goal"]["chapter_id"],
            mode=request.mode,
            status="completed",
            started_at=started_at,
            ended_at=ended_at,
            trace_path=trace_path,
            artifacts=[*artifacts, workspace.path("runs/runs.sqlite")],
        )
        artifacts.append(sqlite_path)
        trace_payload["artifacts"].append(str(sqlite_path.relative_to(workspace.root)))
        validate_schema("run-trace", trace_payload)
        trace_path = workspace.write_json(f"runs/{run_id}/trace.json", trace_payload)
        return NovelFoundationResult(
            run_id=run_id,
            status="completed",
            project_path=workspace.root,
            chapter_id=plan["chapter_goal"]["chapter_id"],
            story_path=story_path,
            foundation_path=foundation_path,
            trace_path=trace_path,
            sqlite_path=sqlite_path,
            artifacts=artifacts,
        )


def load_workflow_result(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise ValueError(f"workflow result file does not exist: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid workflow result JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError("workflow result JSON must be an object")
    return payload


def workflow_params(payload: Dict[str, Any]) -> Dict[str, Any]:
    for key in ["params", "parameters", "workflowParams"]:
        value = payload.get(key)
        if isinstance(value, dict):
            return value
    return {}


def collect_story_workflow_outputs(payload: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    outputs: Dict[str, Dict[str, Any]] = {}
    collect_known_node_outputs(payload, outputs)
    return outputs


def collect_known_node_outputs(value: Any, outputs: Dict[str, Dict[str, Any]]) -> None:
    if isinstance(value, dict):
        for node_id in KNOWN_STORY_WORKFLOW_NODES:
            if node_id in value and node_id not in outputs:
                output = normalize_node_output(value[node_id])
                if output is not None:
                    outputs[node_id] = output
        for child in value.values():
            collect_known_node_outputs(child, outputs)
    elif isinstance(value, list):
        for child in value:
            collect_known_node_outputs(child, outputs)


def normalize_node_output(value: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(value, dict):
        return None
    if is_agent_output(value):
        return value
    for key in ["output", "result", "value", "data"]:
        nested = value.get(key)
        if isinstance(nested, dict) and is_agent_output(nested):
            return nested
    return None


def is_agent_output(value: Dict[str, Any]) -> bool:
    return {"preview", "handoff", "data"}.issubset(value.keys())


def validate_workflow_outputs(node_outputs: Dict[str, Dict[str, Any]]) -> List[str]:
    errors: List[str] = []
    for node_id in REQUIRED_STORY_WORKFLOW_NODES:
        if node_id not in node_outputs:
            errors.append(f"missing required node output: {node_id}")
    for node_id, output in sorted(node_outputs.items()):
        for field, expected_type in AGENT_OUTPUT_FIELDS.items():
            if field not in output:
                errors.append(f"{node_id}.{field} is required")
                continue
            if not isinstance(output[field], expected_type):
                errors.append(f"{node_id}.{field} expected {expected_type.__name__}")
    return errors


def workflow_outputs_to_foundation_plan(
    *,
    request: NovelWorkflowFoundationImportRequest,
    params: Dict[str, Any],
    node_outputs: Dict[str, Dict[str, Any]],
    workflow_result_path: Path,
) -> Tuple[Dict[str, Any], List[str]]:
    warnings: List[str] = []
    story_output = node_outputs["story_bible_package"]
    wiki_output = node_outputs["wiki_sync_plan"]
    story_data = object_or_empty(story_output.get("data"))
    revision_data = object_or_empty(node_outputs.get("foundation_revision", {}).get("data"))
    creative_data = object_or_empty(node_outputs.get("creative_foundation", {}).get("data"))
    context_data = object_or_empty(node_outputs.get("context_scan", {}).get("data"))

    title = first_text(
        request.title,
        params.get("title"),
        story_data.get("title"),
        story_data.get("project_title"),
        default="Untitled Novel",
        warnings=warnings,
        warning="missing title; using Untitled Novel",
    )
    inspiration = first_text(
        request.inspiration,
        params.get("inspiration"),
        story_data.get("inspiration"),
        story_output.get("preview"),
        default=story_output["handoff"],
        warnings=warnings,
        warning="missing inspiration; using Story Bible handoff",
    )
    genre = first_text(params.get("genre"), story_data.get("genre"), default="unspecified", warnings=warnings)
    target_length = first_text(params.get("targetLength"), story_data.get("target_length"), default="", warnings=warnings)
    plot_arc = object_or_empty(story_data.get("plot_arc") or story_data.get("plot") or revision_data.get("revised_plot_beats"))
    story_promise = first_text(
        story_data.get("story_promise"),
        plot_arc.get("story_promise"),
        story_output.get("preview"),
        default=story_output["handoff"],
        warnings=warnings,
    )
    theme = first_text(
        story_data.get("theme"),
        plot_arc.get("theme"),
        story_data.get("central_theme"),
        default=story_promise,
        warnings=warnings,
    )
    core_conflict = first_text(
        story_data.get("core_conflict"),
        plot_arc.get("core_conflict"),
        story_promise,
        default=story_output["handoff"],
        warnings=warnings,
    )
    ending_constraint = first_text(
        story_data.get("ending_constraint"),
        plot_arc.get("ending_constraint"),
        story_data.get("final_pressure"),
        default="Resolve the central conflict using approved foreshadowing and character choices.",
        warnings=warnings,
        warning="missing ending constraint; using generic approved-foreshadowing constraint",
    )

    characters = normalize_characters(
        first_existing(
            story_data.get("characters"),
            revision_data.get("revised_characters"),
            creative_data.get("characters"),
            story_data.get("character_table"),
        )
    )
    relationships = normalize_relationships(
        first_existing(
            story_data.get("relationships"),
            revision_data.get("revised_relationships"),
            creative_data.get("relationships"),
        ),
        project_title=title,
    )
    scene_settings = normalize_scene_settings(
        first_existing(
            story_data.get("settings"),
            story_data.get("scene_settings"),
            revision_data.get("revised_settings"),
            creative_data.get("settings"),
            creative_data.get("scene_settings"),
        )
    )
    rules = normalize_rules(story_data.get("rules"), revision_data.get("revised_settings"), scene_settings, warnings)
    turning_points = normalize_turning_points(plot_arc, story_data, warnings)
    chapter_goal = normalize_chapter_goal(
        chapter_number=request.chapter_number,
        story_data=story_data,
        plot_arc=plot_arc,
        scene_settings=scene_settings,
        characters=characters,
        forbidden=rules["forbidden"],
    )

    plan = {
        "project": {
            "title": title,
            "mode": request.mode,
            "stage": "ImportedWorkflowFoundation",
            "current_chapter": chapter_id(request.chapter_number),
            "word_target": request.word_target,
            "quality_thresholds": {
                "progression": 7,
                "emotion": 7,
                "character": 8,
                "pacing": 7,
                "style": 8,
            },
            "source_workflow_result": str(workflow_result_path),
        },
        "story_bible": {
            "theme": theme,
            "inspiration": inspiration,
            "core_conflict": core_conflict,
            "ending_constraint": ending_constraint,
            "workflow_handoff": story_output["handoff"],
        },
        "genre": {
            "primary": genre,
            "target_length": target_length,
            "reader_expectations": string_list(
                story_data.get("reader_expectations")
                or story_data.get("target_readers")
                or ["clear story promise", "character pressure", "causal reversals"]
            ),
            "selling_points": string_list(
                story_data.get("selling_points")
                or story_data.get("story_hooks")
                or [story_promise]
            ),
        },
        "world": rules,
        "characters": characters,
        "relationships": relationships,
        "scene_settings": scene_settings,
        "style_profile": normalize_style_profile(story_data),
        "volume_outline": {
            "volume": first_text(plot_arc.get("volume"), story_data.get("volume"), default="Volume 1", warnings=warnings),
            "goal": first_text(plot_arc.get("goal"), story_promise, default=core_conflict, warnings=warnings),
            "turning_points": turning_points,
        },
        "chapter_goal": chapter_goal,
        "workflow_source": {
            "result_path": str(workflow_result_path),
            "story_bible_package": story_output,
            "wiki_sync_plan": wiki_output,
            "context_scan": node_outputs.get("context_scan"),
            "foundation_revision": node_outputs.get("foundation_revision"),
            "workflow_wiki_plan_handoff": wiki_output["handoff"],
            "context_plan": context_data,
        },
    }
    return plan, warnings


def normalize_characters(value: Any) -> List[Dict[str, Any]]:
    items = object_values_or_list(value, nested_keys=["characters", "revised_characters", "cast"])
    characters: List[Dict[str, Any]] = []
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            continue
        name = first_text(item.get("name"), item.get("title"), item.get("id"), default=f"Character {index}")
        character_id = safe_id(item.get("id") or name, prefix="character", index=index)
        characters.append(
            {
                "id": character_id,
                "name": name,
                "role": first_text(item.get("role"), item.get("function"), default="story role"),
                "motivation": first_text(item.get("motivation"), item.get("desire"), item.get("want"), default="TBD"),
                "current_state": first_text(
                    item.get("current_state"),
                    item.get("state"),
                    item.get("status"),
                    default="TBD",
                ),
                "secret": first_text(item.get("secret"), item.get("misbelief"), item.get("hidden_truth"), default="TBD"),
            }
        )
    if not characters:
        raise ValueError("story_bible_package.data.characters must contain at least one character object")
    return characters


def normalize_relationships(value: Any, *, project_title: str) -> Dict[str, Any]:
    items = object_values_or_list(value, nested_keys=["edges", "relationships", "revised_relationships"])
    edges: List[Dict[str, Any]] = []
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            continue
        source = first_text(item.get("source"), item.get("from"), item.get("a"), default="")
        target = first_text(item.get("target"), item.get("to"), item.get("b"), default="")
        if not source or not target:
            continue
        edges.append(
            {
                "source": source,
                "target": target,
                "type": first_text(item.get("type"), item.get("relation"), default="pressure"),
                "pressure": first_text(item.get("pressure"), item.get("conflict"), item.get("tension"), default="TBD"),
                "secret": first_text(item.get("secret"), item.get("hidden_truth"), default="TBD"),
            }
        )
    if not edges:
        raise ValueError("story_bible_package.data.relationships must contain at least one edge with source and target")
    return {"project_title": project_title, "edges": edges}


def normalize_scene_settings(value: Any) -> List[Dict[str, Any]]:
    items = object_values_or_list(value, nested_keys=["settings", "scene_settings", "scenes", "locations"])
    scenes: List[Dict[str, Any]] = []
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            continue
        name = first_text(item.get("name"), item.get("title"), item.get("id"), default=f"Scene {index}")
        scenes.append(
            {
                "id": safe_id(item.get("id") or name, prefix="scene", index=index),
                "name": name,
                "kind": first_text(item.get("kind"), item.get("type"), default="location"),
                "function": first_text(item.get("function"), item.get("purpose"), default="TBD"),
                "conflict_pressure": first_text(
                    item.get("conflict_pressure"),
                    item.get("pressure"),
                    item.get("conflict"),
                    default="TBD",
                ),
                "rules": string_list(item.get("rules") or item.get("constraints") or ["TBD"]),
                "reuse_value": first_text(item.get("reuse_value"), item.get("payoff"), default="TBD"),
            }
        )
    if not scenes:
        raise ValueError("story_bible_package.data.settings must contain at least one scene or setting object")
    return scenes


def normalize_rules(
    value: Any,
    revised_settings: Any,
    scene_settings: List[Dict[str, Any]],
    warnings: List[str],
) -> Dict[str, List[str]]:
    if isinstance(value, dict):
        rules = string_list(value.get("world_rules") or value.get("rules") or value.get("continuity_rules"))
        forbidden = string_list(value.get("forbidden") or value.get("hard_constraints") or value.get("forbidden_reveals"))
    else:
        rules = string_list(value)
        forbidden = []
    if not rules:
        rules = [rule for scene in scene_settings for rule in scene.get("rules", []) if rule]
    if not rules:
        rules = string_list(revised_settings)
    if not rules:
        warnings.append("missing world rules; using a generic continuity rule")
        rules = ["Do not contradict confirmed Story Bible facts without change_declarations."]
    if not forbidden:
        warnings.append("missing forbidden constraints; using generic reveal discipline")
        forbidden = ["Do not reveal final answers before approved setup and payoff."]
    return {"rules": rules, "forbidden": forbidden}


def normalize_turning_points(plot_arc: Dict[str, Any], story_data: Dict[str, Any], warnings: List[str]) -> List[str]:
    turning_points = string_list(
        plot_arc.get("turning_points")
        or plot_arc.get("key_plot_beats")
        or story_data.get("plot_beats")
        or story_data.get("key_plot_beats")
    )
    if not turning_points:
        warnings.append("missing turning points; using generic five-beat structure")
        turning_points = ["Opening hook", "First turn", "Midpoint reversal", "Low point", "Final pressure"]
    return turning_points


def normalize_chapter_goal(
    *,
    chapter_number: int,
    story_data: Dict[str, Any],
    plot_arc: Dict[str, Any],
    scene_settings: List[Dict[str, Any]],
    characters: List[Dict[str, Any]],
    forbidden: List[str],
) -> Dict[str, Any]:
    objective = first_text(
        story_data.get("initial_chapter_goal"),
        story_data.get("chapter_goal"),
        plot_arc.get("opening_hook"),
        plot_arc.get("opening"),
        default="Open with the approved story promise, introduce pressure, and seed the central conflict.",
    )
    must_include = string_list(
        story_data.get("must_include")
        or [*(scene["name"] for scene in scene_settings[:2]), *(character["name"] for character in characters[:2])]
    )
    return {
        "chapter_id": chapter_id(chapter_number),
        "objective": objective,
        "must_include": must_include,
        "forbidden": forbidden,
    }


def normalize_style_profile(story_data: Dict[str, Any]) -> Dict[str, Any]:
    style = object_or_empty(story_data.get("style_profile") or story_data.get("style"))
    return {
        "id": safe_id(style.get("id") or "workflow-import-style", prefix="style", index=1),
        "tone": first_text(style.get("tone"), story_data.get("tone"), default="controlled, specific, scene-led"),
        "rules": string_list(style.get("rules") or ["Prefer concrete actions over explanation.", "Keep dialogue subtextual."]),
        "forbidden_expressions": string_list(style.get("forbidden_expressions") or ["suddenly", "very shocked"]),
        "positive_examples": string_list(style.get("positive_examples") or ["A specific action reveals the emotional turn."]),
        "negative_examples": string_list(style.get("negative_examples") or ["The character felt very surprised."]),
    }


def object_values_or_list(value: Any, *, nested_keys: List[str]) -> List[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        for key in nested_keys:
            nested = value.get(key)
            if isinstance(nested, list):
                return nested
        if all(isinstance(item, dict) for item in value.values()):
            return list(value.values())
    return []


def object_or_empty(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def first_existing(*values: Any) -> Any:
    for value in values:
        if value not in (None, "", [], {}):
            return value
    return None


def first_text(*values: Any, default: str, warnings: Optional[List[str]] = None, warning: Optional[str] = None) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, dict) and value:
            return json.dumps(value, ensure_ascii=False, sort_keys=True)
        if isinstance(value, list) and value:
            return "; ".join(str(item) for item in value if item not in (None, ""))
    if warning and warnings is not None:
        warnings.append(warning)
    return default


def string_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return [first_text(item, default="").strip() for item in value if first_text(item, default="").strip()]
    if isinstance(value, dict):
        return [first_text(item, default="").strip() for item in value.values() if first_text(item, default="").strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def safe_id(value: Any, *, prefix: str, index: int) -> str:
    text = first_text(value, default="")
    text = text.strip().lower().replace("_", "-")
    text = re.sub(r"[^a-z0-9-]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    if not text:
        text = f"{prefix}-{index}"
    return text[:80]


def chapter_id(chapter_number: int) -> str:
    return f"ch-{chapter_number:03d}"
