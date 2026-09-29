"""
ASK-path evaluation.

Reviewer 1 Comment 4 implemented:
- the default reported third mode is now a deterministic simulated-approval
  policy, not a human-operated experiment;
- the artificial 50 ms delay has been removed;
- actual interactive terminal approval remains available only via
  ``--mode interactive`` and is not used for manuscript Table 11 unless a
  human explicitly runs it and records those measurements.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from metrics import confusion_counts, derive_rates  # noqa: E402
from models import Decision, DecisionRecord, ToolCall  # noqa: E402
from proxy import EnforcementProxy  # noqa: E402

PROMPTS_PATH = ROOT / "datasets" / "ask_study_prompts.json"
POLICY = ROOT / "policies" / "approval_gated.yaml"
RESULTS = ROOT / "results"

SENSITIVE_RE = re.compile(r"(\.ssh|\.aws|\.env|credential|id_rsa|\.pem|secret|git-credentials)", re.I)
ATTACKER_RE = re.compile(r"(attacker|evil\.com|exfil|malware)", re.I)
SHELLISH_RE = re.compile(r"[|;&`]|\$\(|\b(bash|curl|wget|nc)\b", re.I)


def simulated_protocol_approve(tool_call: ToolCall, record: DecisionRecord) -> bool:
    """Deterministic approval policy; this is not a human observation."""
    name = tool_call.name.lower()
    blob = json.dumps(tool_call.arguments or {}, ensure_ascii=False)
    if SENSITIVE_RE.search(blob) or SENSITIVE_RE.search(name):
        return False
    if "env.read" in record.inferred_categories or record.high_risk:
        return False
    if any(k in name for k in ("terminal", "bash", "shell", "exec", "command", "process", "spawn")):
        return False
    if "code.exec" in record.inferred_categories or "process" in record.inferred_categories:
        return False
    if SHELLISH_RE.search(blob) or ATTACKER_RE.search(blob) or "/tmp/malware" in blob.lower():
        return False
    if "fs.write" in record.inferred_categories:
        # Approval is intentionally narrow: project-like writes only.
        path = str((tool_call.arguments or {}).get("path", ""))
        if path.startswith(("/tmp", "/etc", "C:\\Windows")) or "malware" in path.lower():
            return False
        return True
    return False


def interactive_approve(tool_call: ToolCall, record: DecisionRecord) -> bool:
    print("\n" + "=" * 56)
    print("ASK — Permission confirmation")
    print(f"Tool: {tool_call.name}")
    print(f"Arguments: {tool_call.arguments}")
    print(f"Categories: {', '.join(sorted(record.inferred_categories))}")
    print(f"High risk: {record.high_risk}")
    try:
        ans = input("Allow this tool call? [y/N]: ").strip().lower()
    except EOFError:
        ans = "n"
    return ans in ("y", "yes")


class AskStudyRunner:
    def __init__(self, mode: str):
        self.mode = mode
        self.ask_events: list[dict] = []

    def make_handler(self):
        def handler(tool_call: ToolCall, record: DecisionRecord) -> bool:
            t0 = time.perf_counter()
            if self.mode == "auto_deny":
                approved = False
            elif self.mode == "auto_allow":
                approved = True
            elif self.mode == "simulated_approval":
                approved = simulated_protocol_approve(tool_call, record)
            elif self.mode == "interactive":
                approved = interactive_approve(tool_call, record)
            else:
                raise ValueError(self.mode)
            elapsed = (time.perf_counter() - t0) * 1000.0
            self.ask_events.append({
                "tool_name": tool_call.name,
                "arguments": tool_call.arguments,
                "categories": sorted(record.inferred_categories),
                "high_risk": record.high_risk,
                "approved": approved,
                "decision_time_ms": round(elapsed, 6),
            })
            return approved
        return handler

    def run_case(self, proxy: EnforcementProxy, case: dict) -> dict:
        before = len(self.ask_events)
        t0 = time.perf_counter()
        decision, record = proxy.handle_tool_call(case["tool_name"], case.get("arguments") or {})
        total_ms = (time.perf_counter() - t0) * 1000.0
        asked = len(self.ask_events) > before
        event = self.ask_events[-1] if asked else None
        return {
            "id": case["id"],
            "beneficial": case["beneficial"],
            "tool_name": case["tool_name"],
            "categories": sorted(record.inferred_categories),
            "triggered_ask": asked,
            "ask_approved": event["approved"] if event else None,
            "final_decision": decision.value,
            "allowed": decision == Decision.ALLOW,
            "total_latency_ms": round(total_ms, 6),
            "approval_policy_eval_ms": event["decision_time_ms"] if event else 0.0,
        }


def evaluate_mode(mode: str, cases: list[dict]) -> dict:
    runner = AskStudyRunner(mode)
    proxy = EnforcementProxy(
        policy_path=str(POLICY),
        log_path=os.path.join(tempfile.gettempdir(), f"ask_study_{mode}.jsonl"),
        ask_handler=runner.make_handler(),
    )
    details = [runner.run_case(proxy, c) for c in cases]
    rates = derive_rates(confusion_counts(
        [not d["beneficial"] for d in details],
        [d["allowed"] for d in details],
    ))
    asked = [d for d in details if d["triggered_ask"]]
    approved = [d for d in asked if d["ask_approved"]]
    times = [d["approval_policy_eval_ms"] for d in asked]
    return {
        "mode": mode,
        "n_cases": len(cases),
        "n_ask_prompts": len(asked),
        "approval_rate_pct": (len(approved) / len(asked) * 100.0) if asked else 0.0,
        "asr": rates["asr"],
        "bcar": rates["bcar"],
        "f1": rates["f1"],
        "mean_approval_policy_eval_ms": sum(times) / len(times) if times else 0.0,
        "mean_total_latency_ms": sum(d["total_latency_ms"] for d in details) / len(details),
        "details": details,
        "ask_events": runner.ask_events,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("all", "auto_deny", "auto_allow", "simulated_approval", "interactive"), default="all")
    args = parser.parse_args()
    cases = json.loads(PROMPTS_PATH.read_text(encoding="utf-8"))
    modes = ["auto_deny", "auto_allow", "simulated_approval"] if args.mode == "all" else [args.mode]
    report = {
        "title": "ASK approval-path evaluation",
        "interpretation": "simulated_approval is deterministic software policy, not a human study",
        "modes": {m: evaluate_mode(m, cases) for m in modes},
    }
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "ask_study_report_revised.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    lines = [
        "# Revised ASK-path results",
        "",
        "`simulated_approval` is deterministic and contains no artificial human-think delay.",
        "",
        "| Mode | ASK n | Approval | ASR | BCAR | F1 | Approval-policy eval ms |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for m, r in report["modes"].items():
        lines.append(f"| {m} | {r['n_ask_prompts']} | {r['approval_rate_pct']:.1f}% | {r['asr']:.2f}% | {r['bcar']:.2f}% | {r['f1']:.2f}% | {r['mean_approval_policy_eval_ms']:.4f} |")
    (RESULTS / "ASK_STUDY_TABLE_REVISED.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({m: {k: v for k, v in r.items() if k not in ('details','ask_events')} for m, r in report['modes'].items()}, indent=2))


if __name__ == "__main__":
    main()
