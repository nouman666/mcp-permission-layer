"""
Real MCP stdio enforcement proxy.

Client (Cursor / eval harness)
    --stdio JSON-RPC-->
this proxy (permission check)
    --stdio JSON-RPC-->
upstream MCP server (filesystem / fetch / git / shell)

Usage:
  python scripts/mcp_enforcement_proxy.py \\
      --policy policies/limited_network.yaml \\
      --server-name filesystem \\
      -- \\
      npx -y @modelcontextprotocol/server-filesystem /path/to/root
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mcp import ClientSession, StdioServerParameters, types  # noqa: E402
from mcp.client.stdio import stdio_client  # noqa: E402
from mcp.server.lowlevel.server import Server  # noqa: E402
from mcp.server.stdio import stdio_server  # noqa: E402

from models import Decision  # noqa: E402
from proxy import EnforcementProxy, always_deny_ask_handler  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="MCP permission enforcement proxy")
    parser.add_argument(
        "--policy",
        default=str(ROOT / "policies" / "limited_network.yaml"),
        help="Path to YAML policy",
    )
    parser.add_argument(
        "--log",
        default=str(ROOT / "logs" / "live_mcp_proxy.jsonl"),
        help="Audit log path",
    )
    parser.add_argument(
        "--server-name",
        default="upstream",
        help="Logical upstream server name (for audit)",
    )
    parser.add_argument(
        "--ask-mode",
        choices=("deny", "allow"),
        default="deny",
        help="Automated ASK handling (default deny)",
    )
    parser.add_argument(
        "upstream",
        nargs=argparse.REMAINDER,
        help="Upstream command after --",
    )
    return parser.parse_args(argv)


async def run_proxy(args: argparse.Namespace) -> None:
    upstream_args = list(args.upstream)
    if upstream_args and upstream_args[0] == "--":
        upstream_args = upstream_args[1:]
    if not upstream_args:
        raise SystemExit("Upstream command required after --")

    command, cmd_args = upstream_args[0], upstream_args[1:]
    Path(args.log).parent.mkdir(parents=True, exist_ok=True)

    ask_handler = always_deny_ask_handler if args.ask_mode == "deny" else (
        lambda *_: True
    )
    enforcer = EnforcementProxy(
        policy_path=args.policy,
        log_path=args.log,
        ask_handler=ask_handler,
    )

    params = StdioServerParameters(command=command, args=cmd_args, env=os.environ.copy())

    async with stdio_client(params) as (up_read, up_write):
        async with ClientSession(up_read, up_write) as upstream:
            await upstream.initialize()

            async def on_list_tools(ctx, params):
                result = await upstream.list_tools()
                return types.ListToolsResult(tools=result.tools)

            async def on_call_tool(ctx, params):
                name = params.name
                arguments = dict(params.arguments or {})
                decision, record = enforcer.handle_tool_call(
                    name=name,
                    arguments=arguments,
                    server=args.server_name,
                )
                if decision != Decision.ALLOW:
                    msg = (
                        f"PERMISSION DENIED by runtime enforcement layer "
                        f"(policy={record.policy_name}, "
                        f"categories={sorted(record.inferred_categories)}, "
                        f"high_risk={record.high_risk})"
                    )
                    return types.CallToolResult(
                        content=[types.TextContent(type="text", text=msg)],
                        is_error=True,
                    )

                # Forward to real upstream MCP server
                return await upstream.call_tool(name, arguments)

            app = Server(
                f"enforced-{args.server_name}",
                on_list_tools=on_list_tools,
                on_call_tool=on_call_tool,
            )

            init = app.create_initialization_options()
            async with stdio_server() as (client_read, client_write):
                await app.run(client_read, client_write, init)


def main() -> None:
    args = parse_args()
    # Keep stdout clean for MCP JSON-RPC: send logs to stderr only.
    asyncio.run(run_proxy(args))


if __name__ == "__main__":
    main()
