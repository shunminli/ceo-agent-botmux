from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from botmux_novel import NovelChapterWorkflowImporter, NovelChapterWorkflowImportRequest


class NovelChapterWorkflowImportTest(unittest.TestCase):
    def test_chapter_workflow_import_writes_final_and_archive(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            workflow_result = root / "chapter-workflow-result.json"
            project = root / "chapter-project"
            foundation = root / "foundation.json"
            foundation.write_text("{}", encoding="utf-8")
            workflow_result.write_text(json.dumps(sample_chapter_workflow_result(), ensure_ascii=False, indent=2), encoding="utf-8")

            result = NovelChapterWorkflowImporter().import_chapter(
                NovelChapterWorkflowImportRequest(
                    workflow_result_path=workflow_result,
                    project_path=project,
                    foundation_path=foundation,
                )
            )

            self.assertEqual(result.status, "completed")
            self.assertEqual(result.chapter_id, "ch-001")
            self.assertTrue((project / "manuscript/draft/ch-001.md").exists())
            self.assertTrue((project / "manuscript/revised/ch-001.md").exists())
            self.assertTrue((project / "manuscript/final/ch-001.md").exists())
            self.assertIn("妹妹的影子", (project / "manuscript/final/ch-001.md").read_text(encoding="utf-8"))
            self.assertTrue((project / "tracking/facts.yaml").exists())
            self.assertTrue((project / "tracking/foreshadowing.yaml").exists())
            self.assertTrue((project / "runs/archive-ch-001.json").exists())
            self.assertTrue((project / f"runs/{result.run_id}/workflow-result-source.json").exists())
            self.assertTrue((project / f"runs/{result.run_id}/workflow-node-outputs.json").exists())
            self.assertTrue((project / f"runs/{result.run_id}/next-chapter-command.json").exists())

            next_command = json.loads((project / f"runs/{result.run_id}/next-chapter-command.json").read_text(encoding="utf-8"))
            self.assertEqual(next_command["next_chapter_id"], "ch-002")
            self.assertEqual(next_command["chapter_goal"], "让林烬用半张残页验证巡夜钟异常，并把妹妹影子证词转成下一章追查目标。")
            self.assertIn("妹妹的影子会在巡夜钟异常时开口。", next_command["prior_context"])
            self.assertIn("巡夜钟提前震响", next_command["prior_context"])
            self.assertIn("novel-chapter-production", next_command["workflow_command"])
            self.assertTrue(any(item.startswith("priorContext=") for item in next_command["workflow_command"]))
            self.assertIn("wordTarget=1200", next_command["workflow_command"])
            self.assertIn("mode=lean", next_command["workflow_command"])
            self.assertIn("--chapter-goal", next_command["local_command"])
            self.assertIn("--foundation-json", next_command["local_command"])

            archive = json.loads((project / "runs/archive-ch-001.json").read_text(encoding="utf-8"))
            self.assertEqual(archive["archive_decision"], "archive")
            self.assertEqual(archive["facts"][0]["chapter_id"], "ch-001")
            self.assertEqual(archive["foreshadowing"][0]["status"], "open")
            self.assertEqual(archive["character_state"][0]["id"], "protagonist")

    def test_cli_chapter_workflow_import_uses_real_entrypoint(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            workflow_result = root / "chapter-workflow-result.json"
            project = root / "cli-chapter-project"
            workflow_result.write_text(json.dumps(sample_chapter_workflow_result(), ensure_ascii=False, indent=2), encoding="utf-8")

            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "botmux_novel",
                    "chapter-workflow-import",
                    "--workflow-result",
                    str(workflow_result),
                    "--project",
                    str(project),
                ],
                check=True,
                text=True,
                capture_output=True,
            )

            payload = json.loads(completed.stdout)
            self.assertEqual(payload["status"], "completed")
            self.assertEqual(payload["chapter_id"], "ch-001")
            self.assertTrue(Path(payload["final_path"]).exists())
            self.assertTrue((project / "runs/archive-ch-001.json").exists())

    def test_chapter_workflow_import_preserves_archived_chapter_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            project = root / "multi-import-project"
            first_result = root / "chapter-001-result.json"
            second_result = root / "chapter-002-result.json"
            first_result.write_text(json.dumps(sample_chapter_workflow_result(), ensure_ascii=False, indent=2), encoding="utf-8")
            second_payload = sample_chapter_workflow_result()
            second_payload["params"]["chapterNumber"] = 2
            second_payload["params"]["chapterGoal"] = "让林烬用半张残页验证巡夜钟异常，并把妹妹影子证词转成下一章追查目标。"
            second_result.write_text(json.dumps(second_payload, ensure_ascii=False, indent=2), encoding="utf-8")

            first = NovelChapterWorkflowImporter().import_chapter(
                NovelChapterWorkflowImportRequest(workflow_result_path=first_result, project_path=project)
            )
            second = NovelChapterWorkflowImporter().import_chapter(
                NovelChapterWorkflowImportRequest(workflow_result_path=second_result, project_path=project)
            )

            self.assertEqual(first.status, "completed")
            self.assertEqual(second.status, "completed")
            self.assertTrue((project / "runs/archive-ch-001.json").exists())
            self.assertTrue((project / "runs/archive-ch-002.json").exists())
            project_yaml = (project / "project.yaml").read_text(encoding="utf-8")
            self.assertIn("current_chapter: \"ch-002\"", project_yaml)
            self.assertIn("- \"ch-001\"", project_yaml)
            self.assertIn("- \"ch-002\"", project_yaml)

    def test_chapter_workflow_import_blocks_without_final_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            workflow_result = root / "chapter-workflow-result.json"
            project = root / "blocked-chapter-project"
            payload = sample_chapter_workflow_result()
            payload["nodes"]["director_approval_package"]["output"]["data"]["decision"] = "block"
            workflow_result.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

            result = NovelChapterWorkflowImporter().import_chapter(
                NovelChapterWorkflowImportRequest(
                    workflow_result_path=workflow_result,
                    project_path=project,
                )
            )

            self.assertEqual(result.status, "blocked")
            self.assertFalse((project / "manuscript/final/ch-001.md").exists())
            self.assertTrue((project / f"runs/{result.run_id}/blocked-chapter-import.json").exists())
            self.assertTrue((project / "manuscript/draft/ch-001.md").exists())
            self.assertTrue((project / "manuscript/revised/ch-001.md").exists())

    def test_chapter_workflow_import_rejects_missing_required_node(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            workflow_result = root / "chapter-workflow-result.json"
            payload = sample_chapter_workflow_result()
            del payload["nodes"]["archive_plan"]
            workflow_result.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "missing required node output: archive_plan"):
                NovelChapterWorkflowImporter().import_chapter(
                    NovelChapterWorkflowImportRequest(
                        workflow_result_path=workflow_result,
                        project_path=root / "project",
                    )
                )


