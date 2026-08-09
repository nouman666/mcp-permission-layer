"""
Core data models for the Runtime Permission Enforcement Layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Decision(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    ASK = "ask"


@dataclass
class ToolCall:
    """Canonical representation of an incoming tool call."""
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    server: str | None = None
    raw: dict[str, Any] | None = None


@dataclass
class InferenceResult:
    """Output of category inference."""
    categories: set[str] = field(default_factory=set)
    reasons: dict[str, list[str]] = field(default_factory=dict)
    high_risk: bool = False

    def add(self, category: str, reason: str) -> None:
        self.categories.add(category)
        self.reasons.setdefault(category, []).append(reason)


@dataclass
class CategoryRule:
    """Rule for a single permission category."""
    allow: bool = False
    mode: Decision = Decision.ALLOW          # used only when allow=True
    deny_paths: list[str] = field(default_factory=list)
    allow_paths: list[str] = field(default_factory=list)
    deny_domains: list[str] = field(default_factory=list)
    allow_domains: list[str] = field(default_factory=list)


@dataclass
class Policy:
    """Full policy loaded from YAML."""
    name: str
    version: str = "1.0"
    description: str = ""
    default: Decision = Decision.DENY
    permissions: dict[str, CategoryRule] = field(default_factory=dict)
    sensitive_paths: list[str] = field(default_factory=list)


@dataclass
class DecisionRecord:
    """Audit record produced for every tool call."""
    timestamp: str
    tool_name: str
    server: str | None
    arguments_summary: dict[str, Any]
    inferred_categories: set[str]
    inference_reasons: dict[str, list[str]]
    high_risk: bool
    category_decisions: dict[str, Decision]
    final_decision: Decision
    latency_ms: float
    policy_name: str = ""
