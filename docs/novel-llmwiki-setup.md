# Novel llmwiki Setup Runbook

本 runbook 说明如何把本项目的小说 `wiki-bundle` 接到 [lucasastorian/llmwiki](https://github.com/lucasastorian/llmwiki)。它只定义安全接入步骤；不把草稿、候选设定或未审批内容自动写入长期知识库。

## 当前边界

- `python3 -m botmux_novel wiki-bundle` 只写本地 Markdown 审核包：`wiki/novels/{project_slug}/`。
- `python3 -m botmux_novel llmwiki-sync` 默认只生成同步计划；传 `--approve` 后才把审核包写入 llmwiki workspace 的 Markdown source-of-truth 文件树。
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
  --approve
```

6. 用 llmwiki 打开小说项目目录。

```bash
llmwiki open /path/to/novel-project
```

7. 生成 MCP 配置，并把该 workspace 暴露给需要读写的 bot harness。

```bash
llmwiki mcp-config /path/to/novel-project
```

8. 给 bot 分配权限。

| Bot | llmwiki 权限 | 规则 |
| --- | --- | --- |
| `Novel-Director-Curator` | read/search/create/edit/append/lint | 写入前必须 humanGate，写后必须 lint。 |
| `Novel-Creative-Architect` | 无直接写权限；必要时由总导演提供引用摘要 | 豆包或创作候选不能直接进入长期事实。 |
| `Novel-Continuity-Validator` | read/search | 只读校验，不改页面，不重写 Story Bible。 |

## 写入门禁

任何 llmwiki 写入 workflow 或手工操作前，必须输出：

- `preview`：页面清单和核心变更摘要。
- `impact`：会影响哪些人物、关系、场景、伏笔、世界规则和章节。
- `source_refs`：来自 Story Bible、章节候选包或用户批准的哪一份材料。
- `rollback_plan`：误写后如何撤销或恢复。
- `lint_plan`：写后运行 llmwiki lint 的方式和错误处理策略。

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
```

再用真实小说项目执行一次：

```bash
python3 -m botmux_novel foundation --project /path/to/novel-project --title <title> --inspiration <brief>
python3 -m botmux_novel wiki-bundle --project /path/to/novel-project --project-slug <slug>
python3 -m botmux_novel llmwiki-sync --project /path/to/novel-project --project-slug <slug>
llmwiki open /path/to/novel-project
```

如果 llmwiki lint 报错，先修 Markdown bundle 或写入计划，不要继续章节生产。

## 尚未自动化

- 本仓库还没有自动安装 llmwiki 或创建 llmwiki workspace。
- 本仓库不直接调用 llmwiki MCP `create/edit/append`；`llmwiki-sync` 只写本地 workspace Markdown 文件树，MCP 写工具仍需由 `Novel-Director-Curator` 在 humanGate 后调用。
- 首次真实写入必须由用户审批 Story Bible 和 wiki 页面清单后再执行；CLI 层用 `--approve` 表示这个审批已经完成。
