# Novel llmwiki Setup Runbook

本 runbook 说明如何把本项目的小说 `wiki-bundle` 接到 [lucasastorian/llmwiki](https://github.com/lucasastorian/llmwiki)。它只定义安全接入步骤；不把草稿、候选设定或未审批内容自动写入长期知识库。

## 当前边界

- `python3 -m botmux_novel wiki-bundle` 只写本地 Markdown 审核包：`wiki/novels/{project_slug}/`。
- `python3 -m botmux_novel llmwiki-sync` 默认只生成同步计划；传 `--approve` 后才把审核包写入 llmwiki workspace 的 Markdown source-of-truth 文件树，传 `--lint` 后会执行写后 lint 门禁；若当前 llmwiki CLI 不支持 `lint` 子命令，则自动执行本地 `wiki-lint` fallback。
- 仓库内 workflow 只生成 Story Bible 候选包、章节候选包和同步计划。
- 真实 llmwiki 写入前必须经过 `Novel-Director-Curator` preview、影响面说明和 humanGate。
- `Novel-Creative-Architect` 不直接写 llmwiki；`Novel-Continuity-Validator` 只读检索和校验。

## 前置检查

```bash
command -v llmwiki
python3 --version
node --version
```

若 `llmwiki` 不存在，先按官方仓库安装。官方 README 说明 llmwiki 支持本地 workspace、MCP server、Markdown/PDF/DOCX/PPTX/TXT/HTML ingest、搜索、读取、页面创建和编辑等能力；本项目只依赖本地 Markdown workspace 与 MCP 读写能力。

当前本机已安装本地 llmwiki：

- 仓库副本：`/Users/xiaochen/.local/opt/llmwiki`
- PATH wrapper：`/Users/xiaochen/.local/bin/llmwiki`
- Python：`/Users/xiaochen/.local/opt/llmwiki/.venv/bin/python`
- 当前安装提交：`542561d`

安装副本的 `llmwiki` 入口脚本已固定到 venv Python，确保 `llmwiki mcp-config` 输出的仓库脚本路径也能独立运行。

## 推荐目录

优先把单个小说项目目录作为 llmwiki workspace，这样本地 runtime、wiki bundle 和 llmwiki 索引指向同一份文件树：

```text
novel-project/
  bible/
  story.md
  characters/
  settings/
  manuscript/
    final/
  publish/
    fanqie/
  tracking/
  comms/
    handoffs/
    decisions/
  runs/
  wiki/
    novels/
      {project_slug}/
    llmwiki-workspace/
```

不要把多个无关小说混到同一个 workspace，除非它们共享世界观且用户明确批准。

推荐先初始化独立小说目录：

```bash
python3 -m botmux_novel project-init \
  --project /Users/xiaochen/NovelProjects/sanguo-daily-strategy-resources \
  --project-slug sanguo-daily-strategy-resources \
  --title 三国：每日战略资源，只能建设辖区 \
  --genre "三国历史脑洞 / 系统种田 / 领地经营 / 争霸" \
  --target-length "长篇连载，约150万字"
```

单本小说可以在自己的目录单独启用私有 git。建议版本化 `bible/`、`manuscript/final/`、`publish/fanqie/`、`tracking/` 和 `comms/decisions/`；`runs/`、bot 临时笔记、SQLite、日志和 `wiki/llmwiki-workspace/` 默认本地管理。

## 建库流程

推荐真实项目先走启动包。它会串联开书设定、项目内 wiki 审核包、llmwiki dry-run sync plan、MCP 配置和人工审批包。它不会执行 approved sync、不会覆盖外部 llmwiki workspace，也不会重建索引：

```bash
python3 -m botmux_novel novel-bootstrap \
  --project /path/to/novel-project \
  --title 影钟旧案 \
  --inspiration "一个背负旧案污名的少年，在巡夜钟声中发现妹妹影子会说真话。" \
  --project-slug shadow-clock-case
```

产物在 `runs/{bootstrap_run_id}/approval-package.md` 和 `approval-package.json`，写入前会按 `approval-package.schema.json` 校验必填字段和基础类型。审批通过前先执行 `approval-check --apply-dry-run`，它会再次检查 schema，并校验审核材料、humanGate 命令、llmwiki preview、MCP 角色策略、真实 BotMux 首章 workflow 命令和 dry-run apply 路径。审批通过后先执行其中的 `approval-decision --decision approve` 命令，记录 reviewer、notes、timestamp 和历史；再执行 `approval-apply --approve`。`approval-decision` 和 `approval-apply` 读取审批包时都会执行同一 schema 校验。`approval-apply` 会读取审批包中的 project、slug、workspace 和 llmwiki 配置；如果目标 workspace 还没有 llmwiki index，会先初始化；底层仍调用 `llmwiki-sync --approve --reindex --lint`，CLI 不支持 lint 时会运行本地 `wiki-lint` fallback，lint 返回非 0 时写入结果为 `failed`。完成知识库写入后，可继续执行审批包里的 `next_actions.chapter_workflow_command`，用已批准的 `foundation.json` 参数启动真实三 bot 首章 workflow；如只想本地 smoke，可执行 `next_actions.chapter_start_command`。

如果开书设定先由真实 BotMux `novel-story-foundation` 三 bot workflow 产出，先生成并审阅启动命令；真实 run 完成后导出 workflow 结果 JSON，再导入同一套本地审批链路：

```bash
python3 -m botmux_novel workflow-foundation-command \
  --project-slug shadow-clock-case \
  --title 影钟旧案 \
  --inspiration "一个背负旧案污名的少年，在巡夜钟声中发现妹妹影子会说真话。" \
  --genre 东方悬疑奇幻 \
  --target-length 长篇

python3 -m botmux_novel workflow-export \
  --run-id <botmux-run-id> \
  > /path/to/novel-story-foundation-result.json

python3 -m botmux_novel workflow-foundation-import \
  --workflow-result /path/to/novel-story-foundation-result.json \
  --project /path/to/novel-project \
  --project-slug shadow-clock-case
```

该导入会校验 `story_bible_package` 和 `wiki_sync_plan` 节点输出契约，保存原始 workflow result、节点输出和规范化 `foundation.json`，然后生成 wiki bundle、llmwiki dry-run sync plan、MCP config 和 `approval-package.md|json`。后续仍执行同一套 `approval-check`、`approval-decision`、`approval-apply` 和 `chapter` 命令。

```bash
python3 -m botmux_novel approval-check \
  --approval-package /path/to/novel-project/runs/<bootstrap-run-id>/approval-package.json \
  --apply-dry-run

python3 -m botmux_novel approval-decision \
  --approval-package /path/to/novel-project/runs/<bootstrap-run-id>/approval-package.json \
  --decision approve \
  --reviewer human \
  --notes "Approved after reviewing approval-package.md and wiki bundle."

python3 -m botmux_novel approval-apply \
  --approval-package /path/to/novel-project/runs/<bootstrap-run-id>/approval-package.json \
  --approve

python3 -m botmux_novel chapter \
  --project /path/to/novel-project \
  --chapter-number 1 \
  --foundation-json /path/to/novel-project/runs/<foundation-run-id>/foundation.json
```

如果章节正文由真实 BotMux `novel-chapter-production` workflow 产出，完成 humanGate 后可导入本地章节文件和归档：

```bash
python3 -m botmux_novel chapter-workflow-import \
  --workflow-result /path/to/novel-chapter-production-result.json \
  --project /path/to/novel-project \
  --foundation-json /path/to/novel-project/runs/<foundation-run-id>/foundation.json
```

该命令只写本地 `manuscript/`、`tracking/`、`runs/archive-{chapter}.json`、trace 和下一章 handoff；不写 llmwiki。成功导入会从现有 `runs/archive-*.json` 汇总 `project.yaml.archived_chapters`，保留多章 workflow 导入历史。下一章 handoff 里的 BotMux workflow 命令会携带本章归档摘要作为 `priorContext`，并保留 `wordTarget`、`mode` 和下一章目标；若传入 `--foundation-json`，本地 runtime 命令也会带 `--chapter-goal`。同一 handoff 的 `knowledge_handoff` 会给出重新运行 `wiki-bundle`、生成 dry-run `llmwiki-sync --reindex --lint` 计划，以及 humanGate 后 `--approve` 同步的命令。后续再次运行 `wiki-bundle` 时会自动把已有 `runs/archive-*.json`、定稿正文、事实、时间线、伏笔和人物状态纳入本地审核包；真正写入仍需要 `llmwiki-sync --approve` 或其他 humanGate-approved sync。

章节定稿后，如需准备番茄后台上传素材，使用本地导出命令：

```bash
python3 -m botmux_novel fanqie-export \
  --project /path/to/novel-project \
  --title 影钟旧案
```

导出产物为 `publish/fanqie/chapters/*.txt`、`publish/fanqie/book.txt` 和 `publish/fanqie/upload-checklist.md`。该命令只整理 UTF-8 纯文本，不调用番茄后台 API。

手动拆步流程如下：

1. 生成或更新开书资产。

```bash
python3 -m botmux_novel foundation \
  --project /path/to/novel-project \
  --title 影钟旧案 \
  --inspiration "一个背负旧案污名的少年，在巡夜钟声中发现妹妹影子会说真话。"
```

2. 导出本地 wiki 审核包。

```bash
python3 -m botmux_novel wiki-bundle \
  --project /path/to/novel-project \
  --project-slug shadow-clock-case
```

如果项目已有章节归档，审核包会额外包含 `chapter-archive.md`、`timeline.md`、`character-state.md` 和 `chapters/{chapter}.md`。

3. 人工审核 `wiki/novels/shadow-clock-case/` 下的 Markdown 页面。

4. 生成同步计划，确认页面清单、影响面和回滚策略。

```bash
python3 -m botmux_novel llmwiki-sync \
  --project /path/to/novel-project \
  --project-slug shadow-clock-case
```

5. 审批后把 Markdown bundle 写入 llmwiki workspace。若 workspace 就是小说项目目录，可省略 `--workspace`。

```bash
python3 -m botmux_novel llmwiki-sync \
  --project /path/to/novel-project \
  --project-slug shadow-clock-case \
  --workspace /path/to/novel-project \
  --approve \
  --reindex \
  --lint

python3 -m botmux_novel wiki-lint \
  --workspace /path/to/novel-project
```

6. 用 llmwiki 打开小说项目目录。

```bash
llmwiki open /path/to/novel-project
```

7. 生成项目级 MCP 配置片段和角色绑定策略。推荐先用仓库命令输出 Codex TOML、标准 MCP JSON、角色权限和 humanGate 规则；该命令不会修改全局配置。

```bash
python3 -m botmux_novel llmwiki-mcp-config \
  --workspace /path/to/novel-project \
  --project-slug shadow-clock-case
```

输出中的 `codex_toml` 适合加入 Codex `mcp_servers.*` 配置；`mcp_json` 与官方 `llmwiki mcp-config` 的结构一致，适合其他 MCP client。

8. 如需核对官方 llmwiki 输出，可运行：

```bash
llmwiki mcp-config /path/to/novel-project
```

9. 给 bot 分配权限。

| Bot | llmwiki 权限 | 规则 |
| --- | --- | --- |
| `Novel-Director-Curator` | read/search/create/edit/append/lint | 写入前必须 humanGate，写后必须 lint。 |
| `Novel-Creative-Architect` | 不直接配置 llmwiki MCP；必要时由总导演提供引用摘要 | 豆包或创作候选不能直接进入长期事实。 |
| `Novel-Continuity-Validator` | read/search | 只读校验，不改页面，不重写 Story Bible。 |

## 写入门禁

任何 llmwiki 写入 workflow 或手工操作前，必须输出：

- `preview`：页面清单和核心变更摘要。
- `impact`：会影响哪些人物、关系、场景、伏笔、世界规则和章节。
- `source_refs`：来自 Story Bible、章节候选包或用户批准的哪一份材料。
- `rollback_plan`：误写后如何撤销或恢复。
- `lint_plan`：写后运行 llmwiki lint 或本地 `wiki-lint` fallback 的方式和错误处理策略。
- `decision_record`：通过 `approval-decision` 写入审批包的 reviewer、decision、notes 和 `decided_at`。

禁止写入：

- 未审批草稿和豆包候选原文。
- 与已确认 Story Bible 冲突但没有变更声明的设定。
- 未标注 `proposed` / `confirmed` / `deprecated` 状态的长期事实。
- 会提前泄露终局、核心反转或禁区设定的页面。

## 验证

接入后至少跑：

```bash
python3 -m unittest discover -s tests -v
/Users/xiaochen/.botmux/bin/botmux workflow validate workflows/novel-story-foundation.workflow.json
/Users/xiaochen/.botmux/bin/botmux workflow validate workflows/novel-chapter-production.workflow.json
llmwiki --help
python3 -m botmux_novel readiness --bootstrap-smoke
python3 -m botmux_novel readiness --approval-apply-smoke
python3 -m botmux_novel readiness --series-smoke --smoke-chapter-count 20
python3 -m botmux_novel readiness --bootstrap-smoke --approval-apply-smoke --series-smoke --smoke-chapter-count 20 --llmwiki-smoke
python3 -m botmux_novel llmwiki-mcp-config --workspace /path/to/novel-project --project-slug <slug>
```

再用真实小说项目执行一次：

```bash
python3 -m botmux_novel foundation --project /path/to/novel-project --title <title> --inspiration <brief>
python3 -m botmux_novel wiki-bundle --project /path/to/novel-project --project-slug <slug>
python3 -m botmux_novel llmwiki-sync --project /path/to/novel-project --project-slug <slug>
python3 -m botmux_novel wiki-lint --workspace /path/to/novel-project
llmwiki init /path/to/novel-project
llmwiki lint /path/to/novel-project  # optional when this llmwiki build exposes a lint subcommand
llmwiki reindex /path/to/novel-project
llmwiki mcp-config /path/to/novel-project
```

如果 llmwiki lint 或本地 `wiki-lint` 报错，先修 Markdown bundle 或写入计划，不要继续章节生产。

## 尚未自动化

- 本仓库还没有自动安装 llmwiki；当前安装是本机一次性环境准备。
- 本仓库不直接调用 llmwiki MCP `create/edit/append`；`llmwiki-sync` 只写本地 workspace Markdown 文件树，MCP 写工具仍需由 `Novel-Director-Curator` 在 humanGate 后调用。
- 首次真实写入必须由用户审批 Story Bible 和 wiki 页面清单后再执行；正式 CLI 路径用 `approval-decision --decision approve` 记录审批，再用 `approval-apply --approve` 执行写入、lint 和 reindex。
