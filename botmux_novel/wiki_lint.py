from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List


REQUIRED_NAMESPACE_PAGES = {
    "overview.md",
    "story-bible.md",
    "relationships.md",
    "plot-trajectory.md",
    "world-scenes.md",
    "foreshadowing.md",
    "continuity-rules.md",
    "chapter-index.md",
    "sync-plan.md",
}

LINK_PATTERN = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


@dataclass(frozen=True)
class WikiLintIssue:
    path: Path
    severity: str
    message: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": str(self.path),
            "severity": self.severity,
            "message": self.message,
        }


@dataclass(frozen=True)
class WikiLintResult:
    status: str
    workspace_path: Path
    checked_files: List[Path]
    issues: List[WikiLintIssue]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "workspace_path": str(self.workspace_path),
            "checked_files": [str(path) for path in self.checked_files],
            "issues": [issue.to_dict() for issue in self.issues],
        }


class WikiLinter:
    def lint(self, workspace_path: Path) -> WikiLintResult:
        workspace = workspace_path.expanduser().resolve()
        wiki_root = workspace / "wiki" / "novels"
        issues: List[WikiLintIssue] = []
        if not wiki_root.exists():
            issues.append(WikiLintIssue(path=wiki_root, severity="error", message="wiki/novels directory is missing"))
            return WikiLintResult(status="failed", workspace_path=workspace, checked_files=[], issues=issues)
        if not wiki_root.is_dir():
            issues.append(WikiLintIssue(path=wiki_root, severity="error", message="wiki/novels is not a directory"))
            return WikiLintResult(status="failed", workspace_path=workspace, checked_files=[], issues=issues)

        markdown_files = sorted(path for path in wiki_root.rglob("*.md") if path.is_file())
        if not markdown_files:
            issues.append(WikiLintIssue(path=wiki_root, severity="error", message="no Markdown files found under wiki/novels"))

        for namespace in sorted(path for path in wiki_root.iterdir() if path.is_dir()):
            issues.extend(self._lint_namespace(namespace))
        for markdown_file in markdown_files:
            issues.extend(self._lint_markdown_file(workspace=workspace, path=markdown_file))

        status = "failed" if any(issue.severity == "error" for issue in issues) else "passed"
        return WikiLintResult(
            status=status,
            workspace_path=workspace,
            checked_files=markdown_files,
            issues=issues,
        )

    def _lint_namespace(self, namespace_path: Path) -> List[WikiLintIssue]:
        issues: List[WikiLintIssue] = []
        present_pages = {path.name for path in namespace_path.glob("*.md") if path.is_file()}
        for page in sorted(REQUIRED_NAMESPACE_PAGES - present_pages):
            issues.append(WikiLintIssue(path=namespace_path / page, severity="error", message="required wiki page is missing"))

        characters_path = namespace_path / "characters"
        if not characters_path.is_dir():
            issues.append(WikiLintIssue(path=characters_path, severity="error", message="characters directory is missing"))
        elif not any(path.suffix == ".md" and path.is_file() for path in characters_path.iterdir()):
            issues.append(WikiLintIssue(path=characters_path, severity="error", message="characters directory has no Markdown pages"))
        return issues

    def _lint_markdown_file(self, *, workspace: Path, path: Path) -> List[WikiLintIssue]:
        issues: List[WikiLintIssue] = []
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return [WikiLintIssue(path=path, severity="error", message="file is not valid UTF-8")]

        if not text.strip():
            issues.append(WikiLintIssue(path=path, severity="error", message="file is empty"))
            return issues

        first_content_line = next((line.strip() for line in text.splitlines() if line.strip()), "")
        if not first_content_line.startswith("# "):
            issues.append(WikiLintIssue(path=path, severity="error", message="first non-empty line must be an H1 heading"))

        issues.extend(self._lint_links(workspace=workspace, path=path, text=text))
        return issues

    def _lint_links(self, *, workspace: Path, path: Path, text: str) -> List[WikiLintIssue]:
        issues: List[WikiLintIssue] = []
        for raw_target in LINK_PATTERN.findall(text):
            target = raw_target.strip()
            if not target or target.startswith(("#", "http://", "https://", "mailto:")):
                continue
            clean_target = target.split("#", 1)[0].strip()
            if not clean_target:
                continue
            if clean_target.startswith("/wiki/novels/"):
                linked_path = workspace / clean_target.lstrip("/")
            elif clean_target.startswith("/"):
                continue
            else:
                linked_path = (path.parent / clean_target).resolve()
            if not linked_path.exists():
                issues.append(
                    WikiLintIssue(
                        path=path,
                        severity="error",
                        message=f"broken local Markdown link: {target}",
                    )
                )
        return issues


def result_to_stdout(result: WikiLintResult) -> str:
    return json.dumps(result.to_dict(), ensure_ascii=False, indent=2)
