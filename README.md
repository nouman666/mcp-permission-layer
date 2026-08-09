# MCP Permission Layer (Artifact)

**Argument-aware runtime least-privilege enforcement for MCP tool calls** — research artifact accompanying the MDPI *Computers* manuscript by Mohammad Nouman, Syed Ijlal Haider, and Rajja Ujjan (University of the West of Scotland).

Client-side runtime least-privilege gate for Model Context Protocol (MCP) tool calls.
Intercepts tool invocations, infers permission categories, enforces declarative YAML policies, and emits JSON Lines audit logs — without modifying MCP clients or servers.

See `CITATION.md` for citation text.

## Setup

```bash
cd mcp_permission_layer
python -m pip install -r requirements.txt
```

## Quick demo

```bash
python demo.py
python -m unittest discover -s tests -v
python evaluate_dataset.py
```

## Reproduce IEEE evaluation tables (one command)

```bash
python scripts/build_holdout.py
python scripts/run_full_evaluation.py
```

Full 20k stress corpus (slower):

```bash
set STRESS_N=20000
python scripts/run_full_evaluation.py
```

### Organic-style hold-out (non-template)

```bash
python scripts/run_organic_holdout.py
```

90 hand-authored MCPTox-like / realistic workflow cases (`datasets/organic_holdout.json`).

### ASK / human-in-the-loop (Step 9)

```bash
python scripts/run_ask_study.py
# optional real terminal prompts:
python scripts/run_ask_study.py --mode interactive
```

Compares `auto_deny`, `auto_allow`, and author-as-user ASK protocol
(`datasets/ask_author_protocol.md`). Outputs `results/ASK_STUDY_TABLE.md`.

### Live Real MCP deployment (client → proxy → real servers)

```bash
python scripts/run_live_mcp_eval.py
```

This:
1. Starts real MCP upstreams (official filesystem via `npx`, plus fetch/git/shell MCP servers)
2. Wraps each with `scripts/mcp_enforcement_proxy.py` (stdio JSON-RPC)
3. Runs 25 workflows over the live path
4. Writes Cursor config to `configs/cursor_mcp.json` and merges into `~/.cursor/mcp.json`

Outputs:

- `results/ieee_evaluation_report.json` — machine-readable tables
- `results/TABLES_FOR_PAPER.md` — paste-ready markdown tables
- `results/live_mcp_deployment.json` / `results/LIVE_MCP_TABLE.md` — **live** Real MCP results

### Tables produced

| Table | Content |
|-------|---------|
| Real MCP Deployment Results | Simulated filesystem/git/fetch/terminal workflows |
| Baseline Comparison | B0–B4 on pilot_87 + real set |
| Template stress vs Unseen test | Hold-out with remapped tool names |
| Adaptive ASR | Benign names / args-only / encoding cases |
| Multi-step escalation | Per-call vs optional session-taint |
| Ablation | Component knock-outs |
| Stats + latency | Bootstrap CI + P95/P99 |
| False-positive analysis | Blocked benign categories + examples |

## Layout

```
mcp_permission_layer/
  src/                 # inference, checker, proxy, policy, audit
  policies/            # read_only, limited_network, no_code_exec, approval_gated
  baselines/           # B0–B3 simple defenses
  datasets/            # pilot, large stress, adaptive, multi-step, real MCP
  scripts/             # hold-out builder + full evaluation
  tests/               # 33 unit tests
  results/             # generated tables
```

## Update IEEE paper from results

```bash
python scripts/update_ieee_paper.py
```

Writes `STRENGTHENED_IEEE_PAPER_FULL_EVAL.docx` (Desktop `bodmas/` + `results/`).

## Notes

- Automated non-ASK runs map **ASK → DENY** (conservative); see ASK study for author-as-user.
- Live Real MCP path: client → stdio enforcement proxy → real upstream servers; Cursor `mcp.json` is generated for attach.
- Session taint is an optional extension for multi-step chains; the core contribution remains per-call enforcement.
- Artifacts: `src/`, `policies/`, `datasets/`, `baselines/`, `servers/`, evaluation scripts.
