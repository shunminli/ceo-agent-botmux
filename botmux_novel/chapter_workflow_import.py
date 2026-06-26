from __future__ import annotations

import json
import re
import shlex
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from .chapter_goals import chapter_goal_for
from .schema_validation import validate_required
from .workspace import NovelWorkspace, markdown_list, utc_now
from .workflow_import import AGENT_OUTPUT_FIELDS, load_workflow_result, workflow_params


REQUIRED_CHAPTER_WORKFLOW_NODES = [
    "chapter_prepare",
    "chapter_blueprint",
    "chapter_draft",
    "continuity_review",
    "chapter_revision",
    "director_approval_package",
    "archive_plan",
]
PASS_DECISIONS = {"pass", "passed", "approve", "approved", "archive", "ready"}
BLOCK_DECISIONS = {"block", "blocked", "reject", "rejected", "request_changes", "revise"}


@dataclass(frozen=True)
class NovelChapterWorkflowImportRequest:
    workflow_result_path: Path
    project_path: Path
    chapter_number: Optional[int] = None
    title: Optional[str] = None
    mode: str = "lean"
    word_target: int = 1200
    foundation_path: Optional[Path] = None


@dataclass(frozen=True)
class NovelChapterWorkflowImportResult:
    run_id: str
    status: str
    project_path: Path
    workflow_result_path: Path
    chapter_id: str
    final_path: Path
    trace_path: Path
    sqlite_path: Path
    imported_nodes: List[str]
    warnings: List[str]
    artifacts: List[Path]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "status": self.status,
            "project_path": str(self.project_path),
            "workflow_result_path": str(self.workflow_result_path),
            "chapter_id": self.chapter_id,
            "final_path": str(self.final_path),
            "trace_path": str(self.trace_path),
            "sqlite_path": str(self.sqlite_path),
            "imported_nodes": self.imported_nodes,
            "warnings": self.warnings,
            "artifacts": [str(path) for path in self.artifacts],
        }


