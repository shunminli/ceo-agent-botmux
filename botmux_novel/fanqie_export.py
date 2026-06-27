from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .workspace import utc_now


@dataclass(frozen=True)
class FanqieExportRequest:
    project_path: Path
    source_dir: str = "manuscript/final"
    output_dir: str = "publish/fanqie"
    title: Optional[str] = None


@dataclass(frozen=True)
class FanqieChapterExport:
    chapter_id: str
    title: str
    source_path: Path
    output_path: Path
    character_count: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chapter_id": self.chapter_id,
            "title": self.title,
            "source_path": str(self.source_path),
            "output_path": str(self.output_path),
            "character_count": self.character_count,
        }


@dataclass(frozen=True)
class FanqieExportResult:
    status: str
    project_path: Path
    output_dir: Path
    book_path: Path
    checklist_path: Path
    chapters: List[FanqieChapterExport]
    warnings: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "project_path": str(self.project_path),
            "output_dir": str(self.output_dir),
            "book_path": str(self.book_path),
            "checklist_path": str(self.checklist_path),
            "chapters": [chapter.to_dict() for chapter in self.chapters],
            "warnings": self.warnings,
        }


class FanqieExporter:
    def export(self, request: FanqieExportRequest) -> FanqieExportResult:
        project_path = request.project_path.expanduser().resolve()
        source_dir = project_path / request.source_dir
        output_dir = project_path / request.output_dir
        chapters_dir = output_dir / "chapters"
        chapters_dir.mkdir(parents=True, exist_ok=True)

        source_paths = sorted(source_dir.glob("ch-*.md"), key=chapter_sort_key)
        warnings: List[str] = []
        if not source_paths:
            warnings.append(f"no final manuscript files found under {source_dir}")

        chapters: List[FanqieChapterExport] = []
        book_sections: List[str] = []
        for index, source_path in enumerate(source_paths, start=1):
            chapter_id = source_path.stem
            raw_text = source_path.read_text(encoding="utf-8")
            title, body = split_chapter_title(raw_text, chapter_id, index)
            plain_body = normalize_for_fanqie(body)
            chapter_text = f"{title}\n\n{plain_body.strip()}\n"
            output_path = chapters_dir / f"{index:03d}_{sanitize_filename(title)}.txt"
            output_path.write_text(chapter_text, encoding="utf-8")
            character_count = count_non_space_characters(plain_body)
            chapters.append(
                FanqieChapterExport(
                    chapter_id=chapter_id,
                    title=title,
                    source_path=source_path,
                    output_path=output_path,
                    character_count=character_count,
                )
            )
            book_sections.append(chapter_text.strip())

        book_path = output_dir / "book.txt"
        book_path.write_text("\n\n".join(book_sections).strip() + ("\n" if book_sections else ""), encoding="utf-8")
        checklist_path = output_dir / "upload-checklist.md"
        checklist_path.write_text(render_upload_checklist(request.title, chapters), encoding="utf-8")
        status = "completed" if chapters else "empty"
        return FanqieExportResult(
            status=status,
            project_path=project_path,
            output_dir=output_dir,
            book_path=book_path,
            checklist_path=checklist_path,
            chapters=chapters,
            warnings=warnings,
        )


def chapter_sort_key(path: Path) -> Tuple[int, str]:
    match = re.fullmatch(r"ch-(\d+)", path.stem)
    if match:
        return int(match.group(1)), path.stem
    return 10**9, path.stem


def split_chapter_title(raw_text: str, chapter_id: str, index: int) -> Tuple[str, str]:
    text = raw_text.replace("\ufeff", "").replace("\r\n", "\n").replace("\r", "\n").strip()
    lines = text.splitlines()
    while lines and not lines[0].strip():
        lines.pop(0)
    if not lines:
        return default_chapter_title(chapter_id, index), ""

    first = lines[0].strip()
    heading_match = re.fullmatch(r"#{1,6}\s+(.+)", first)
    if heading_match:
        return clean_title(heading_match.group(1)), "\n".join(lines[1:])
    if re.match(r"^第[零〇一二三四五六七八九十百千万\d]+[章节回卷部](?:\s|$)", first):
        return clean_title(first), "\n".join(lines[1:])
    return default_chapter_title(chapter_id, index), "\n".join(lines)


def default_chapter_title(chapter_id: str, index: int) -> str:
    match = re.fullmatch(r"ch-(\d+)", chapter_id)
    number = int(match.group(1)) if match else index
    return f"第{number:03d}章"


def clean_title(title: str) -> str:
    title = re.sub(r"[*_`]+", "", title)
    title = re.sub(r"\s+", " ", title)
    return title.strip() or "未命名章节"


def normalize_for_fanqie(markdown_text: str) -> str:
    text = markdown_text.replace("\ufeff", "").replace("\r\n", "\n").replace("\r", "\n")
    text = strip_front_matter(text)
    lines: List[str] = []
    in_fence = False
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if line.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        heading_match = re.fullmatch(r"\s*#{1,6}\s+(.+)", line)
        if heading_match:
            line = heading_match.group(1).strip()
        line = re.sub(r"^\s*>\s?", "", line)
        line = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", line)
        line = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", line)
        line = re.sub(r"[*_`]+", "", line)
        lines.append(line.strip())
    return collapse_blank_lines("\n".join(lines)).strip()


def strip_front_matter(text: str) -> str:
    lines = text.splitlines()
    if len(lines) >= 3 and lines[0].strip() == "---":
        for index in range(1, len(lines)):
            if lines[index].strip() == "---":
                return "\n".join(lines[index + 1 :])
    return text


def collapse_blank_lines(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", text)


def sanitize_filename(value: str) -> str:
    cleaned = re.sub(r"[\\/:*?\"<>|]", "", value)
    cleaned = re.sub(r"\s+", "_", cleaned.strip())
    return cleaned[:80] or "untitled"


def count_non_space_characters(value: str) -> int:
    return len(re.sub(r"\s+", "", value))


def render_upload_checklist(title: Optional[str], chapters: List[FanqieChapterExport]) -> str:
    lines = ["# Fanqie Upload Checklist", ""]
    if title:
        lines.extend([f"- Project: {title}", ""])
    lines.extend(
        [
            f"- Generated at: {utc_now()}",
            "- Source: `manuscript/final`",
            "- Export: `publish/fanqie/chapters`",
            "",
            "| Chapter | File | Character Count | Upload Status | Notes |",
            "|---|---|---:|---|---|",
        ]
    )
    for chapter in chapters:
        rel_path = chapter.output_path.parent.name + "/" + chapter.output_path.name
        lines.append(
            f"| {chapter.title} | `{rel_path}` | {chapter.character_count} | pending |  |"
        )
    return "\n".join(lines) + "\n"
