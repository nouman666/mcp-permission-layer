"""Real MCP git helper server (stdio)."""

from __future__ import annotations

import subprocess
import os
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

server = FastMCP("real-git")
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO/"src"))
from safe_files import read_under, open_under


@server.tool(name="read_file", description="Read a file from the git working tree")
def read_file(path: str) -> str:
    return read_under(REPO, path)


@server.tool(name="list_dir", description="List directory in repository")
def list_dir(path: str = ".") -> str:
    if path == '.':
        fd = os.open(REPO, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    else:
        fd = open_under(REPO, path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        return '\n'.join(sorted(os.listdir(fd)))
    finally:
        os.close(fd)


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
