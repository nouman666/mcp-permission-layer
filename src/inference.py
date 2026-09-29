"""
Category Inference Module
-------------------------
Infers the set of permission categories required by a tool call.
Design principles:
  - Over-approximate (safety first)
  - Deterministic
  - Explainable (reasons for each category)
  - Fail-closed for unknown or semantically unresolved tool calls
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterator
import os
import posixpath
import re
from urllib.parse import urlparse


# Review Part C is implemented (Reviewer 3 Comments 1-3):
# - validate capability inference independently of YAML policy outcomes;
# - recognize documented Git read/write tool semantics used in the external mechanism audit;
# - prevent URL-valued arguments from being double-classified as filesystem paths;
# - preserve conservative fail-closed handling for unresolved resource intent.
#
# Review Part A is implemented (Reviewer 1 Comment 1(a)-(f)):
# Reviewer 1 Comment 1(a)-(f) implemented:
# - recursively traverse nested dictionaries/lists;
# - canonicalize path and network destinations before evaluation;
# - recognize split host/domain representations;
# - infer unfamiliar write-like operations from name/argument semantics;
# - broaden sensitive-path handling across POSIX/Windows/relative variants;
# - fail closed when a path-bearing call remains semantically ambiguous.


@dataclass
class InferenceResult:
    categories: set[str] = field(default_factory=set)
    reasons: dict[str, list[str]] = field(default_factory=dict)
    high_risk: bool = False

    def add(self, category: str, reason: str) -> None:
        self.categories.add(category)
        self.reasons.setdefault(category, []).append(reason)


# Strong name patterns -> category. Matching is token-aware rather than raw
# substring matching so incidental fragments (e.g., "cat" in "concatenate")
# do not accidentally classify a call.
NAME_RULES: list[tuple[list[str], str]] = [
    # fs.read
    (["read_file", "read_text_file", "read_media_file", "read_multiple_files",
      "read_file_content", "get_file", "cat", "list_dir", "list_files", "ls",
      "glob", "search_files", "view_file", "open_file", "list_directory",
      "list_directory_with_sizes", "directory_tree", "get_file_info",
      "list_allowed_directories",
      "git_status", "git_diff_unstaged", "git_diff_staged", "git_diff",
      "git_log", "git_show", "git_branch"],
     "fs.read"),
    # fs.write
    (["write_file", "create_file", "create_directory", "edit_file", "delete_file",
      "remove_file", "mkdir", "rmdir", "move_file", "rename_file", "append_file",
      "save_file", "persist_blob", "store_file", "put_file", "patch_file",
      "replace_file", "git_commit", "git_add", "git_reset",
      "git_create_branch", "git_checkout"],
     "fs.write"),
    # code.exec
    (["run_terminal", "execute_command", "run_command", "bash", "shell", "exec",
      "python_exec", "code_interpreter", "run_code", "terminal", "pwsh",
      "powershell"],
     "code.exec"),
    # net.http
    (["http_request", "fetch", "web_fetch", "get_url", "api_call", "send_request",
      "post_request", "download", "upload", "send_email", "slack_send", "notify"],
     "net.http"),
    # env.read
    (["get_env", "read_env", "get_environment", "list_env", "getenv", "printenv"],
     "env.read"),
    # process
    (["start_process", "kill_process", "list_processes", "process_list", "spawn",
      "terminate"],
     "process"),
]

PATH_KEY_HINTS = {
    "path", "paths", "filepath", "file_path", "filename", "file", "files",
    "dir", "directory", "folder", "root", "cwd", "source", "src", "target",
    "destination", "dest", "output", "output_path", "input_path", "config_path",
    "kubeconfig", "keyfile", "cert", "certificate",
}
WRITE_PATH_KEY_HINTS = {
    "destination", "dest", "output", "output_path", "target_path", "save_path",
}
WRITE_PAYLOAD_KEY_HINTS = {
    "content", "contents", "data", "payload", "body", "text", "bytes", "blob",
    "edits", "newtext", "new_text", "replacement", "value",
}
HOST_KEY_HINTS = {
    "host", "hostname", "domain", "server_host", "remote_host", "endpoint_host",
}
URL_KEY_HINTS = {
    "url", "uri", "endpoint", "endpoint_url", "request_url", "callback",
    "webhook", "webhook_url", "base_url",
}

PATH_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".json", ".yaml", ".yml", ".env",
    ".txt", ".md", ".log", ".cfg", ".ini", ".toml", ".key", ".pem", ".sh",
    ".bash", ".zsh", ".csv", ".xml", ".html", ".css", ".p12", ".pfx",
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
DOMAIN_LITERAL = re.compile(
    r"^(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}(?::\d{1,5})?\.?$"
)


def _norm_key(key: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (key or "").lower()).strip("_")


def _name_tokens(text: str) -> list[str]:
    return [t for t in re.split(r"[^a-z0-9]+", text.lower()) if t]


def tool_name_matches(tool_name: str, pattern: str) -> bool:
    """Token-aware contiguous match, allowing server namespaces/prefixes."""
    nt = _name_tokens(tool_name)
    pt = _name_tokens(pattern)
    if not nt or not pt or len(pt) > len(nt):
        return False
    width = len(pt)
    return any(nt[i:i + width] == pt for i in range(len(nt) - width + 1))


def iter_argument_scalars(value: Any, path: tuple[str, ...] = (), key_hint: str | None = None) -> Iterator[tuple[tuple[str, ...], str | None, Any]]:
    """Recursively yield scalar leaves from nested dict/list argument structures."""
    if isinstance(value, dict):
        for k, v in value.items():
            key = str(k)
            yield from iter_argument_scalars(v, path + (key,), key)
    elif isinstance(value, (list, tuple)):
        for i, v in enumerate(value):
            yield from iter_argument_scalars(v, path + (f"[{i}]",), key_hint)
    else:
        yield path, key_hint, value


def canonicalize_path(value: str) -> str:
    """Lexically normalize POSIX/Windows/relative paths without filesystem access."""
    v = str(value).strip().strip('"\'')
    if v.lower().startswith("file://"):
        v = v[7:]
    v = v.replace("\\", "/")
    # Preserve a leading ~/ marker rather than expanding to the evaluator host home.
    home_prefix = v.startswith("~/") or v == "~"
    drive = ""
    m = re.match(r"^([A-Za-z]:)(/.*)?$", v)
    if m:
        drive = m.group(1).lower()
        v = m.group(2) or "/"
    normalized = posixpath.normpath(v)
    if home_prefix and not normalized.startswith("~"):
        normalized = "~/" + normalized.lstrip("/")
    if drive:
        normalized = drive + (normalized if normalized.startswith("/") else "/" + normalized)
    return normalized


def looks_like_path(value: Any, key_hint: str | None = None) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    key = _norm_key(key_hint)
    v = value.strip()
    if key in PATH_KEY_HINTS or key.endswith("_path") or key.endswith("_file") or key.endswith("_dir"):
        # Resource-bearing schema fields count even for relative forms such as README.md or ".".
        return True
    if v in (".", "..") or v.startswith(("/", "~", "./", "../", "\\\\")):
        return True
    if re.match(r"^[A-Za-z]:[\\/]", v):
        return True
    lower = v.lower().replace("\\", "/")
    if "/" in lower:
        return True
    return any(lower.endswith(ext) for ext in PATH_EXTENSIONS)


def looks_like_url(value: Any, key_hint: str | None = None) -> bool:
    if not isinstance(value, str):
        return False
    key = _norm_key(key_hint)
    if URL_PATTERN.search(value):
        return True
    return key in URL_KEY_HINTS and bool(value.strip())


def canonicalize_domain(value: Any, key_hint: str | None = None) -> str | None:
    """Extract and normalize a hostname from a URL or host/domain schema field."""
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip().strip('"\'')
    key = _norm_key(key_hint)
    host: str | None = None
    try:
        if re.match(r"^[a-z][a-z0-9+.-]*://", raw, flags=re.IGNORECASE):
            host = urlparse(raw).hostname
        elif key in HOST_KEY_HINTS or key.endswith("_host") or key.endswith("_domain"):
            # // form lets urlparse handle ports and IPv6 literals.
            host = urlparse("//" + raw).hostname
        elif key in URL_KEY_HINTS and DOMAIN_LITERAL.match(raw):
            host = urlparse("//" + raw).hostname
    except Exception:
        host = None
    if not host:
        return None
    host = host.strip().rstrip(".").lower()
    try:
        host = host.encode("idna").decode("ascii")
    except Exception:
        pass
    return host or None


def looks_like_shell_command(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    return bool(SHELL_META.search(value) or SHELL_COMMANDS.search(value))


def looks_like_env_access(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    if ENV_VAR_PATTERN.search(value):
        return True
    lower = value.lower()
    keywords = ("api_key", "secret", "token", "password", "credential", "private_key")
    return any(k in lower for k in keywords)


def matches_sensitive_path(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    p = canonicalize_path(value).lower()
    # Work with a slash-delimited sentinel so relative and absolute variants match.
    sentinel = "/" + p.lstrip("/")
    base = posixpath.basename(p)
    if "/.ssh/" in sentinel or sentinel.endswith("/.ssh"):
        return True
    if "/.aws/" in sentinel or sentinel.endswith("/.aws"):
        return True
    if "/.kube/" in sentinel or sentinel.endswith("/.kube"):
        return True
    if "/.config/gcloud/" in sentinel or sentinel.endswith("/.config/gcloud"):
        return True
    if "/.docker/" in sentinel or sentinel.endswith("/.docker"):
        return True
    if base in {"id_rsa", "id_ed25519", ".npmrc", ".netrc", ".git-credentials",
                ".bash_history", ".zsh_history", "cookies", "authorized_keys"}:
        return True
    if base == ".env" or base.startswith(".env."):
        return True
    if any(p.endswith(ext) for ext in (".pem", ".key", ".p12", ".pfx")):
        return True
    if any(k in p for k in ("credential", "secret", "private_key")):
        return True
    if p.endswith("/config.json") and any(seg in sentinel for seg in ("/.config/", "/.docker/")):
        return True
    return False


def is_write_operation(tool_name: str) -> bool:
    tokens = set(_name_tokens(tool_name))
    write_tokens = {
        "write", "create", "edit", "delete", "remove", "save", "append", "mkdir",
        "rmdir", "move", "rename", "persist", "store", "put", "patch", "replace",
        "overwrite", "update", "commit",
    }
    return bool(tokens & write_tokens)


def _arguments_have_write_payload(arguments: dict[str, Any]) -> bool:
    for _, key, value in iter_argument_scalars(arguments):
        nk = _norm_key(key)
        if nk in WRITE_PAYLOAD_KEY_HINTS and value not in (None, "", [], {}):
            return True
    return False


def _path_role(key_hint: str | None) -> str:
    key = _norm_key(key_hint)
    if key in WRITE_PATH_KEY_HINTS or key.startswith("output") or key.startswith("dest"):
        return "write"
    if key.startswith("input") or key.startswith("source") or key in {"src"}:
        return "read"
    return "ambiguous"


@dataclass
class InferenceConfig:
    """Feature toggles for ablation studies. Defaults preserve full system."""
    use_name_heuristics: bool = True
    use_argument_inspection: bool = True
    use_sensitive_path_elevation: bool = True
    use_default_deny_unknown: bool = True


DEFAULT_INFERENCE_CONFIG = InferenceConfig()


def infer_categories(
    tool_name: str,
    arguments: dict[str, Any] | None = None,
    config: InferenceConfig | None = None,
) -> InferenceResult:
    """Infer permission categories for a tool call."""
    cfg = config or DEFAULT_INFERENCE_CONFIG
    result = InferenceResult()
    arguments = arguments or {}

    matched_name = False
    name_categories: set[str] = set()

    # ----- Layer 1: token-aware name heuristics -----
    if cfg.use_name_heuristics:
        for patterns, category in NAME_RULES:
            for pat in patterns:
                if tool_name_matches(tool_name, pat):
                    result.add(category, f"name:{pat}")
                    name_categories.add(category)
                    matched_name = True
                    break

    # ----- Layer 2: recursive argument inspection -----
    write_by_name = is_write_operation(tool_name)
    write_payload = _arguments_have_write_payload(arguments)
    saw_path = False
    saw_ambiguous_path = False
    saw_network_resource = False

    if cfg.use_argument_inspection:
        for path_parts, key, value in iter_argument_scalars(arguments):
            loc = ".".join(path_parts) if path_parts else (key or "arg")

            domain = canonicalize_domain(value, key)
            is_network_value = looks_like_url(value, key) or domain is not None

            # Reviewer 3 mechanism audit: a URL such as https://example.com/path
            # is a network destination, not a filesystem path merely because it
            # contains slash characters. Network-valued schema fields therefore
            # take precedence over generic path-shape heuristics.
            if looks_like_path(value, key) and not is_network_value:
                saw_path = True
                role = _path_role(key)
                write_context = write_by_name or ("fs.write" in name_categories) or write_payload or role == "write"
                if write_context:
                    result.add("fs.write", f"arg_path_write:{loc}")
                else:
                    result.add("fs.read", f"arg_path_read:{loc}")
                    if role == "ambiguous" and not ("fs.read" in name_categories):
                        saw_ambiguous_path = True

            if is_network_value:
                saw_network_resource = True
                result.add("net.http", f"arg_network:{loc}")

            if looks_like_shell_command(value):
                result.add("code.exec", f"arg_shell:{loc}")

            if looks_like_env_access(value):
                result.add("env.read", f"arg_env:{loc}")

            if isinstance(value, str) and ATTACKERISH.search(value):
                result.add("net.http", f"arg_attackerish:{loc}")
                result.add("code.exec", f"arg_attackerish_sink:{loc}")
                result.high_risk = True

    # ----- Layer 3: recursive sensitive-resource elevation -----
    if cfg.use_sensitive_path_elevation:
        for path_parts, key, value in iter_argument_scalars(arguments):
            if looks_like_path(value, key) and matches_sensitive_path(value):
                loc = ".".join(path_parts) if path_parts else (key or "arg")
                result.add("env.read", f"sensitive_path:{loc}:{canonicalize_path(str(value))}")
                result.high_risk = True

    # If a resource-bearing path is present but the operation is not reliably
    # distinguishable as read vs write, add the existing high-risk surrogate.
    # This closes the earlier gap where a partial category prevented fallback.
    if cfg.use_default_deny_unknown and saw_ambiguous_path and not matched_name:
        result.add("code.exec", "ambiguous_resource_intent_fail_closed")
        result.high_risk = True

    # Network arguments are a sufficiently conservative capability signal;
    # malformed/unextractable destinations are denied later by restriction logic.
    _ = saw_network_resource

    # ----- Fail-closed / default-deny unknown -----
    if not result.categories and cfg.use_default_deny_unknown:
        result.add("code.exec", "unknown_tool_fail_closed")
        result.high_risk = True

    return result
