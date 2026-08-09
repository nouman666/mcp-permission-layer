"""
Simple defense baselines (B0–B3) for head-to-head comparison with B4 (full layer).
"""

from __future__ import annotations

import re
from typing import Any, Protocol

# Suspicious keywords for definition-scanning baseline (B2)
SUSPICIOUS_DESC_KEYWORDS = [
    "ignore previous",
    "ignore all previous",
    "system prompt",
    "exfiltrat",
    "steal",
    "send to",
    "attacker",
    "malicious",
    "do not tell the user",
    "hidden instruction",
    "override",
    "bypass",
    "credential",
    "private key",
    "api key",
    "wget",
    "curl",
    "| bash",
    "; bash",
]

# High-risk tool name fragments for gateway-style filter (B3)
HIGH_RISK_NAME_FRAGMENTS = [
    "terminal", "bash", "shell", "exec", "run_command", "execute",
    "get_env", "getenv", "kill_process", "spawn", "python_exec",
    "code_interpreter",
]

# Static allowlist of "known safe" tool names (B1)
SAFE_TOOL_ALLOWLIST = {
    "read_file", "read_file_content", "view_file", "open_file", "get_file",
    "list_dir", "list_files", "ls", "glob", "search_files",
    "http_request", "fetch", "web_fetch", "get_url",
    "write_file", "create_file", "edit_file", "save_file",
}


class Defense(Protocol):
    name: str

    def decide(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        description: str | None = None,
    ) -> str:
        """Return 'allow' or 'deny'."""
        ...


class B0NoDefense:
    name = "B0_no_defense"

    def decide(self, tool_name, arguments=None, description=None) -> str:
        return "allow"


class B1StaticAllowlist:
    name = "B1_static_allowlist"

    def __init__(self, allowlist: set[str] | None = None) -> None:
        self.allowlist = {n.lower() for n in (allowlist or SAFE_TOOL_ALLOWLIST)}

    def decide(self, tool_name, arguments=None, description=None) -> str:
        return "allow" if tool_name.lower() in self.allowlist else "deny"


class B2DefinitionScanning:
    """Flag suspicious description keywords; no argument checks."""

    name = "B2_definition_scan"

    def __init__(self, keywords: list[str] | None = None) -> None:
        self.keywords = [k.lower() for k in (keywords or SUSPICIOUS_DESC_KEYWORDS)]

    def decide(self, tool_name, arguments=None, description=None) -> str:
        text = (description or "").lower()
        # Also scan tool name lightly for obvious poison markers
        blob = f"{tool_name} {text}"
        for kw in self.keywords:
            if kw in blob:
                return "deny"
        return "allow"


class B3GatewayFilter:
    """
    Lightweight gateway-style filter:
      - block high-risk tool names
      - block obvious shell / attacker URL patterns in arguments
    """

    name = "B3_gateway_filter"
    ATTACKER_URL = re.compile(
        r"https?://[^/\s]*(attacker|evil|exfil|malware|pastebin)[^/\s]*",
        re.IGNORECASE,
    )
    SHELLISH = re.compile(r"[|;&`]|\$\(|curl\s|wget\s|\bbash\b", re.IGNORECASE)

    def decide(self, tool_name, arguments=None, description=None) -> str:
        name = tool_name.lower()
        for frag in HIGH_RISK_NAME_FRAGMENTS:
            if frag in name:
                return "deny"
        for value in (arguments or {}).values():
            if not isinstance(value, str):
                continue
            if self.ATTACKER_URL.search(value) or self.SHELLISH.search(value):
                return "deny"
            # crude sensitive-path block
            low = value.lower()
            if any(x in low for x in (".ssh", ".aws", ".env", "id_rsa", "credential")):
                return "deny"
        return "allow"


class B4FullLayer:
    """Wraps EnforcementProxy; ASK → DENY in automated runs."""

    name = "B4_full_layer"

    def __init__(self, proxy) -> None:
        self.proxy = proxy

    def decide(self, tool_name, arguments=None, description=None) -> str:
        from models import Decision
        decision, _ = self.proxy.handle_tool_call(tool_name, arguments or {})
        return "allow" if decision == Decision.ALLOW else "deny"


def all_simple_baselines() -> list[Defense]:
    return [B0NoDefense(), B1StaticAllowlist(), B2DefinitionScanning(), B3GatewayFilter()]
