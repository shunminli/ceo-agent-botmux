from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from .llmwiki_sync import resolve_executable, validate_project_slug


DEFAULT_CODEX_STARTUP_TIMEOUT_SEC = 20


@dataclass(frozen=True)
class NovelLlmwikiMcpConfigRequest:
    workspace_path: Path
    project_slug: str
    server_name: Optional[str] = None
    llmwiki_bin: str = "llmwiki"
    codex_startup_timeout_sec: int = DEFAULT_CODEX_STARTUP_TIMEOUT_SEC


@dataclass(frozen=True)
class NovelLlmwikiMcpConfigResult:
    status: str
    project_slug: str
    workspace_path: Path
    server_name: str
    llmwiki_command: str
    llmwiki_available: bool
    mcp_json: Dict[str, Any]
    codex_toml: str
    role_bindings: List[Dict[str, Any]]
    human_gate_policy: Dict[str, Any]
    warnings: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "project_slug": self.project_slug,
            "workspace_path": str(self.workspace_path),
            "server_name": self.server_name,
            "llmwiki_command": self.llmwiki_command,
            "llmwiki_available": self.llmwiki_available,
            "mcp_json": self.mcp_json,
            "codex_toml": self.codex_toml,
            "role_bindings": self.role_bindings,
            "human_gate_policy": self.human_gate_policy,
            "warnings": self.warnings,
        }


class NovelLlmwikiMcpConfigBuilder:
    def build(self, request: NovelLlmwikiMcpConfigRequest) -> NovelLlmwikiMcpConfigResult:
        project_slug = validate_project_slug(request.project_slug)
        workspace_path = request.workspace_path.expanduser().resolve()
        server_name = validate_server_name(request.server_name or default_server_name(project_slug))
        if request.codex_startup_timeout_sec < 1:
            raise ValueError("codex_startup_timeout_sec must be positive")

        llmwiki_executable = resolve_executable(request.llmwiki_bin)
        llmwiki_command = llmwiki_executable if llmwiki_executable is not None else request.llmwiki_bin
        warnings: List[str] = []
        if llmwiki_executable is None:
            warnings.append(f"llmwiki executable not found: {request.llmwiki_bin}; generated config will not run until it is installed")

        mcp_json = {
            "mcpServers": {
                server_name: {
                    "command": llmwiki_command,
                    "args": ["mcp", str(workspace_path)],
                }
            }
        }
        status = "ready" if not warnings else "ready_with_warnings"
        return NovelLlmwikiMcpConfigResult(
            status=status,
            project_slug=project_slug,
            workspace_path=workspace_path,
            server_name=server_name,
            llmwiki_command=llmwiki_command,
            llmwiki_available=llmwiki_executable is not None,
            mcp_json=mcp_json,
            codex_toml=render_codex_toml(
                server_name=server_name,
                command=llmwiki_command,
                args=["mcp", str(workspace_path)],
                startup_timeout_sec=request.codex_startup_timeout_sec,
            ),
            role_bindings=role_bindings(server_name),
            human_gate_policy=human_gate_policy(project_slug),
            warnings=warnings,
        )


def default_server_name(project_slug: str) -> str:
    return f"llmwiki-novel-{project_slug}"


def validate_server_name(server_name: str) -> str:
    name = server_name.strip()
    if re.fullmatch(r"[A-Za-z0-9_-]{1,80}", name) is None:
        raise ValueError("server_name must use 1-80 letters, digits, hyphen, or underscore")
    return name


def render_codex_toml(*, server_name: str, command: str, args: List[str], startup_timeout_sec: int) -> str:
    return "\n".join(
        [
            f"[mcp_servers.{server_name}]",
            f"command = {toml_string(command)}",
            f"args = {toml_array(args)}",
            f"startup_timeout_sec = {startup_timeout_sec}",
            "",
        ]
    )


def toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def toml_array(values: List[str]) -> str:
    return "[" + ", ".join(toml_string(value) for value in values) + "]"


def role_bindings(server_name: str) -> List[Dict[str, Any]]:
    return [
        {
            "bot": "Novel-Director-Curator",
            "configure_mcp_server": True,
            "server_name": server_name,
            "allowed_llmwiki_tools": ["guide", "list_knowledge_bases", "search", "read", "create", "edit", "append", "lint"],
            "write_gate": "create/edit/append require preview, impact, source_refs, rollback_plan, lint_plan, and humanGate approval",
        },
        {
            "bot": "Novel-Creative-Architect",
            "configure_mcp_server": False,
            "server_name": None,
            "allowed_llmwiki_tools": [],
            "write_gate": "no direct llmwiki MCP access; use Director-provided reference summaries",
        },
        {
            "bot": "Novel-Continuity-Validator",
            "configure_mcp_server": True,
            "server_name": server_name,
            "allowed_llmwiki_tools": ["guide", "search", "read"],
            "write_gate": "read-only role; never call create/edit/append or mutate project memory",
        },
    ]


def human_gate_policy(project_slug: str) -> Dict[str, Any]:
    return {
        "project_namespace": f"/wiki/novels/{project_slug}/",
        "required_before_writes": ["preview", "impact", "source_refs", "rollback_plan", "lint_plan", "humanGate approval"],
        "forbidden_writes": [
            "unapproved drafts",
            "raw creative-assist candidates",
            "facts without proposed/confirmed/deprecated status",
            "changes that conflict with the confirmed Story Bible without change_declarations",
        ],
        "post_write": ["run llmwiki lint", "run llmwiki reindex when local source files changed", "record sync plan path in the Director handoff"],
        "note": "Generated config does not enforce MCP tool ACLs; role boundaries are enforced by bot identity prompts and workflow gates.",
    }
