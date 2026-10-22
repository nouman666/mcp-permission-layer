"""Opt-in MCP endpoint for the administrator-approved HTTP reference adapter.
No contract or server identity is accepted from client arguments.
"""
import argparse
import asyncio
from dataclasses import asdict
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from mcp import types
from mcp.server.lowlevel.server import Server
from mcp.server.stdio import stdio_server
from trusted_http_contract import ApprovedHttpRouteBinding, ApprovedHttpRouteService
from policy_manager import PolicyManager
from models import Decision, ToolCall
from live_outcomes import stamp_result

async def run(args):
    manifest = json.loads(Path(args.manifest).read_text())
    source = ROOT / manifest['source']
    binding = ApprovedHttpRouteBinding.load(source, manifest['sha256'])
    service = ApprovedHttpRouteService(binding, PolicyManager().load(args.policy))
    app = Server('approved-http-route-reference')
    async def list_tools(req):
        return types.ServerResult(types.ListToolsResult(tools=[types.Tool(
            name='http_request', description='HTTPS GET; host/path is a remote route, never a local file',
            inputSchema=binding._implementation.INPUT_SCHEMA)]))
    async def call_tool(req):
        params = req.params
        if params.name != 'http_request':
            result = types.CallToolResult(content=[types.TextContent(type='text', text='Unsupported tool')], isError=True)
            return types.ServerResult(stamp_result(result, 'deny', 'not_forwarded'))
        decision, record = service.checker.evaluate(ToolCall(name=params.name, arguments=params.arguments or {}), service.policy)
        with open(args.log, 'a') as log:
            log.write(json.dumps(asdict(record), default=lambda x: sorted(x) if isinstance(x, set) else str(x))+'\n')
        if decision != Decision.ALLOW:
            result = types.CallToolResult(content=[types.TextContent(type='text', text='Policy or contract denied request')], isError=True)
            return types.ServerResult(stamp_result(result, 'deny', 'not_forwarded'))
        try:
            output = await asyncio.to_thread(binding.invoke, params.name, params.arguments or {})
            result = types.CallToolResult(content=[types.TextContent(type='text', text=output)])
            return types.ServerResult(stamp_result(result, 'allow', 'upstream_ok'))
        except Exception as exc:
            result = types.CallToolResult(content=[types.TextContent(type='text', text=str(exc))], isError=True)
            return types.ServerResult(stamp_result(result, 'allow', 'upstream_error'))
    app.request_handlers[types.ListToolsRequest] = list_tools
    app.request_handlers[types.CallToolRequest] = call_tool
    async with stdio_server() as (rd, wr):
        await app.run(rd, wr, app.create_initialization_options())

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--manifest', required=True)
    p.add_argument('--policy', default=str(ROOT/'policies/limited_network.yaml'))
    p.add_argument('--log', required=True)
    asyncio.run(run(p.parse_args()))
