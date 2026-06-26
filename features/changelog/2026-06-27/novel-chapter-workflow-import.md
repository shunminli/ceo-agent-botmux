Updated: 2026-06-27

# Novel Chapter Workflow Import

Added a bridge from real BotMux `novel-chapter-production` workflow output into the local chapter archive chain.

New command:

```bash
python3 -m botmux_novel chapter-workflow-import \
  --workflow-result /path/to/novel-chapter-production-result.json \
  --project /path/to/novel-project
```

The importer:

- Extracts and validates all seven chapter workflow node outputs.
- Writes local chapter blueprint, draft, revised manuscript, and source workflow artifacts.
- Writes `manuscript/final/{chapter}.md`, tracking YAML, and `runs/archive-{chapter}.json` only when Director approval and archive plan both pass.
- Records blocked imports without writing a final manuscript when the workflow result is not approved.
- Emits `runs/{run_id}/next-chapter-command.md|json` for the next BotMux workflow run, and a local runtime command when an approved `--foundation-json` is supplied.
- Does not write llmwiki; knowledge sync remains a separate humanGate-approved step.

Readiness now has `--chapter-import-smoke`, which imports a synthetic approved chapter workflow result and confirms final/archive/next handoff artifacts are created.
