"""
Category Inference Module
-------------------------
Infers the set of permission categories required by a tool call.
Design principles:
  - Over-approximate (safety first)
  - Deterministic
  - Explainable (reasons for each category)
  - Fail-closed for unknown tools
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
import re
import os


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class InferenceResult:
    categories: set[str] = field(default_factory=set)
    reasons: dict[str, list[str]] = field(default_factory=dict)
    high_risk: bool = False

    def add(self, category: str, reason: str) -> None:
        self.categories.add(category)
        self.reasons.setdefault(category, []).append(reason)


# ---------------------------------------------------------------------------
# Configuration (can later be moved to YAML)
# ---------------------------------------------------------------------------

# Strong name patterns → category
NAME_RULES: list[tuple[list[str], str]] = [
    # fs.read
    (["read_file", "read_file_content", "get_file", "cat", "list_dir",
      "list_files", "ls", "glob", "search_files", "view_file", "open_file",
      "list_directory"],
     "fs.read"),
    # fs.write
    (["write_file", "create_file", "edit_file", "delete_file", "remove_file",
      "mkdir", "rmdir", "move_file", "rename_file", "append_file", "save_file"],
     "fs.write"),
    # code.exec
    (["run_terminal", "execute_command", "run_command", "bash", "shell",
      "exec", "python_exec", "code_interpreter", "run_code", "terminal",
      "pwsh", "powershell"],
     "code.exec"),
    # net.http
    (["http_request", "fetch", "web_fetch", "get_url", "api_call",
      "send_request", "post_request", "download", "upload",
      "send_email", "slack_send", "notify"],
     "net.http"),
    # env.read
    (["get_env", "read_env", "get_environment", "list_env", "getenv"],
     "env.read"),
    # process
    (["start_process", "kill_process", "list_processes", "process_list",
      "spawn", "terminate"],
     "process"),
]

# Sensitive path glob-like patterns (simplified matching)
SENSITIVE_PATH_PATTERNS = [
    r"~/\.ssh(/|$)",
    r".*/id_rsa",
    r".*/id_ed25519",
    r".*\.pem$",
    r".*\.key$",
    r".*\.p12$",
    r".*\.pfx$",
    r"~/\.aws(/|$)",
    r"~/\.config/gcloud(/|$)",
    r"~/\.kube(/|$)",
    r".*/\.env$",
    r".*/\.env\.",
    r".*credential",
    r".*secret",
    r".*/secrets\.",
    r".*/credentials\.",
    r".*/config\.json$",
    r".*/\.npmrc$",
    r".*/\.netrc$",
    r".*/\.git-credentials$",
    r".*/\.bash_history$",
    r".*/\.zsh_history$",
    r".*/Cookies$",
    r"~/\.docker(/|$)",
]

# Common file extensions that suggest a path
PATH_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".json", ".yaml", ".yml",
    ".env", ".txt", ".md", ".log", ".cfg", ".ini", ".toml", ".key",
    ".pem", ".sh", ".bash", ".zsh", ".csv", ".xml", ".html", ".css",
}

SHELL_META = re.compile(r"[|;&`$]|\$\(|\$\{")
SHELL_COMMANDS = re.compile(
    r"\b(curl|wget|bash|sh|zsh|python\s+-c|node\s+-e|rm\s+-rf|chmod|chown|nc|ncat|"
    r"powershell|pwsh|iex|downloadstring)\b",
    re.IGNORECASE,
)
ATTACKERISH = re.compile(
    r"(attacker|evil\.com|exfil|malware-c2|malware_c2|hooks\.attacker)",
    re.IGNORECASE,
)
URL_PATTERN = re.compile(r"https?://[^\s]+", re.IGNORECASE)
ENV_VAR_PATTERN = re.compile(r"(\$[A-Za-z_][A-Za-z0-9_]*|\$\{[^}]+\}|%[A-Za-z_][A-Za-z0-9_]*%)")


# ---------------------------------------------------------------------------
# Helper predicates
# ---------------------------------------------------------------------------

def looks_like_path(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    v = value.strip()
    if v.startswith(("/", "~", "./", "../")):
        return True
    if re.match(r"^[A-Za-z]:[\\/]", v):  # Windows
        return True
    # contains slash + known extension
    lower = v.lower()
    if "/" in v or "\\" in v:
        for ext in PATH_EXTENSIONS:
            if lower.endswith(ext):
                return True
    return False


def looks_like_url(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    return bool(URL_PATTERN.search(value))


def looks_like_shell_command(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    if SHELL_META.search(value):
        return True
    if SHELL_COMMANDS.search(value):
        return True
    return False


def looks_like_env_access(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    if ENV_VAR_PATTERN.search(value):
        return True
    lower = value.lower()
    keywords = ("api_key", "secret", "token", "password", "credential", "private_key")
    return any(k in lower for k in keywords)


def matches_sensitive_path(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    # Expand ~ for matching
    expanded = os.path.expanduser(value)
    candidates = [value, expanded]
    for cand in candidates:
        for pat in SENSITIVE_PATH_PATTERNS:
            if re.search(pat, cand, re.IGNORECASE):
                return True
    return False


def is_write_operation(tool_name: str) -> bool:
    name = tool_name.lower()
    write_keywords = ("write", "create", "edit", "delete", "remove",
                      "save", "append", "mkdir", "rmdir", "move", "rename")
    return any(k in name for k in write_keywords)


# ---------------------------------------------------------------------------
# Ablation / feature flags
# ---------------------------------------------------------------------------

@dataclass
class InferenceConfig:
    """Feature toggles for ablation studies. Defaults preserve full system."""
    use_name_heuristics: bool = True
    use_argument_inspection: bool = True
    use_sensitive_path_elevation: bool = True
    use_default_deny_unknown: bool = True  # fail-closed unknown → code.exec


DEFAULT_INFERENCE_CONFIG = InferenceConfig()


# ---------------------------------------------------------------------------
# Main inference function
# ---------------------------------------------------------------------------

def infer_categories(
    tool_name: str,
    arguments: dict[str, Any] | None = None,
    config: InferenceConfig | None = None,
) -> InferenceResult:
    """
    Infer permission categories for a tool call.

    Parameters
    ----------
    tool_name : str
        Name of the tool being called.
    arguments : dict, optional
        Tool arguments.
    config : InferenceConfig, optional
        Ablation feature flags. Defaults to full system.

    Returns
    -------
    InferenceResult
        categories, reasons, high_risk flag.
    """
    cfg = config or DEFAULT_INFERENCE_CONFIG
    result = InferenceResult()
    arguments = arguments or {}
    name_lower = tool_name.lower()

    # ----- Layer 1: Name heuristics -----
    if cfg.use_name_heuristics:
        for patterns, category in NAME_RULES:
            for pat in patterns:
                if pat in name_lower:
                    result.add(category, f"name:{pat}")
                    break  # one match per rule group is enough

    # ----- Layer 2: Argument inspection -----
    if cfg.use_argument_inspection:
        for key, value in arguments.items():
            if looks_like_path(value):
                if is_write_operation(tool_name):
                    result.add("fs.write", f"arg_path_write:{key}")
                else:
                    result.add("fs.read", f"arg_path_read:{key}")

            if looks_like_url(value):
                result.add("net.http", f"arg_url:{key}")

            if looks_like_shell_command(value):
                result.add("code.exec", f"arg_shell:{key}")

            if looks_like_env_access(value):
                result.add("env.read", f"arg_env:{key}")

            if isinstance(value, str) and ATTACKERISH.search(value):
                # Treat attacker-marked destinations as high-risk sink (fail closed).
                result.add("net.http", f"arg_attackerish:{key}")
                result.add("code.exec", f"arg_attackerish_sink:{key}")
                result.high_risk = True

    # ----- Layer 3: Sensitive resource elevation -----
    if cfg.use_sensitive_path_elevation:
        for key, value in arguments.items():
            if matches_sensitive_path(value):
                result.add("env.read", f"sensitive_path:{value}")
                result.high_risk = True

    # ----- Fail-closed / default-deny unknown -----
    if not result.categories:
        if cfg.use_default_deny_unknown:
            result.add("code.exec", "unknown_tool_fail_closed")
            result.high_risk = True
        # else: leave empty → checker may default-allow if policy default=allow

    return result


# ---------------------------------------------------------------------------
# Convenience wrapper that accepts a simple namespace/dict
# ---------------------------------------------------------------------------

def infer_from_tool_call(tool_call: Any) -> InferenceResult:
    """
    Accepts an object with .name and .arguments attributes
    or a dict with 'name' and 'arguments' keys.
    """
    if isinstance(tool_call, dict):
        name = tool_call.get("name", "")
        args = tool_call.get("arguments", {})
    else:
        name = getattr(tool_call, "name", "")
        args = getattr(tool_call, "arguments", {})
    return infer_categories(name, args)
