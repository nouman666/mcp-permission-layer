"""
One-command IEEE evaluation suite.

Produces tables for:
  1) Real-MCP-style workflow set (simulated client→proxy→tools)
  2) Baseline comparison B0–B4
  3) Template stress vs unseen hold-out
  4) Adaptive ASR
  5) Multi-step escalation (per-call vs session taint)
  6) Ablation
  7) Stats + latency
  8) False-positive analysis

Usage (from mcp_permission_layer/):
  python scripts/build_holdout.py
  python scripts/run_full_evaluation.py
"""

from __future__ import annotations

import json
import os
import platform
import sys
import tempfile
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

from baselines.defenses import (  # noqa: E402
    B0NoDefense,
    B1StaticAllowlist,
    B2DefinitionScanning,
    B3GatewayFilter,
    B4FullLayer,
)
from metrics import (  # noqa: E402
    bootstrap_ci,
    confusion_counts,
    derive_rates,
    mean_std,
    percentile,
)
from inference import InferenceConfig  # noqa: E402
from models import Decision  # noqa: E402
from proxy import EnforcementProxy, always_deny_ask_handler  # noqa: E402

RESULTS = ROOT / "results"
POLICIES = ROOT / "policies"
DATA = ROOT / "datasets"
PROFILES = [
    "read_only",
    "limited_network",
    "no_code_exec",
    "approval_gated",
]


