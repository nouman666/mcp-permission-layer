"""
Step 9 — ASK / human-in-the-loop evaluation.

Modes:
  auto_deny   — ASK → DENY (conservative automated lab setting)
  auto_allow  — ASK → ALLOW
  author_ask  — author-as-user protocol (default non-interactive)
  interactive — real terminal prompts for a human

Usage (from mcp_permission_layer/):
  python scripts/run_ask_study.py
  python scripts/run_ask_study.py --mode interactive
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

SENSITIVE_RE = re.compile(
    r"(\.ssh|\.aws|\.env|credential|id_rsa|\.pem|secret|git-credentials)",
    re.IGNORECASE,
)
ATTACKER_RE = re.compile(r"(attacker|evil\.com|exfil|malware)", re.IGNORECASE)
SHELLISH_RE = re.compile(r"[|;&`]|\$\(|\b(bash|curl|wget|nc)\b", re.IGNORECASE)


def author_protocol_approve(tool_call: ToolCall, record: DecisionRecord) -> bool:
    """
    Deterministic author-as-user policy (see datasets/ask_author_protocol.md).
    Returns True to approve ASK.
    """
    name = tool_call.name.lower()
    blob = json.dumps(tool_call.arguments or {}, ensure_ascii=False)

    # Rule 1: sensitive / env
    if SENSITIVE_RE.search(blob) or SENSITIVE_RE.search(name):
        return False
    if "env.read" in record.inferred_categories or record.high_risk:
        # Approve only if not actually sensitive-looking args
        if SENSITIVE_RE.search(blob) or "api_key" in blob.lower() or "token" in blob.lower():
            return False
        # high_risk alone → deny
        if record.high_risk:
            return False

    # Rule 2: shell / process
    if any(k in name for k in ("terminal", "bash", "shell", "exec", "command", "process", "spawn")):
        return False
    if "code.exec" in record.inferred_categories or "process" in record.inferred_categories:
        return False
    if SHELLISH_RE.search(blob):
        return False

    # Rule 3: attacker / malware payloads
    if ATTACKER_RE.search(blob):
        return False
    if "/tmp/malware" in blob.lower():
        return False

    # Rule 4: approve legitimate project writes / already-allowed paths
    # (If we reached ASK, typical cases are fs.write or borderline.)
    if "fs.write" in record.inferred_categories:
        path = str((tool_call.arguments or {}).get("path", ""))
        # deny writes clearly outside project-ish paths
        if path.startswith("/tmp") or "malware" in path.lower():
            return False
        return True

    # Default uncertain → deny
    return False


def interactive_approve(tool_call: ToolCall, record: DecisionRecord) -> bool:
    print("\n" + "=" * 56)
    print("  ASK — Permission confirmation")
    print("=" * 56)
    print(f"  Tool       : {tool_call.name}")
    print(f"  Arguments  : {tool_call.arguments}")
    print(f"  Categories : {', '.join(sorted(record.inferred_categories))}")
    print(f"  High risk  : {record.high_risk}")
    print(f"  Policy     : {record.policy_name}")
    print("=" * 56)
    try:
        ans = input("  Allow this tool call? [y/N]: ").strip().lower()
    except EOFError:
        ans = "n"
    return ans in ("y", "yes")


class AskStudyRunner:
    def __init__(self, mode: str):
        self.mode = mode
        self.ask_events: list[dict] = []
        self._last_was_ask = False
        self._ask_decision_time_ms = 0.0

    def make_handler(self):
        def handler(tool_call: ToolCall, record: DecisionRecord) -> bool:
            self._last_was_ask = True
            t0 = time.perf_counter()

            if self.mode == "auto_deny":
                approved = False
                # negligible decision time
            elif self.mode == "auto_allow":
                approved = True
            elif self.mode == "author_ask":
                # simulate brief human think-time for realism in totals
                time.sleep(0.05)
                approved = author_protocol_approve(tool_call, record)
            elif self.mode == "interactive":
                approved = interactive_approve(tool_call, record)
            else:
                raise ValueError(self.mode)

            self._ask_decision_time_ms = (time.perf_counter() - t0) * 1000.0
            self.ask_events.append({
                "tool_name": tool_call.name,
                "arguments": tool_call.arguments,
                "categories": sorted(record.inferred_categories),
                "high_risk": record.high_risk,
                "approved": approved,
                "decision_time_ms": round(self._ask_decision_time_ms, 3),
            })
            return approved

        return handler

    def run_case(self, proxy: EnforcementProxy, case: dict) -> dict:
        self._last_was_ask = False
        self._ask_decision_time_ms = 0.0
        n_asks_before = len(self.ask_events)

        t0 = time.perf_counter()
        decision, record = proxy.handle_tool_call(
            case["tool_name"], case.get("arguments") or {}
        )
        total_ms = (time.perf_counter() - t0) * 1000.0

        asked = len(self.ask_events) > n_asks_before
        approved = None
        ask_ms = 0.0
        if asked:
            approved = self.ask_events[-1]["approved"]
            ask_ms = self.ask_events[-1]["decision_time_ms"]

        return {
            "id": case["id"],
            "beneficial": case["beneficial"],
            "tool_name": case["tool_name"],
            "user_prompt": case.get("user_prompt", ""),
            "raw_high_risk": record.high_risk,
            "categories": sorted(record.inferred_categories),
            "triggered_ask": asked,
            "ask_approved": approved,
            "final_decision": decision.value,
            "allowed": decision == Decision.ALLOW,
            "total_latency_ms": round(total_ms, 3),
            "ask_extra_time_ms": round(ask_ms, 3),
            "expected_author": case.get("expected_author"),
        }


def evaluate_mode(mode: str, cases: list[dict]) -> dict:
    runner = AskStudyRunner(mode)
    log_path = os.path.join(tempfile.gettempdir(), f"ask_study_{mode}.jsonl")
    proxy = EnforcementProxy(
        policy_path=str(POLICY),
        log_path=log_path,
        ask_handler=runner.make_handler(),
    )

    details = []
    for case in cases:
        details.append(runner.run_case(proxy, case))

    y_true = [not d["beneficial"] for d in details]
    y_pred = [d["allowed"] for d in details]
    rates = derive_rates(confusion_counts(y_true, y_pred))

    ask_cases = [d for d in details if d["triggered_ask"]]
    approvals = [d for d in ask_cases if d["ask_approved"]]
    approval_rate = (len(approvals) / len(ask_cases) * 100.0) if ask_cases else 0.0
    extra_times = [d["ask_extra_time_ms"] for d in ask_cases]
    mean_extra = sum(extra_times) / len(extra_times) if extra_times else 0.0
    total_extra = sum(extra_times)

    # Author protocol agreement (only meaningful for author_ask / interactive)
    agreement = None
    if mode in ("author_ask", "interactive"):
        comparable = [d for d in ask_cases if d.get("expected_author")]
        if comparable:
            ok = 0
            for d in comparable:
                exp = d["expected_author"]
                got = "approve" if d["ask_approved"] else "deny"
                if exp == got:
                    ok += 1
            agreement = ok / len(comparable) * 100.0

    return {
        "mode": mode,
        "n_cases": len(cases),
        "n_ask_prompts": len(ask_cases),
        "approval_rate_pct": approval_rate,
        "asr": rates["asr"],
        "block_rate": rates["block_rate"],
        "tsr": rates["tsr"],
        "f1": rates["f1"],
        "mean_ask_extra_time_ms": mean_extra,
        "total_ask_extra_time_ms": total_extra,
        "mean_total_latency_ms": sum(d["total_latency_ms"] for d in details) / len(details),
        "author_protocol_agreement_pct": agreement,
        "details": details,
        "ask_events": runner.ask_events,
    }


def render_markdown(report: dict) -> str:
    lines = [
        "# ASK / Human-in-the-loop Results (Step 9)\n",
        "_Policy: `approval_gated`. Automated modes treat ASK without a human; "
        "`author_ask` follows `datasets/ask_author_protocol.md`._\n",
        "| Mode | ASK prompts | Approval rate | Final ASR | Final TSR | F1 | Mean extra ASK time (ms) |",
        "|------|-------------|---------------|-----------|-----------|----|--------------------------|",
    ]
    for mode, r in report["modes"].items():
        lines.append(
            f"| {mode} | {r['n_ask_prompts']} | {r['approval_rate_pct']:.1f}% | "
            f"{r['asr']:.2f}% | {r['tsr']:.2f}% | {r['f1']:.2f}% | "
            f"{r['mean_ask_extra_time_ms']:.1f} |"
        )

    lines.append("\n## Notes\n")
    lines.append(report["notes"])
    lines.append("\n## Author-as-user ASK decisions\n")
    author = report["modes"].get("author_ask", {})
    lines.append("| ID | Beneficial | Tool | ASK? | Approved | Final | Expected |")
    lines.append("|----|------------|------|------|----------|-------|----------|")
    for d in author.get("details", []):
        lines.append(
            f"| {d['id']} | {d['beneficial']} | {d['tool_name']} | "
            f"{d['triggered_ask']} | {d['ask_approved']} | {d['final_decision']} | "
            f"{d.get('expected_author')} |"
        )
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=("all", "auto_deny", "auto_allow", "author_ask", "interactive"),
        default="all",
    )
    args = parser.parse_args()

    cases = json.loads(PROMPTS_PATH.read_text(encoding="utf-8"))
    modes = (
        ["auto_deny", "auto_allow", "author_ask"]
        if args.mode == "all"
        else [args.mode]
    )

    report = {
        "title": "ASK / human-in-the-loop evaluation",
        "policy": "approval_gated",
        "n_prompts": len(cases),
        "protocol": "datasets/ask_author_protocol.md",
        "modes": {},
        "notes": (
            "Author-as-user lab protocol used when multi-participant recruitment "
            "is unavailable. Interactive mode is available via "
            "`python scripts/run_ask_study.py --mode interactive`. "
            "Prior automated paper runs that map ASK→DENY correspond to `auto_deny`."
        ),
    }

    for mode in modes:
        print(f"\n=== MODE: {mode} ===")
        result = evaluate_mode(mode, cases)
        report["modes"][mode] = result
        print(
            f"  ASK prompts={result['n_ask_prompts']}  "
            f"approval={result['approval_rate_pct']:.1f}%  "
            f"ASR={result['asr']:.2f}%  TSR={result['tsr']:.2f}%  "
            f"extra_ms={result['mean_ask_extra_time_ms']:.1f}"
        )
        if result["author_protocol_agreement_pct"] is not None:
            print(f"  protocol agreement={result['author_protocol_agreement_pct']:.1f}%")

    RESULTS.mkdir(parents=True, exist_ok=True)
    out_json = RESULTS / "ask_study_report.json"
    out_md = RESULTS / "ASK_STUDY_TABLE.md"
    out_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    out_md.write_text(render_markdown(report), encoding="utf-8")

    # Append into TABLES_FOR_PAPER.md
    paper = RESULTS / "TABLES_FOR_PAPER.md"
    section = "## Table: ASK / Human-in-the-loop\n\n" + "\n".join(
        render_markdown(report).splitlines()[2:8]
    ) + "\n"
    if paper.exists():
        text = paper.read_text(encoding="utf-8")
        marker = "## Table: ASK / Human-in-the-loop"
        if marker in text:
            pre, rest = text.split(marker, 1)
            if "\n## " in rest[len(marker):] if False else "\n## " in rest:
                # rest starts with marker content already stripped? we split on marker
                pass
            # simpler: remove old section
            parts = text.split(marker)
            pre = parts[0]
            if len(parts) > 1 and "\n## " in parts[1]:
                post = parts[1].split("\n## ", 1)[1]
                text = pre + section + "\n## " + post
            else:
                text = pre + section
        else:
            text = text.rstrip() + "\n\n" + section
        paper.write_text(text, encoding="utf-8")

    print("\nSaved", out_json)
    print("Saved", out_md)


if __name__ == "__main__":
    main()
