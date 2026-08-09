"""Real MCP fetch/HTTP server (stdio)."""

from __future__ import annotations

import urllib.error
import urllib.request

from mcp.server import MCPServer

server = MCPServer("real-fetch")


def _fetch(url: str, max_chars: int = 4000) -> str:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "mcp-permission-layer-fetch/1.0"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = resp.read(max_chars + 1)
    text = data.decode("utf-8", errors="replace")
    if len(data) > max_chars:
        text = text[:max_chars] + "\n...[truncated]..."
    return text


@server.tool(name="http_request", description="Perform an HTTP GET request to a URL")
def http_request(url: str) -> str:
    try:
        return _fetch(url)
    except Exception as e:
        return f"ERROR: {e}"


@server.tool(name="fetch", description="Fetch URL content")
def fetch(url: str) -> str:
    return http_request(url)


@server.tool(name="web_fetch", description="Fetch web page content")
def web_fetch(url: str) -> str:
    return http_request(url)


if __name__ == "__main__":
    server.run()
