from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from .agents import (
    ArchiveMemoryAgent,
    BlueprintAgent,
    ConsistencyAgent,
    ContextPackBuilder,
    DirectorAgent,
    DraftWriterAgent,
    EditorAgent,
    chapter_id as make_chapter_id,
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
class NovelFoundationRequest:
    project_path: Path
    title: str
    inspiration: str
    chapter_number: int = 1
    mode: str = "lean"
    word_target: int = 1200


@dataclass(frozen=True)
class NovelChapterRequest:
    project_path: Path
    chapter_number: int
    chapter_goal: str
    foundation_path: Optional[Path] = None
    mode: Optional[str] = None
    word_target: Optional[int] = None


@dataclass(frozen=True)
class NovelWikiBundleRequest:
    project_path: Path
    project_slug: str
    foundation_path: Optional[Path] = None


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


@dataclass(frozen=True)
class NovelFoundationResult:
    run_id: str
    status: str
    project_path: Path
    chapter_id: str
    story_path: Path
    foundation_path: Path
    trace_path: Path
    sqlite_path: Path
    artifacts: List[Path]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "status": self.status,
            "project_path": str(self.project_path),
            "chapter_id": self.chapter_id,
            "story_path": str(self.story_path),
            "foundation_path": str(self.foundation_path),
            "trace_path": str(self.trace_path),
            "sqlite_path": str(self.sqlite_path),
            "artifacts": [str(path) for path in self.artifacts],
        }


@dataclass(frozen=True)
class NovelWikiBundleResult:
    status: str
    project_path: Path
    project_slug: str
    source_path: Path
    bundle_path: Path
    artifacts: List[Path]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "project_path": str(self.project_path),
            "project_slug": self.project_slug,
            "source_path": str(self.source_path),
            "bundle_path": str(self.bundle_path),
            "artifacts": [str(path) for path in self.artifacts],
        }


