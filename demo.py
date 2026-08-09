"""
Simple demo of the Runtime Permission Enforcement Layer.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from proxy import EnforcementProxy
from models import Decision


def main():
    print("=" * 60)
    print("Runtime Permission Enforcement Layer — Demo")
    print("=" * 60)

    proxy = EnforcementProxy(
        policy_path="policies/read_only.yaml",
        log_path="logs/demo_decisions.jsonl",
    )

    test_calls = [
        ("read_file", {"path": "src/main.py"}),
        ("read_file", {"path": "~/.ssh/id_rsa"}),
        ("write_file", {"path": "out.txt", "content": "hello"}),
        ("run_terminal", {"cmd": "ls -la"}),
        ("http_request", {"url": "https://api.github.com"}),
    ]

    print("\nPolicy: read-only\n")
    for name, args in test_calls:
        decision, record = proxy.handle_tool_call(name, args)
        status = decision.value.upper()
        cats = ", ".join(sorted(record.inferred_categories))
        print(f"  {name:20s} → {status:6s}  (categories: {cats})")

    print(f"\nAudit log entries: {len(proxy.get_audit_records())}")
    print("Demo finished.")


if __name__ == "__main__":
    main()