def load_json(path: Path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_jsonl(path: Path, max_rows: int | None = None):
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            rows.append(json.loads(line))
            if max_rows and len(rows) >= max_rows:
                break
    return rows


def load_stress_stratified(path: Path, n: int) -> list:
    """
    large_dataset.jsonl is ordered as 10k attacks then 10k benign.
    Take a balanced prefix sample so TSR is meaningful when n < 20000.
    """
    if n >= 20000:
        return load_jsonl(path)
    half = max(1, n // 2)
    attacks, benign = [], []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("beneficial"):
                if len(benign) < half:
                    benign.append(row)
            else:
                if len(attacks) < half:
                    attacks.append(row)
            if len(attacks) >= half and len(benign) >= half:
                break
    return attacks + benign


def make_proxy(profile: str, **kwargs) -> EnforcementProxy:
    log_path = os.path.join(tempfile.gettempdir(), f"ieee_eval_{profile}.jsonl")
    return EnforcementProxy(
        policy_path=str(POLICIES / f"{profile}.yaml"),
        log_path=log_path,
        ask_handler=always_deny_ask_handler,
        **kwargs,
    )


def eval_cases_with_defense(cases, decide_fn) -> dict:
    y_true, y_pred, latencies = [], [], []
    for case in cases:
        is_attack = not case.get("beneficial", False)
        t0 = time.perf_counter()
        outcome = decide_fn(case)
        latencies.append((time.perf_counter() - t0) * 1000.0)
        allowed = outcome == "allow"
        y_true.append(is_attack)
        y_pred.append(allowed)
    rates = derive_rates(confusion_counts(y_true, y_pred))
    rates["latency_mean_ms"] = sum(latencies) / len(latencies) if latencies else 0.0
    rates["latency_median_ms"] = percentile(latencies, 50)
    rates["latency_p95_ms"] = percentile(latencies, 95)
    rates["latency_p99_ms"] = percentile(latencies, 99)
    rates["_y_true"] = y_true
    rates["_y_pred"] = y_pred
    rates["_latencies"] = latencies
    return rates


def proxy_decide(proxy: EnforcementProxy, case) -> str:
    d, _ = proxy.handle_tool_call(case["tool_name"], case.get("arguments") or {})
    return "allow" if d == Decision.ALLOW else "deny"


def fmt_row(name: str, r: dict) -> str:
    return (
        f"{name:<28} ASR={r['asr']:6.2f}%  Block={r['block_rate']:6.2f}%  "
        f"TSR={r['tsr']:6.2f}%  F1={r['f1']:6.2f}%  lat={r['latency_mean_ms']:.3f}ms"
    )


# ---------------------------------------------------------------------------
# Table builders
# ---------------------------------------------------------------------------

def table_real_mcp() -> dict:
    cases = load_json(DATA / "real_mcp_workflows.json")
    out = {"title": "Real MCP Deployment Results (simulated workflows)", "rows": {}}
    # B0
    out["rows"]["B0_no_defense"] = strip_internal(
        eval_cases_with_defense(cases, lambda c: B0NoDefense().decide(
            c["tool_name"], c.get("arguments"), c.get("poisoned_description")
        ))
    )
    for profile in PROFILES:
        proxy = make_proxy(profile)
        out["rows"][f"B4_{profile}"] = strip_internal(
            eval_cases_with_defense(cases, lambda c, p=proxy: proxy_decide(p, c))
        )
    return out


def table_baselines(pilot, real_cases) -> dict:
    out = {"title": "Baseline Comparison", "pilot": {}, "real_mcp": {}}
    defenses_factory = lambda proxy: [
        B0NoDefense(),
        B1StaticAllowlist(),
        B2DefinitionScanning(),
        B3GatewayFilter(),
        B4FullLayer(proxy),
    ]
    proxy = make_proxy("limited_network")
    for label, cases in (("pilot", pilot), ("real_mcp", real_cases)):
        rows = {}
        for defense in defenses_factory(proxy):
            rows[defense.name] = strip_internal(
                eval_cases_with_defense(
                    cases,
                    lambda c, d=defense: d.decide(
                        c["tool_name"],
                        c.get("arguments"),
                        c.get("poisoned_description") or c.get("description"),
                    ),
                )
            )
        out[label] = rows
    return out


def table_holdout(stress_sample, unseen) -> dict:
    out = {"title": "Template stress vs Unseen test", "rows": {}}
    for profile in PROFILES:
        proxy = make_proxy(profile)
        stress_r = eval_cases_with_defense(stress_sample, lambda c, p=proxy: proxy_decide(p, c))
        # fresh proxy for unseen (same policy)
        proxy2 = make_proxy(profile)
        unseen_r = eval_cases_with_defense(unseen, lambda c, p=proxy2: proxy_decide(p, c))
        out["rows"][profile] = {
            "stress": strip_internal(stress_r),
            "unseen": strip_internal(unseen_r),
        }
    return out


def table_adaptive(adaptive_cases) -> dict:
    out = {"title": "Adaptive ASR", "rows": {}, "by_family": {}}
    for profile in PROFILES:
        proxy = make_proxy(profile)
        r = eval_cases_with_defense(adaptive_cases, lambda c, p=proxy: proxy_decide(p, c))
        out["rows"][profile] = strip_internal(r)

        # family breakdown (attacks only)
        fam = defaultdict(lambda: {"total": 0, "allowed": 0})
        for case in adaptive_cases:
            if case.get("beneficial"):
                continue
            family = case.get("family", "unknown")
            outcome = proxy_decide(proxy, case)
            fam[family]["total"] += 1
            if outcome == "allow":
                fam[family]["allowed"] += 1
        out["by_family"][profile] = {
            k: {
                "asr": (v["allowed"] / v["total"] * 100.0) if v["total"] else 0.0,
                **v,
            }
            for k, v in fam.items()
        }
    # B0 reference
    out["rows"]["B0_no_defense"] = strip_internal(
        eval_cases_with_defense(adaptive_cases, lambda c: "allow")
    )
    return out


def table_multistep(chains) -> dict:
    """
    Per-call: chain succeeds if every step ALLOWED.
    Session taint: after a sensitive/taint-source step is observed (even if denied
    for reading secrets that produce taint on allow OR if inferred high_risk),
    subsequent net.http / write / exec with outbound effect are denied.
    """
    out = {"title": "Multi-step escalation results", "rows": {}}

    for profile in PROFILES:
        proxy = make_proxy(profile)
        per_call_success = 0
        taint_success = 0
        attack_chains = 0
        detail = []

        for chain in chains:
            is_attack = not chain.get("beneficial", False)
            if is_attack:
                attack_chains += 1

            # Per-call only
            step_allows = []
            for step in chain["steps"]:
                d, rec = proxy.handle_tool_call(step["tool_name"], step.get("arguments") or {})
                step_allows.append(d == Decision.ALLOW)
            pc_ok = all(step_allows)

            # Session taint
            tainted = False
            taint_allows = []
            proxy_t = make_proxy(profile)
            for i, step in enumerate(chain["steps"]):
                d, rec = proxy_t.handle_tool_call(step["tool_name"], step.get("arguments") or {})
                allowed = d == Decision.ALLOW
                # Mark taint if this step is a configured taint source and would read sensitive/high_risk
                if i in set(chain.get("taint_sources") or []):
                    if rec.high_risk or "env.read" in rec.inferred_categories:
                        # Even if denied, attacker "obtained" intent; for session policy we
                        # taint when the step was allowed OR when categories indicate secret read attempt.
                        # Conservative: taint on high_risk attempt regardless of allow.
                        tainted = True
                    if allowed:
                        tainted = True
                if tainted and allowed:
                    # block escalation sinks under session taint
                    sinks = {"net.http", "fs.write", "code.exec", "process"}
                    if rec.inferred_categories & sinks:
                        allowed = False
                taint_allows.append(allowed)

            t_ok = all(taint_allows)

            if is_attack:
                if pc_ok:
                    per_call_success += 1
                if t_ok:
                    taint_success += 1

            detail.append({
                "id": chain["id"],
                "beneficial": chain.get("beneficial", False),
                "per_call_full_success": pc_ok,
                "session_taint_full_success": t_ok,
            })

        out["rows"][profile] = {
            "n_attack_chains": attack_chains,
            "per_call_chains_fully_succeed": per_call_success,
            "per_call_asr_pct": (per_call_success / attack_chains * 100.0) if attack_chains else 0.0,
            "session_taint_chains_fully_succeed": taint_success,
            "session_taint_asr_pct": (taint_success / attack_chains * 100.0) if attack_chains else 0.0,
            "detail": detail,
        }
    return out


def table_ablation(pilot) -> dict:
    out = {"title": "Ablation study (limited_network base)", "rows": {}}
    configs = {
        "Full system": dict(),
        "- argument inspection": dict(
            inference_config=InferenceConfig(use_argument_inspection=False)
        ),
        "- sensitive-path elevation": dict(
            inference_config=InferenceConfig(use_sensitive_path_elevation=False)
        ),
        "- domain allow-list": dict(use_domain_allow_list=False),
        "- name heuristics": dict(
            inference_config=InferenceConfig(use_name_heuristics=False)
        ),
        "- default-deny (default allow)": dict(
            inference_config=InferenceConfig(use_default_deny_unknown=False),
            force_default_allow=True,
        ),
    }
    for name, kwargs in configs.items():
        proxy = make_proxy("limited_network", **kwargs)
        out["rows"][name] = strip_internal(
            eval_cases_with_defense(pilot, lambda c, p=proxy: proxy_decide(p, c))
        )
    return out


def table_stats_latency(pilot) -> dict:
    proxy = make_proxy("limited_network")
    r = eval_cases_with_defense(pilot, lambda c: proxy_decide(proxy, c))
    stats = {}
    for metric in ("asr", "tsr", "f1"):
        stats[metric] = bootstrap_ci(r["_y_true"], r["_y_pred"], metric=metric, n_boot=1000)

    lats = r["_latencies"]
    # Warm repeat for latency distribution stability
    warm = []
    for _ in range(5):
        for case in pilot:
            t0 = time.perf_counter()
            proxy_decide(proxy, case)
            warm.append((time.perf_counter() - t0) * 1000.0)

    latency_table = {
        "CPU": platform.processor() or platform.machine(),
        "RAM": "n/a (see host)",
        "OS": f"{platform.system()} {platform.release()}",
        "Python": platform.python_version(),
        "N_calls_pilot": len(pilot),
        "N_calls_warm_repeats": len(warm),
        "Mean_ms": sum(warm) / len(warm),
        "Median_ms": percentile(warm, 50),
        "P95_ms": percentile(warm, 95),
        "P99_ms": percentile(warm, 99),
        "Includes_MCP_serialization": "No (decision path only)",
    }
    return {
        "title": "Statistics + latency",
        "bootstrap": stats,
        "latency": latency_table,
        "point": strip_internal(r),
    }


def table_false_positives(pilot) -> dict:
    proxy = make_proxy("limited_network")
    blocked = []
    for case in pilot:
        if not case.get("beneficial"):
            continue
        outcome = proxy_decide(proxy, case)
        if outcome != "allow":
            # categorize
            name = case["tool_name"].lower()
            args = case.get("arguments") or {}
            cat = "unknown-tool"
            if any(k in name for k in ("write", "create", "edit", "delete", "save", "mkdir")):
                cat = "write"
            elif any(k in name for k in ("http", "fetch", "request", "download", "upload")):
                cat = "network"
            elif "env" in name:
                cat = "env"
            elif any(k in name for k in ("terminal", "bash", "shell", "exec", "command")):
                cat = "code.exec"
            else:
                # argument-based
                blob = " ".join(str(v) for v in args.values())
                if "http://" in blob or "https://" in blob:
                    cat = "network"
                elif any(x in blob for x in ("/", "\\", ".py", ".md", ".json")):
                    cat = "path"
            blocked.append({
                "id": case["id"],
                "tool_name": case["tool_name"],
                "category": cat,
                "description": case.get("description", ""),
                "arguments": args,
            })

    by_cat = defaultdict(int)
    for b in blocked:
        by_cat[b["category"]] += 1

    return {
        "title": "False-positive analysis (limited_network)",
        "n_benign": sum(1 for c in pilot if c.get("beneficial")),
        "n_blocked": len(blocked),
        "by_category": dict(by_cat),
        "examples": blocked[:10],
        "discussion": (
            "Most FPs under limited-network are expected policy cost: writes and "
            "non-allowlisted network/env/exec. Remaining path/unknown-tool FPs may "
            "indicate over-approximation in fail-closed inference rather than "
            "intentional policy."
        ),
    }


def strip_internal(r: dict) -> dict:
    return {k: v for k, v in r.items() if not k.startswith("_")}


def print_section(title: str):
    print("\n" + "=" * 78)
    print(f"  {title}")
    print("=" * 78)


def main():
    RESULTS.mkdir(parents=True, exist_ok=True)

    # Ensure holdout exists
    holdout_dir = DATA / "holdout"
    if not (holdout_dir / "pilot_87.json").exists():
        from build_holdout import main as build_holdout
        build_holdout()

    pilot_87 = load_json(holdout_dir / "pilot_87.json")
    unseen = load_json(holdout_dir / "unseen_test.json")
    adaptive = load_json(DATA / "adaptive_attacks.json")
    chains = load_json(DATA / "multi_step_chains.json")
    real_cases = load_json(DATA / "real_mcp_workflows.json")
    # Stress sample: stratified by default; full 20k via STRESS_N=20000
    stress_n = int(os.environ.get("STRESS_N", "2000"))
    stress = load_stress_stratified(DATA / "large_dataset.jsonl", stress_n)

    report = {}

    print_section("1) Real MCP Deployment Results")
    report["real_mcp"] = table_real_mcp()
    for k, r in report["real_mcp"]["rows"].items():
        print(fmt_row(k, r))

    print_section("2) Baseline Comparison (pilot_87 + real set)")
    report["baselines"] = table_baselines(pilot_87, real_cases)
    for split in ("pilot", "real_mcp"):
        print(f"\n  [{split}]")
        for k, r in report["baselines"][split].items():
            print("  " + fmt_row(k, r))

    print_section("3) Template stress vs Unseen test")
    report["holdout"] = table_holdout(stress, unseen)
    print(f"  stress N={len(stress)} (set STRESS_N=20000 for full corpus)")
    for profile, pair in report["holdout"]["rows"].items():
        print(
            f"  {profile:<18} stress ASR={pair['stress']['asr']:.2f}% TSR={pair['stress']['tsr']:.2f}% | "
            f"unseen ASR={pair['unseen']['asr']:.2f}% TSR={pair['unseen']['tsr']:.2f}%"
        )

    print_section("4) Adaptive ASR")
    report["adaptive"] = table_adaptive(adaptive)
    for k, r in report["adaptive"]["rows"].items():
        print(fmt_row(k, r))

    print_section("5) Multi-step escalation")
    report["multistep"] = table_multistep(chains)
    for profile, r in report["multistep"]["rows"].items():
        print(
            f"  {profile:<18} per-call ASR={r['per_call_asr_pct']:.1f}% "
            f"({r['per_call_chains_fully_succeed']}/{r['n_attack_chains']}) | "
            f"session-taint ASR={r['session_taint_asr_pct']:.1f}% "
            f"({r['session_taint_chains_fully_succeed']}/{r['n_attack_chains']})"
        )

    print_section("6) Ablation")
    report["ablation"] = table_ablation(pilot_87)
    for k, r in report["ablation"]["rows"].items():
        print(fmt_row(k, r))

    print_section("7) Statistics + latency")
    report["stats_latency"] = table_stats_latency(pilot_87)
    for metric, s in report["stats_latency"]["bootstrap"].items():
        print(
            f"  {metric.upper():<6} point={s['point']:.2f}%  "
            f"mean±std={s['mean']:.2f}±{s['std']:.2f}  "
            f"95% CI [{s['ci95_low']:.2f}, {s['ci95_high']:.2f}]"
        )
    lat = report["stats_latency"]["latency"]
    print(
        f"  Latency mean/median/p95/p99 = "
        f"{lat['Mean_ms']:.3f}/{lat['Median_ms']:.3f}/{lat['P95_ms']:.3f}/{lat['P99_ms']:.3f} ms"
    )
    print(f"  Host: {lat['OS']} | Python {lat['Python']} | MCP serialization: {lat['Includes_MCP_serialization']}")

    print_section("8) False-positive analysis")
    report["false_positives"] = table_false_positives(pilot_87)
    fp = report["false_positives"]
    print(f"  Blocked benign: {fp['n_blocked']}/{fp['n_benign']}  by_category={fp['by_category']}")
    for ex in fp["examples"][:5]:
        print(f"    - {ex['id']} [{ex['category']}] {ex['tool_name']}: {ex['description'][:60]}")
    print(f"  Note: {fp['discussion']}")

    # Persist
    out_path = RESULTS / "ieee_evaluation_report.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    # Markdown summary for paper paste
    md_path = RESULTS / "TABLES_FOR_PAPER.md"
    md_path.write_text(render_markdown(report, stress_n=len(stress)), encoding="utf-8")

    print_section("DONE")
    print(f"  JSON : {out_path}")
    print(f"  MD   : {md_path}")


def render_markdown(report: dict, stress_n: int) -> str:
    lines = ["# IEEE Evaluation Tables (auto-generated)\n"]

    lines.append("## Table: Real MCP Deployment Results\n")
    lines.append("| Defense | ASR (%) | Block (%) | TSR (%) | F1 (%) | Latency ms |")
    lines.append("|---------|---------|-----------|---------|--------|------------|")
    for k, r in report["real_mcp"]["rows"].items():
        lines.append(
            f"| {k} | {r['asr']:.2f} | {r['block_rate']:.2f} | {r['tsr']:.2f} | "
            f"{r['f1']:.2f} | {r['latency_mean_ms']:.3f} |"
        )

    lines.append("\n## Table: Baseline Comparison (pilot_87)\n")
    lines.append("| Baseline | ASR (%) | Block (%) | TSR (%) | F1 (%) | Latency ms |")
    lines.append("|----------|---------|-----------|---------|--------|------------|")
    for k, r in report["baselines"]["pilot"].items():
        lines.append(
            f"| {k} | {r['asr']:.2f} | {r['block_rate']:.2f} | {r['tsr']:.2f} | "
            f"{r['f1']:.2f} | {r['latency_mean_ms']:.3f} |"
        )

    lines.append("\n## Table: Template stress vs Unseen test\n")
    lines.append(f"_Stress N={stress_n} (template); Unseen = remapped tool names on pilot_87._\n")
    lines.append("| Profile | Stress ASR | Stress TSR | Unseen ASR | Unseen TSR |")
    lines.append("|---------|------------|------------|------------|------------|")
    for profile, pair in report["holdout"]["rows"].items():
        lines.append(
            f"| {profile} | {pair['stress']['asr']:.2f} | {pair['stress']['tsr']:.2f} | "
            f"{pair['unseen']['asr']:.2f} | {pair['unseen']['tsr']:.2f} |"
        )

    lines.append("\n## Table: Adaptive ASR\n")
    lines.append("| Profile | ASR (%) | TSR (%) | F1 (%) |")
    lines.append("|---------|---------|---------|--------|")
    for k, r in report["adaptive"]["rows"].items():
        lines.append(f"| {k} | {r['asr']:.2f} | {r['tsr']:.2f} | {r['f1']:.2f} |")

    lines.append("\n## Table: Multi-step escalation results\n")
    lines.append("| Profile | Per-call chain ASR | Session-taint chain ASR | N attack chains |")
    lines.append("|---------|--------------------|-------------------------|-----------------|")
    for profile, r in report["multistep"]["rows"].items():
        lines.append(
            f"| {profile} | {r['per_call_asr_pct']:.1f}% "
            f"({r['per_call_chains_fully_succeed']}/{r['n_attack_chains']}) | "
            f"{r['session_taint_asr_pct']:.1f}% "
            f"({r['session_taint_chains_fully_succeed']}/{r['n_attack_chains']}) | "
            f"{r['n_attack_chains']} |"
        )

    lines.append("\n## Table: Ablation\n")
    lines.append("| Config | ASR (%) | TSR (%) | F1 (%) |")
    lines.append("|--------|---------|---------|--------|")
    for k, r in report["ablation"]["rows"].items():
        lines.append(f"| {k} | {r['asr']:.2f} | {r['tsr']:.2f} | {r['f1']:.2f} |")

    lat = report["stats_latency"]["latency"]
    lines.append("\n## Table: Latency / environment\n")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    for k, v in lat.items():
        if isinstance(v, float):
            lines.append(f"| {k} | {v:.4f} |")
        else:
            lines.append(f"| {k} | {v} |")

    lines.append("\n## Bootstrap (limited_network, pilot_87)\n")
    lines.append("| Metric | Point | Mean ± Std | 95% CI |")
    lines.append("|--------|-------|------------|--------|")
    for metric, s in report["stats_latency"]["bootstrap"].items():
        lines.append(
            f"| {metric.upper()} | {s['point']:.2f} | {s['mean']:.2f} ± {s['std']:.2f} | "
            f"[{s['ci95_low']:.2f}, {s['ci95_high']:.2f}] |"
        )

    fp = report["false_positives"]
    lines.append("\n## False-positive analysis (limited_network)\n")
    lines.append(f"Blocked benign: **{fp['n_blocked']}/{fp['n_benign']}** — {fp['by_category']}\n")
    lines.append("| ID | Category | Tool | Description |")
    lines.append("|----|----------|------|-------------|")
    for ex in fp["examples"]:
        desc = ex["description"].replace("|", "/")
        lines.append(f"| {ex['id']} | {ex['category']} | {ex['tool_name']} | {desc} |")
    lines.append(f"\n_{fp['discussion']}_\n")

    lines.append(
        "\n## Notes\n"
        "- Real MCP table uses realistic tool/server workflows evaluated through the same proxy API "
        "(not a live Cursor/Claude Desktop attach in this automated run).\n"
        "- ASK treated as DENY in automated runs.\n"
        "- Session taint is an optional extension beyond per-call enforcement.\n"
    )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
