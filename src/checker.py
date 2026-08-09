"""
Permission Checker
------------------
Implements the five-stage decision pipeline:
  1. Parse / Normalise (already done by caller)
  2. Category Inference
  3. Policy Lookup
  4. Restriction Evaluation
  5. Aggregate Decision
"""

from __future__ import annotations

import time
import fnmatch
import os
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from models import (
    ToolCall,
    Policy,
    CategoryRule,
    Decision,
    DecisionRecord,
    InferenceResult,
)
from inference import infer_categories, InferenceConfig, DEFAULT_INFERENCE_CONFIG


class PermissionChecker:
    """
    Core decision engine.

    Usage:
        checker = PermissionChecker()
        decision, record = checker.evaluate(tool_call, policy)
    """

    def __init__(
        self,
        inference_config: InferenceConfig | None = None,
        use_domain_allow_list: bool = True,
        force_default_allow: bool = False,
    ) -> None:
        self.inference_config = inference_config or DEFAULT_INFERENCE_CONFIG
        self.use_domain_allow_list = use_domain_allow_list
        # Ablation: treat missing categories as ALLOW instead of policy default DENY
        self.force_default_allow = force_default_allow

    def evaluate(self, tool_call: ToolCall, policy: Policy) -> tuple[Decision, DecisionRecord]:
        """
        Run the full decision pipeline.

        Returns
        -------
        (final_decision, audit_record)
        """
        start = time.perf_counter()

        # ----- Stage 2: Category Inference -----
        inference: InferenceResult = infer_categories(
            tool_call.name, tool_call.arguments, config=self.inference_config
        )

        # If inference produced nothing and default-allow ablation is on → ALLOW
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

        # ----- Stage 3 & 4: Lookup + Restriction Evaluation -----
        category_decisions: dict[str, Decision] = {}

        for cat in inference.categories:
            rule = self._lookup(policy, cat)
            decision = self._evaluate_rule(tool_call, rule, cat)
            category_decisions[cat] = decision

        # ----- Stage 5: Aggregate -----
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

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _lookup(self, policy: Policy, category: str) -> CategoryRule:
        """Return the rule for a category, or a default-deny rule."""
        if category in policy.permissions:
            return policy.permissions[category]
        if self.force_default_allow:
            return CategoryRule(allow=True, mode=Decision.ALLOW)
        # fall back to policy default
        return CategoryRule(
            allow=(policy.default == Decision.ALLOW),
            mode=policy.default,
        )

    def _evaluate_rule(self, tool_call: ToolCall, rule: CategoryRule, category: str) -> Decision:
        """Evaluate a single category rule against the tool call."""
        if not rule.allow:
            return Decision.DENY

        # Check path restrictions (relevant for fs.* and env.read)
        if category in ("fs.read", "fs.write", "env.read"):
            if self._violates_path_restrictions(tool_call, rule):
                return Decision.DENY

        # Check domain restrictions (relevant for net.http)
        if category == "net.http":
            if self._violates_domain_restrictions(tool_call, rule):
                return Decision.DENY

        # If we reach here, the category is allowed → use its mode
        return rule.mode  # ALLOW or ASK

    def _violates_path_restrictions(self, tool_call: ToolCall, rule: CategoryRule) -> bool:
        paths = self._extract_paths(tool_call.arguments)
        if not paths:
            return False

        for path in paths:
            expanded = os.path.expanduser(path)

            # deny_paths: if any match → violate
            for pat in rule.deny_paths:
                if self._path_matches(expanded, pat) or self._path_matches(path, pat):
                    return True

            # allow_paths: if list is non-empty, path must match at least one
            if rule.allow_paths:
                if not any(
                    self._path_matches(expanded, pat) or self._path_matches(path, pat)
                    for pat in rule.allow_paths
                ):
                    return True

        return False

    def _violates_domain_restrictions(self, tool_call: ToolCall, rule: CategoryRule) -> bool:
        """
        Domain restriction logic:
          - If allow_domains is non-empty → allow-list mode.
            Domain must match at least one allow pattern.
            Specific deny_domains (not '*') can still block.
          - If only deny_domains is present → deny-list mode.
        """
        domains = self._extract_domains(tool_call.arguments)
        if not domains:
            return False

        for domain in domains:
            # Specific denies (ignore wildcard '*' when allow-list is active)
            specific_denies = [p for p in rule.deny_domains if p.strip() != "*"]
            for pat in specific_denies:
                if self._domain_matches(domain, pat):
                    return True

            if not self.use_domain_allow_list:
                # Ablation: ignore domain restrictions entirely
                continue

            if rule.allow_domains:
                # Allow-list mode: must match at least one allowed domain
                if not any(self._domain_matches(domain, pat) for pat in rule.allow_domains):
                    return True
            else:
                # Deny-list mode (including possible '*')
                for pat in rule.deny_domains:
                    if self._domain_matches(domain, pat):
                        return True

        return False

    def _aggregate(self, category_decisions: dict[str, Decision]) -> Decision:
        """Deny > Ask > Allow"""
        if any(d == Decision.DENY for d in category_decisions.values()):
            return Decision.DENY
        if any(d == Decision.ASK for d in category_decisions.values()):
            return Decision.ASK
        return Decision.ALLOW

    # ----- extraction helpers -----

    def _extract_paths(self, arguments: dict[str, Any]) -> list[str]:
        paths = []
        for value in arguments.values():
            if isinstance(value, str) and self._looks_like_path(value):
                paths.append(value)
        return paths

    def _extract_domains(self, arguments: dict[str, Any]) -> list[str]:
        domains = []
        for value in arguments.values():
            if isinstance(value, str) and ("http://" in value or "https://" in value):
                try:
                    parsed = urlparse(value)
                    if parsed.hostname:
                        domains.append(parsed.hostname.lower())
                except Exception:
                    pass
        return domains

    def _looks_like_path(self, value: str) -> bool:
        v = value.strip()
        if v.startswith(("/", "~", "./", "../")):
            return True
        if "/" in v or "\\" in v:
            return True
        return False

    def _path_matches(self, path: str, pattern: str) -> bool:
        """Simple glob matching with ** and ~ support."""
        # Expand ~ in pattern
        pat = os.path.expanduser(pattern)
        # fnmatch does not treat ** specially, so we do a simple approach
        if "**" in pat:
            # convert ** to * for crude matching
            pat = pat.replace("**", "*")
        return fnmatch.fnmatch(path, pat) or fnmatch.fnmatch(path, pattern)

    def _domain_matches(self, domain: str, pattern: str) -> bool:
        pattern = pattern.lower().strip()
        if pattern == "*":
            return True
        if pattern.startswith("*."):
            suffix = pattern[1:]  # e.g. ".example.com"
            return domain.endswith(suffix) or domain == pattern[2:]
        return domain == pattern

    def _summarise_args(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Create a short summary (truncate long values)."""
        summary = {}
        for k, v in arguments.items():
            if isinstance(v, str) and len(v) > 120:
                summary[k] = v[:117] + "..."
            else:
                summary[k] = v
        return summary
