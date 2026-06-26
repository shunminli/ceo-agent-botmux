from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from .llmwiki_sync import LlmwikiSyncRequest, LlmwikiSyncResult, LlmwikiSyncer
from .runtime import (
    NovelChapterRequest,
    NovelFoundationRequest,
    NovelFoundationResult,
    NovelRunResult,
    NovelRuntime,
    NovelWikiBundleRequest,
    NovelWikiBundleResult,
)
from .workspace import NovelWorkspace, utc_now


@dataclass(frozen=True)
class NovelSeriesRequest:
    project_path: Path
    title: str
    inspiration: str
    project_slug: str
    chapter_count: int = 5
    mode: str = "lean"
    word_target: int = 1200
    llmwiki_sync: bool = False
    approve_llmwiki: bool = False
    llmwiki_workspace_path: Optional[Path] = None
    llmwiki_bin: str = "llmwiki"
    reindex: bool = False


@dataclass(frozen=True)
class NovelSeriesResult:
    run_id: str
    status: str
    project_path: Path
    foundation: NovelFoundationResult
    chapters: List[NovelRunResult]
    wiki_bundle: NovelWikiBundleResult
    llmwiki_sync: Optional[LlmwikiSyncResult]
    metrics_path: Path
    metrics: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "run_id": self.run_id,
            "status": self.status,
            "project_path": str(self.project_path),
            "foundation": self.foundation.to_dict(),
            "chapters": [chapter.to_dict() for chapter in self.chapters],
            "wiki_bundle": self.wiki_bundle.to_dict(),
            "llmwiki_sync": self.llmwiki_sync.to_dict() if self.llmwiki_sync is not None else None,
            "metrics_path": str(self.metrics_path),
            "metrics": self.metrics,
        }
        return payload


class NovelSeriesRunner:
    def __init__(self, runtime: Optional[NovelRuntime] = None) -> None:
        self.runtime = runtime or NovelRuntime()

    def run(self, request: NovelSeriesRequest) -> NovelSeriesResult:
        self._validate_request(request)
        project_path = request.project_path.expanduser().resolve()
        run_id = f"series-{utc_now().replace(':', '').replace('-', '')}-{uuid.uuid4().hex[:8]}"

        foundation = self.runtime.foundation(
            NovelFoundationRequest(
                project_path=project_path,
                title=request.title,
                inspiration=request.inspiration,
                chapter_number=1,
                mode=request.mode,
                word_target=request.word_target,
            )
        )

        chapters: List[NovelRunResult] = []
        for chapter_number in range(1, request.chapter_count + 1):
            chapters.append(
                self.runtime.chapter(
                    NovelChapterRequest(
                        project_path=project_path,
                        chapter_number=chapter_number,
                        chapter_goal=chapter_goal_for(chapter_number),
                        foundation_path=foundation.foundation_path,
                        mode=request.mode,
                        word_target=request.word_target,
                    )
                )
            )

        wiki_bundle = self.runtime.wiki_bundle(
            NovelWikiBundleRequest(
                project_path=project_path,
                project_slug=request.project_slug,
                foundation_path=foundation.foundation_path,
            )
        )

        llmwiki_result: Optional[LlmwikiSyncResult] = None
        if request.llmwiki_sync or request.approve_llmwiki:
            llmwiki_result = LlmwikiSyncer().sync(
                LlmwikiSyncRequest(
                    project_path=project_path,
                    project_slug=request.project_slug,
                    workspace_path=request.llmwiki_workspace_path,
                    approve=request.approve_llmwiki,
                    llmwiki_bin=request.llmwiki_bin,
                    reindex=request.reindex,
                )
            )

        metrics = collect_series_metrics(project_path=project_path, chapters=chapters)
        metrics.update(
            {
                "series_run_id": run_id,
                "project_slug": request.project_slug,
                "llmwiki_sync_status": llmwiki_result.status if llmwiki_result is not None else "not_requested",
            }
        )
        workspace = NovelWorkspace(project_path)
        metrics_path = workspace.write_json(f"runs/{run_id}/series-metrics.json", metrics)
        status = "completed" if all(chapter.status == "completed" for chapter in chapters) else "blocked"
        if llmwiki_result is not None and llmwiki_result.status == "failed":
            status = "failed"
        return NovelSeriesResult(
            run_id=run_id,
            status=status,
            project_path=project_path,
            foundation=foundation,
            chapters=chapters,
            wiki_bundle=wiki_bundle,
            llmwiki_sync=llmwiki_result,
            metrics_path=metrics_path,
            metrics=metrics,
        )

    def _validate_request(self, request: NovelSeriesRequest) -> None:
        if request.chapter_count < 1:
            raise ValueError("chapter_count must be >= 1")
        if request.chapter_count > 50:
            raise ValueError("chapter_count must be <= 50")
        if request.mode not in {"full", "lean", "solo"}:
            raise ValueError("mode must be one of: full, lean, solo")
        if request.word_target < 300:
            raise ValueError("word_target must be >= 300")


