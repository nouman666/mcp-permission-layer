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

# Reviewer 1 Comment 1 / Comment 3 restriction-boundary tests implemented.
def test_nested_ssh_path_denied_under_read_only():
    policy = load_policy("read_only.yaml")
    checker = PermissionChecker()
    call = ToolCall(name="read_file", arguments={"input": {"path": "~/.ssh/id_rsa"}})
    decision, _ = checker.evaluate(call, policy)
    assert decision == Decision.DENY


def test_nested_untrusted_url_denied_under_limited_network():
    policy = load_policy("limited_network.yaml")
    checker = PermissionChecker()
    call = ToolCall(name="http_request", arguments={"request": {"url": "https://untrusted.example/collect"}})
    decision, _ = checker.evaluate(call, policy)
    assert decision == Decision.DENY


def test_split_untrusted_host_denied_under_limited_network():
    policy = load_policy("limited_network.yaml")
    checker = PermissionChecker()
    call = ToolCall(name="http_request", arguments={"host": "untrusted.example", "path": "/collect"})
    decision, _ = checker.evaluate(call, policy)
    assert decision == Decision.DENY


def test_split_allowlisted_host_allowed_under_limited_network():
    policy = load_policy("limited_network.yaml")
    checker = PermissionChecker()
    call = ToolCall(name="http_request", arguments={"host": "api.github.com", "path": "/zen"})
    decision, _ = checker.evaluate(call, policy)
    assert decision == Decision.ALLOW


def test_unresolved_network_destination_denied_when_allowlist_active():
    policy = load_policy("limited_network.yaml")
    checker = PermissionChecker()
    call = ToolCall(name="http_request", arguments={"request": {"method": "GET"}})
    decision, _ = checker.evaluate(call, policy)
    assert decision == Decision.DENY


def test_persist_blob_write_denied_under_read_only():
    policy = load_policy("read_only.yaml")
    checker = PermissionChecker()
    call = ToolCall(name="persist_blob", arguments={"content": "x", "path": "/etc/hosts"})
    decision, record = checker.evaluate(call, policy)
    assert "fs.write" in record.inferred_categories
    assert decision == Decision.DENY


# Review Part B is implemented (Reviewer 2 Comment 2):
# The same renamed-write ordinary-path case is denied under a read-permitting
# profile because its operation intent is unresolved, rather than being allowed
# as an ordinary read.
def test_reviewer2_renamed_write_ordinary_path_denied():
    policy = load_policy("limited_network.yaml")
    checker = PermissionChecker()
    call = ToolCall(name="archive_object", arguments={"path": "workspace/output.txt"})
    decision, record = checker.evaluate(call, policy)
    assert "fs.read" in record.inferred_categories
    assert "code.exec" in record.inferred_categories
    assert decision == Decision.DENY
