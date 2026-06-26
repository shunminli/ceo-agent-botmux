# Novel llmwiki Setup Runbook

本 runbook 说明如何把本项目的小说 `wiki-bundle` 接到 [lucasastorian/llmwiki](https://github.com/lucasastorian/llmwiki)。它只定义安全接入步骤；不把草稿、候选设定或未审批内容自动写入长期知识库。

## 当前边界

- `python3 -m botmux_novel wiki-bundle` 只写本地 Markdown 审核包：`wiki/novels/{project_slug}/`。
- `python3 -m botmux_novel llmwiki-sync` 默认只生成同步计划；传 `--approve` 后才把审核包写入 llmwiki workspace 的 Markdown source-of-truth 文件树，传 `--lint` 后会执行写后 lint 门禁；若当前 llmwiki CLI 不支持 `lint` 子命令，则跳过并返回 warning。
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
  story.md
  characters/
  settings/
  tracking/
  runs/
  wiki/
    novels/
      {project_slug}/
```

不要把多个无关小说混到同一个 workspace，除非它们共享世界观且用户明确批准。

## 建库流程

推荐真实项目先走启动包。它会串联开书设定、项目内 wiki 审核包、llmwiki dry-run sync plan、MCP 配置和人工审批包。它不会执行 approved sync、不会覆盖外部 llmwiki workspace，也不会重建索引：

```bash
python3 -m botmux_novel novel-bootstrap \
  --project /path/to/novel-project \
  --title 影钟旧案 \
  --inspiration "一个背负旧案污名的少年，在巡夜钟声中发现妹妹影子会说真话。" \
  --project-slug shadow-clock-case
```

产物在 `runs/{bootstrap_run_id}/approval-package.md` 和 `approval-package.json`。审批通过后先执行其中的 `approval-decision --decision approve` 命令，记录 reviewer、notes、timestamp 和历史；再执行 `approval-apply --approve`。`approval-apply` 会读取审批包中的 project、slug、workspace 和 llmwiki 配置；如果目标 workspace 还没有 llmwiki index，会先初始化；底层仍调用 `llmwiki-sync --approve --reindex --lint`，CLI 不支持 lint 时返回 warning，支持 lint 但返回非 0 时写入结果为 `failed`。完成知识库写入后，可继续执行审批包里的 `next_actions.chapter_start_command`，直接从批准的 `foundation.json` 生成首章。

```bash
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
- `lint_plan`：写后运行 llmwiki lint 的方式和错误处理策略。
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
llmwiki init /path/to/novel-project
llmwiki lint /path/to/novel-project
llmwiki reindex /path/to/novel-project
llmwiki mcp-config /path/to/novel-project
```

如果 llmwiki lint 报错，先修 Markdown bundle 或写入计划，不要继续章节生产。

## 尚未自动化

- 本仓库还没有自动安装 llmwiki；当前安装是本机一次性环境准备。
- 本仓库不直接调用 llmwiki MCP `create/edit/append`；`llmwiki-sync` 只写本地 workspace Markdown 文件树，MCP 写工具仍需由 `Novel-Director-Curator` 在 humanGate 后调用。
- 首次真实写入必须由用户审批 Story Bible 和 wiki 页面清单后再执行；正式 CLI 路径用 `approval-decision --decision approve` 记录审批，再用 `approval-apply --approve` 执行写入、lint 和 reindex。