def chapter_goal_for(chapter_number: int) -> str:
    goals = {
        1: "用旧书楼残页引出主角秘密能力并埋下巡夜钟伏笔。",
        2: "让林烬用半张残页验证巡夜钟异常，并把妹妹影子证词转成下一章追查目标。",
        3: "让林烬追查巡夜钟提前响起的原因，发现夜巡记录被人为改写。",
        4: "让玄衣巡使从压迫者变成可疑盟友，暴露真正执棋者的外层线索。",
        5: "让林烬公开利用影子证词反击一次清查，并留下第一卷中段反转钩子。",
    }
    return goals.get(
        chapter_number,
        f"推进第 {chapter_number} 章主线，回收前文章节事实并新增可追踪伏笔。",
    )


def collect_series_metrics(*, project_path: Path, chapters: List[NovelRunResult]) -> Dict[str, Any]:
    p0_p1_issue_count = 0
    issue_counts: Dict[str, int] = {"P0": 0, "P1": 0, "P2": 0, "P3": 0}
    review_decisions: Dict[str, int] = {}
    revision_rounds = 0
    archive_complete_count = 0
    prior_context_ready_count = 0
    blocked_chapters: List[str] = []

    for chapter in chapters:
        run_dir = project_path / "runs" / chapter.run_id
        trace = read_json(chapter.trace_path)
        revision_rounds += sum(1 for step in trace.get("steps", []) if step.get("stage") == "Revise")
        if chapter.status != "completed":
            blocked_chapters.append(chapter.chapter_id)

        for review_path in sorted(run_dir.glob("review-*.json")):
            review = read_json(review_path)
            decision = review.get("decision", "unknown")
            review_decisions[decision] = review_decisions.get(decision, 0) + 1
            for issue in review.get("issues", []):
                severity = issue.get("severity", "unknown")
                issue_counts[severity] = issue_counts.get(severity, 0) + 1
                if severity in {"P0", "P1"}:
                    p0_p1_issue_count += 1

        archive = read_optional_json(project_path / f"runs/archive-{chapter.chapter_id}.json")
        if archive_is_complete(archive):
            archive_complete_count += 1

        prior_context = read_optional_json(run_dir / "prior-context.json")
        if chapter.chapter_id == "ch-001" or prior_context.get("source_chapters"):
            prior_context_ready_count += 1

    chapter_count = len(chapters)
    archive_completion_rate = archive_complete_count / chapter_count if chapter_count else 0
    prior_context_rate = prior_context_ready_count / chapter_count if chapter_count else 0
    return {
        "chapter_count": chapter_count,
        "completed_chapter_count": sum(1 for chapter in chapters if chapter.status == "completed"),
        "blocked_chapters": blocked_chapters,
        "p0_p1_issue_count": p0_p1_issue_count,
        "issue_counts": issue_counts,
        "review_decisions": review_decisions,
        "revision_rounds": revision_rounds,
        "archive_complete_count": archive_complete_count,
        "archive_completion_rate": archive_completion_rate,
        "prior_context_ready_count": prior_context_ready_count,
        "prior_context_rate": prior_context_rate,
        "user_modification_points": 0,
        "notes": [
            "本地 series 使用确定性 Agent，不代表真实模型文学质量。",
            "user_modification_points 在无人工编辑的本地 smoke 中固定为 0。",
        ],
    }


def read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_optional_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    return read_json(path)


def archive_is_complete(archive: Dict[str, Any]) -> bool:
    if not archive:
        return False
    required = ["facts", "timeline", "foreshadowing", "character_state", "continuity_issues"]
    for key in required:
        if key not in archive or not isinstance(archive[key], list):
            return False
    return bool(archive["facts"] and archive["timeline"] and archive["foreshadowing"] and archive["character_state"])
