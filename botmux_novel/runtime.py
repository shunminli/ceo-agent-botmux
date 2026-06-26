from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from .agents import (
    ArchiveMemoryAgent,
    BlueprintAgent,
    ConsistencyAgent,
    ContextPackBuilder,
    DirectorAgent,
    DraftWriterAgent,
    EditorAgent,
)
from .schema_validation import validate_required
from .workspace import NovelWorkspace, markdown_list, utc_now


@dataclass(frozen=True)
class NovelRunRequest:
    project_path: Path
    title: str
    inspiration: str
    chapter_number: int = 1
    mode: str = "lean"
    word_target: int = 1200


@dataclass(frozen=True)
class NovelRunResult:
    run_id: str
    status: str
    project_path: Path
    chapter_id: str
    final_path: Path
    trace_path: Path
    sqlite_path: Path
    artifacts: List[Path]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "status": self.status,
            "project_path": str(self.project_path),
            "chapter_id": self.chapter_id,
            "final_path": str(self.final_path),
            "trace_path": str(self.trace_path),
            "sqlite_path": str(self.sqlite_path),
            "artifacts": [str(path) for path in self.artifacts],
        }


class RunTrace:
    def __init__(self, *, run_id: str, request: NovelRunRequest, started_at: str):
        self.payload: Dict[str, Any] = {
            "run_id": run_id,
            "started_at": started_at,
            "ended_at": None,
            "status": "running",
            "request": {
                "project_path": str(request.project_path),
                "title": request.title,
                "inspiration": request.inspiration,
                "chapter_number": request.chapter_number,
                "mode": request.mode,
                "word_target": request.word_target,
            },
            "steps": [],
            "artifacts": [],
        }

    def add_step(self, stage: str, agent: str, status: str, summary: str, data: Dict[str, Any]) -> None:
        self.payload["steps"].append(
            {
                "stage": stage,
                "agent": agent,
                "status": status,
                "summary": summary,
                "output_keys": sorted(data.keys()),
            }
        )

    def add_artifact(self, path: Path, root: Path) -> None:
        self.payload["artifacts"].append(str(path.relative_to(root)))

    def finish(self, *, status: str, ended_at: str) -> Dict[str, Any]:
        self.payload["status"] = status
        self.payload["ended_at"] = ended_at
        return self.payload


