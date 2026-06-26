from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from botmux_novel import (
    NovelApprovalCheckRequest,
    NovelApprovalPackageChecker,
    NovelWorkflowFoundationImporter,
    NovelWorkflowFoundationImportRequest,
)


class NovelWorkflowFoundationImportTest(unittest.TestCase):
    def test_workflow_foundation_import_creates_review_package(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            workflow_result = root / "workflow-result.json"
            project = root / "workflow-novel-project"
            workspace = root / "workflow-llmwiki-workspace"
            fake_llmwiki = root / "llmwiki"
            write_fake_llmwiki(fake_llmwiki)
            workflow_result.write_text(json.dumps(sample_workflow_result(), ensure_ascii=False, indent=2), encoding="utf-8")

            result = NovelWorkflowFoundationImporter().import_foundation(
                NovelWorkflowFoundationImportRequest(
                    workflow_result_path=workflow_result,
                    project_path=project,
                    project_slug="shadow-clock-case",
                    workspace_path=workspace,
                    llmwiki_bin=str(fake_llmwiki),
                )
            )

            self.assertEqual(result.status, "ready")
            self.assertTrue(result.foundation.foundation_path.exists())
            self.assertIn("story_bible_package", result.imported_nodes)
            self.assertIn("wiki_sync_plan", result.imported_nodes)
            self.assertTrue((project / "runs" / result.foundation.run_id / "workflow-result-source.json").exists())
            self.assertTrue((project / "runs" / result.foundation.run_id / "workflow-node-outputs.json").exists())
            self.assertTrue((result.wiki_bundle.bundle_path / "story-bible.md").exists())
            self.assertEqual(result.llmwiki_sync.status, "planned")
            self.assertFalse((workspace / "wiki/novels/shadow-clock-case/overview.md").exists())
            self.assertTrue(result.approval_package_path.exists())
            self.assertTrue(result.approval_package_json_path.exists())

            package = json.loads(result.approval_package_json_path.read_text(encoding="utf-8"))
            self.assertEqual(package["status"], "ready_for_human_review")
            self.assertEqual(package["workflow_import"]["source_path"], str(workflow_result.resolve()))
            self.assertIn("approval-apply", package["human_gate"]["approval_apply_command"])
            self.assertIn("--foundation-json", package["next_actions"]["chapter_start_command"])
            self.assertIn(str(result.foundation.foundation_path), package["next_actions"]["chapter_start_command"])

            check = NovelApprovalPackageChecker().check(
                NovelApprovalCheckRequest(
                    approval_package_path=result.approval_package_json_path,
                    run_apply_dry_run=True,
                )
            )
            self.assertEqual(check.status, "ready")
            checks = {item.name: item for item in check.checks}
            self.assertEqual(checks["package_json"].status, "pass")
            self.assertEqual(checks["review_materials"].status, "pass")
            self.assertEqual(checks["human_gate"].status, "pass")
            self.assertEqual(checks["apply_dry_run"].status, "pass")

            chapter = subprocess.run(
                package["next_actions"]["chapter_start_command"],
                check=True,
                text=True,
                capture_output=True,
            )
            chapter_payload = json.loads(chapter.stdout)
            self.assertEqual(chapter_payload["status"], "completed")
            self.assertEqual(chapter_payload["chapter_id"], "ch-001")

    def test_cli_workflow_foundation_import_uses_real_entrypoint(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            workflow_result = root / "workflow-result.json"
            project = root / "cli-workflow-novel-project"
            workspace = root / "cli-workflow-llmwiki-workspace"
            fake_llmwiki = root / "llmwiki"
            write_fake_llmwiki(fake_llmwiki)
            workflow_result.write_text(json.dumps(sample_workflow_result(), ensure_ascii=False, indent=2), encoding="utf-8")

            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "botmux_novel",
                    "workflow-foundation-import",
                    "--workflow-result",
                    str(workflow_result),
                    "--project",
                    str(project),
                    "--project-slug",
                    "shadow-clock-case",
                    "--workspace",
                    str(workspace),
                    "--llmwiki-bin",
                    str(fake_llmwiki),
                ],
                check=True,
                text=True,
                capture_output=True,
            )

            payload = json.loads(completed.stdout)
            self.assertEqual(payload["status"], "ready")
            self.assertTrue(Path(payload["approval_package_json_path"]).exists())
            self.assertTrue(Path(payload["foundation"]["foundation_path"]).exists())
            self.assertEqual(payload["llmwiki_sync"]["status"], "planned")

            check_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "botmux_novel",
                    "approval-check",
                    "--approval-package",
                    payload["approval_package_json_path"],
                    "--apply-dry-run",
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            check_payload = json.loads(check_completed.stdout)
            self.assertEqual(check_payload["status"], "ready")

    def test_workflow_foundation_import_rejects_missing_required_node(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            workflow_result = root / "workflow-result.json"
            payload = sample_workflow_result()
            del payload["nodes"]["wiki_sync_plan"]
            workflow_result.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "missing required node output: wiki_sync_plan"):
                NovelWorkflowFoundationImporter().import_foundation(
                    NovelWorkflowFoundationImportRequest(
                        workflow_result_path=workflow_result,
                        project_path=root / "project",
                        project_slug="shadow-clock-case",
                    )
                )


def sample_workflow_result() -> dict:
    return {
        "workflowId": "novel-story-foundation",
        "params": {
            "projectSlug": "shadow-clock-case",
            "title": "影钟旧案",
            "inspiration": "一个背负旧案污名的少年，在巡夜钟声中发现妹妹影子会说真话。",
            "genre": "东方悬疑幻想",
            "targetLength": "长篇",
            "mode": "lean",
        },
        "nodes": {
            "story_bible_package": {
                "output": agent_output(
                    preview="Story Bible 已审批候选：旧案、巡夜钟、妹妹影子证词形成核心钩子。",
                    handoff="完整 Story Bible：林烬必须用旧案残页和巡夜钟规则找回选择权。",
                    data={
                        "story_promise": "背负旧案污名的少年用被删改的残页反击巡城司。",
                        "theme": "在被规定的人生里夺回选择权",
                        "core_conflict": "林烬必须在保护妹妹户籍和揭开父亲旧案之间选择。",
                        "ending_constraint": "终局必须用已铺垫的残页、巡夜钟和记忆代价反击。",
                        "characters": [
                            {
                                "id": "protagonist",
                                "name": "林烬",
                                "role": "主角",
                                "motivation": "查清父亲旧案并保住妹妹户籍。",
                                "current_state": "贫寒、克制、背负污名。",
                                "secret": "能看见被抵押记忆留下的残光。",
                            },
                            {
                                "id": "antagonist",
                                "name": "玄衣巡使",
                                "role": "明面阻力",
                                "motivation": "压下旧案残页，维护巡城司权威。",
                                "current_state": "掌控城门和夜巡记录。",
                                "secret": "他只是在替真正主谋清场。",
                            },
                        ],
                        "relationships": {
                            "edges": [
                                {
                                    "source": "protagonist",
                                    "target": "antagonist",
                                    "type": "conflict",
                                    "pressure": "巡使掌握妹妹户籍和旧案清场权。",
                                    "secret": "巡使知道残页会指向真正主谋。",
                                }
                            ]
                        },
                        "settings": [
                            {
                                "id": "old-library",
                                "name": "旧书楼",
                                "kind": "location",
                                "function": "提供旧案残页并测试主角是否愿意付出记忆代价。",
                                "conflict_pressure": "答案必须用记忆交换，且守灯人不完全可信。",
                                "rules": ["旧书楼只保存被删改前的残页。"],
                                "reuse_value": "后续可用于线索补给、代价抉择和版本对照。",
                            },
                            {
                                "id": "patrol-bell",
                                "name": "巡夜钟",
                                "kind": "world_rule",
                                "function": "让谎言在影子里显形，形成悬疑验证机制。",
                                "conflict_pressure": "钟声时间可被篡改，真相和陷阱会同时出现。",
                                "rules": ["钟响后三刻内，谎言会在影子里显形。"],
                                "reuse_value": "用于审讯、反转、伏笔回收和终局反击。",
                            },
                        ],
                        "rules": {
                            "world_rules": [
                                "城中术法必须以记忆作抵押。",
                                "巡夜钟响后三刻内，谎言会在影子里显形。",
                            ],
                            "forbidden": ["不能让主角突然无代价突破。", "不能提前揭示禁术源头。"],
                        },
                        "plot_arc": {
                            "volume": "第一卷：影子里的旧案",
                            "goal": "林烬从被动背锅到掌握第一份旧案证据。",
                            "turning_points": ["旧书楼残页", "巡夜钟试探", "妹妹被卷入户籍清查", "主角公开反击"],
                            "opening_hook": "用旧书楼残页引出主角秘密能力，并埋下巡夜钟伏笔。",
                        },
                        "style_profile": {
                            "id": "shadow-clock-style",
                            "tone": "冷峻、克制、悬疑压迫",
                            "rules": ["减少解释性总结。", "对话保留潜台词。"],
                            "forbidden_expressions": ["感到无比震惊"],
                            "positive_examples": ["林烬把指腹按在那行墨痕上。"],
                            "negative_examples": ["林烬感到无比震惊。"],
                        },
                    },
                )
            },
            "wiki_sync_plan": {
                "output": agent_output(
                    preview="计划写入 overview、story-bible、characters、relationships 和 world-scenes。",
                    handoff="llmwiki 写入计划：先 overview，再 story-bible，再角色和关系页面。",
                    data={
                        "write_plan": ["overview.md", "story-bible.md", "characters/*.md", "relationships.md"],
                        "rollback_plan": "写入前保留本地 bundle，写入后执行 lint/reindex。",
                    },
                )
            },
        },
    }


def agent_output(*, preview: str, handoff: str, data: dict) -> dict:
    return {
        "preview": preview,
        "handoff": handoff,
        "data": data,
        "open_questions": [],
        "risks": [],
        "wiki_refs": [],
        "change_declarations": [],
    }


def write_fake_llmwiki(path: Path) -> None:
    path.write_text("#!/bin/sh\necho planned \"$@\"\n", encoding="utf-8")
    path.chmod(0o755)


if __name__ == "__main__":
    unittest.main()
