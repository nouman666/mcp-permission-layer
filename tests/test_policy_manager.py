"""
Basic tests for Policy Manager.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from policy_manager import PolicyManager, PolicyError
from models import Decision


def test_load_read_only():
    pm = PolicyManager()
    policy = pm.load(os.path.join(os.path.dirname(__file__), "..", "policies", "read_only.yaml"))

    assert policy.name == "read-only"
    assert policy.default == Decision.DENY
    assert "fs.read" in policy.permissions
    assert policy.permissions["fs.read"].allow is True
    assert policy.permissions["code.exec"].allow is False
    assert pm.is_loaded is True
    print("✓ test_load_read_only")


def test_load_no_code_exec():
    pm = PolicyManager()
    policy = pm.load(os.path.join(os.path.dirname(__file__), "..", "policies", "no_code_exec.yaml"))

    assert policy.name == "no-code-exec"
    assert policy.permissions["fs.write"].allow is True
    assert policy.permissions["net.http"].allow is True
    assert policy.permissions["code.exec"].allow is False
    print("✓ test_load_no_code_exec")


def test_get_current():
    pm = PolicyManager()
    pm.load(os.path.join(os.path.dirname(__file__), "..", "policies", "read_only.yaml"))
    policy = pm.get_current()
    assert policy.name == "read-only"
    print("✓ test_get_current")


def test_missing_file():
    pm = PolicyManager()
    try:
        pm.load("nonexistent.yaml")
        assert False, "Should have raised"
    except PolicyError:
        print("✓ test_missing_file")


def test_not_loaded():
    pm = PolicyManager()
    try:
        pm.get_current()
        assert False, "Should have raised"
    except PolicyError:
        print("✓ test_not_loaded")


if __name__ == "__main__":
    print("Running Policy Manager tests...\n")
    test_load_read_only()
    test_load_no_code_exec()
    test_get_current()
    test_missing_file()
    test_not_loaded()
    print("\nAll Policy Manager tests passed.")
