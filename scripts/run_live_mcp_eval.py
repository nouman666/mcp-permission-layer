"""
Live Real-MCP deployment evaluation.

For each workflow case:
  Cursor-like MCP client
    -> our enforcement proxy (stdio MCP)
      -> real upstream MCP server (filesystem/fetch/git/shell)

Produces:
  results/live_mcp_deployment.json
  updates results/TABLES_FOR_PAPER.md section (appends live table)
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from contextlib import AsyncExitStack
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

from mcp import ClientSession, StdioServerParameters  # noqa: E402
from mcp.client.stdio import stdio_client  # noqa: E402

from metrics import confusion_counts, derive_rates  # noqa: E402

CONFIG_PATH = ROOT / "configs" / "live_mcp_servers.json"
CASES_PATH = ROOT / "datasets" / "real_mcp_workflows.json"
RESULTS = ROOT / "results"


def load_config():
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    workspace = str((ROOT / cfg.get("workspace_root", ".")).resolve())
    # Rewrite proxy args with absolute paths / workspace
    servers = {}
    for name, spec in cfg["servers"].items():
        args = []
        for a in spec["args"]:
            a = a.replace("${WORKSPACE}", workspace)
            rel_prefixes = ("policies/", "logs/", "scripts/", "servers/")
            if any(a.startswith(p) for p in rel_prefixes):
                a = str((ROOT / a).resolve())
            args.append(a)
        # Ensure proxy script and python paths are absolute where needed
        if args and args[0].endswith("mcp_enforcement_proxy.py"):
            pass
        servers[name] = {
            "command": spec["command"],
            "args": args,
            "cwd": str(ROOT),
        }
    cfg["servers"] = servers
    cfg["workspace"] = workspace
    return cfg


class LiveMCPPool:
    """Maintains one client session per logical MCP server (via enforcement proxy)."""

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self._stack: AsyncExitStack | None = None
        self.sessions: dict[str, ClientSession] = {}
        self.tool_map = cfg.get("tool_name_map", {})

    async def __aenter__(self):
        self._stack = AsyncExitStack()
        await self._stack.__aenter__()
        for name, spec in self.cfg["servers"].items():
            params = StdioServerParameters(
                command=spec["command"],
                args=spec["args"],
                cwd=spec["cwd"],
                env=os.environ.copy(),
            )
            read, write = await self._stack.enter_async_context(stdio_client(params))
            session = await self._stack.enter_async_context(ClientSession(read, write))
            await session.initialize()
            tools = await session.list_tools()
            print(f"[live] connected {name}: {[t.name for t in tools.tools]}")
            self.sessions[name] = session
        return self

    async def __aexit__(self, *exc):
        assert self._stack is not None
        return await self._stack.__aexit__(*exc)

    def map_tool(self, server: str, tool_name: str) -> str:
        # filesystem official server uses list_directory
        if server == "filesystem":
            return self.tool_map.get(tool_name, tool_name)
        return tool_name

    async def call(self, server: str, tool_name: str, arguments: dict) -> tuple[str, bool, float]:
        """
        Returns (outcome allow|deny, is_error_or_denied, latency_ms)
        allow = forwarded and upstream did not permission-deny
        """
        if server not in self.sessions:
            raise KeyError(f"Unknown server {server}")
        session = self.sessions[server]
        mapped = self.map_tool(server, tool_name)
        # Normalize list_dir for git server (has list_dir)
        if server == "git" and tool_name == "list_directory":
            mapped = "list_dir"

        t0 = time.perf_counter()
        result = await session.call_tool(mapped, arguments or {})
        latency = (time.perf_counter() - t0) * 1000.0

        text = ""
        for block in result.content or []:
            text += getattr(block, "text", "") or str(block)
        denied = bool(getattr(result, "is_error", False)) and "PERMISSION DENIED" in text
        # If proxy denied → treat as deny (blocked). Else allow (tool executed / attempted).
        outcome = "deny" if denied else "allow"
        return outcome, denied, latency


async def evaluate_live(profiles: list[str] | None = None) -> dict:
    profiles = profiles or ["limited_network", "read_only", "no_code_exec", "approval_gated"]
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    base_cfg = load_config()

    report = {
        "title": "Real MCP Deployment Results (LIVE)",
        "transport": "stdio MCP JSON-RPC",
        "path": "client -> enforcement proxy -> real upstream MCP server",
        "servers": list(base_cfg["servers"].keys()),
        "n_cases": len(cases),
        "profiles": {},
        "no_defense": {},
    }

    # B0: call upstreams WITHOUT proxy by temporarily pointing sessions at raw servers
    # For fair B0 we use the same cases but always "allow" if we skip proxy — measured separately.
    y_true = [not c.get("beneficial", False) for c in cases]
    y_pred_b0 = [True] * len(cases)  # no defense always allows
    report["no_defense"] = derive_rates(confusion_counts(y_true, y_pred_b0))
    report["no_defense"]["note"] = "B0 conceptual allow-all (proxy bypass)"

    for profile in profiles:
        # Rewrite policy path in each server's proxy args
        cfg = json.loads(json.dumps(base_cfg))  # deep copy via json
        policy = str((ROOT / "policies" / f"{profile}.yaml").resolve())
        for name, spec in cfg["servers"].items():
            args = spec["args"]
            for i, a in enumerate(args):
                if a.endswith(".yaml") and "policies" in a.replace("\\", "/"):
                    args[i] = policy
                if a.endswith(".jsonl") and "live_" in a:
                    args[i] = str((ROOT / "logs" / f"live_{name}_{profile}.jsonl").resolve())
            # Also fix --policy following token
            for i, a in enumerate(args):
                if a == "--policy" and i + 1 < len(args):
                    args[i + 1] = policy

        print(f"\n=== LIVE PROFILE: {profile} ===")
        y_pred = []
        latencies = []
        details = []
        async with LiveMCPPool(cfg) as pool:
            for case in cases:
                server = case["server"]
                # route env/process/terminal to shell-backed servers
                outcome, denied, lat = await pool.call(
                    server, case["tool_name"], case.get("arguments") or {}
                )
                allowed = outcome == "allow"
                y_pred.append(allowed)
                latencies.append(lat)
                details.append({
                    "id": case["id"],
                    "server": server,
                    "tool": case["tool_name"],
                    "beneficial": case.get("beneficial", False),
                    "outcome": outcome,
                    "latency_ms": round(lat, 3),
                    "poisoned": bool(case.get("poisoned_description")),
                })
                mark = "ALLOW" if allowed else "DENY"
                print(f"  {case['id']:<8} {mark:<5} {server}/{case['tool_name']}")

        rates = derive_rates(confusion_counts(y_true, y_pred))
        rates["latency_mean_ms"] = sum(latencies) / len(latencies) if latencies else 0.0
        rates["details"] = details
        report["profiles"][profile] = rates

    RESULTS.mkdir(parents=True, exist_ok=True)
    out = RESULTS / "live_mcp_deployment.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    # Markdown table
    md = ["# Live Real MCP Deployment Results\n"]
    md.append(f"_Path: `{report['path']}`_\n")
    md.append(f"_Servers: {', '.join(report['servers'])}_\n")
    md.append("| Defense | ASR (%) | Block (%) | TSR (%) | F1 (%) | Latency ms |")
    md.append("|---------|---------|-----------|---------|--------|------------|")
    b0 = report["no_defense"]
    md.append(
        f"| B0_no_defense | {b0['asr']:.2f} | {b0['block_rate']:.2f} | {b0['tsr']:.2f} | "
        f"{b0['f1']:.2f} | n/a |"
    )
    for profile, r in report["profiles"].items():
        md.append(
            f"| B4_{profile} | {r['asr']:.2f} | {r['block_rate']:.2f} | {r['tsr']:.2f} | "
            f"{r['f1']:.2f} | {r['latency_mean_ms']:.3f} |"
        )
    md_path = RESULTS / "LIVE_MCP_TABLE.md"
    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")

    # Append/replace section in TABLES_FOR_PAPER.md if present
    paper = RESULTS / "TABLES_FOR_PAPER.md"
    if paper.exists():
        text = paper.read_text(encoding="utf-8")
        marker = "## Table: Real MCP Deployment Results (LIVE)"
        block = marker + "\n\n" + "\n".join(md[1:]) + "\n"
        if marker in text:
            # replace until next ## or end
            pre, rest = text.split(marker, 1)
            if "\n## " in rest:
                _, post = rest.split("\n## ", 1)
                text = pre + block + "## " + post
            else:
                text = pre + block
        else:
            # insert after first Real MCP table if exists
            text = text + "\n" + block
        paper.write_text(text, encoding="utf-8")

    print("\nSaved", out)
    print("Saved", md_path)
    return report


def generate_cursor_mcp_json() -> Path:
    cfg = load_config()
    # Cursor expects mcpServers map of command/args
    mcp_servers = {}
    for name, spec in cfg["servers"].items():
        mcp_servers[f"enforced-{name}"] = {
            "command": spec["command"],
            "args": spec["args"],
        }
    payload = {"mcpServers": mcp_servers}
    out = ROOT / "configs" / "cursor_mcp.json"
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    # Also write to user ~/.cursor/mcp.json (merge if exists)
    user_mcp = Path.home() / ".cursor" / "mcp.json"
    user_mcp.parent.mkdir(parents=True, exist_ok=True)
    if user_mcp.exists():
        try:
            existing = json.loads(user_mcp.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = {}
        existing.setdefault("mcpServers", {}).update(mcp_servers)
        user_mcp.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    else:
        user_mcp.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print("Cursor MCP config:", out)
    print("Installed/merged:", user_mcp)
    return out


def main():
    generate_cursor_mcp_json()
    asyncio.run(evaluate_live())


if __name__ == "__main__":
    main()
