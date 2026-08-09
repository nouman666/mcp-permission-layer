"""Evaluate organic-style (non-template) hold-out set and update paper tables."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from metrics import bootstrap_ci, confusion_counts, derive_rates  # noqa: E402
from models import Decision  # noqa: E402
from proxy import EnforcementProxy, always_deny_ask_handler  # noqa: E402

DATA = ROOT / "datasets" / "organic_holdout.json"
RESULTS = ROOT / "results"
PROFILES = ["read_only", "limited_network", "no_code_exec", "approval_gated"]


def eval_profile(profile: str, cases: list) -> dict:
    log = os.path.join(tempfile.gettempdir(), f"organic_{profile}.jsonl")
    proxy = EnforcementProxy(
        policy_path=str(ROOT / "policies" / f"{profile}.yaml"),
        log_path=log,
        ask_handler=always_deny_ask_handler,
    )
    y_true, y_pred, lats = [], [], []
    residuals = []
    fps = []
    for c in cases:
        t0 = time.perf_counter()
        d, _ = proxy.handle_tool_call(c["tool_name"], c.get("arguments") or {})
        lats.append((time.perf_counter() - t0) * 1000)
        allowed = d == Decision.ALLOW
        is_attack = not c["beneficial"]
        y_true.append(is_attack)
        y_pred.append(allowed)
        if is_attack and allowed:
            residuals.append(c["id"])
        if (not is_attack) and (not allowed):
            fps.append(c["id"])
    rates = derive_rates(confusion_counts(y_true, y_pred))
    rates["latency_mean_ms"] = sum(lats) / len(lats)
    rates["residual_attack_ids"] = residuals
    rates["false_positive_ids"] = fps
    rates["bootstrap_asr"] = bootstrap_ci(y_true, y_pred, "asr", n_boot=500)
    rates["bootstrap_tsr"] = bootstrap_ci(y_true, y_pred, "tsr", n_boot=500)
    return rates


def main():
    cases = json.loads(DATA.read_text(encoding="utf-8"))
    mal = sum(1 for c in cases if not c["beneficial"])
    ben = sum(1 for c in cases if c["beneficial"])
    report = {
        "title": "Organic-style hold-out (non-template)",
        "n_total": len(cases),
        "n_malicious": mal,
        "n_benign": ben,
        "note": (
            "Hand-authored MCPTox-style / realistic workflow cases with diverse tool names; "
            "not produced by template expansion of the 20k stress corpus."
        ),
        "profiles": {},
    }
    print(f"Organic hold-out: {len(cases)} cases ({mal} mal / {ben} ben)")
    for profile in PROFILES:
        r = eval_profile(profile, cases)
        report["profiles"][profile] = r
        print(
            f"  {profile:<18} ASR={r['asr']:.2f}% TSR={r['tsr']:.2f}% F1={r['f1']:.2f}% "
            f"resid={r['residual_attack_ids']} fps={len(r['false_positive_ids'])}"
        )

    RESULTS.mkdir(parents=True, exist_ok=True)
    out = RESULTS / "organic_holdout_report.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    md = [
        "# Organic-style Hold-out (non-template)\n",
        f"_N={len(cases)} ({mal} attack / {ben} benign). Hand-authored; not template-expanded._\n",
        "| Profile | ASR (%) | TSR (%) | F1 (%) | Residual attacks | Benign blocked |",
        "|---------|---------|---------|--------|------------------|----------------|",
    ]
    for profile, r in report["profiles"].items():
        md.append(
            f"| {profile} | {r['asr']:.2f} | {r['tsr']:.2f} | {r['f1']:.2f} | "
            f"{len(r['residual_attack_ids'])} | {len(r['false_positive_ids'])} |"
        )
    ln = report["profiles"]["limited_network"]
    md.append(
        f"\nlimited_network bootstrap ASR 95% CI "
        f"[{ln['bootstrap_asr']['ci95_low']:.2f}, {ln['bootstrap_asr']['ci95_high']:.2f}]; "
        f"TSR 95% CI [{ln['bootstrap_tsr']['ci95_low']:.2f}, {ln['bootstrap_tsr']['ci95_high']:.2f}].\n"
    )
    md_path = RESULTS / "ORGANIC_HOLDOUT_TABLE.md"
    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")

    # Patch TABLES_FOR_PAPER.md
    paper_tables = RESULTS / "TABLES_FOR_PAPER.md"
    block = "## Table: Organic-style hold-out (non-template)\n\n" + "\n".join(md[1:]) + "\n"
    if paper_tables.exists():
        text = paper_tables.read_text(encoding="utf-8")
        marker = "## Table: Organic-style hold-out (non-template)"
        if marker in text:
            pre, rest = text.split(marker, 1)
            if "\n## " in rest:
                post = rest.split("\n## ", 1)[1]
                text = pre + block + "## " + post
            else:
                text = pre + block
        else:
            text = text.rstrip() + "\n\n" + block
        paper_tables.write_text(text, encoding="utf-8")

    print("Saved", out)
    print("Saved", md_path)
    return report


if __name__ == "__main__":
    main()
