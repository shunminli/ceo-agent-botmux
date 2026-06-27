from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from .workspace import NovelWorkspace, render_yaml, utc_now


@dataclass(frozen=True)
class NovelProjectInitRequest:
    project_path: Path
    project_slug: str
    title: str
    inspiration: str = ""
    genre: str = ""
    target_length: str = ""
    mode: str = "lean"
    write_gitignore: bool = True


@dataclass(frozen=True)
class NovelProjectInitResult:
    status: str
    project_path: Path
    created: List[Path]
    skipped: List[Path]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "project_path": str(self.project_path),
            "created": [str(path) for path in self.created],
            "skipped": [str(path) for path in self.skipped],
        }


class NovelProjectInitializer:
    def initialize(self, request: NovelProjectInitRequest) -> NovelProjectInitResult:
        if request.mode not in {"full", "lean", "solo"}:
            raise ValueError("mode must be one of: full, lean, solo")
        project_path = request.project_path.expanduser().resolve()
        workspace = NovelWorkspace(project_path)
        workspace.ensure_layout()

        created: List[Path] = []
        skipped: List[Path] = []

        project_payload = {
            "project_slug": request.project_slug,
            "title": request.title,
            "inspiration": request.inspiration,
            "genre": request.genre,
            "target_length": request.target_length,
            "mode": request.mode,
            "created_at": utc_now(),
            "artifact_policy": {
                "source_of_truth": "bible, manuscript/final, publish/fanqie, tracking, comms/decisions",
                "local_only": "runs, llmwiki indexes, bot notes, transient logs",
            },
        }
        self._write_if_absent(
            project_path / "project.yaml",
            render_yaml(project_payload) + "\n",
            created,
            skipped,
        )
        self._write_if_absent(
            project_path / "bible" / "README.md",
            render_bible_readme(request),
            created,
            skipped,
        )
        self._write_if_absent(
            project_path / "publish" / "fanqie" / "metadata.yaml",
            render_yaml(
                {
                    "platform": "fanqie",
                    "project_slug": request.project_slug,
                    "title": request.title,
                    "genre": request.genre,
                    "target_length": request.target_length,
                    "source_dir": "manuscript/final",
                    "export_dir": "publish/fanqie",
                    "chapter_format": "UTF-8 plain text, one chapter per file",
                    "updated_at": utc_now(),
                }
            )
            + "\n",
            created,
            skipped,
        )
        self._write_if_absent(
            project_path / "publish" / "fanqie" / "upload-checklist.md",
            render_upload_checklist_header(request),
            created,
            skipped,
        )
        self._write_if_absent(
            project_path / "comms" / "handoffs" / "README.md",
            render_handoff_readme(),
            created,
            skipped,
        )
        self._write_if_absent(
            project_path / "comms" / "decisions" / "README.md",
            "# Decisions\n\nRecord human approvals, platform upload decisions, and major story direction changes here.\n",
            created,
            skipped,
        )
        if request.write_gitignore:
            self._write_if_absent(
                project_path / ".gitignore",
                render_project_gitignore(),
                created,
                skipped,
            )

        status = "initialized" if created else "unchanged"
        return NovelProjectInitResult(status=status, project_path=project_path, created=created, skipped=skipped)

    def _write_if_absent(self, path: Path, content: str, created: List[Path], skipped: List[Path]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            skipped.append(path)
            return
        path.write_text(content, encoding="utf-8")
        created.append(path)


def render_bible_readme(request: NovelProjectInitRequest) -> str:
    return f"""# {request.title} Bible

- Project slug: `{request.project_slug}`
- Genre: {request.genre or "未指定"}
- Target length: {request.target_length or "未指定"}
- Mode: `{request.mode}`

This directory stores approved story foundation assets: Story Bible, character settings, plot arc, relationships, and scene rules.
"""


def render_upload_checklist_header(request: NovelProjectInitRequest) -> str:
    return f"""# Fanqie Upload Checklist

- Project: {request.title}
- Project slug: `{request.project_slug}`
- Source: `manuscript/final`
- Export: `publish/fanqie`

| Chapter | File | Character Count | Upload Status | Notes |
|---|---|---:|---|---|
"""


def render_handoff_readme() -> str:
    return """# Bot Handoffs

Store structured bot-to-bot handoff payloads here.

Required fields for each handoff:

- `preview`: human-readable summary.
- `handoff`: complete downstream context.
- `data`: structured facts and decisions.
- `open_questions`: unresolved questions.
- `risks`: known risks.
- `wiki_refs`: llmwiki references or proposed page ids.
- `change_declarations`: proposed changes to the current story state.
"""


def render_project_gitignore() -> str:
    return """# Local execution artifacts
runs/
*.sqlite
*.sqlite-*
*.log

# Bot scratch notes and transient communication
comms/bot-notes/

# Local llmwiki index/workspace internals
wiki/llmwiki-workspace/
.llmwiki/

# OS/editor noise
.DS_Store
*.tmp
"""
