from __future__ import annotations

import json
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = REPO_ROOT / "workflows"
INSTALLED_WORKFLOW_DIR = Path.home() / ".botmux" / "workflows"

DIRECTOR_BOT = "cli_aab42d6152f89be8"
CREATIVE_BOT = "cli_aab42e1c87385bfc"
VALIDATOR_BOT = "cli_aab42e443bf89bde"

CONTRACT_FIELDS = {
    "preview",
    "handoff",
    "data",
    "open_questions",
    "risks",
    "wiki_refs",
    "change_declarations",
}

NO_WRITE_MARKERS = ("不写", "不写入", "不要写入", "不要实际写入", "不执行外部写入")


EXPECTED_WORKFLOWS = {
    "novel-story-foundation.workflow.json": {
        "workflow_id": "novel-story-foundation",
        "params": {"projectSlug", "title", "inspiration", "genre", "targetLength", "mode"},
        "nodes": {
            "intake_brief": DIRECTOR_BOT,
            "context_scan": DIRECTOR_BOT,
            "creative_foundation": CREATIVE_BOT,
            "continuity_review": VALIDATOR_BOT,
            "foundation_revision": CREATIVE_BOT,
            "story_bible_package": DIRECTOR_BOT,
            "wiki_sync_plan": DIRECTOR_BOT,
        },
        "human_gates": {"story_bible_package"},
    },
    "novel-chapter-production.workflow.json": {
        "workflow_id": "novel-chapter-production",
        "params": {
            "projectSlug",
            "title",
            "storyBible",
            "chapterNumber",
            "chapterGoal",
            "priorContext",
            "wordTarget",
            "mode",
        },
        "nodes": {
            "chapter_prepare": DIRECTOR_BOT,
            "chapter_blueprint": CREATIVE_BOT,
            "chapter_draft": CREATIVE_BOT,
            "continuity_review": VALIDATOR_BOT,
            "chapter_revision": CREATIVE_BOT,
            "director_approval_package": DIRECTOR_BOT,
            "archive_plan": DIRECTOR_BOT,
        },
        "human_gates": {"director_approval_package"},
    },
}


IDENTITY_DOCS = {
    DIRECTOR_BOT: ("Novel-Director-Curator", REPO_ROOT / "agents" / "novel-director-curator.identity.md"),
    CREATIVE_BOT: ("Novel-Creative-Architect", REPO_ROOT / "agents" / "novel-creative-architect.identity.md"),
    VALIDATOR_BOT: ("Novel-Continuity-Validator", REPO_ROOT / "agents" / "novel-continuity-validator.identity.md"),
}


def load_workflow(filename: str) -> dict:
    return json.loads((WORKFLOW_DIR / filename).read_text(encoding="utf-8"))


class NovelWorkflowTemplateTest(unittest.TestCase):
    def test_templates_define_expected_team_contracts(self) -> None:
        for filename, expected in EXPECTED_WORKFLOWS.items():
            with self.subTest(filename=filename):
                workflow = load_workflow(filename)
                self.assertEqual(workflow["workflowId"], expected["workflow_id"])
                self.assertEqual(workflow["version"], 1)
                self.assertEqual(set(workflow["params"].keys()), expected["params"])
                self.assertEqual(set(workflow["nodes"].keys()), set(expected["nodes"].keys()))

                human_gates = set()
                for node_name, bot_id in expected["nodes"].items():
                    node = workflow["nodes"][node_name]
                    self.assertEqual(node["type"], "subagent")
                    self.assertEqual(node["bot"], bot_id)
                    self.assertTrue(any(marker in node["prompt"] for marker in NO_WRITE_MARKERS), node_name)
                    self.assertIn("llmwiki", node["prompt"])

                    schema = node["outputSchema"]
                    self.assertTrue(CONTRACT_FIELDS.issubset(set(schema["required"])))
                    self.assertEqual(schema["properties"]["handoff"]["type"], "string")

                    if "humanGate" in node:
                        human_gates.add(node_name)
                        self.assertEqual(node["humanGate"]["stage"], "before")
                        self.assertEqual(node["humanGate"]["onTimeout"], "fail")
                        self.assertIn("不写入", node["humanGate"]["prompt"])

                self.assertEqual(human_gates, expected["human_gates"])

    def test_workflow_bot_ids_have_matching_identity_documents(self) -> None:
        used_bot_ids = {
            bot_id
            for expected in EXPECTED_WORKFLOWS.values()
            for bot_id in expected["nodes"].values()
        }
        self.assertEqual(used_bot_ids, set(IDENTITY_DOCS.keys()))

        for bot_id, (role_name, path) in IDENTITY_DOCS.items():
            with self.subTest(bot_id=bot_id):
                text = path.read_text(encoding="utf-8")
                self.assertIn(role_name, text)
                self.assertIn("统一输出契约", text)
                self.assertIn("handoff", text)

    def test_installed_workflows_match_repo_templates_when_available(self) -> None:
        for filename in EXPECTED_WORKFLOWS:
            with self.subTest(filename=filename):
                installed_path = INSTALLED_WORKFLOW_DIR / filename
                if not installed_path.exists():
                    self.skipTest(f"installed workflow missing: {installed_path}")
                repo_payload = json.loads((WORKFLOW_DIR / filename).read_text(encoding="utf-8"))
                installed_payload = json.loads(installed_path.read_text(encoding="utf-8"))
                self.assertEqual(installed_payload, repo_payload)


if __name__ == "__main__":
    unittest.main()
