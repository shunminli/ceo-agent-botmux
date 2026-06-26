from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def render_yaml(value: Any, indent: int = 0) -> str:
    spaces = " " * indent
    if isinstance(value, dict):
        lines: List[str] = []
        for key, item in value.items():
            if isinstance(item, (dict, list)):
                lines.append(f"{spaces}{key}:")
                lines.append(render_yaml(item, indent + 2))
            else:
                lines.append(f"{spaces}{key}: {render_yaml(item, 0).strip()}")
        return "\n".join(lines)
    if isinstance(value, list):
        lines = []
        for item in value:
            if isinstance(item, (dict, list)):
                lines.append(f"{spaces}-")
                lines.append(render_yaml(item, indent + 2))
            else:
                lines.append(f"{spaces}- {render_yaml(item, 0).strip()}")
        return "\n".join(lines)
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return json.dumps(str(value), ensure_ascii=False)


class NovelWorkspace:
    def __init__(self, root: Path):
        self.root = root

    def ensure_layout(self) -> None:
        directories = [
            "settings",
            "characters",
            "outline/chapter-blueprints",
            "manuscript/draft",
            "manuscript/revised",
            "manuscript/final",
            "tracking",
            "memory/examples",
            "runs",
            "references/benchmark",
            "references/prompts",
        ]
        for directory in directories:
            (self.root / directory).mkdir(parents=True, exist_ok=True)

    def path(self, relative: str) -> Path:
        return self.root / relative

    def write_text(self, relative: str, content: str) -> Path:
        path = self.path(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def write_json(self, relative: str, payload: Dict[str, Any]) -> Path:
        return self.write_text(relative, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")

    def write_yaml(self, relative: str, payload: Any) -> Path:
        return self.write_text(relative, render_yaml(payload) + "\n")

    def record_run(
        self,
        *,
        run_id: str,
        project_title: str,
        chapter_id: str,
        mode: str,
        status: str,
        started_at: str,
        ended_at: str,
        trace_path: Path,
        artifacts: Iterable[Path],
    ) -> Path:
        db_path = self.root / "runs" / "runs.sqlite"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(db_path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    project_title TEXT NOT NULL,
                    chapter_id TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    status TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    ended_at TEXT NOT NULL,
                    trace_path TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS artifacts (
                    run_id TEXT NOT NULL,
                    path TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    PRIMARY KEY (run_id, path)
                )
                """
            )
            connection.execute(
                """
                INSERT OR REPLACE INTO runs (
                    run_id, project_title, chapter_id, mode, status, started_at, ended_at, trace_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    project_title,
                    chapter_id,
                    mode,
                    status,
                    started_at,
                    ended_at,
                    str(trace_path.relative_to(self.root)),
                ),
            )
            for artifact in artifacts:
                relative = artifact.relative_to(self.root)
                kind = relative.parts[0] if relative.parts else "root"
                connection.execute(
                    "INSERT OR REPLACE INTO artifacts (run_id, path, kind) VALUES (?, ?, ?)",
                    (run_id, str(relative), kind),
                )
        return db_path


def markdown_list(items: Iterable[str]) -> str:
    return "\n".join(f"- {item}" for item in items)