class NovelChapterWorkflowImporter:
    def import_chapter(self, request: NovelChapterWorkflowImportRequest) -> NovelChapterWorkflowImportResult:
        workflow_result_path = request.workflow_result_path.expanduser().resolve()
        project_path = request.project_path.expanduser().resolve()
        raw_result = load_workflow_result(workflow_result_path)
        params = workflow_params(raw_result)
        node_outputs = collect_chapter_workflow_outputs(raw_result)
        errors = validate_chapter_workflow_outputs(node_outputs)
        if errors:
            raise ValueError("invalid chapter workflow result: " + "; ".join(errors))

        chapter_number = resolve_chapter_number(request, params, node_outputs)
        chapter = chapter_id(chapter_number)
        title = first_text(request.title, params.get("title"), default="Untitled Novel")
        mode = first_text(params.get("mode"), request.mode, default=request.mode)
        word_target = int_or_default(params.get("wordTarget"), request.word_target)

        director = node_outputs["director_approval_package"]
        archive_output = node_outputs["archive_plan"]
        director_data = object_or_empty(director.get("data"))
        archive_data = object_or_empty(archive_output.get("data"))
        director_decision = first_text(director_data.get("decision"), default="block").lower()
        archive_decision = first_text(archive_data.get("archive_decision"), default=director_decision).lower()
        warnings: List[str] = []

        workspace = NovelWorkspace(project_path)
        workspace.ensure_layout()
        started_at = utc_now()
        run_id = f"workflow-chapter-{started_at.replace(':', '').replace('-', '')}-{uuid.uuid4().hex[:8]}"
        artifacts: List[Path] = []

        trace_payload: Dict[str, Any] = {
            "run_id": run_id,
            "started_at": started_at,
            "ended_at": None,
            "status": "running",
            "request": {
                "project_path": str(project_path),
                "workflow_result_path": str(workflow_result_path),
                "chapter_number": chapter_number,
                "chapter_id": chapter,
                "mode": mode,
                "word_target": word_target,
                "foundation_path": str(request.foundation_path.expanduser().resolve()) if request.foundation_path else None,
            },
            "steps": [
                {
                    "stage": "LoadWorkflowResult",
                    "agent": "director",
                    "status": "pass",
                    "summary": "Loaded chapter workflow outputs.",
                    "output_keys": sorted(node_outputs.keys()),
                },
                {
                    "stage": "DirectorDecision",
                    "agent": "director",
                    "status": director_decision,
                    "summary": director.get("preview", ""),
                    "output_keys": sorted(director_data.keys()),
                },
                {
                    "stage": "ArchivePlan",
                    "agent": "director",
                    "status": archive_decision,
                    "summary": archive_output.get("preview", ""),
                    "output_keys": sorted(archive_data.keys()),
                },
            ],
            "artifacts": [],
        }

        source_path = workspace.write_json(f"runs/{run_id}/workflow-result-source.json", raw_result)
        outputs_path = workspace.write_json(f"runs/{run_id}/workflow-node-outputs.json", node_outputs)
        artifacts.extend([source_path, outputs_path])

        blueprint = normalize_blueprint(node_outputs["chapter_blueprint"], chapter=chapter)
        validate_required("chapter-blueprint", blueprint)
        blueprint_path = workspace.write_json(f"outline/chapter-blueprints/{chapter}.json", blueprint)
        blueprint_md_path = workspace.write_text(f"outline/chapter-blueprints/{chapter}.md", render_blueprint_markdown(blueprint))
        artifacts.extend([blueprint_path, blueprint_md_path])

        draft_text = text_from_node(node_outputs["chapter_draft"], "draft_text", fallback_key="handoff")
        revised_text = text_from_node(node_outputs["chapter_revision"], "revised_text", fallback_key="handoff")
        final_text = first_text(director_data.get("final_text"), revised_text, default="")
        if not final_text:
            warnings.append("director final_text missing; import cannot write final manuscript")

        draft_path = workspace.write_text(f"manuscript/draft/{chapter}.md", draft_text)
        revised_path = workspace.write_text(f"manuscript/revised/{chapter}.md", revised_text)
        artifacts.extend([draft_path, revised_path])

        can_archive = director_decision in PASS_DECISIONS and archive_decision in PASS_DECISIONS and bool(final_text)
        final_path = workspace.path(f"manuscript/final/{chapter}.md")
        if can_archive:
            final_path = workspace.write_text(f"manuscript/final/{chapter}.md", final_text)
            artifacts.append(final_path)
            archive = normalize_archive(archive_data, chapter=chapter, final_text=final_text)
            validate_archive(archive)
            artifacts.extend(write_archive_assets(workspace, archive, chapter))
            project_path_written = workspace.write_yaml(
                "project.yaml",
                {
                    "title": title,
                    "mode": mode,
                    "stage": "Archive",
                    "current_chapter": chapter,
                    "word_target": word_target,
                    "quality_thresholds": {
                        "progression": 7,
                        "emotion": 7,
                        "character": 8,
                        "pacing": 7,
                        "style": 8,
                    },
                    "latest_run_id": run_id,
                    "archived_chapters": [chapter],
                    "source_workflow_result": str(workflow_result_path),
                },
            )
            artifacts.append(project_path_written)
            next_handoff = next_chapter_handoff(
                project_path=project_path,
                run_id=run_id,
                title=title,
                current_chapter=chapter,
                current_chapter_number=chapter_number,
                archive=archive,
                params=params,
                request=request,
            )
            artifacts.append(workspace.write_json(f"runs/{run_id}/next-chapter-command.json", next_handoff))
            artifacts.append(workspace.write_text(f"runs/{run_id}/next-chapter-command.md", render_next_chapter_markdown(next_handoff)))
            status = "completed"
        else:
            warnings.append(
                f"chapter workflow import blocked: director_decision={director_decision}, archive_decision={archive_decision}"
            )
            block_payload = {
                "chapter_id": chapter,
                "director_decision": director_decision,
                "archive_decision": archive_decision,
                "director_preview": director.get("preview", ""),
                "archive_preview": archive_output.get("preview", ""),
                "open_questions": director.get("open_questions", []) + archive_output.get("open_questions", []),
                "risks": director.get("risks", []) + archive_output.get("risks", []),
            }
            artifacts.append(workspace.write_json(f"runs/{run_id}/blocked-chapter-import.json", block_payload))
            status = "blocked"

        summary_path = workspace.write_text(
            f"runs/{run_id}/summary.md",
            render_import_summary(
                run_id=run_id,
                title=title,
                chapter=chapter,
                status=status,
                director_decision=director_decision,
                archive_decision=archive_decision,
                warnings=warnings,
            ),
        )
        artifacts.append(summary_path)

        ended_at = utc_now()
        trace_payload["status"] = status
        trace_payload["ended_at"] = ended_at
        for artifact in artifacts:
            trace_payload["artifacts"].append(str(artifact.relative_to(workspace.root)))
        validate_required("run-trace", trace_payload)
        trace_path = workspace.write_json(f"runs/{run_id}/trace.json", trace_payload)
        artifacts.append(trace_path)
        sqlite_path = workspace.record_run(
            run_id=run_id,
            project_title=title,
            chapter_id=chapter,
            mode=mode,
            status=status,
            started_at=started_at,
            ended_at=ended_at,
            trace_path=trace_path,
            artifacts=[*artifacts, workspace.path("runs/runs.sqlite")],
        )
        artifacts.append(sqlite_path)
        trace_payload["artifacts"].append(str(sqlite_path.relative_to(workspace.root)))
        validate_required("run-trace", trace_payload)
        trace_path = workspace.write_json(f"runs/{run_id}/trace.json", trace_payload)
        return NovelChapterWorkflowImportResult(
            run_id=run_id,
            status=status,
            project_path=workspace.root,
            workflow_result_path=workflow_result_path,
            chapter_id=chapter,
            final_path=final_path,
            trace_path=trace_path,
            sqlite_path=sqlite_path,
            imported_nodes=sorted(node_outputs.keys()),
            warnings=warnings,
            artifacts=artifacts,
        )


