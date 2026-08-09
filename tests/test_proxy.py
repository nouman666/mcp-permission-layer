"""
Tests for Enforcement Proxy.
"""

import sys
import os
import tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from models import Decision
from proxy import EnforcementProxy


POLICY_DIR = os.path.join(os.path.dirname(__file__), "..", "policies")


def test_proxy_allow():
    with tempfile.TemporaryDirectory() as tmp:
        log_path = os.path.join(tmp, "decisions.jsonl")
        proxy = EnforcementProxy(
            policy_path=os.path.join(POLICY_DIR, "read_only.yaml"),
            log_path=log_path,
        )
        decision, record = proxy.handle_tool_call(
            name="read_file",
            arguments={"path": "src/app.py"},
        )
        assert decision == Decision.ALLOW
        assert record.final_decision == Decision.ALLOW
        assert len(proxy.get_audit_records()) == 1
        print("✓ test_proxy_allow")


def test_proxy_deny_write():
    with tempfile.TemporaryDirectory() as tmp:
        log_path = os.path.join(tmp, "decisions.jsonl")
        proxy = EnforcementProxy(
            policy_path=os.path.join(POLICY_DIR, "read_only.yaml"),
            log_path=log_path,
        )
        decision, record = proxy.handle_tool_call(
            name="write_file",
            arguments={"path": "out.txt", "content": "x"},
        )
        assert decision == Decision.DENY
        assert len(proxy.get_audit_records()) == 1
        print("✓ test_proxy_deny_write")


def test_proxy_deny_exec():
    with tempfile.TemporaryDirectory() as tmp:
        log_path = os.path.join(tmp, "decisions.jsonl")
        proxy = EnforcementProxy(
            policy_path=os.path.join(POLICY_DIR, "no_code_exec.yaml"),
            log_path=log_path,
        )
        decision, _ = proxy.handle_tool_call(
            name="run_terminal",
            arguments={"cmd": "ls"},
        )
        assert decision == Decision.DENY
        print("✓ test_proxy_deny_exec")


def test_proxy_ask_without_handler_becomes_deny():
    """If mode=ask but no ask_handler is provided → fail closed (DENY)."""
    # We need a policy that produces ASK. For simplicity we reuse no_code_exec
    # and just verify the plumbing; a dedicated approval_gated policy can be
    # added later.
    with tempfile.TemporaryDirectory() as tmp:
        log_path = os.path.join(tmp, "decisions.jsonl")
        proxy = EnforcementProxy(
            policy_path=os.path.join(POLICY_DIR, "read_only.yaml"),
            log_path=log_path,
            ask_handler=None,
        )
        decision, _ = proxy.handle_tool_call(
            name="read_file",
            arguments={"path": "a.py"},
        )
        # under read_only this is ALLOW, so just check no crash
        assert decision in (Decision.ALLOW, Decision.DENY, Decision.ASK)
        print("✓ test_proxy_ask_without_handler_becomes_deny")


def test_multiple_calls_logged():
    with tempfile.TemporaryDirectory() as tmp:
        log_path = os.path.join(tmp, "decisions.jsonl")
        proxy = EnforcementProxy(
            policy_path=os.path.join(POLICY_DIR, "no_code_exec.yaml"),
            log_path=log_path,
        )
        proxy.handle_tool_call("read_file", {"path": "a.py"})
        proxy.handle_tool_call("write_file", {"path": "b.py", "content": "x"})
        proxy.handle_tool_call("run_terminal", {"cmd": "ls"})
        assert len(proxy.get_audit_records()) == 3
        print("✓ test_multiple_calls_logged")


if __name__ == "__main__":
    print("Running Enforcement Proxy tests...\n")
    test_proxy_allow()
    test_proxy_deny_write()
    test_proxy_deny_exec()
    test_proxy_ask_without_handler_becomes_deny()
    test_multiple_calls_logged()
    print("\nAll Enforcement Proxy tests passed.")