class RunTrace:
    def __init__(self, *, run_id: str, request: Any, started_at: str):
        request_payload: Dict[str, Any] = {"project_path": str(request.project_path)}
        for attribute in [
            "title",
            "inspiration",
            "chapter_number",
            "chapter_goal",
            "mode",
            "word_target",
            "foundation_path",
        ]:
            value = getattr(request, attribute, None)
            if value is not None:
                request_payload[attribute] = str(value) if isinstance(value, Path) else value
        self.payload: Dict[str, Any] = {
            "run_id": run_id,
            "started_at": started_at,
            "ended_at": None,
            "status": "running",
            "request": request_payload,
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

    def wiki_bundle(self, request: NovelWikiBundleRequest) -> NovelWikiBundleResult:
        project_slug = self._validate_project_slug(request.project_slug)
        workspace = NovelWorkspace(request.project_path)
        source_path = self._resolve_foundation_path(workspace, request.foundation_path)
        plan = json.loads(source_path.read_text(encoding="utf-8"))
        self._validate_plan(plan)
        artifacts = self._write_wiki_bundle(workspace, plan, project_slug)
        return NovelWikiBundleResult(
            status="completed",
            project_path=workspace.root,
            project_slug=project_slug,
            source_path=source_path,
            bundle_path=workspace.path(f"wiki/novels/{project_slug}"),
            artifacts=artifacts,
        )

    def foundation(self, request: NovelFoundationRequest) -> NovelFoundationResult:
        self._validate_request(request)
        workspace = NovelWorkspace(request.project_path)
        workspace.ensure_layout()

        started_at = utc_now()
        run_id = f"foundation-{started_at.replace(':', '').replace('-', '')}-{uuid.uuid4().hex[:8]}"
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
        self._validate_plan(plan)
        trace.add_step("Foundation", plan_output.name, "pass", plan_output.summary, plan)
        artifacts.extend(self._write_project_assets(workspace, plan, request))

        foundation_path = workspace.write_json(f"runs/{run_id}/foundation.json", plan)
        artifacts.append(foundation_path)
        story_path = workspace.path("story.md")

        ended_at = utc_now()
        trace_payload = trace.finish(status="completed", ended_at=ended_at)
        validate_required("run-trace", trace_payload)
        trace_path = workspace.write_json(f"runs/{run_id}/trace.json", trace_payload)
        artifacts.append(trace_path)
        for artifact in artifacts:
            trace.add_artifact(artifact, workspace.root)
        trace_payload = trace.finish(status="completed", ended_at=ended_at)
        validate_required("run-trace", trace_payload)
        trace_path = workspace.write_json(f"runs/{run_id}/trace.json", trace_payload)
        expected_sqlite_path = workspace.path("runs/runs.sqlite")
        sqlite_path = workspace.record_run(
            run_id=run_id,
            project_title=request.title,
            chapter_id=plan["chapter_goal"]["chapter_id"],
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

    def chapter(self, request: NovelChapterRequest) -> NovelRunResult:
        self._validate_chapter_request(request)
        workspace = NovelWorkspace(request.project_path)
        workspace.ensure_layout()

        source_path = self._resolve_foundation_path(workspace, request.foundation_path)
        plan = json.loads(source_path.read_text(encoding="utf-8"))
        self._validate_plan(plan)

        chapter = make_chapter_id(request.chapter_number)
        mode = request.mode or plan["project"].get("mode", "lean")
        word_target = request.word_target or int(plan["project"].get("word_target", 1200))
        plan["project"].update(
            {
                "stage": "ChapterProduction",
                "mode": mode,
                "current_chapter": chapter,
                "word_target": word_target,
                "source_foundation": str(source_path),
            }
        )
        chapter_goal = dict(plan["chapter_goal"])
        chapter_goal.update(
            {
                "chapter_id": chapter,
                "objective": request.chapter_goal.strip(),
            }
        )
        plan["chapter_goal"] = chapter_goal

        started_at = utc_now()
        run_id = f"chapter-{started_at.replace(':', '').replace('-', '')}-{uuid.uuid4().hex[:8]}"
        trace = RunTrace(run_id=run_id, request=request, started_at=started_at)
        artifacts: List[Path] = []
        trace.add_step(
            "LoadFoundation",
            "director",
            "pass",
            "读取已批准的开书设定包，准备章节生产。",
            {"source_path": str(source_path), "chapter_id": chapter, "objective": request.chapter_goal.strip()},
        )

        asset_request = NovelFoundationRequest(
            project_path=request.project_path,
            title=plan["project"]["title"],
            inspiration=plan["story_bible"]["inspiration"],
            chapter_number=request.chapter_number,
            mode=mode,
            word_target=word_target,
        )
        artifacts.extend(self._write_project_assets(workspace, plan, asset_request))
        artifacts.append(workspace.write_json(f"runs/{run_id}/source-foundation.json", plan))

        return self._execute_chapter_pipeline(
            workspace=workspace,
            request=request,
            run_id=run_id,
            trace=trace,
            artifacts=artifacts,
            plan=plan,
            started_at=started_at,
        )

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
        self._validate_plan(plan)
        trace.add_step("Intake", plan_output.name, "pass", plan_output.summary, plan)
        artifacts.extend(self._write_project_assets(workspace, plan, request))

        return self._execute_chapter_pipeline(
            workspace=workspace,
            request=request,
            run_id=run_id,
            trace=trace,
            artifacts=artifacts,
            plan=plan,
            started_at=started_at,
        )

    def _execute_chapter_pipeline(
        self,
        *,
        workspace: NovelWorkspace,
        request: Any,
        run_id: str,
        trace: RunTrace,
        artifacts: List[Path],
        plan: Dict[str, Any],
        started_at: str,
    ) -> NovelRunResult:
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
        blocked_request = NovelRunRequest(
            project_path=request.project_path,
            title=plan["project"]["title"],
            inspiration=plan["story_bible"]["inspiration"],
            chapter_number=int(blueprint["chapter_id"].split("-")[-1]),
            mode=plan["project"]["mode"],
            word_target=int(plan["project"]["word_target"]),
        )
        if review["decision"] == "block":
            return self._finish_blocked(
                workspace=workspace,
                request=blocked_request,
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
                    request=blocked_request,
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
        trace.add_step("Approve", "director", "pass", "质量门禁通过，批准章节定稿。", {"final_path": str(final_path)})

        archive_output = self.archive_agent.archive(final_text=revised_text, plan=plan, blueprint=blueprint, review=review)
        archive = archive_output.data
        for fact in archive["facts"]:
            validate_required("fact-snapshot", fact)
        for foreshadowing in archive["foreshadowing"]:
            validate_required("foreshadowing-ledger", foreshadowing)
        for character_state in archive["character_state"]:
            validate_required("character-state", character_state)
        trace.add_step("Archive", archive_output.name, archive["archive_decision"], archive_output.summary, archive)
        archived_chapters = list(plan["project"].get("archived_chapters", []))
        if blueprint["chapter_id"] not in archived_chapters:
            archived_chapters.append(blueprint["chapter_id"])
        plan["project"].update(
            {
                "stage": "Archive",
                "latest_run_id": run_id,
                "archived_chapters": archived_chapters,
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
            project_title=plan["project"]["title"],
            chapter_id=blueprint["chapter_id"],
            mode=plan["project"]["mode"],
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

    def _write_project_assets(self, workspace: NovelWorkspace, plan: Dict[str, Any], request: Any) -> List[Path]:
        artifacts = [
            workspace.write_yaml("project.yaml", plan["project"]),
            workspace.write_text("story.md", self._story_markdown(plan)),
            workspace.write_yaml("settings/genre.yaml", plan["genre"]),
            workspace.write_yaml("settings/world.yaml", plan["world"]),
            workspace.write_json("settings/scenes.json", {"scene_settings": plan["scene_settings"]}),
            workspace.write_json("settings/style-profile.json", plan["style_profile"]),
            workspace.write_text(
                "settings/style.md",
                "# Style Profile\n\n- 减少解释性总结。\n- 对话保留潜台词。\n- 用动作和场景承载情绪。\n",
            ),
            workspace.write_yaml(
                "settings/constraints.yaml",
                {"mode": request.mode, "hard_constraints": plan["world"]["forbidden"] + plan["chapter_goal"]["forbidden"]},
            ),
            workspace.write_yaml("characters/index.yaml", {"characters": plan["characters"]}),
            workspace.write_json("characters/relationships.json", plan["relationships"]),
            workspace.write_text("outline/global-outline.md", self._global_outline(plan)),
            workspace.write_text("outline/volume-001.md", self._volume_outline(plan["volume_outline"])),
            workspace.write_text("memory/session.md", f"# Session Memory\n\n- 初始灵感：{request.inspiration}\n"),
            workspace.write_text("memory/permanent.md", "# Permanent Memory\n\n- 暂无跨项目永久偏好。\n"),
        ]
        for character in plan["characters"]:
            artifacts.append(workspace.write_text(f"characters/{character['id']}.md", self._character_markdown(character)))
        return artifacts

    def _validate_plan(self, plan: Dict[str, Any]) -> None:
        validate_required("project-state", plan["project"])
        validate_required("story-bible", plan["story_bible"])
        validate_required("relationship-map", plan["relationships"])
        validate_required("style-profile", plan["style_profile"])
        for scene_setting in plan["scene_settings"]:
            validate_required("scene-setting", scene_setting)

    def _write_archive_assets(self, workspace: NovelWorkspace, archive: Dict[str, Any], chapter: str) -> List[Path]:
        return [
            workspace.write_yaml("tracking/facts.yaml", {"facts": archive["facts"]}),
            workspace.write_yaml("tracking/timeline.yaml", {"timeline": archive["timeline"]}),
            workspace.write_yaml("tracking/foreshadowing.yaml", {"foreshadowing": archive["foreshadowing"]}),
            workspace.write_yaml("tracking/character-state.yaml", {"characters": archive["character_state"]}),
            workspace.write_yaml("tracking/continuity-issues.yaml", {"issues": archive["continuity_issues"]}),
            workspace.write_json(f"runs/archive-{chapter}.json", archive),
        ]

    def _resolve_foundation_path(self, workspace: NovelWorkspace, explicit_path: Optional[Path]) -> Path:
        if explicit_path is not None:
            path = explicit_path.expanduser().resolve()
            if not path.exists():
                raise ValueError(f"foundation file does not exist: {path}")
            return path
        candidates = sorted(workspace.root.glob("runs/foundation-*/foundation.json"), key=lambda path: path.stat().st_mtime)
        if not candidates:
            raise ValueError("no foundation.json found; run `python -m botmux_novel foundation` first or pass --foundation-json")
        return candidates[-1]

    def _validate_project_slug(self, project_slug: str) -> str:
        slug = project_slug.strip()
        if not slug:
            raise ValueError("project_slug is required")
        if re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,79}", slug) is None:
            raise ValueError("project_slug must use 1-80 lowercase letters, digits, hyphen, or underscore")
        return slug

    def _write_wiki_bundle(self, workspace: NovelWorkspace, plan: Dict[str, Any], project_slug: str) -> List[Path]:
        base = f"wiki/novels/{project_slug}"
        artifacts = [
            workspace.write_text(f"{base}/overview.md", self._wiki_overview(plan, project_slug)),
            workspace.write_text(f"{base}/story-bible.md", self._story_markdown(plan)),
            workspace.write_text(f"{base}/relationships.md", self._wiki_relationships(plan["relationships"])),
            workspace.write_text(f"{base}/plot-trajectory.md", self._wiki_plot_trajectory(plan)),
            workspace.write_text(f"{base}/world-scenes.md", self._wiki_scene_settings(plan["scene_settings"])),
            workspace.write_text(f"{base}/foreshadowing.md", self._wiki_foreshadowing_seed(plan)),
            workspace.write_text(f"{base}/continuity-rules.md", self._wiki_continuity_rules(plan)),
            workspace.write_text(f"{base}/chapter-index.md", self._wiki_chapter_index(plan)),
            workspace.write_text(f"{base}/sync-plan.md", self._wiki_sync_plan(plan, project_slug)),
        ]
        for character in plan["characters"]:
            artifacts.append(workspace.write_text(f"{base}/characters/{character['id']}.md", self._character_markdown(character)))
        return artifacts

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

    def _wiki_overview(self, plan: Dict[str, Any], project_slug: str) -> str:
        return f"""# {plan['project']['title']}

- Project slug: `{project_slug}`
- Mode: `{plan['project']['mode']}`
- Current chapter: `{plan['project']['current_chapter']}`
- Word target: {plan['project']['word_target']}

## Story Promise

{plan['story_bible']['core_conflict']}

## Reader Expectations

{markdown_list(plan['genre']['reader_expectations'])}

## Selling Points

{markdown_list(plan['genre']['selling_points'])}
"""

    def _wiki_relationships(self, relationships: Dict[str, Any]) -> str:
        lines = [f"# Relationships\n\nProject: {relationships['project_title']}\n"]
        for edge in relationships["edges"]:
            lines.append(
                f"## {edge['source']} -> {edge['target']}\n\n"
                f"- Type: {edge['type']}\n"
                f"- Pressure: {edge['pressure']}\n"
                f"- Secret: {edge.get('secret', '无')}\n"
            )
        return "\n".join(lines)

    def _wiki_plot_trajectory(self, plan: Dict[str, Any]) -> str:
        return f"""# Plot Trajectory

## Volume

{plan['volume_outline']['volume']}

## Goal

{plan['volume_outline']['goal']}

## Turning Points

{markdown_list(plan['volume_outline']['turning_points'])}

## Initial Chapter Goal

- Chapter: {plan['chapter_goal']['chapter_id']}
- Objective: {plan['chapter_goal']['objective']}
- Must include: {', '.join(plan['chapter_goal']['must_include'])}
- Forbidden: {', '.join(plan['chapter_goal']['forbidden'])}
"""

    def _wiki_scene_settings(self, scene_settings: List[Dict[str, Any]]) -> str:
        lines = ["# World Scenes\n"]
        for scene in scene_settings:
            lines.append(
                f"## {scene['name']}\n\n"
                f"- ID: `{scene['id']}`\n"
                f"- Kind: {scene['kind']}\n"
                f"- Function: {scene['function']}\n"
                f"- Conflict Pressure: {scene['conflict_pressure']}\n"
                f"- Reuse Value: {scene['reuse_value']}\n"
                f"- Rules:\n{markdown_list(scene['rules'])}\n"
            )
        return "\n".join(lines)

    def _wiki_foreshadowing_seed(self, plan: Dict[str, Any]) -> str:
        return f"""# Foreshadowing

## Seed Rules

{markdown_list(plan['world']['rules'])}

## Initial Hooks

{markdown_list(plan['chapter_goal']['must_include'])}

## Payoff Discipline

- Every new clue must record introduced chapter, planned payoff, current status, and risk level.
- P0/P1 foreshadowing changes require Director approval and Validator review.
"""

    def _wiki_continuity_rules(self, plan: Dict[str, Any]) -> str:
        thresholds = "\n".join(f"- {key}: {value}" for key, value in plan["project"]["quality_thresholds"].items())
        return f"""# Continuity Rules

## World Rules

{markdown_list(plan['world']['rules'])}

## Forbidden

{markdown_list(plan['world']['forbidden'] + plan['chapter_goal']['forbidden'])}

## Quality Thresholds

{thresholds}
"""

    def _wiki_chapter_index(self, plan: Dict[str, Any]) -> str:
        return f"""# Chapter Index

| Chapter | Objective | Status |
| --- | --- | --- |
| {plan['chapter_goal']['chapter_id']} | {plan['chapter_goal']['objective']} | planned |
"""

    def _wiki_sync_plan(self, plan: Dict[str, Any], project_slug: str) -> str:
        return f"""# Wiki Sync Plan

This bundle is a local export for review before llmwiki writes.

## Target Namespace

`/wiki/novels/{project_slug}/`

## Write Order

1. `overview.md`
2. `story-bible.md`
3. `characters/*.md`
4. `relationships.md`
5. `plot-trajectory.md`
6. `world-scenes.md`
7. `foreshadowing.md`
8. `continuity-rules.md`
9. `chapter-index.md`

## Human Gate Checklist

- Confirm Story Bible facts are approved.
- Confirm proposed relationships and scene rules are not draft-only ideas.
- Confirm no copyrighted expression from references is copied into wiki pages.
- Run llmwiki lint after any actual write.
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

    def _validate_chapter_request(self, request: NovelChapterRequest) -> None:
        if request.chapter_number < 1:
            raise ValueError("chapter_number must be >= 1")
        if not request.chapter_goal.strip():
            raise ValueError("chapter_goal is required")
        if request.mode is not None and request.mode not in {"full", "lean", "solo"}:
            raise ValueError("mode must be one of: full, lean, solo")
        if request.word_target is not None and request.word_target < 300:
            raise ValueError("word_target must be >= 300")
