"""Real MCP git helper server (stdio)."""

from __future__ import annotations

import subprocess
from pathlib import Path

from mcp.server import MCPServer

server = MCPServer("real-git")
REPO = Path(__file__).resolve().parents[1]


@server.tool(name="read_file", description="Read a file from the git working tree")
def read_file(path: str) -> str:
    p = (REPO / path).resolve()
    if not str(p).startswith(str(REPO.resolve())):
        return "ERROR: path outside repository"
    if not p.exists():
        return f"ERROR: not found: {path}"
    return p.read_text(encoding="utf-8", errors="replace")[:8000]


@server.tool(name="list_dir", description="List directory in repository")
def list_dir(path: str = ".") -> str:
    p = (REPO / path).resolve()
    if not p.exists():
        return f"ERROR: not found: {path}"
    entries = sorted(x.name for x in p.iterdir())
    return "\n".join(entries)


@server.tool(name="git_status", description="Run git status --short")
def git_status() -> str:
    try:
        completed = subprocess.run(
            ["git", "status", "--short"],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=10,
        )
        return (completed.stdout or completed.stderr or "(clean)")[:4000]
    except Exception as e:
        return f"ERROR: {e}"


if __name__ == "__main__":
    server.run()
