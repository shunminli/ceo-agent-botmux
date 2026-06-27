from __future__ import annotations

import json
import re
import shlex
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
from .chapter_goals import chapter_goal_for
from .foundation_paths import resolve_foundation_path
from .handoff_commands import build_chapter_knowledge_handoff
from .schema_validation import validate_schema
from .workspace import NovelWorkspace, markdown_list, utc_now
from .workflow_commands import build_chapter_workflow_command


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
    chapter_goal: Optional[str] = None
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
        validate_schema("run-trace", trace_payload)
        trace_path = workspace.write_json(f"runs/{run_id}/trace.json", trace_payload)
        artifacts.append(trace_path)
        for artifact in artifacts:
            trace.add_artifact(artifact, workspace.root)
        trace_payload = trace.finish(status="completed", ended_at=ended_at)
        validate_schema("run-trace", trace_payload)
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

    def chapter(self, request: NovelChapterRequest) -> NovelRunResult:
        self._validate_chapter_request(request)
        workspace = NovelWorkspace(request.project_path)
        workspace.ensure_layout()

        source_path = self._resolve_foundation_path(workspace, request.foundation_path)
        plan = json.loads(source_path.read_text(encoding="utf-8"))
        self._validate_plan(plan)

        chapter = make_chapter_id(request.chapter_number)
        resolved_chapter_goal = self._resolve_chapter_goal(plan, request.chapter_goal)
        effective_request = NovelChapterRequest(
            project_path=request.project_path,
            chapter_number=request.chapter_number,
            chapter_goal=resolved_chapter_goal,
            foundation_path=request.foundation_path,
            mode=request.mode,
            word_target=request.word_target,
        )
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
                "objective": resolved_chapter_goal,
            }
        )
        plan["chapter_goal"] = chapter_goal
        prior_context = self._load_prior_context(workspace, before_chapter_id=chapter)
        plan["prior_context"] = prior_context

        started_at = utc_now()
        run_id = f"chapter-{started_at.replace(':', '').replace('-', '')}-{uuid.uuid4().hex[:8]}"
        trace = RunTrace(run_id=run_id, request=effective_request, started_at=started_at)
        artifacts: List[Path] = []
        trace.add_step(
            "LoadFoundation",
            "director",
            "pass",
            "读取已批准的开书设定包，准备章节生产。",
            {"source_path": str(source_path), "chapter_id": chapter, "objective": resolved_chapter_goal},
        )
        trace.add_step(
            "LoadPriorContext",
            "director",
            "pass",
            f"读取 {len(prior_context['source_chapters'])} 个前文章节归档，注入连续性上下文。",
            prior_context,
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
        artifacts.append(workspace.write_json(f"runs/{run_id}/prior-context.json", prior_context))

        return self._execute_chapter_pipeline(
            workspace=workspace,
            request=effective_request,
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
        validate_schema("chapter-blueprint", blueprint)
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
            validate_schema("fact-snapshot", fact)
        for foreshadowing in archive["foreshadowing"]:
            validate_schema("foreshadowing-ledger", foreshadowing)
        for character_state in archive["character_state"]:
            validate_schema("character-state", character_state)
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
        if plan["project"].get("source_foundation"):
            next_handoff = self._next_chapter_handoff(
                workspace=workspace,
                run_id=run_id,
                plan=plan,
                blueprint=blueprint,
                archive=archive,
            )
            trace.add_step("NextChapterHandoff", "director", "pass", "生成下一章启动命令。", next_handoff)
            validate_schema("next-chapter-command", next_handoff)
            artifacts.append(workspace.write_json(f"runs/{run_id}/next-chapter-command.json", next_handoff))
            artifacts.append(workspace.write_text(f"runs/{run_id}/next-chapter-command.md", self._next_chapter_markdown(next_handoff)))

        ended_at = utc_now()
        trace_payload = trace.finish(status="completed", ended_at=ended_at)
        validate_schema("run-trace", trace_payload)
        trace_path = workspace.write_json(f"runs/{run_id}/trace.json", trace_payload)
        artifacts.append(trace_path)
        summary_path = workspace.write_text(f"runs/{run_id}/summary.md", self._run_summary(run_id, plan, blueprint, review, archive))
        artifacts.append(summary_path)
        for artifact in artifacts:
            trace.add_artifact(artifact, workspace.root)
        trace_payload = trace.finish(status="completed", ended_at=ended_at)
        validate_schema("run-trace", trace_payload)
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
        validate_schema("run-trace", trace_payload)
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
        validate_schema("run-trace", trace_payload)
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
        validate_schema("project-state", plan["project"])
        validate_schema("story-bible", plan["story_bible"])
        validate_schema("relationship-map", plan["relationships"])
        validate_schema("style-profile", plan["style_profile"])
        for scene_setting in plan["scene_settings"]:
            validate_schema("scene-setting", scene_setting)

    def _write_archive_assets(self, workspace: NovelWorkspace, archive: Dict[str, Any], chapter: str) -> List[Path]:
        return [
            workspace.write_yaml("tracking/facts.yaml", {"facts": archive["facts"]}),
            workspace.write_yaml("tracking/timeline.yaml", {"timeline": archive["timeline"]}),
            workspace.write_yaml("tracking/foreshadowing.yaml", {"foreshadowing": archive["foreshadowing"]}),
            workspace.write_yaml("tracking/character-state.yaml", {"characters": archive["character_state"]}),
            workspace.write_yaml("tracking/continuity-issues.yaml", {"issues": archive["continuity_issues"]}),
            workspace.write_json(f"runs/archive-{chapter}.json", archive),
        ]

    def _load_prior_context(self, workspace: NovelWorkspace, *, before_chapter_id: str) -> Dict[str, Any]:
        current_sort_key = self._chapter_sort_key(before_chapter_id)
        context: Dict[str, Any] = {
            "source_chapters": [],
            "source_refs": [],
            "facts": [],
            "timeline": [],
            "foreshadowing": [],
            "character_state": [],
            "continuity_issues": [],
        }
        archives: List[tuple[int, str, Path, Dict[str, Any]]] = []
        for path in sorted(workspace.root.glob("runs/archive-*.json")):
            chapter = path.stem.removeprefix("archive-")
            sort_key = self._chapter_sort_key(chapter)
            if sort_key is None:
                continue
            if current_sort_key is not None and sort_key >= current_sort_key:
                continue
            try:
                archive = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid prior archive JSON: {path}") from exc
            archives.append((sort_key, chapter, path, archive))

        for _, chapter, path, archive in sorted(archives, key=lambda item: item[0]):
            context["source_chapters"].append(chapter)
            context["source_refs"].append(str(path.relative_to(workspace.root)))
            for key in ["facts", "timeline", "foreshadowing", "character_state", "continuity_issues"]:
                items = archive.get(key, [])
                if not isinstance(items, list):
                    raise ValueError(f"prior archive {path} field {key} must be an array")
                for item in items:
                    if isinstance(item, dict):
                        normalized = dict(item)
                        normalized.setdefault("chapter_id", chapter)
                        normalized.setdefault("source_archive", str(path.relative_to(workspace.root)))
                        context[key].append(normalized)
                    else:
                        context[key].append(
                            {
                                "chapter_id": chapter,
                                "value": item,
                                "source_archive": str(path.relative_to(workspace.root)),
                            }
                        )
        return context

    def _chapter_sort_key(self, chapter_id: str) -> Optional[int]:
        match = re.fullmatch(r"ch-(\d+)", chapter_id)
        if match is None:
            return None
        return int(match.group(1))

    def _resolve_foundation_path(self, workspace: NovelWorkspace, explicit_path: Optional[Path]) -> Path:
        return resolve_foundation_path(workspace.root, explicit_path)

    def _validate_project_slug(self, project_slug: str) -> str:
        slug = project_slug.strip()
        if not slug:
            raise ValueError("project_slug is required")
        if re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,79}", slug) is None:
            raise ValueError("project_slug must use 1-80 lowercase letters, digits, hyphen, or underscore")
        return slug

    def _write_wiki_bundle(self, workspace: NovelWorkspace, plan: Dict[str, Any], project_slug: str) -> List[Path]:
        base = f"wiki/novels/{project_slug}"
        archives = self._load_archives_for_wiki(workspace)
        self._clear_wiki_archive_pages(workspace, base)
        artifacts = [
            workspace.write_text(f"{base}/overview.md", self._wiki_overview(plan, project_slug)),
            workspace.write_text(f"{base}/story-bible.md", self._story_markdown(plan)),
            workspace.write_text(f"{base}/relationships.md", self._wiki_relationships(plan["relationships"])),
            workspace.write_text(f"{base}/plot-trajectory.md", self._wiki_plot_trajectory(plan)),
            workspace.write_text(f"{base}/world-scenes.md", self._wiki_scene_settings(plan["scene_settings"])),
            workspace.write_text(f"{base}/foreshadowing.md", self._wiki_foreshadowing_seed(plan, archives)),
            workspace.write_text(f"{base}/continuity-rules.md", self._wiki_continuity_rules(plan)),
            workspace.write_text(f"{base}/chapter-index.md", self._wiki_chapter_index(plan, archives)),
            workspace.write_text(f"{base}/sync-plan.md", self._wiki_sync_plan(plan, project_slug, archives)),
        ]
        for character in plan["characters"]:
            artifacts.append(workspace.write_text(f"{base}/characters/{character['id']}.md", self._character_markdown(character)))
        if archives:
            artifacts.append(workspace.write_text(f"{base}/chapter-archive.md", self._wiki_chapter_archive(archives)))
            artifacts.append(workspace.write_text(f"{base}/timeline.md", self._wiki_archive_timeline(archives)))
            artifacts.append(workspace.write_text(f"{base}/character-state.md", self._wiki_archive_character_state(archives)))
            for archive_record in archives:
                chapter = archive_record["chapter_id"]
                artifacts.append(workspace.write_text(f"{base}/chapters/{chapter}.md", self._wiki_chapter_archive_page(archive_record)))
        return artifacts

    def _load_archives_for_wiki(self, workspace: NovelWorkspace) -> List[Dict[str, Any]]:
        records: List[Dict[str, Any]] = []
        for path in workspace.root.glob("runs/archive-*.json"):
            chapter = path.stem.removeprefix("archive-")
            try:
                archive = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid archive JSON for wiki bundle: {path}") from exc
            for key in ["facts", "timeline", "foreshadowing", "character_state", "continuity_issues"]:
                if not isinstance(archive.get(key, []), list):
                    raise ValueError(f"archive {path} field {key} must be an array")
            final_path = workspace.root / "manuscript" / "final" / f"{chapter}.md"
            records.append(
                {
                    "chapter_id": chapter,
                    "sort_key": self._chapter_sort_key(chapter),
                    "source_ref": str(path.relative_to(workspace.root)),
                    "archive": archive,
                    "final_path": final_path if final_path.exists() else None,
                }
            )
        return sorted(
            records,
            key=lambda item: (
                item["sort_key"] is None,
                item["sort_key"] if item["sort_key"] is not None else 0,
                item["chapter_id"],
            ),
        )

    def _clear_wiki_archive_pages(self, workspace: NovelWorkspace, base: str) -> None:
        namespace_path = workspace.root / base
        for name in ["chapter-archive.md", "timeline.md", "character-state.md"]:
            path = namespace_path / name
            if path.exists():
                path.unlink()
        chapters_path = namespace_path / "chapters"
        if chapters_path.is_dir():
            for path in chapters_path.glob("*.md"):
                path.unlink()
            try:
                chapters_path.rmdir()
            except OSError:
                pass

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

    def _wiki_foreshadowing_seed(self, plan: Dict[str, Any], archives: List[Dict[str, Any]]) -> str:
        archived_items: List[str] = []
        for record in archives:
            chapter = record["chapter_id"]
            for item in record["archive"].get("foreshadowing", []):
                archived_items.append(self._wiki_foreshadowing_item(chapter, item))
        archive_section = ""
        if archived_items:
            archive_section = "\n## Archived Ledger\n\n" + "\n".join(archived_items) + "\n"
        return f"""# Foreshadowing

## Seed Rules

{markdown_list(plan['world']['rules'])}

## Initial Hooks

{markdown_list(plan['chapter_goal']['must_include'])}

{archive_section}## Payoff Discipline

- Every new clue must record introduced chapter, planned payoff, current status, and risk level.
- P0/P1 foreshadowing changes require Director approval and Validator review.
"""

    def _wiki_foreshadowing_item(self, chapter: str, item: Any) -> str:
        if not isinstance(item, dict):
            return f"- {chapter}: {self._wiki_inline(item)}"
        clue = item.get("clue") or item.get("item") or item.get("description") or item.get("id") or "clue"
        status = item.get("status", "unknown")
        payoff = item.get("payoff_plan") or item.get("planned_payoff") or item.get("payoff") or "unplanned"
        risk = item.get("risk_level") or item.get("risk") or "unknown"
        introduced = item.get("introduced_chapter") or item.get("introduced_in") or chapter
        return (
            f"- {chapter}: {self._wiki_inline(clue)} "
            f"(status: `{self._wiki_inline(status)}`, introduced: `{self._wiki_inline(introduced)}`, "
            f"payoff: {self._wiki_inline(payoff)}, risk: `{self._wiki_inline(risk)}`)"
        )

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

    def _wiki_chapter_index(self, plan: Dict[str, Any], archives: List[Dict[str, Any]]) -> str:
        rows = ["| Chapter | Objective | Status | Source |", "| --- | --- | --- | --- |"]
        archived_chapters = {record["chapter_id"] for record in archives}
        for record in archives:
            archive = record["archive"]
            objective = archive.get("objective") or archive.get("chapter_goal") or archive.get("summary") or "archived chapter"
            rows.append(
                f"| {record['chapter_id']} | {self._wiki_table_cell(objective)} | archived | `{record['source_ref']}` |"
            )
        planned_chapter = plan["chapter_goal"]["chapter_id"]
        if planned_chapter not in archived_chapters:
            rows.append(
                f"| {planned_chapter} | {self._wiki_table_cell(plan['chapter_goal']['objective'])} | planned | `foundation.json` |"
            )
        return "# Chapter Index\n\n" + "\n".join(rows) + "\n"

    def _wiki_sync_plan(self, plan: Dict[str, Any], project_slug: str, archives: List[Dict[str, Any]]) -> str:
        write_order = [
            "`overview.md`",
            "`story-bible.md`",
            "`characters/*.md`",
            "`relationships.md`",
            "`plot-trajectory.md`",
            "`world-scenes.md`",
            "`foreshadowing.md`",
            "`continuity-rules.md`",
            "`chapter-index.md`",
        ]
        if archives:
            write_order.extend(
                [
                    "`chapter-archive.md`",
                    "`timeline.md`",
                    "`character-state.md`",
                    "`chapters/*.md`",
                ]
            )
        write_order_text = "\n".join(f"{index}. {item}" for index, item in enumerate(write_order, start=1))
        archive_gate = ""
        if archives:
            archive_gate = "\n- Confirm archived chapter facts, timeline, foreshadowing, and character state match the final manuscript.\n"
        return f"""# Wiki Sync Plan

This bundle is a local export for review before llmwiki writes.

## Target Namespace

`/wiki/novels/{project_slug}/`

## Write Order

{write_order_text}

## Human Gate Checklist

- Confirm Story Bible facts are approved.
- Confirm proposed relationships and scene rules are not draft-only ideas.
{archive_gate}- Confirm no copyrighted expression from references is copied into wiki pages.
- Run llmwiki lint after any actual write.
"""

    def _wiki_chapter_archive(self, archives: List[Dict[str, Any]]) -> str:
        rows = [
            "| Chapter | Facts | Timeline | Foreshadowing | Character State | Continuity Issues | Source |",
            "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
        ]
        for record in archives:
            archive = record["archive"]
            rows.append(
                "| "
                f"{record['chapter_id']} | "
                f"{len(archive.get('facts', []))} | "
                f"{len(archive.get('timeline', []))} | "
                f"{len(archive.get('foreshadowing', []))} | "
                f"{len(archive.get('character_state', []))} | "
                f"{len(archive.get('continuity_issues', []))} | "
                f"`{record['source_ref']}` |"
            )
        return "# Chapter Archive\n\n" + "\n".join(rows) + "\n"

    def _wiki_archive_timeline(self, archives: List[Dict[str, Any]]) -> str:
        lines = ["# Timeline\n"]
        for record in archives:
            entries = record["archive"].get("timeline", [])
            lines.append(f"## {record['chapter_id']}\n")
            lines.append(self._wiki_object_list(entries, preferred_keys=["event", "summary", "value"], empty="No timeline entries."))
            lines.append("")
        return "\n".join(lines)

    def _wiki_archive_character_state(self, archives: List[Dict[str, Any]]) -> str:
        lines = ["# Character State\n"]
        for record in archives:
            states = record["archive"].get("character_state", [])
            lines.append(f"## {record['chapter_id']}\n")
            lines.append(self._wiki_object_list(states, preferred_keys=["state", "current_state", "summary", "value"], label_keys=["character_id", "character", "name"], empty="No character states."))
            lines.append("")
        return "\n".join(lines)

    def _wiki_chapter_archive_page(self, record: Dict[str, Any]) -> str:
        archive = record["archive"]
        final_section = "No final manuscript found for this archive."
        final_path = record.get("final_path")
        if isinstance(final_path, Path) and final_path.exists():
            final_section = self._wiki_body_text(final_path.read_text(encoding="utf-8"))
        return f"""# {record['chapter_id']}

- Source archive: `{record['source_ref']}`
- Archive decision: `{self._wiki_inline(archive.get('archive_decision', 'unknown'))}`
- Final word count: {self._wiki_inline(archive.get('final_word_count', 'unknown'))}

## Facts

{self._wiki_object_list(archive.get('facts', []), preferred_keys=['fact', 'summary', 'value'], empty='No facts archived.')}

## Timeline

{self._wiki_object_list(archive.get('timeline', []), preferred_keys=['event', 'summary', 'value'], empty='No timeline entries archived.')}

## Foreshadowing

{self._wiki_object_list(archive.get('foreshadowing', []), preferred_keys=['clue', 'item', 'description', 'id'], empty='No foreshadowing archived.')}

## Character State

{self._wiki_object_list(archive.get('character_state', []), preferred_keys=['state', 'current_state', 'summary', 'value'], label_keys=['character_id', 'character', 'name'], empty='No character states archived.')}

## Continuity Issues

{self._wiki_object_list(archive.get('continuity_issues', []), preferred_keys=['issue', 'summary', 'value'], empty='No continuity issues archived.')}

## Final Manuscript

{final_section}
"""

    def _wiki_object_list(
        self,
        items: Any,
        *,
        preferred_keys: List[str],
        empty: str,
        label_keys: Optional[List[str]] = None,
    ) -> str:
        if not isinstance(items, list) or not items:
            return f"- {empty}"
        lines = []
        for item in items:
            if isinstance(item, dict):
                label = self._first_present(item, label_keys or [])
                value = self._first_present(item, preferred_keys)
                if value is None:
                    value = json.dumps(item, ensure_ascii=False, sort_keys=True)
                detail_parts = []
                for detail_key in [
                    "status",
                    "risk_level",
                    "risk",
                    "source",
                    "source_archive",
                    "introduced_chapter",
                    "introduced_in",
                    "payoff_plan",
                    "planned_payoff",
                ]:
                    if item.get(detail_key) not in (None, ""):
                        detail_parts.append(f"{detail_key}: {self._wiki_inline(item[detail_key])}")
                details = f" ({'; '.join(detail_parts)})" if detail_parts else ""
                prefix = f"{self._wiki_inline(label)}: " if label is not None else ""
                lines.append(f"- {prefix}{self._wiki_inline(value)}{details}")
            else:
                lines.append(f"- {self._wiki_inline(item)}")
        return "\n".join(lines)

    def _first_present(self, item: Dict[str, Any], keys: List[str]) -> Optional[Any]:
        for key in keys:
            value = item.get(key)
            if value not in (None, ""):
                return value
        return None

    def _wiki_body_text(self, value: Any) -> str:
        text = str(value).strip()
        if not text:
            return "No final manuscript found for this archive."
        return text.replace("[", "&#91;").replace("]", "&#93;")

    def _wiki_inline(self, value: Any) -> str:
        if isinstance(value, (dict, list)):
            text = json.dumps(value, ensure_ascii=False, sort_keys=True)
        else:
            text = str(value)
        return text.replace("\n", " ").replace("|", "\\|").replace("[", "&#91;").replace("]", "&#93;")

    def _wiki_table_cell(self, value: Any) -> str:
        return self._wiki_inline(value)

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

    def _next_chapter_handoff(
        self,
        *,
        workspace: NovelWorkspace,
        run_id: str,
        plan: Dict[str, Any],
        blueprint: Dict[str, Any],
        archive: Dict[str, Any],
    ) -> Dict[str, Any]:
        current_number = int(str(blueprint["chapter_id"]).split("-")[-1])
        next_number = current_number + 1
        next_goal = chapter_goal_for(next_number)
        command = [
            "python3",
            "-m",
            "botmux_novel",
            "chapter",
            "--project",
            str(workspace.root),
            "--chapter-number",
            str(next_number),
            "--chapter-goal",
            next_goal,
        ]
        source_foundation = plan["project"].get("source_foundation")
        if source_foundation:
            command.extend(["--foundation-json", str(source_foundation)])
        project_slug = self._resolve_project_slug_for_handoff(workspace, plan)
        prior_context = self._workflow_prior_context(blueprint["chapter_id"], archive)
        workflow_command = build_chapter_workflow_command(
            project_slug=project_slug,
            title=plan["project"]["title"],
            foundation_payload=plan,
            default_chapter_number=current_number,
            chapter_number=next_number,
            chapter_goal=next_goal,
            prior_context=prior_context,
            word_target=int(plan["project"].get("word_target", 1200)),
            mode=str(plan["project"].get("mode", "lean")),
        )
        knowledge_handoff = build_chapter_knowledge_handoff(
            project_path=workspace.root,
            project_slug=project_slug,
            foundation_path=source_foundation,
        )

        return {
            "status": "suggested",
            "project_path": str(workspace.root),
            "project_slug": project_slug,
            "current_chapter_id": blueprint["chapter_id"],
            "next_chapter_id": make_chapter_id(next_number),
            "next_chapter_number": next_number,
            "chapter_goal": next_goal,
            "command": command,
            "command_text": shlex.join(command),
            "workflow_command": workflow_command,
            "workflow_command_text": shlex.join(workflow_command),
            "knowledge_handoff": knowledge_handoff,
            "prior_context": prior_context,
            "source_foundation": source_foundation,
            "source_refs": [
                f"runs/{run_id}/summary.md",
                f"runs/archive-{blueprint['chapter_id']}.json",
            ],
            "handoff": (
                f"下一章 {make_chapter_id(next_number)} 建议目标：{next_goal} "
                f"请先审阅 runs/archive-{blueprint['chapter_id']}.json 的事实、伏笔和人物状态；"
                "如目标不符合人类主创意图，先修改 --chapter-goal 再运行。"
            ),
            "archive_snapshot": {
                "fact_count": len(archive.get("facts", [])),
                "foreshadowing_count": len(archive.get("foreshadowing", [])),
                "character_state_count": len(archive.get("character_state", [])),
            },
        }

    def _next_chapter_markdown(self, handoff: Dict[str, Any]) -> str:
        return f"""# Next Chapter Command

- Current chapter: `{handoff["current_chapter_id"]}`
- Next chapter: `{handoff["next_chapter_id"]}`
- Suggested goal: {handoff["chapter_goal"]}
- Project slug: `{handoff["project_slug"]}`
- Source foundation: `{handoff.get("source_foundation")}`

## Local Runtime

```bash
{handoff["command_text"]}
```

## BotMux Workflow

```bash
{handoff["workflow_command_text"]}
```

## Knowledge Update

Regenerate the reviewable wiki bundle:

```bash
{handoff["knowledge_handoff"]["wiki_bundle_command_text"]}
```

Create a dry-run llmwiki sync plan:

```bash
{handoff["knowledge_handoff"]["llmwiki_sync_plan_command_text"]}
```

After humanGate approval only:

```bash
{handoff["knowledge_handoff"]["approved_llmwiki_sync_command_text"]}
```

## Prior Context

{handoff["prior_context"]}

## Handoff

{handoff["handoff"]}
"""

    def _resolve_project_slug_for_handoff(self, workspace: NovelWorkspace, plan: Dict[str, Any]) -> str:
        project_slug = plan.get("project", {}).get("project_slug")
        if isinstance(project_slug, str) and project_slug.strip():
            return project_slug.strip()
        wiki_root = workspace.root / "wiki" / "novels"
        if wiki_root.is_dir():
            candidates = sorted(path.name for path in wiki_root.iterdir() if path.is_dir())
            if len(candidates) == 1:
                return candidates[0]
        return "project-slug"

    def _workflow_prior_context(self, current_chapter: str, archive: Dict[str, Any]) -> str:
        sections = [
            f"Source chapter: {current_chapter}",
            self._workflow_archive_items("Facts", archive.get("facts", []), ["fact", "summary", "value"]),
            self._workflow_archive_items("Timeline", archive.get("timeline", []), ["event", "summary", "value"]),
            self._workflow_archive_items("Foreshadowing", archive.get("foreshadowing", []), ["item", "clue", "description", "id"]),
            self._workflow_archive_items(
                "Character state",
                archive.get("character_state", []),
                ["state", "current_state", "summary", "value"],
                label_keys=["name", "id", "character_id"],
            ),
            self._workflow_archive_items("Continuity issues", archive.get("continuity_issues", []), ["issue", "summary", "value"]),
        ]
        return "\n".join(section for section in sections if section.strip())

    def _workflow_archive_items(
        self,
        title: str,
        items: Any,
        preferred_keys: List[str],
        *,
        label_keys: Optional[List[str]] = None,
    ) -> str:
        if not isinstance(items, list) or not items:
            return f"{title}: none"
        lines = [f"{title}:"]
        for item in items:
            if isinstance(item, dict):
                value = self._first_present_text(item, preferred_keys)
                if not value:
                    value = json.dumps(item, ensure_ascii=False, sort_keys=True)
                label = self._first_present_text(item, label_keys or [])
                detail_parts = []
                for key in ["status", "risk", "risk_level", "planned_payoff", "payoff_plan"]:
                    if item.get(key) not in (None, ""):
                        detail_parts.append(f"{key}={item.get(key)}")
                detail = f" ({'; '.join(detail_parts)})" if detail_parts else ""
                prefix = f"{label}: " if label else ""
                lines.append(f"- {prefix}{value}{detail}")
            else:
                lines.append(f"- {item}")
        return "\n".join(lines)

    def _first_present_text(self, item: Dict[str, Any], keys: List[str]) -> str:
        for key in keys:
            value = item.get(key)
            if value not in (None, ""):
                return str(value)
        return ""

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
        if request.mode is not None and request.mode not in {"full", "lean", "solo"}:
            raise ValueError("mode must be one of: full, lean, solo")
        if request.word_target is not None and request.word_target < 300:
            raise ValueError("word_target must be >= 300")

    def _resolve_chapter_goal(self, plan: Dict[str, Any], requested_goal: Optional[str]) -> str:
        if requested_goal is not None and requested_goal.strip():
            return requested_goal.strip()
        foundation_goal = plan.get("chapter_goal", {}).get("objective")
        if isinstance(foundation_goal, str) and foundation_goal.strip():
            return foundation_goal.strip()
        raise ValueError("chapter_goal is required when foundation has no chapter_goal.objective")
