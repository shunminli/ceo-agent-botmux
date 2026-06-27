from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, List

from botmux_novel import (
    NovelWorkflowFoundationImporter,
    NovelWorkflowFoundationImportRequest,
    NovelWorkflowRunExporter,
    NovelWorkflowRunExportRequest,
)


class NovelWorkflowRunExportTest(unittest.TestCase):
    def test_exports_botmux_run_dir_to_importable_workflow_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            run_dir = root / "workflow-runs" / "story-run-001"
            write_story_workflow_run(run_dir)
            export = NovelWorkflowRunExporter().export(NovelWorkflowRunExportRequest(run_dir=run_dir))

            self.assertEqual(export.status, "completed")
            self.assertEqual(export.workflow_id, "novel-story-foundation")
            self.assertEqual(export.params["projectSlug"], "shadow-clock-case")
            self.assertEqual(export.nodes["story_bible_package"]["status"], "succeeded")
            self.assertIn("Story Bible", export.nodes["story_bible_package"]["output"]["preview"])
            self.assertEqual(export.errors, [])

            workflow_result = root / "exported-result.json"
            workflow_result.write_text(json.dumps(export.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
            project = root / "imported-project"
            fake_llmwiki = root / "llmwiki"
            write_fake_llmwiki(fake_llmwiki)

            imported = NovelWorkflowFoundationImporter().import_foundation(
                NovelWorkflowFoundationImportRequest(
                    workflow_result_path=workflow_result,
                    project_path=project,
                    project_slug="shadow-clock-case",
                    llmwiki_bin=str(fake_llmwiki),
                )
            )

            self.assertEqual(imported.status, "ready")
            self.assertTrue(imported.foundation.foundation_path.exists())
            self.assertTrue(imported.approval_package_json_path.exists())

    def test_cli_workflow_export_uses_real_entrypoint(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            run_dir = root / "workflow-runs" / "story-run-002"
            write_story_workflow_run(run_dir, run_id="story-run-002")

            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "botmux_novel",
                    "workflow-export",
                    "--run-dir",
                    str(run_dir),
                ],
                check=True,
                text=True,
                capture_output=True,
            )

            payload = json.loads(completed.stdout)
            self.assertEqual(payload["runId"], "story-run-002")
            self.assertEqual(payload["workflowId"], "novel-story-foundation")
            self.assertEqual(payload["status"], "completed")
            self.assertIn("wiki_sync_plan", payload["nodes"])

    def test_workflow_export_resolves_run_id_from_runs_dir_and_preserves_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            runs_dir = root / "workflow-runs"
            run_dir = runs_dir / "failed-run"
            write_failed_echo_run(run_dir)

            export = NovelWorkflowRunExporter().export(
                NovelWorkflowRunExportRequest(run_id="failed-run", runs_dir=runs_dir)
            )

            self.assertEqual(export.status, "failed")
            self.assertEqual(export.nodes["intake_brief"]["output"]["echo"], "not an agent output")
            self.assertEqual(export.nodes["context_scan"]["status"], "failed")
            self.assertEqual(export.errors[-1]["failedNodeId"], "context_scan")


def write_story_workflow_run(run_dir: Path, *, run_id: str = "story-run-001") -> None:
    run_dir.mkdir(parents=True)
    (run_dir / "blobs").mkdir()
    (run_dir / "workflow.json").write_text(
        json.dumps({"workflowId": "novel-story-foundation", "version": 1}, ensure_ascii=False),
        encoding="utf-8",
    )
    events: List[Dict[str, Any]] = []
    params_ref = write_blob(
        run_dir,
        "params",
        {
            "projectSlug": "shadow-clock-case",
            "title": "影钟旧案",
            "inspiration": "一个背负旧案污名的少年，在巡夜钟声中发现妹妹影子会说真话。",
            "genre": "东方悬疑幻想",
            "targetLength": "长篇",
            "mode": "lean",
        },
    )
    events.append(event(run_id, 1, "runCreated", {"workflowId": "novel-story-foundation", "inputRef": params_ref}))
    events.append(event(run_id, 2, "runStarted", {}))
    seq = 3
    for node_id, output in story_outputs().items():
        activity_id = f"{run_id}::work::{node_id}"
        events.append(
            event(
                run_id,
                seq,
                "attemptCreated",
                {
                    "nodeId": node_id,
                    "activityId": activity_id,
                    "attemptId": f"{activity_id}::att-1",
                    "inputRef": write_blob(run_dir, f"{node_id}-input", {"prompt": node_id}),
                },
            )
        )
        seq += 1
        events.append(
            event(
                run_id,
                seq,
                "activitySucceeded",
                {
                    "activityId": activity_id,
                    "attemptId": f"{activity_id}::att-1",
                    "outputRef": write_blob(run_dir, f"{node_id}-output", output),
                },
            )
        )
        seq += 1
        events.append(event(run_id, seq, "nodeSucceeded", {"nodeId": node_id, "lastActivityId": activity_id}))
        seq += 1
    events.append(event(run_id, seq, "runCompleted", {}))
    write_events(run_dir, events)


def write_failed_echo_run(run_dir: Path) -> None:
    run_id = "failed-run"
    run_dir.mkdir(parents=True)
    (run_dir / "blobs").mkdir()
    (run_dir / "workflow.json").write_text(
        json.dumps({"workflowId": "novel-story-foundation", "version": 1}, ensure_ascii=False),
        encoding="utf-8",
    )
    intake_activity = f"{run_id}::work::intake_brief"
    context_activity = f"{run_id}::work::context_scan"
    events = [
        event(run_id, 1, "runCreated", {"workflowId": "novel-story-foundation", "inputRef": write_blob(run_dir, "params", {})}),
        event(run_id, 2, "runStarted", {}),
        event(run_id, 3, "attemptCreated", {"nodeId": "intake_brief", "activityId": intake_activity}),
        event(run_id, 4, "activitySucceeded", {"activityId": intake_activity, "outputRef": write_blob(run_dir, "echo", {"echo": "not an agent output"})}),
        event(run_id, 5, "nodeSucceeded", {"nodeId": "intake_brief", "lastActivityId": intake_activity}),
        event(run_id, 6, "attemptCreated", {"nodeId": "context_scan", "activityId": context_activity}),
        event(
            run_id,
            7,
            "activityFailed",
            {
                "activityId": context_activity,
                "error": {
                    "errorCode": "InputBindingFailed",
                    "errorClass": "userFault",
                    "errorMessage": "$ref 'intake_brief.output.handoff' segment 'handoff' not found",
                },
            },
        ),
        event(run_id, 8, "nodeFailed", {"nodeId": "context_scan", "lastActivityId": context_activity, "errorClass": "userFault"}),
        event(run_id, 9, "runFailed", {"failedNodeId": "context_scan", "rootCauseEventId": f"{run_id}-7"}),
    ]
    write_events(run_dir, events)


def story_outputs() -> Dict[str, Dict[str, Any]]:
    return {
        "story_bible_package": agent_output(
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
                        "motivation": "压下旧案残页。",
                        "current_state": "掌控城门和夜巡记录。",
                        "secret": "替真正主谋清场。",
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
                        "function": "提供旧案残页。",
                        "conflict_pressure": "答案必须用记忆交换。",
                        "rules": ["旧书楼只保存被删改前的残页。"],
                        "reuse_value": "线索补给和代价抉择。",
                    }
                ],
                "rules": {
                    "world_rules": ["城中术法必须以记忆作抵押。"],
                    "forbidden": ["不能让主角突然无代价突破。"],
                },
                "plot_arc": {
                    "volume": "第一卷：影子里的旧案",
                    "goal": "林烬掌握第一份旧案证据。",
                    "turning_points": ["旧书楼残页", "巡夜钟试探", "主角公开反击"],
                    "opening_hook": "用旧书楼残页引出主角秘密能力，并埋下巡夜钟伏笔。",
                },
            },
        ),
        "wiki_sync_plan": agent_output(
            preview="wiki 同步计划已准备。",
            handoff="写入 story-bible、characters、settings，并建立双向链接。",
            data={"write_plan": ["story-bible.md", "characters/protagonist.md"]},
        ),
    }


