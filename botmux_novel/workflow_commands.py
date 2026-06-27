from __future__ import annotations

from typing import Any, Dict, List, Optional


def build_story_foundation_workflow_command(
    *,
    project_slug: str,
    title: str,
    inspiration: str,
    genre: str = "未指定",
    target_length: str = "长篇",
    mode: str = "lean",
) -> List[str]:
    return [
        "botmux",
        "workflow",
        "run",
        "novel-story-foundation",
        "--param",
        f"projectSlug={project_slug}",
        "--param",
        f"title={title}",
        "--param",
        f"inspiration={inspiration}",
        "--param",
        f"genre={genre}",
        "--param",
        f"targetLength={target_length}",
        "--param",
        f"mode={mode}",
    ]


def build_chapter_workflow_command(
    *,
    project_slug: str,
    title: str,
    foundation_payload: Dict[str, Any],
    default_chapter_number: int = 1,
    chapter_number: Optional[int] = None,
    chapter_goal: Optional[str] = None,
    prior_context: str = "无",
    word_target: Optional[int] = None,
    mode: Optional[str] = None,
) -> List[str]:
    foundation_chapter_goal = foundation_payload.get("chapter_goal", {})
    project = foundation_payload.get("project", {})
    chapter_id = str(foundation_chapter_goal.get("chapter_id", f"ch-{default_chapter_number:03d}"))
    resolved_chapter_number = chapter_number or chapter_number_from_id(chapter_id, default=default_chapter_number)
    resolved_goal = chapter_goal if chapter_goal is not None else str(foundation_chapter_goal.get("objective", ""))
    resolved_word_target = int(word_target if word_target is not None else project.get("word_target", 1200))
    resolved_mode = str(mode if mode is not None else project.get("mode", "lean"))
    return [
        "botmux",
        "workflow",
        "run",
        "novel-chapter-production",
        "--param",
        f"projectSlug={project_slug}",
        "--param",
        f"title={title}",
        "--param",
        f"storyBible={story_bible_workflow_param(foundation_payload)}",
        "--param",
        f"chapterNumber={resolved_chapter_number}",
        "--param",
        f"chapterGoal={resolved_goal}",
        "--param",
        f"priorContext={prior_context}",
        "--param",
        f"wordTarget={resolved_word_target}",
        "--param",
        f"mode={resolved_mode}",
    ]


def chapter_number_from_id(chapter_id: str, *, default: int) -> int:
    prefix = "ch-"
    if chapter_id.startswith(prefix):
        suffix = chapter_id[len(prefix):]
        if suffix.isdigit():
            return int(suffix)
    return default


def story_bible_workflow_param(foundation_payload: Dict[str, Any]) -> str:
    project = object_or_empty(foundation_payload.get("project"))
    story = object_or_empty(foundation_payload.get("story_bible"))
    genre = object_or_empty(foundation_payload.get("genre"))
    world = object_or_empty(foundation_payload.get("world"))
    volume = object_or_empty(foundation_payload.get("volume_outline"))
    chapter_goal = object_or_empty(foundation_payload.get("chapter_goal"))
    characters = foundation_payload.get("characters", [])
    relationships = object_or_empty(foundation_payload.get("relationships")).get("edges", [])
    scenes = foundation_payload.get("scene_settings", [])

    character_lines = [
        f"- {item.get('name', item.get('id', 'unknown'))}: {item.get('role', '')}; motivation={item.get('motivation', '')}; state={item.get('current_state', '')}"
        for item in list_of_objects(characters)
    ]
    relationship_lines = [
        f"- {item.get('source', '')}->{item.get('target', '')}: {item.get('type', '')}; pressure={item.get('pressure', '')}"
        for item in list_of_objects(relationships)
    ]
    scene_lines = [
        f"- {item.get('name', item.get('id', 'unknown'))}: {item.get('function', '')}"
        for item in list_of_objects(scenes)
    ]
    sections = [
        f"Title: {project.get('title', '')}",
        f"Genre: {genre.get('primary', '')}",
        f"Theme: {story.get('theme', '')}",
        f"Inspiration: {story.get('inspiration', '')}",
        f"Core conflict: {story.get('core_conflict', '')}",
        f"Ending constraint: {story.get('ending_constraint', '')}",
        "World rules:\n" + "\n".join(f"- {item}" for item in world.get("rules", []) if item),
        "Forbidden:\n" + "\n".join(f"- {item}" for item in world.get("forbidden", []) if item),
        "Characters:\n" + "\n".join(character_lines),
        "Relationships:\n" + "\n".join(relationship_lines),
        f"Volume goal: {volume.get('goal', '')}",
        "Turning points:\n" + "\n".join(f"- {item}" for item in volume.get("turning_points", []) if item),
        "Scene settings:\n" + "\n".join(scene_lines),
        f"Opening chapter goal: {chapter_goal.get('objective', '')}",
    ]
    return "\n\n".join(section for section in sections if section.strip())


def object_or_empty(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def list_of_objects(value: Any) -> List[Dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []
