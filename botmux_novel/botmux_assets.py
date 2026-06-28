from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


REPO_ROOT = Path(__file__).resolve().parents[1]

WORKFLOW_FILES = [
    "novel-story-foundation.workflow.json",
    "novel-chapter-production.workflow.json",
]

ROLE_IDENTITIES = {
    "Novel-Director-Curator": "novel-director-curator.identity.md",
    "Novel-Creative-Architect": "novel-creative-architect.identity.md",
    "Novel-Continuity-Validator": "novel-continuity-validator.identity.md",
}

DEVELOPMENT_CLOSURE_PRINCIPLES = """## 开发闭环原则

当任务涉及研发、文档、配置、脚本、仓库治理或可交付物修改时，默认按以下闭环推进，除非用户明确要求更窄动作：

1. 先判断目标、成功标准、范围、影响面、风险、阻塞和真实验证方案。
2. 实施时修根因，不停在半成品；在当前影响面内处理相邻风险和验证缺口。
3. 需要对齐时，向用户说明目标、证据、偏差、完成比例和剩余工作。
4. 交付前优先用真实入口、真实依赖、代表性数据和可观察结果验证，不把 mock、dry-run 或孤立单测当成唯一完成证据。
5. 若代码语义、模块职责、功能行为或重要历史变化发生稳定改变，更新相关本地 memory 文档，只记录稳定知识，不写任务流水账。
6. 收尾时说明做了什么、影响范围、验证结果、剩余风险、待办和最终交付判断。
"""


@dataclass(frozen=True)
class BotmuxAssetSyncRequest:
    repo_path: Path = REPO_ROOT
    botmux_home: Path = Path.home() / ".botmux"
    write: bool = False
    backup: bool = True


@dataclass(frozen=True)
class BotmuxAssetAction:
    kind: str
    source_path: Path
    target_path: Path
    status: str
    backup_path: Optional[Path] = None

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "kind": self.kind,
            "source_path": str(self.source_path),
            "target_path": str(self.target_path),
            "status": self.status,
        }
        if self.backup_path is not None:
            payload["backup_path"] = str(self.backup_path)
        return payload


@dataclass(frozen=True)
class BotmuxAssetSyncResult:
    status: str
    repo_path: Path
    botmux_home: Path
    write: bool
    actions: List[BotmuxAssetAction]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "repo_path": str(self.repo_path),
            "botmux_home": str(self.botmux_home),
            "write": self.write,
            "actions": [action.to_dict() for action in self.actions],
        }


class BotmuxAssetSyncer:
    def sync(self, request: BotmuxAssetSyncRequest) -> BotmuxAssetSyncResult:
        repo_path = request.repo_path.expanduser().resolve()
        botmux_home = request.botmux_home.expanduser().resolve()
        actions: List[BotmuxAssetAction] = []

        for filename in WORKFLOW_FILES:
            source = repo_path / "workflows" / filename
            target = botmux_home / "workflows" / filename
            actions.append(
                self._sync_text_asset(
                    kind="workflow",
                    source_path=source,
                    target_path=target,
                    content=source.read_text(encoding="utf-8"),
                    write=request.write,
                    backup=request.backup,
                )
            )

        for role_name, identity_filename in ROLE_IDENTITIES.items():
            source = repo_path / "agents" / identity_filename
            target = botmux_home / "workspace" / role_name / "AGENTS.md"
            content = render_workspace_agents(role_name=role_name, identity_path=source)
            actions.append(
                self._sync_text_asset(
                    kind="workspace-agents",
                    source_path=source,
                    target_path=target,
                    content=content,
                    write=request.write,
                    backup=request.backup,
                )
            )

        status = "completed" if request.write else "planned"
        return BotmuxAssetSyncResult(
            status=status,
            repo_path=repo_path,
            botmux_home=botmux_home,
            write=request.write,
            actions=actions,
        )

    def _sync_text_asset(
        self,
        *,
        kind: str,
        source_path: Path,
        target_path: Path,
        content: str,
        write: bool,
        backup: bool,
    ) -> BotmuxAssetAction:
        if not source_path.exists():
            raise ValueError(f"source asset does not exist: {source_path}")

        existing = target_path.read_text(encoding="utf-8") if target_path.exists() else None
        if existing == content:
            return BotmuxAssetAction(kind=kind, source_path=source_path, target_path=target_path, status="unchanged")

        if not write:
            status = "would_update" if target_path.exists() else "would_create"
            return BotmuxAssetAction(kind=kind, source_path=source_path, target_path=target_path, status=status)

        backup_path = None
        target_path.parent.mkdir(parents=True, exist_ok=True)
        if backup and target_path.exists():
            backup_path = target_path.with_name(f"{target_path.name}.bak-{timestamp_suffix()}")
            shutil.copy2(target_path, backup_path)
        target_path.write_text(content, encoding="utf-8")
        status = "updated" if existing is not None else "created"
        return BotmuxAssetAction(
            kind=kind,
            source_path=source_path,
            target_path=target_path,
            status=status,
            backup_path=backup_path,
        )


def render_workspace_agents(*, role_name: str, identity_path: Path) -> str:
    identity_text = identity_path.read_text(encoding="utf-8").strip()
    return f"""# {role_name} Workspace Instructions

本文件由 `python3 -m botmux_novel botmux-assets --write` 从仓库身份文档生成。不要在 BotMux workspace 中长期手改；请先修改仓库 `agents/{identity_path.name}` 后重新同步。

用户最新明确要求优先；若本文件与更具体的任务说明、workflow prompt、代码注释或既有设计文档冲突，以更具体且更严格的要求为准。

## BotMux 身份绑定

- 你是 `{role_name}`。
- 你运行在 BotMux bot workspace 中，终端输出不能替代用户可见回复。
- 面向用户的关键结论、进度、阻塞和最终结果应返回给用户。
- 本文件只提供角色身份；单本小说项目上下文由本次任务的 `Project working directory` 或等价工作目录声明提供，不应写死在本文件中。

## Canonical Identity

{identity_text}

{DEVELOPMENT_CLOSURE_PRINCIPLES}
"""


def timestamp_suffix() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d%H%M%SZ")