def agent_output(preview: str, handoff: str, data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "preview": preview,
        "handoff": handoff,
        "data": data,
        "open_questions": [],
        "risks": [],
        "wiki_refs": [],
        "change_declarations": [],
    }


def event(run_id: str, seq: int, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "eventId": f"{run_id}-{seq}",
        "runId": run_id,
        "timestamp": 1782487124000 + seq,
        "schemaVersion": 1,
        "actor": "test",
        "type": event_type,
        "payload": payload,
    }


def write_blob(run_dir: Path, name: str, payload: Any) -> Dict[str, Any]:
    path = run_dir / "blobs" / name
    encoded = json.dumps(payload, ensure_ascii=False)
    path.write_text(encoded, encoding="utf-8")
    return {
        "outputHash": f"test:{name}",
        "outputPath": str(path),
        "outputBytes": len(encoded.encode("utf-8")),
        "outputSchemaVersion": 1,
        "contentType": "application/json",
    }


def write_events(run_dir: Path, events: List[Dict[str, Any]]) -> None:
    (run_dir / "events.ndjson").write_text(
        "\n".join(json.dumps(item, ensure_ascii=False) for item in events) + "\n",
        encoding="utf-8",
    )


def write_fake_llmwiki(path: Path) -> None:
    path.write_text("#!/bin/sh\necho planned \"$@\"\n", encoding="utf-8")
    path.chmod(0o755)


if __name__ == "__main__":
    unittest.main()
