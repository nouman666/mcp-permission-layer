"""Real MCP shell/env/process server (stdio). Used behind the enforcement proxy."""

from __future__ import annotations

import os
import subprocess

from mcp.server.fastmcp import FastMCP

server = FastMCP("real-shell")


@server.tool(name="run_terminal", description="Run a shell command")
def run_terminal(cmd: str) -> str:
    try:
        completed = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=20,
        )
        out = (completed.stdout or "") + (completed.stderr or "")
        if completed.returncode != 0:
            raise RuntimeError(f"process exit {completed.returncode}: {out[:8000]}")
        return out[:8000] if out else f"(exit {completed.returncode})"
    except Exception as e:
        raise RuntimeError(str(e)) from e


@server.tool(name="get_env", description="Read an environment variable")
def get_env(name: str) -> str:
    return os.environ.get(name, "")


@server.tool(name="start_process", description="Start a background-like process command")
def start_process(cmd: str) -> str:
    # For evaluation safety we still execute synchronously with a short timeout.
    return run_terminal(cmd)


if __name__ == "__main__":
    server.run()