class NovelRuntime:
    def __init__(self) -> None:
        self.director = DirectorAgent()
        self.blueprint = BlueprintAgent()
        self.context = ContextPackBuilder()
        self.writer = DraftWriterAgent()
        self.checker = ConsistencyAgent()
        self.editor = EditorAgent()
        self.archive_agent = ArchiveMemoryAgent()

    def run(self, request: NovelRunRequest) -> NovelRunResult:
        self._validate_request(request)
        workspace = NovelWorkspace(request.project_path)
        workspace.ensure_layout()

        started_at = utc_now()
        run_id = f"run-{started_at.replace(':', '').replace('-', '')}-{uuid.uuid4().hex[:8]}"
        trace = RunTrace(run_id=run_id, request=request, started_at=started_at)
        artifacts: List[Path] = []

        plan_output = self.director.plan_project(
            title=request.title,
            inspiration=request.inspiration,
            mode=request.mode,
            chapter_number=request.chapter_number,
            word_target=request.word_target,
        )
        plan = plan_output.data
        validate_required("project-state", plan["project"])
        validate_required("story-bible", plan["story_bible"])
        trace.add_step("Intake", plan_output.name, "pass", plan_output.summary, plan)
        artifacts.extend(self._write_project_assets(workspace, plan, request))

        blueprint_output = self.blueprint.generate(plan)
        blueprint = blueprint_output.data
        validate_required("chapter-blueprint", blueprint)
        trace.add_step("Plan", blueprint_output.name, "pass", blueprint_output.summary, blueprint)
        artifacts.append(workspace.write_json(f"outline/chapter-blueprints/{blueprint['chapter_id']}.json", blueprint))
        artifacts.append(workspace.write_text(f"outline/chapter-blueprints/{blueprint['chapter_id']}.md", self._blueprint_markdown(blueprint)))

        context_output = self.context.build(plan, blueprint)
        context = context_output.data
        trace.add_step("RetrieveContext", context_output.name, "pass", context_output.summary, context)
        artifacts.append(workspace.write_json(f"runs/{run_id}/context-pack.json", context))

        draft_output = self.writer.draft(blueprint, context)
        draft = draft_output.data
        trace.add_step("Generate", draft_output.name, "pass", draft_output.summary, draft)
        artifacts.append(workspace.write_text(f"manuscript/draft/{blueprint['chapter_id']}.md", draft["text"]))

        review_output = self.checker.review(draft["text"], blueprint, context)
        review = review_output.data
        trace.add_step("Review", review_output.name, review["decision"], review_output.summary, review)
        artifacts.append(workspace.write_json(f"runs/{run_id}/review-initial.json", review))
        if review["decision"] == "block":
            return self._finish_blocked(
                workspace=workspace,
                request=request,
                run_id=run_id,
                trace=trace,
                artifacts=artifacts,
                chapter_id=blueprint["chapter_id"],
                started_at=started_at,
            )

        if review["decision"] == "revise":
            revision_output = self.editor.revise(draft["text"], review)
            revision = revision_output.data
            trace.add_step("Revise", revision_output.name, "pass", revision_output.summary, revision)
            revised_text = revision["text"]
            artifacts.append(workspace.write_text(f"manuscript/revised/{blueprint['chapter_id']}.md", revised_text))

            review_output = self.checker.review(revised_text, blueprint, context)
            review = review_output.data
            trace.add_step("Review", review_output.name, review["decision"], review_output.summary, review)
            artifacts.append(workspace.write_json(f"runs/{run_id}/review-final.json", review))
            if review["decision"] != "pass":
                return self._finish_blocked(
                    workspace=workspace,
                    request=request,
                    run_id=run_id,
                    trace=trace,
                    artifacts=artifacts,
                    chapter_id=blueprint["chapter_id"],
                    started_at=started_at,
                )
        else:
            revised_text = draft["text"]
            artifacts.append(workspace.write_text(f"manuscript/revised/{blueprint['chapter_id']}.md", revised_text))

        final_path = workspace.write_text(f"manuscript/final/{blueprint['chapter_id']}.md", revised_text)
        artifacts.append(final_path)
        trace.add_step("Approve", "director", "pass", "质量门禁通过，批准首章定稿。", {"final_path": str(final_path)})

        archive_output = self.archive_agent.archive(final_text=revised_text, plan=plan, blueprint=blueprint, review=review)
        archive = archive_output.data
        for fact in archive["facts"]:
            validate_required("fact-snapshot", fact)
        for character_state in archive["character_state"]:
            validate_required("character-state", character_state)
        trace.add_step("Archive", archive_output.name, archive["archive_decision"], archive_output.summary, archive)
        plan["project"].update(
            {
                "stage": "Archive",
                "latest_run_id": run_id,
                "archived_chapters": [blueprint["chapter_id"]],
            }
        )
        updated_project_path = workspace.write_yaml("project.yaml", plan["project"])
        if updated_project_path not in artifacts:
            artifacts.append(updated_project_path)
        artifacts.extend(self._write_archive_assets(workspace, archive, blueprint["chapter_id"]))

        ended_at = utc_now()
        trace_payload = trace.finish(status="completed", ended_at=ended_at)
        validate_required("run-trace", trace_payload)
        trace_path = workspace.write_json(f"runs/{run_id}/trace.json", trace_payload)
        artifacts.append(trace_path)
        summary_path = workspace.write_text(f"runs/{run_id}/summary.md", self._run_summary(run_id, plan, blueprint, review, archive))
        artifacts.append(summary_path)
        for artifact in artifacts:
            trace.add_artifact(artifact, workspace.root)
        trace_payload = trace.finish(status="completed", ended_at=ended_at)
        validate_required("run-trace", trace_payload)
        trace_path = workspace.write_json(f"runs/{run_id}/trace.json", trace_payload)
        expected_sqlite_path = workspace.path("runs/runs.sqlite")

        sqlite_path = workspace.record_run(
            run_id=run_id,
            project_title=request.title,
            chapter_id=blueprint["chapter_id"],
            mode=request.mode,
            status="completed",
            started_at=started_at,
            ended_at=ended_at,
            trace_path=trace_path,
            artifacts=[*artifacts, expected_sqlite_path],
        )
        artifacts.append(sqlite_path)
        trace.add_artifact(sqlite_path, workspace.root)
        trace_payload = trace.finish(status="completed", ended_at=ended_at)
        validate_required("run-trace", trace_payload)
        trace_path = workspace.write_json(f"runs/{run_id}/trace.json", trace_payload)
        return NovelRunResult(
            run_id=run_id,
            status="completed",
            project_path=workspace.root,
            chapter_id=blueprint["chapter_id"],
            final_path=final_path,
            trace_path=trace_path,
            sqlite_path=sqlite_path,
            artifacts=artifacts,
        )

    def _finish_blocked(
        self,
        *,
        workspace: NovelWorkspace,
        request: NovelRunRequest,
        run_id: str,
        trace: RunTrace,
        artifacts: List[Path],
        chapter_id: str,
        started_at: str,
    ) -> NovelRunResult:
        ended_at = utc_now()
        trace_payload = trace.finish(status="blocked", ended_at=ended_at)
        validate_required("run-trace", trace_payload)
        trace_path = workspace.write_json(f"runs/{run_id}/trace.json", trace_payload)
        artifacts.append(trace_path)
        expected_sqlite_path = workspace.path("runs/runs.sqlite")
        sqlite_path = workspace.record_run(
            run_id=run_id,
            project_title=request.title,
            chapter_id=chapter_id,
            mode=request.mode,
            status="blocked",
            started_at=started_at,
            ended_at=ended_at,
            trace_path=trace_path,
            artifacts=[*artifacts, expected_sqlite_path],
        )
        artifacts.append(sqlite_path)
        return NovelRunResult(
            run_id=run_id,
            status="blocked",
            project_path=workspace.root,
            chapter_id=chapter_id,
            final_path=workspace.path(f"manuscript/final/{chapter_id}.md"),
            trace_path=trace_path,
            sqlite_path=sqlite_path,
            artifacts=artifacts,
        )

    def _write_project_assets(self, workspace: NovelWorkspace, plan: Dict[str, Any], request: NovelRunRequest) -> List[Path]:
        artifacts = [
            workspace.write_yaml("project.yaml", plan["project"]),
            workspace.write_text("story.md", self._story_markdown(plan)),
            workspace.write_yaml("settings/genre.yaml", plan["genre"]),
            workspace.write_yaml("settings/world.yaml", plan["world"]),
            workspace.write_text(
                "settings/style.md",
                "# Style Profile\n\n- 减少解释性总结。\n- 对话保留潜台词。\n- 用动作和场景承载情绪。\n",
            ),
            workspace.write_yaml(
                "settings/constraints.yaml",
                {"mode": request.mode, "hard_constraints": plan["world"]["forbidden"] + plan["chapter_goal"]["forbidden"]},
            ),
            workspace.write_yaml("characters/index.yaml", {"characters": plan["characters"]}),
            workspace.write_text("outline/global-outline.md", self._global_outline(plan)),
            workspace.write_text("outline/volume-001.md", self._volume_outline(plan["volume_outline"])),
            workspace.write_text("memory/session.md", f"# Session Memory\n\n- 初始灵感：{request.inspiration}\n"),
            workspace.write_text("memory/permanent.md", "# Permanent Memory\n\n- 暂无跨项目永久偏好。\n"),
        ]
        for character in plan["characters"]:
            artifacts.append(workspace.write_text(f"characters/{character['id']}.md", self._character_markdown(character)))
        return artifacts

    def _write_archive_assets(self, workspace: NovelWorkspace, archive: Dict[str, Any], chapter: str) -> List[Path]:
        return [
            workspace.write_yaml("tracking/facts.yaml", {"facts": archive["facts"]}),
            workspace.write_yaml("tracking/timeline.yaml", {"timeline": archive["timeline"]}),
            workspace.write_yaml("tracking/foreshadowing.yaml", {"foreshadowing": archive["foreshadowing"]}),
            workspace.write_yaml("tracking/character-state.yaml", {"characters": archive["character_state"]}),
            workspace.write_yaml("tracking/continuity-issues.yaml", {"issues": archive["continuity_issues"]}),
            workspace.write_json(f"runs/archive-{chapter}.json", archive),
        ]

    def _story_markdown(self, plan: Dict[str, Any]) -> str:
        return f"""# {plan['project']['title']}

## Theme

{plan['story_bible']['theme']}

## Inspiration

{plan['story_bible']['inspiration']}

## Core Conflict

{plan['story_bible']['core_conflict']}

## Ending Constraint

{plan['story_bible']['ending_constraint']}
"""

    def _global_outline(self, plan: Dict[str, Any]) -> str:
        return f"""# Global Outline

## Story Direction

{plan['story_bible']['core_conflict']}

## Main Cast

{markdown_list(character['name'] + '：' + character['role'] for character in plan['characters'])}
"""

    def _volume_outline(self, volume: Dict[str, Any]) -> str:
        return f"""# {volume['volume']}

## Goal

{volume['goal']}

## Turning Points

{markdown_list(volume['turning_points'])}
"""

    def _character_markdown(self, character: Dict[str, Any]) -> str:
        return f"""# {character['name']}

- Role: {character['role']}
- Motivation: {character['motivation']}
- Current State: {character['current_state']}
- Secret: {character['secret']}
"""

    def _blueprint_markdown(self, blueprint: Dict[str, Any]) -> str:
        scenes = "\n".join(
            f"## {scene['id']}\n\n- Purpose: {scene['purpose']}\n- Location: {scene['location']}\n- Conflict: {scene['conflict']}\n- Turn: {scene['turn']}\n"
            for scene in blueprint["scenes"]
        )
        return f"""# {blueprint['title']}

Objective: {blueprint['objective']}

{scenes}
"""

    def _run_summary(
        self,
        run_id: str,
        plan: Dict[str, Any],
        blueprint: Dict[str, Any],
        review: Dict[str, Any],
        archive: Dict[str, Any],
    ) -> str:
        return f"""# Run Summary

- Run: {run_id}
- Project: {plan['project']['title']}
- Chapter: {blueprint['chapter_id']} {blueprint['title']}
- Decision: {review['decision']}
- Archive: {archive['archive_decision']}
- Final character count: {archive['final_word_count']}
- Continuity issues: {len(archive['continuity_issues'])}
"""

    def _validate_request(self, request: NovelRunRequest) -> None:
        if not request.title.strip():
            raise ValueError("title is required")
        if not request.inspiration.strip():
            raise ValueError("inspiration is required")
        if request.mode not in {"full", "lean", "solo"}:
            raise ValueError("mode must be one of: full, lean, solo")
        if request.chapter_number < 1:
            raise ValueError("chapter_number must be >= 1")
        if request.word_target < 300:
            raise ValueError("word_target must be >= 300")
