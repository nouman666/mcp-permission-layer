"""
Unit tests for Permission Checker.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from models import ToolCall, Decision
from policy_manager import PolicyManager
from checker import PermissionChecker


POLICY_DIR = os.path.join(os.path.dirname(__file__), "..", "policies")


def load_policy(name: str):
    pm = PolicyManager()
    return pm.load(os.path.join(POLICY_DIR, name))


def test_read_only_allows_normal_read():
    policy = load_policy("read_only.yaml")
    checker = PermissionChecker()
    call = ToolCall(name="read_file", arguments={"path": "src/main.py"})
    decision, record = checker.evaluate(call, policy)

    assert decision == Decision.ALLOW
    assert "fs.read" in record.inferred_categories
    print("✓ test_read_only_allows_normal_read")


def test_read_only_denies_sensitive_read():
    policy = load_policy("read_only.yaml")
    checker = PermissionChecker()
    call = ToolCall(name="read_file", arguments={"path": "~/.ssh/id_rsa"})
    decision, record = checker.evaluate(call, policy)

    # sensitive path should cause deny (via env.read being denied, or path restriction)
    assert decision == Decision.DENY
    print("✓ test_read_only_denies_sensitive_read")


def test_read_only_denies_write():
    policy = load_policy("read_only.yaml")
    checker = PermissionChecker()
    call = ToolCall(name="write_file", arguments={"path": "out.txt", "content": "x"})
    decision, record = checker.evaluate(call, policy)

    assert decision == Decision.DENY
    assert "fs.write" in record.inferred_categories
    print("✓ test_read_only_denies_write")


def test_read_only_denies_exec():
    policy = load_policy("read_only.yaml")
    checker = PermissionChecker()
    call = ToolCall(name="run_terminal", arguments={"cmd": "ls"})
    decision, record = checker.evaluate(call, policy)

    assert decision == Decision.DENY
    assert "code.exec" in record.inferred_categories
    print("✓ test_read_only_denies_exec")


def test_no_code_exec_allows_write():
    policy = load_policy("no_code_exec.yaml")
    checker = PermissionChecker()
    call = ToolCall(name="write_file", arguments={"path": "report.md", "content": "hi"})
    decision, record = checker.evaluate(call, policy)

    assert decision == Decision.ALLOW
    print("✓ test_no_code_exec_allows_write")


def test_no_code_exec_denies_exec():
    policy = load_policy("no_code_exec.yaml")
    checker = PermissionChecker()
    call = ToolCall(name="run_terminal", arguments={"cmd": "echo hello"})
    decision, record = checker.evaluate(call, policy)

    assert decision == Decision.DENY
    print("✓ test_no_code_exec_denies_exec")


def test_no_code_exec_allows_http():
    policy = load_policy("no_code_exec.yaml")
    checker = PermissionChecker()
    call = ToolCall(name="http_request", arguments={"url": "https://api.github.com"})
    decision, record = checker.evaluate(call, policy)

    assert decision == Decision.ALLOW
    print("✓ test_no_code_exec_allows_http")


def test_record_has_latency():
    policy = load_policy("read_only.yaml")
    checker = PermissionChecker()
    call = ToolCall(name="read_file", arguments={"path": "a.py"})
    decision, record = checker.evaluate(call, policy)

    assert record.latency_ms >= 0
    assert record.policy_name == "read-only"
    assert record.tool_name == "read_file"
    print("✓ test_record_has_latency")


if __name__ == "__main__":
    print("Running Permission Checker tests...\n")
    test_read_only_allows_normal_read()
    test_read_only_denies_sensitive_read()
    test_read_only_denies_write()
    test_read_only_denies_exec()
    test_no_code_exec_allows_write()
    test_no_code_exec_denies_exec()
    test_no_code_exec_allows_http()
    test_record_has_latency()
    print("\nAll Permission Checker tests passed.")
