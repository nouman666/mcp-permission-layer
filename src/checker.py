"""
Permission Checker
------------------
Implements the five-stage decision pipeline:
  1. Parse / Normalise
  2. Category Inference
  3. Policy Lookup
  4. Restriction Evaluation
  5. Aggregate Decision
"""

from __future__ import annotations

from pathlib import Path
from dataclasses import replace
import fnmatch
import posixpath
import time
from datetime import datetime, timezone
from typing import Any

from models import (
    ToolCall,
    Policy,
    CategoryRule,
    Decision,
    DecisionRecord,
    InferenceResult,
)
from inference import (
    infer_categories,
    InferenceConfig,
    DEFAULT_INFERENCE_CONFIG,
    iter_argument_scalars,
    looks_like_path,
    canonicalize_path,
    canonicalize_domain,
)


# Review Part A is implemented (Reviewer 1 Comment 1(a)-(f)):
# Reviewer 1 Comment 1(a)-(f) implemented:
# restriction extraction now recursively traverses structured arguments,
# canonicalizes path/domain resources, recognizes split host fields, and treats
# a restricted category with an unresolved resource as a fail-closed violation.


class PermissionChecker:
    """Core decision engine."""

    def __init__(
        self,
        inference_config: InferenceConfig | None = None,
        use_domain_allow_list: bool = True,
        force_default_allow: bool = False,
        path_root: Path | None = None,
    ) -> None:
        self.path_root = path_root.resolve() if path_root is not None else None
        self.inference_config = inference_config or DEFAULT_INFERENCE_CONFIG
        self.use_domain_allow_list = use_domain_allow_list
        self.force_default_allow = force_default_allow

    def evaluate(self, tool_call: ToolCall, policy: Policy) -> tuple[Decision, DecisionRecord]:
        start = time.perf_counter()

        inference: InferenceResult = infer_categories(
            tool_call.name, tool_call.arguments, config=self.inference_config
        )

        if not inference.categories and self.force_default_allow:
            latency_ms = (time.perf_counter() - start) * 1000.0
            record = DecisionRecord(
                timestamp=datetime.now(timezone.utc).isoformat(),
                tool_name=tool_call.name,
                server=tool_call.server,
                arguments_summary=self._summarise_args(tool_call.arguments),
                inferred_categories=set(),
                inference_reasons={},
                high_risk=False,
                category_decisions={},
                final_decision=Decision.ALLOW,
                latency_ms=round(latency_ms, 3),
                policy_name=policy.name,
            )
            return Decision.ALLOW, record

        category_decisions: dict[str, Decision] = {}
        for cat in inference.categories:
            rule = self._lookup(policy, cat)
            if cat in ("fs.read", "fs.write", "env.read") and policy.sensitive_paths:
                rule = replace(rule, deny_paths=list(rule.deny_paths) + list(policy.sensitive_paths))
            category_decisions[cat] = self._evaluate_rule(tool_call, rule, cat)

        final = self._aggregate(category_decisions)
        latency_ms = (time.perf_counter() - start) * 1000.0

        record = DecisionRecord(
            timestamp=datetime.now(timezone.utc).isoformat(),
            tool_name=tool_call.name,
            server=tool_call.server,
            arguments_summary=self._summarise_args(tool_call.arguments),
            inferred_categories=inference.categories,
            inference_reasons=inference.reasons,
            high_risk=inference.high_risk,
            category_decisions=category_decisions,
            final_decision=final,
            latency_ms=round(latency_ms, 3),
            policy_name=policy.name,
        )
        return final, record

    def _lookup(self, policy: Policy, category: str) -> CategoryRule:
        if category in policy.permissions:
            return policy.permissions[category]
        if self.force_default_allow:
            return CategoryRule(allow=True, mode=Decision.ALLOW)
        return CategoryRule(allow=(policy.default == Decision.ALLOW), mode=policy.default)

    def _evaluate_rule(self, tool_call: ToolCall, rule: CategoryRule, category: str) -> Decision:
        if not rule.allow:
            return Decision.DENY

        if category in ("fs.read", "fs.write", "env.read"):
            if self._violates_path_restrictions(tool_call, rule):
                return Decision.DENY

        if category == "net.http":
            if self._violates_domain_restrictions(tool_call, rule):
                return Decision.DENY

        return rule.mode

    def _violates_path_restrictions(self, tool_call: ToolCall, rule: CategoryRule) -> bool:
        has_restrictions = bool(rule.deny_paths or rule.allow_paths)
        paths = self._extract_paths(tool_call.arguments)
        if self.path_root is not None:
            try:
                resolved = []
                for value in paths:
                    p = Path(value).expanduser()
                    p = (p if p.is_absolute() else self.path_root / p).resolve()
                    resolved.append(str(p))
                paths = paths + resolved
            except (OSError, RuntimeError, ValueError):
                return True
        if not paths:
            # Reviewer 1: an absent extraction is unresolved, not unrestricted.
            return has_restrictions

        for path in paths:
            for pat in rule.deny_paths:
                if self._path_matches(path, pat):
                    return True

            if rule.allow_paths and not any(self._path_matches(path, pat) for pat in rule.allow_paths):
                return True
        return False

    def _violates_domain_restrictions(self, tool_call: ToolCall, rule: CategoryRule) -> bool:
        has_restrictions = bool(rule.allow_domains or rule.deny_domains)
        domains = self._extract_domains(tool_call.arguments)
        if not domains:
            # Reviewer 1: restricted network access with no resolvable destination
            # must fail closed instead of silently bypassing the allow-list.
            return has_restrictions and self.use_domain_allow_list

        for domain in domains:
            specific_denies = [p for p in rule.deny_domains if p.strip() != "*"]
            if any(self._domain_matches(domain, pat) for pat in specific_denies):
                return True

            if not self.use_domain_allow_list:
                continue

            if rule.allow_domains:
                if not any(self._domain_matches(domain, pat) for pat in rule.allow_domains):
                    return True
            else:
                if any(self._domain_matches(domain, pat) for pat in rule.deny_domains):
                    return True
        return False

    def _aggregate(self, category_decisions: dict[str, Decision]) -> Decision:
        if any(d == Decision.DENY for d in category_decisions.values()):
            return Decision.DENY
        if any(d == Decision.ASK for d in category_decisions.values()):
            return Decision.ASK
        return Decision.ALLOW

    def _extract_paths(self, arguments: dict[str, Any]) -> list[str]:
        paths: list[str] = []
        seen: set[str] = set()
        for _, key, value in iter_argument_scalars(arguments):
            if isinstance(value, str) and looks_like_path(value, key):
                p = canonicalize_path(value)
                if p not in seen:
                    seen.add(p)
                    paths.append(p)
        return paths

    def _extract_domains(self, arguments: dict[str, Any]) -> list[str]:
        domains: list[str] = []
        seen: set[str] = set()
        for _, key, value in iter_argument_scalars(arguments):
            domain = canonicalize_domain(value, key)
            if domain and domain not in seen:
                seen.add(domain)
                domains.append(domain)
        return domains

    def _path_matches(self, path: str, pattern: str) -> bool:
        p = canonicalize_path(path).lower()
        pat = canonicalize_path(pattern).lower()

        # Directory patterns without glob syntax apply to the directory and descendants.
        if not any(ch in pat for ch in "*?["):
            if p == pat or p.startswith(pat.rstrip("/") + "/"):
                return True
            # A home-scoped sensitive pattern should also protect equivalent absolute homes.
            if pat.startswith("~/"):
                suffix = pat[1:]  # '/.ssh', '/.aws', ...
                if p.endswith(suffix) or suffix + "/" in "/" + p.lstrip("/"):
                    return True

        # Normalize ** for fnmatch's cross-separator behavior in this lexical representation.
        glob_pat = pat.replace("**", "*")
        candidates = {p, p.lstrip("/"), "~/" + p.split("/", 2)[-1] if p.startswith("/home/") else p}
        return any(fnmatch.fnmatch(c, glob_pat) for c in candidates)

    def _domain_matches(self, domain: str, pattern: str) -> bool:
        d = domain.lower().rstrip(".")
        pat = pattern.lower().strip().rstrip(".")
        if pat == "*":
            return True
        if pat.startswith("*."):
            suffix = pat[1:]
            return d.endswith(suffix) or d == pat[2:]
        return d == pat

    def _summarise_args(self, arguments: dict[str, Any]) -> dict[str, Any]:
        def shorten(v: Any) -> Any:
            if isinstance(v, str) and len(v) > 120:
                return v[:117] + "..."
            if isinstance(v, dict):
                return {k: shorten(x) for k, x in v.items()}
            if isinstance(v, list):
                return [shorten(x) for x in v[:20]]
            return v

        return {k: shorten(v) for k, v in arguments.items()}