def collect_chapter_workflow_outputs(payload: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    outputs: Dict[str, Dict[str, Any]] = {}
    collect_node_outputs(payload, outputs)
    return outputs


def collect_node_outputs(value: Any, outputs: Dict[str, Dict[str, Any]]) -> None:
    if isinstance(value, dict):
        for node_id in REQUIRED_CHAPTER_WORKFLOW_NODES:
            if node_id in value and node_id not in outputs:
                output = normalize_node_output(value[node_id])
                if output is not None:
                    outputs[node_id] = output
        for child in value.values():
            collect_node_outputs(child, outputs)
    elif isinstance(value, list):
        for child in value:
            collect_node_outputs(child, outputs)


def normalize_node_output(value: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(value, dict):
        return None
    if {"preview", "handoff", "data"}.issubset(value.keys()):
        return value
    for key in ["output", "result", "value", "data"]:
        nested = value.get(key)
        if isinstance(nested, dict) and {"preview", "handoff", "data"}.issubset(nested.keys()):
            return nested
    return None


def validate_chapter_workflow_outputs(node_outputs: Dict[str, Dict[str, Any]]) -> List[str]:
    errors: List[str] = []
    for node_id in REQUIRED_CHAPTER_WORKFLOW_NODES:
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


def resolve_chapter_number(
    request: NovelChapterWorkflowImportRequest,
    params: Dict[str, Any],
    node_outputs: Dict[str, Dict[str, Any]],
) -> int:
    if request.chapter_number is not None:
        return request.chapter_number
    candidate = params.get("chapterNumber")
    if candidate is None:
        candidate = object_or_empty(node_outputs["chapter_blueprint"].get("data")).get("chapter_number")
    if candidate is None:
        candidate = object_or_empty(node_outputs["chapter_blueprint"].get("data")).get("chapter_id")
    if isinstance(candidate, str):
        match = re.search(r"(\d+)", candidate)
        if match:
            return int(match.group(1))
    if isinstance(candidate, (int, float)):
        return int(candidate)
    raise ValueError("chapter number is required; pass --chapter-number or include params.chapterNumber")


def normalize_blueprint(node_output: Dict[str, Any], *, chapter: str) -> Dict[str, Any]:
    data = object_or_empty(node_output.get("data"))
    scenes = data.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        scenes = [
            {
                "id": "scene-1",
                "purpose": "Imported workflow scene",
                "location": "TBD",
                "conflict": first_text(data.get("objective"), node_output.get("preview"), default="TBD"),
                "turn": "TBD",
            }
        ]
    normalized_scenes = []
    for index, scene in enumerate(scenes, start=1):
        scene_data = object_or_empty(scene)
        normalized_scenes.append(
            {
                "id": first_text(scene_data.get("id"), default=f"scene-{index}"),
                "purpose": first_text(scene_data.get("purpose"), scene_data.get("function"), default="TBD"),
                "location": first_text(scene_data.get("location"), scene_data.get("setting"), default="TBD"),
                "conflict": first_text(scene_data.get("conflict"), scene_data.get("pressure"), default="TBD"),
                "turn": first_text(scene_data.get("turn"), scene_data.get("reversal"), default="TBD"),
            }
        )
    return {
        "chapter_id": first_text(data.get("chapter_id"), default=chapter),
        "title": first_text(data.get("title"), default=chapter),
        "objective": first_text(data.get("objective"), node_output.get("preview"), default="Imported chapter objective"),
        "scenes": normalized_scenes,
        "emotion_curve": string_list(data.get("emotion_curve") or ["pressure", "turn", "hook"]),
        "must_include": string_list(data.get("must_include") or []),
        "forbidden": string_list(data.get("forbidden") or []),
    }


def normalize_archive(data: Dict[str, Any], *, chapter: str, final_text: str) -> Dict[str, Any]:
    archive = {
        "archive_decision": first_text(data.get("archive_decision"), default="archive"),
        "facts": normalize_facts(data.get("facts"), chapter=chapter),
        "timeline": normalize_timeline(data.get("timeline"), chapter=chapter),
        "foreshadowing": normalize_foreshadowing(data.get("foreshadowing"), chapter=chapter),
        "character_state": normalize_character_state(data.get("character_state")),
        "continuity_issues": normalize_continuity_issues(data.get("continuity_issues")),
        "style_feedback": string_list(data.get("style_feedback") or []),
        "wiki_sync_plan": data.get("wiki_sync_plan") if isinstance(data.get("wiki_sync_plan"), dict) else {},
        "rollback_plan": first_text(data.get("rollback_plan"), default="Restore from workflow import run artifacts."),
        "final_word_count": len(final_text),
    }
    return archive


def normalize_facts(value: Any, *, chapter: str) -> List[Dict[str, Any]]:
    facts = []
    for index, item in enumerate(list_or_values(value), start=1):
        item_data = object_or_empty(item)
        fact = first_text(item_data.get("fact"), item_data.get("value"), item, default="")
        if not fact:
            continue
        facts.append(
            {
                "chapter_id": first_text(item_data.get("chapter_id"), default=chapter),
                "fact": fact,
                "source": first_text(item_data.get("source"), default="chapter workflow archive_plan"),
            }
        )
    if not facts:
        facts.append({"chapter_id": chapter, "fact": "Chapter imported from approved workflow output.", "source": "workflow import"})
    return facts


def normalize_timeline(value: Any, *, chapter: str) -> List[Dict[str, Any]]:
    timeline = []
    for index, item in enumerate(list_or_values(value), start=1):
        item_data = object_or_empty(item)
        timeline.append(
            {
                "chapter_id": first_text(item_data.get("chapter_id"), default=chapter),
                "event": first_text(item_data.get("event"), item_data.get("value"), item, default=f"Imported event {index}"),
                "order": item_data.get("order", index),
            }
        )
    return timeline


def normalize_foreshadowing(value: Any, *, chapter: str) -> List[Dict[str, Any]]:
    foreshadowing = []
    for index, item in enumerate(list_or_values(value), start=1):
        item_data = object_or_empty(item)
        seed = first_text(item_data.get("item"), item_data.get("value"), item_data.get("fact"), item, default="")
        if not seed:
            continue
        foreshadowing.append(
            {
                "id": first_text(item_data.get("id"), default=f"{chapter}-foreshadowing-{index}"),
                "chapter_id": first_text(item_data.get("chapter_id"), default=chapter),
                "item": seed,
                "introduced_in": first_text(item_data.get("introduced_in"), default=chapter),
                "planned_payoff": first_text(item_data.get("planned_payoff"), item_data.get("payoff"), default="TBD"),
                "status": valid_choice(item_data.get("status"), {"open", "paid_off", "changed", "dropped"}, default="open"),
                "risk": valid_choice(item_data.get("risk"), {"P0", "P1", "P2", "P3"}, default="P2"),
            }
        )
    return foreshadowing


def normalize_character_state(value: Any) -> List[Dict[str, Any]]:
    states = []
    for index, item in enumerate(list_or_values(value), start=1):
        item_data = object_or_empty(item)
        state = first_text(item_data.get("state"), item_data.get("current_state"), item_data.get("value"), default="")
        if not state:
            continue
        name = first_text(item_data.get("name"), item_data.get("id"), default=f"Character {index}")
        states.append(
            {
                "id": first_text(item_data.get("id"), default=safe_id(name, prefix="character", index=index)),
                "name": name,
                "state": state,
                "known_information": string_list(item_data.get("known_information") or item_data.get("known") or []),
            }
        )
    return states


def normalize_continuity_issues(value: Any) -> List[Dict[str, Any]]:
    issues = []
    for index, item in enumerate(list_or_values(value), start=1):
        item_data = object_or_empty(item)
        issues.append(
            {
                "id": first_text(item_data.get("id"), default=f"issue-{index}"),
                "severity": first_text(item_data.get("severity"), item_data.get("risk"), default="P3"),
                "issue": first_text(item_data.get("issue"), item_data.get("value"), item, default="Imported issue"),
                "status": first_text(item_data.get("status"), default="noted"),
            }
        )
    return issues


def validate_archive(archive: Dict[str, Any]) -> None:
    for fact in archive["facts"]:
        validate_required("fact-snapshot", fact)
    for item in archive["foreshadowing"]:
        validate_required("foreshadowing-ledger", item)
    for state in archive["character_state"]:
        validate_required("character-state", state)


def write_archive_assets(workspace: NovelWorkspace, archive: Dict[str, Any], chapter: str) -> List[Path]:
    return [
        workspace.write_yaml("tracking/facts.yaml", {"facts": archive["facts"]}),
        workspace.write_yaml("tracking/timeline.yaml", {"timeline": archive["timeline"]}),
        workspace.write_yaml("tracking/foreshadowing.yaml", {"foreshadowing": archive["foreshadowing"]}),
        workspace.write_yaml("tracking/character-state.yaml", {"characters": archive["character_state"]}),
        workspace.write_yaml("tracking/continuity-issues.yaml", {"issues": archive["continuity_issues"]}),
        workspace.write_json(f"runs/archive-{chapter}.json", archive),
    ]


def next_chapter_handoff(
    *,
    project_path: Path,
    run_id: str,
    title: str,
    current_chapter: str,
    current_chapter_number: int,
    archive: Dict[str, Any],
    params: Dict[str, Any],
    request: NovelChapterWorkflowImportRequest,
) -> Dict[str, Any]:
    next_number = current_chapter_number + 1
    next_goal = chapter_goal_for(next_number)
    story_bible = first_text(params.get("storyBible"), default="Use the approved Story Bible and latest archive context.")
    prior_context = render_prior_context_for_handoff(current_chapter=current_chapter, archive=archive)
    word_target = int_or_default(params.get("wordTarget"), request.word_target)
    mode = first_text(params.get("mode"), request.mode, default=request.mode)
    command = [
        "botmux",
        "workflow",
        "run",
        "novel-chapter-production",
        "--param",
        f"projectSlug={first_text(params.get('projectSlug'), default='project-slug')}",
        "--param",
        f"title={title}",
        "--param",
        f"storyBible={story_bible}",
        "--param",
        f"chapterNumber={next_number}",
        "--param",
        f"chapterGoal={next_goal}",
        "--param",
        f"priorContext={prior_context}",
        "--param",
        f"wordTarget={word_target}",
        "--param",
        f"mode={mode}",
    ]
    local_command: List[str] = []
    if request.foundation_path is not None:
        local_command = [
            "python3",
            "-m",
            "botmux_novel",
            "chapter",
            "--project",
            str(project_path),
            "--chapter-number",
            str(next_number),
            "--chapter-goal",
            next_goal,
            "--foundation-json",
            str(request.foundation_path.expanduser().resolve()),
        ]
    return {
        "status": "suggested",
        "project_path": str(project_path),
        "current_chapter_id": current_chapter,
        "next_chapter_id": chapter_id(next_number),
        "next_chapter_number": next_number,
        "chapter_goal": next_goal,
        "prior_context": prior_context,
        "word_target": word_target,
        "mode": mode,
        "workflow_command": command,
        "workflow_command_text": shlex.join(command),
        "local_command": local_command,
        "local_command_text": shlex.join(local_command) if local_command else "",
        "source_refs": [
            f"runs/{run_id}/summary.md",
            f"runs/archive-{current_chapter}.json",
        ],
    }


def render_prior_context_for_handoff(*, current_chapter: str, archive: Dict[str, Any]) -> str:
    sections = [
        f"Source chapter: {current_chapter}",
        render_archive_items("Facts", archive.get("facts", []), ["fact", "summary", "value"]),
        render_archive_items("Timeline", archive.get("timeline", []), ["event", "summary", "value"]),
        render_archive_items("Foreshadowing", archive.get("foreshadowing", []), ["item", "clue", "description", "id"]),
        render_archive_items("Character state", archive.get("character_state", []), ["state", "current_state", "summary", "value"], label_keys=["name", "id", "character_id"]),
        render_archive_items("Continuity issues", archive.get("continuity_issues", []), ["issue", "summary", "value"]),
    ]
    return "\n".join(section for section in sections if section.strip())


def render_archive_items(title: str, items: Any, preferred_keys: List[str], label_keys: Optional[List[str]] = None) -> str:
    if not isinstance(items, list) or not items:
        return f"{title}: none"
    lines = [f"{title}:"]
    for item in items:
        if isinstance(item, dict):
            value = first_present_text(item, preferred_keys)
            if not value:
                value = json.dumps(item, ensure_ascii=False, sort_keys=True)
            label = first_present_text(item, label_keys or [])
            detail_parts = []
            for key in ["status", "risk", "risk_level", "planned_payoff", "payoff_plan"]:
                if item.get(key) not in (None, ""):
                    detail_parts.append(f"{key}={first_text(item.get(key), default='')}")
            detail = f" ({'; '.join(detail_parts)})" if detail_parts else ""
            prefix = f"{label}: " if label else ""
            lines.append(f"- {prefix}{value}{detail}")
        else:
            lines.append(f"- {first_text(item, default='')}")
    return "\n".join(lines)


def first_present_text(item: Dict[str, Any], keys: List[str]) -> str:
    for key in keys:
        value = first_text(item.get(key), default="")
        if value:
            return value
    return ""


def render_next_chapter_markdown(payload: Dict[str, Any]) -> str:
    local_command = payload.get("local_command_text") or "Pass --foundation-json to chapter-workflow-import to enable a local chapter command."
    return f"""# Next Chapter Handoff

- Current chapter: `{payload["current_chapter_id"]}`
- Next chapter: `{payload["next_chapter_id"]}`
- Chapter goal: {payload["chapter_goal"]}

## Prior Context

{payload["prior_context"]}

## BotMux Workflow

```bash
{payload["workflow_command_text"]}
```

## Local Runtime

```bash
{local_command}
```
"""


def render_blueprint_markdown(blueprint: Dict[str, Any]) -> str:
    scenes = "\n".join(
        f"## {scene['id']}\n\n- Purpose: {scene['purpose']}\n- Location: {scene['location']}\n- Conflict: {scene['conflict']}\n- Turn: {scene['turn']}\n"
        for scene in blueprint["scenes"]
    )
    return f"""# {blueprint['title']}

Objective: {blueprint['objective']}

{scenes}
"""


def render_import_summary(
    *,
    run_id: str,
    title: str,
    chapter: str,
    status: str,
    director_decision: str,
    archive_decision: str,
    warnings: List[str],
) -> str:
    warning_text = markdown_list(warnings) if warnings else "- None"
    return f"""# Chapter Workflow Import Summary

- Run: {run_id}
- Project: {title}
- Chapter: {chapter}
- Status: {status}
- Director decision: {director_decision}
- Archive decision: {archive_decision}

## Warnings

{warning_text}
"""


def text_from_node(node_output: Dict[str, Any], key: str, *, fallback_key: str) -> str:
    data = object_or_empty(node_output.get("data"))
    return first_text(data.get(key), node_output.get(fallback_key), default="")


def list_or_values(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        if all(isinstance(item, dict) for item in value.values()):
            return list(value.values())
        return [value]
    if value in (None, ""):
        return []
    return [value]


def object_or_empty(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def first_text(*values: Any, default: str) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, dict) and value:
            return json.dumps(value, ensure_ascii=False, sort_keys=True)
        if isinstance(value, list) and value:
            return "; ".join(str(item) for item in value if item not in (None, ""))
    return default


def string_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return [first_text(item, default="").strip() for item in value if first_text(item, default="").strip()]
    if isinstance(value, dict):
        return [first_text(item, default="").strip() for item in value.values() if first_text(item, default="").strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def int_or_default(value: Any, default: int) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        match = re.search(r"\d+", value)
        if match:
            return int(match.group(0))
    return default


def valid_choice(value: Any, choices: set[str], *, default: str) -> str:
    text = first_text(value, default=default)
    return text if text in choices else default


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
