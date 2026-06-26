from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional


FOUNDATION_GLOBS = (
    "runs/foundation-*/foundation.json",
    "runs/workflow-foundation-*/foundation.json",
)


def iter_foundation_paths(project_path: Path) -> Iterable[Path]:
    root = project_path.expanduser().resolve()
    for pattern in FOUNDATION_GLOBS:
        yield from root.glob(pattern)


def find_latest_foundation_path(project_path: Path) -> Optional[Path]:
    candidates = sorted(
        (path for path in iter_foundation_paths(project_path) if path.exists()),
        key=lambda path: path.stat().st_mtime,
    )
    return candidates[-1] if candidates else None


def resolve_optional_foundation_path(project_path: Path, explicit_path: Optional[Path]) -> Optional[Path]:
    if explicit_path is not None:
        path = explicit_path.expanduser().resolve()
        if not path.exists():
            raise ValueError(f"foundation file does not exist: {path}")
        return path
    return find_latest_foundation_path(project_path)


def resolve_foundation_path(project_path: Path, explicit_path: Optional[Path]) -> Path:
    path = resolve_optional_foundation_path(project_path, explicit_path)
    if path is None:
        raise ValueError(
            "no foundation.json found; run `python -m botmux_novel foundation`, "
            "import `novel-story-foundation`, or pass --foundation-json"
        )
    return path
