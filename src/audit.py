"""
Audit Logger
------------
Append-only JSON Lines logger for every permission decision.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from models import DecisionRecord, Decision


class AuditLogger:
    """
    Writes one JSON object per line to a log file.

    Usage:
        logger = AuditLogger("logs/decisions.jsonl")
        logger.log(record)
    """

    def __init__(self, path: str | Path = "logs/decisions.jsonl") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Touch the file so it exists even if empty
        if not self.path.exists():
            self.path.touch()

    def log(self, record: DecisionRecord) -> None:
        """Append a single decision record as one JSON line."""
        entry = self._to_dict(record)
        line = json.dumps(entry, ensure_ascii=False, default=str)
        try:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError:
            # Fallback: keep records in memory if disk write fails
            if not hasattr(self, "_memory_log"):
                self._memory_log = []
            self._memory_log.append(line)

    def read_all(self) -> list[dict[str, Any]]:
        """Read all records (useful for tests / later analysis)."""
        records = []
        # memory fallback first
        if hasattr(self, "_memory_log"):
            for line in self._memory_log:
                records.append(json.loads(line))
        try:
            if self.path.exists():
                with open(self.path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            records.append(json.loads(line))
        except OSError:
            pass
        return records

    def clear(self) -> None:
        """Erase the log file (useful in tests)."""
        if self.path.exists():
            self.path.write_text("", encoding="utf-8")

    def count(self) -> int:
        return len(self.read_all())

    # ------------------------------------------------------------------

    def _to_dict(self, record: DecisionRecord) -> dict[str, Any]:
        return {
            "timestamp": record.timestamp,
            "tool_name": record.tool_name,
            "server": record.server,
            "arguments_summary": record.arguments_summary,
            "inferred_categories": sorted(record.inferred_categories),
            "inference_reasons": record.inference_reasons,
            "high_risk": record.high_risk,
            "category_decisions": {
                k: v.value if isinstance(v, Decision) else v
                for k, v in record.category_decisions.items()
            },
            "final_decision": (
                record.final_decision.value
                if isinstance(record.final_decision, Decision)
                else record.final_decision
            ),
            "latency_ms": record.latency_ms,
            "policy_name": record.policy_name,
        }