def sample_chapter_workflow_result() -> dict:
    return {
        "workflowId": "novel-chapter-production",
        "params": {
            "projectSlug": "shadow-clock-case",
            "title": "影钟旧案",
            "storyBible": "林烬必须用旧案残页和巡夜钟规则找回选择权。",
            "chapterNumber": 1,
            "chapterGoal": "用旧书楼残页引出主角秘密能力，并埋下巡夜钟伏笔。",
            "priorContext": "无",
            "wordTarget": 1200,
            "mode": "lean",
        },
        "nodes": {
            "chapter_prepare": {"output": agent_output("上下文已准备", "上下文包", {"hard_constraints": ["不能提前揭示禁术源头"]})},
            "chapter_blueprint": {
                "output": agent_output(
                    "章纲已准备",
                    "章纲文本",
                    {
                        "chapter_id": "ch-001",
                        "title": "旧书楼的残页",
                        "objective": "用旧书楼残页引出主角秘密能力，并埋下巡夜钟伏笔。",
                        "scenes": [
                            {
                                "id": "scene-1",
                                "purpose": "户籍压力开场",
                                "location": "城南税籍所外",
                                "conflict": "巡城司盘问林烬。",
                                "turn": "林烬在巡使影子里看见旧案残页。",
                            }
                        ],
                        "emotion_curve": ["压迫", "试探", "惊疑"],
                        "must_include": ["旧书楼", "残页", "巡夜钟"],
                        "forbidden": ["不能提前揭示禁术源头"],
                    },
                )
            },
            "chapter_draft": {
                "output": agent_output(
                    "草稿已生成",
                    "草稿全文",
                    {
                        "draft_text": "林烬站在税籍所外，听见巡夜钟尚未入夜便轻轻一震。",
                        "author_notes": ["压低解释，保留钩子。"],
                    },
                )
            },
            "continuity_review": {
                "output": agent_output(
                    "审查通过，有轻微文风建议",
                    "审查报告",
                    {
                        "decision": "pass",
                        "issues": [],
                        "gate_results": [],
                        "required_fixes": [],
                        "optional_suggestions": ["减少解释性句子"],
                    },
                )
            },
            "chapter_revision": {
                "output": agent_output(
                    "修订稿已完成",
                    "修订稿全文",
                    {
                        "revised_text": "林烬站在税籍所外，袖中的残页被汗意浸软。巡夜钟尚未入夜便轻轻一震。",
                        "diff_notes": ["强化动作和物件。"],
                    },
                )
            },
            "director_approval_package": {
                "output": agent_output(
                    "章节可归档",
                    "章节定稿包",
                    {
                        "decision": "pass",
                        "final_text": "林烬站在税籍所外，袖中的残页被汗意浸软。巡夜钟尚未入夜便轻轻一震，妹妹的影子先替她开了口。",
                        "approval_notes": "人类门禁后可进入归档。",
                        "change_summary": ["保留巡夜钟伏笔。"],
                        "residual_risks": [],
                    },
                )
            },
            "archive_plan": {
                "output": agent_output(
                    "归档计划已准备",
                    "归档计划",
                    {
                        "archive_decision": "archive",
                        "facts": [
                            {
                                "fact": "妹妹的影子会在巡夜钟异常时开口。",
                                "source": "chapter final",
                            }
                        ],
                        "timeline": [{"event": "巡夜钟在未入夜时震响。"}],
                        "foreshadowing": [
                            {
                                "id": "patrol-bell-early-ring",
                                "item": "巡夜钟提前震响",
                                "planned_payoff": "后续证明钟声可被篡改。",
                                "status": "open",
                                "risk": "P2",
                            }
                        ],
                        "character_state": [
                            {
                                "id": "protagonist",
                                "name": "林烬",
                                "state": "意识到妹妹影子与旧案有关。",
                                "known_information": ["巡夜钟异常会触发影子证词。"],
                            }
                        ],
                        "continuity_issues": [],
                        "style_feedback": ["动作承载情绪有效。"],
                        "wiki_sync_plan": {"pages": ["chapter-index.md", "foreshadowing.md"]},
                        "rollback_plan": "回滚本次 chapter workflow import run artifacts。",
                    },
                )
            },
        },
    }


def agent_output(preview: str, handoff: str, data: dict) -> dict:
    return {
        "preview": preview,
        "handoff": handoff,
        "data": data,
        "open_questions": [],
        "risks": [],
        "wiki_refs": [],
        "change_declarations": [],
    }


if __name__ == "__main__":
    unittest.main()
