"""
Policy Manager
--------------
Loads, validates, and supplies the active policy.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from models import Policy, CategoryRule, Decision


class PolicyError(Exception):
    """Raised when a policy file is invalid or cannot be loaded."""
    pass


class PolicyManager:
    """
    Responsible for loading and holding the current policy.

    Usage:
        pm = PolicyManager()
        pm.load("policies/read_only.yaml")
        policy = pm.get_current()
    """

    def __init__(self) -> None:
        self._policy: Policy | None = None
        self._path: str | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self, path: str | Path) -> Policy:
        """Load and validate a policy from a YAML file."""
        path = Path(path)
        if not path.exists():
            raise PolicyError(f"Policy file not found: {path}")

        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise PolicyError(f"Invalid YAML in {path}: {e}") from e

        if not isinstance(raw, dict):
            raise PolicyError(f"Policy root must be a mapping, got {type(raw)}")

        policy = self._parse(raw)
        self._policy = policy
        self._path = str(path)
        return policy

    def reload(self) -> Policy:
        """Reload the last loaded policy file."""
        if not self._path:
            raise PolicyError("No policy has been loaded yet")
        return self.load(self._path)

    def get_current(self) -> Policy:
        """Return the currently active policy."""
        if self._policy is None:
            raise PolicyError("No policy loaded. Call load() first.")
        return self._policy

    @property
    def is_loaded(self) -> bool:
        return self._policy is not None

    # ------------------------------------------------------------------
    # Internal parsing & validation
    # ------------------------------------------------------------------

    def _parse(self, raw: dict[str, Any]) -> Policy:
        name = raw.get("name") or raw.get("policy", {}).get("name")
        if not name:
            # support both top-level and nested "policy:" key
            if "policy" in raw and isinstance(raw["policy"], dict):
                meta = raw["policy"]
                name = meta.get("name", "unnamed")
                version = str(meta.get("version", "1.0"))
                description = meta.get("description", "")
            else:
                name = "unnamed"
                version = "1.0"
                description = ""
        else:
            version = str(raw.get("version", "1.0"))
            description = raw.get("description", "")

        # default decision
        default_raw = str(raw.get("default", "deny")).lower()
        if default_raw not in ("allow", "deny"):
            raise PolicyError(f"Invalid default value: {default_raw}")
        default = Decision.ALLOW if default_raw == "allow" else Decision.DENY

        # permissions
        perms_raw = raw.get("permissions", {})
        if not isinstance(perms_raw, dict):
            raise PolicyError("'permissions' must be a mapping")

        permissions: dict[str, CategoryRule] = {}
        for cat, rule_raw in perms_raw.items():
            if cat not in {"fs.read", "fs.write", "net.http", "code.exec", "env.read", "process"}:
                raise PolicyError(f"Unknown permission category: {cat}")
            permissions[cat] = self._parse_rule(cat, rule_raw)

        # optional sensitive paths (can also live under global)
        sensitive = raw.get("sensitive_paths", [])
        if "global" in raw and isinstance(raw["global"], dict):
            sensitive = raw["global"].get("sensitive_paths", sensitive)
        if not isinstance(sensitive, list) or not all(isinstance(x, str) for x in sensitive):
            raise PolicyError("sensitive_paths must be a list of strings")

        return Policy(
            name=name,
            version=version,
            description=description,
            default=default,
            permissions=permissions,
            sensitive_paths=sensitive,
        )

    def _parse_rule(self, category: str, raw: Any) -> CategoryRule:
        if raw is None:
            return CategoryRule(allow=False)

        if isinstance(raw, bool):
            return CategoryRule(allow=raw)

        if not isinstance(raw, dict):
            raise PolicyError(f"Rule for '{category}' must be a mapping or bool")

        allow = raw.get("allow", False)
        if type(allow) is not bool:
            raise PolicyError(f"allow for {category} must be a YAML boolean")

        mode_raw = str(raw.get("mode", "allow")).lower()
        if mode_raw not in ("allow", "deny", "ask"):
            raise PolicyError(f"Invalid mode for '{category}': {mode_raw}")
        mode = Decision(mode_raw)

        restrictions = raw.get("restrictions", {})
        if not isinstance(restrictions, dict):
            raise PolicyError("restrictions must be a mapping")
        unknown = set(restrictions) - {"deny_paths", "allow_paths", "deny_domains", "allow_domains"}
        if unknown:
            raise PolicyError(f"Unknown restrictions: {sorted(unknown)}")
        for key, values in restrictions.items():
            if not isinstance(values, list) or not all(isinstance(x, str) for x in values):
                raise PolicyError(f"{key} must be a list of strings")

        return CategoryRule(
            allow=allow,
            mode=mode if allow else Decision.DENY,
            deny_paths=list(restrictions.get("deny_paths", [])),
            allow_paths=list(restrictions.get("allow_paths", [])),
            deny_domains=list(restrictions.get("deny_domains", [])),
            allow_domains=list(restrictions.get("allow_domains", [])),
        )
