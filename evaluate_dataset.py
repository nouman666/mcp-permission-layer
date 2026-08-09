"""
Phase 4 Evaluation Harness (Expanded)
-------------------------------------
- Overall ASR / Benign SR / Damage Reduction
- Paradigm-wise breakdown
- Category-wise breakdown
- Residual risk (attacks that still succeed)
- Utility cost (benign calls that were denied)
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from proxy import EnforcementProxy, always_deny_ask_handler
from models import Decision


DATASET_PATH = os.path.join(os.path.dirname(__file__), "datasets", "attack_dataset.json")
POLICY_DIR = os.path.join(os.path.dirname(__file__), "policies")

POLICIES = [
    ("baseline", None),
    ("read_only", "read_only.yaml"),
    ("limited_network", "limited_network.yaml"),
    ("no_code_exec", "no_code_exec.yaml"),
    ("approval_gated", "approval_gated.yaml"),
]


def load_dataset():
    with open(DATASET_PATH, encoding="utf-8") as f:
        return json.load(f)


def run_case(proxy, case) -> str:
    if proxy is None:
        return "allow"
    decision, _ = proxy.handle_tool_call(
        name=case["tool_name"],
        arguments=case.get("arguments") or {},
    )
    return decision.value


def evaluate():
    dataset = load_dataset()
    malicious = [c for c in dataset if not c["beneficial"]]
    benign = [c for c in dataset if c["beneficial"]]

    print("=" * 78)
    print("  Phase 4 — Expanded Security Evaluation")
    print("=" * 78)
    print(f"  Dataset : {len(dataset)} cases  ({len(malicious)} malicious, {len(benign)} benign)")
    print()

    results = {}

    for policy_name, policy_file in POLICIES:
        print(f"> {policy_name}")
        print("-" * 60)

        if policy_file is None:
            proxy = None
        else:
            log_path = os.path.join(tempfile.gettempdir(), f"eval_{policy_name}.jsonl")
            proxy = EnforcementProxy(
                policy_path=os.path.join(POLICY_DIR, policy_file),
                log_path=log_path,
                ask_handler=always_deny_ask_handler,
            )

        mal_allow = 0
        ben_allow = 0
        by_paradigm = defaultdict(lambda: {"total": 0, "allowed": 0})
        by_category = defaultdict(lambda: {"total": 0, "allowed": 0})
        residual = []
        utility_cost = []

        for case in malicious:
            outcome = run_case(proxy, case)
            allowed = outcome == "allow"
            if allowed:
                mal_allow += 1
                residual.append(case)

            parad = case.get("paradigm", "unknown")
            cat = case.get("category", "unknown")
            by_paradigm[parad]["total"] += 1
            by_category[cat]["total"] += 1
            if allowed:
                by_paradigm[parad]["allowed"] += 1
                by_category[cat]["allowed"] += 1

        for case in benign:
            outcome = run_case(proxy, case)
            if outcome == "allow":
                ben_allow += 1
            else:
                utility_cost.append(case)

        asr = mal_allow / len(malicious) * 100 if malicious else 0
        bsr = ben_allow / len(benign) * 100 if benign else 0
        block = 100 - asr

        results[policy_name] = {
            "asr": asr, "bsr": bsr, "block": block,
            "mal_allow": mal_allow, "ben_allow": ben_allow,
            "by_paradigm": dict(by_paradigm),
            "by_category": dict(by_category),
            "residual": residual,
            "utility_cost": utility_cost,
        }

        print(f"  Benign Success Rate : {bsr:.1f}%  ({ben_allow}/{len(benign)})")
        print(f"  Attack Success Rate : {asr:.1f}%  ({mal_allow}/{len(malicious)})")
        print(f"  Attack Block Rate   : {block:.1f}%")
        print()

    print("=" * 78)
    print("  OVERALL COMPARISON")
    print("=" * 78)
    print(f"{'Policy':<20} {'Benign SR':>10} {'Attack SR':>10} {'Block Rate':>12} {'Damage Red.':>12}")
    print("-" * 78)
    baseline_asr = results["baseline"]["asr"] or 100.0
    for name, r in results.items():
        if name == "baseline":
            damage_red = 0.0
        else:
            damage_red = (1 - r["asr"] / baseline_asr) * 100
        print(f"{name:<20} {r['bsr']:>9.1f}% {r['asr']:>9.1f}% {r['block']:>11.1f}% {damage_red:>11.1f}%")
    print()

    print("=" * 78)
    print("  PARADIGM-WISE ATTACK SUCCESS RATE (%)")
    print("=" * 78)
    paradigms = sorted({c["paradigm"] for c in malicious})
    header = f"{'Paradigm':<22}" + "".join(f"{p:>14}" for p, _ in POLICIES)
    print(header)
    print("-" * len(header))
    for parad in paradigms:
        row = f"{parad:<22}"
        for pname, _ in POLICIES:
            info = results[pname]["by_paradigm"].get(parad, {"total": 0, "allowed": 0})
            if info["total"] == 0:
                row += f"{'n/a':>14}"
            else:
                pct = info["allowed"] / info["total"] * 100
                row += f"{pct:>13.1f}%"
        print(row)
    print()

    print("=" * 78)
    print("  CATEGORY-WISE ATTACK SUCCESS RATE (%)")
    print("=" * 78)
    categories = sorted({c["category"] for c in malicious})
    header = f"{'Category':<24}" + "".join(f"{p:>14}" for p, _ in POLICIES)
    print(header)
    print("-" * len(header))
    for cat in categories:
        row = f"{cat:<24}"
        for pname, _ in POLICIES:
            info = results[pname]["by_category"].get(cat, {"total": 0, "allowed": 0})
            if info["total"] == 0:
                row += f"{'n/a':>14}"
            else:
                pct = info["allowed"] / info["total"] * 100
                row += f"{pct:>13.1f}%"
        print(row)
    print()

    print("=" * 78)
    print("  RESIDUAL RISK (attacks still ALLOWED under each policy)")
    print("=" * 78)
    for pname, _ in POLICIES:
        if pname == "baseline":
            continue
        residual = results[pname]["residual"]
        print(f"\n  [{pname}] — {len(residual)} residual attack(s)")
        if not residual:
            print("    (none — all evaluated attacks blocked)")
        else:
            for c in residual[:20]:
                print(f"    {c['id']:<10} {c['category']:<22} {c['tool_name']:<16} {c['description'][:40]}")
            if len(residual) > 20:
                print(f"    ... and {len(residual)-20} more")

    print("\n" + "=" * 78)
    print("  UTILITY COST (benign calls DENIED under each policy)")
    print("=" * 78)
    for pname, _ in POLICIES:
        if pname == "baseline":
            continue
        cost = results[pname]["utility_cost"]
        print(f"\n  [{pname}] — {len(cost)} benign denial(s)")
        if not cost:
            print("    (none — all benign calls allowed)")
        else:
            for c in cost:
                print(f"    {c['id']:<10} {c['tool_name']:<16} {c['description'][:50]}")

    print("\n" + "=" * 78)
    print("Note: ASK treated as DENY (conservative automated evaluation).")
    print("Evaluation complete.")


if __name__ == "__main__":
    evaluate()
