"""
Tests for Audit Logger.
"""

import sys
import os
import tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from models import DecisionRecord, Decision
from audit import AuditLogger


def _sample_record(decision: Decision = Decision.ALLOW) -> DecisionRecord:
    return DecisionRecord(
        timestamp="2026-08-09T01:00:00+00:00",
        tool_name="read_file",
        server="filesystem",
        arguments_summary={"path": "src/main.py"},
        inferred_categories={"fs.read"},
        inference_reasons={"fs.read": ["name:read_file"]},
        high_risk=False,
        category_decisions={"fs.read": Decision.ALLOW},
        final_decision=decision,
        latency_ms=1.23,
        policy_name="read-only",
    )


def test_log_and_read():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "test.jsonl")
        logger = AuditLogger(path)

        logger.log(_sample_record(Decision.ALLOW))
        logger.log(_sample_record(Decision.DENY))

        records = logger.read_all()
        assert len(records) == 2
        assert records[0]["final_decision"] == "allow"
        assert records[1]["final_decision"] == "deny"
        assert records[0]["tool_name"] == "read_file"
        assert records[0]["policy_name"] == "read-only"
        print("✓ test_log_and_read")


def test_count_and_clear():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "test.jsonl")
        logger = AuditLogger(path)

        logger.log(_sample_record())
        logger.log(_sample_record())
        assert logger.count() == 2

        logger.clear()
        assert logger.count() == 0
        print("✓ test_count_and_clear")


def test_categories_sorted():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "test.jsonl")
        logger = AuditLogger(path)

        rec = _sample_record()
        rec.inferred_categories = {"net.http", "code.exec", "fs.read"}
        logger.log(rec)

        records = logger.read_all()
        assert records[0]["inferred_categories"] == ["code.exec", "fs.read", "net.http"]
        print("✓ test_categories_sorted")


if __name__ == "__main__":
    print("Running Audit Logger tests...\n")
    test_log_and_read()
    test_count_and_clear()
    test_categories_sorted()
    print("\nAll Audit Logger tests passed.")
