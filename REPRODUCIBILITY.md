# Current hardening reproduction

See HARDENING.md for exact commands, current result paths, launch assumptions and limitations.

# Archived v1.4 reproducibility package — reviewer revision v1.4-r3c2

## Frozen software environment

- Python dependencies: install exactly from `requirements-lock.txt` (`PyYAML==6.0.2`, `pytest==8.4.1`, `mcp==1.14.1`, `anyio==4.10.0`).
- Revised live-rerun config pins the official filesystem MCP server as `@modelcontextprotocol/server-filesystem@2026.8.31`. The fetch, git, shell/environment, and process test servers are local Python files in `servers/` and are therefore versioned by this release.
- The originally submitted/archived Table 8 live run invoked the npm filesystem package without an explicit version. That exact npm version was not captured at run time and cannot be reconstructed honestly; Table 8 is therefore marked archival in the manuscript. Any new live rerun must use the pinned version above.

## Exact reproduction commands

```bash
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows: .venv\Scripts\activate
pip install -r requirements-lock.txt
python scripts/generate_stress_dataset.py
python scripts/build_reviewer_boundary_sets.py
python -m pytest -q
python scripts/run_revision_evaluation.py
python scripts/run_ask_study.py
python scripts/run_reviewer3_validation.py
python scripts/run_reviewer3_comment2_validation.py
# Requires Node/npm and network/package availability:
python scripts/run_live_mcp_eval.py
```

`run_revision_evaluation.py` writes raw per-case decisions under `results/raw/` and records the exact host allocation, repetition counts, operations per repetition, and timing boundaries used for latency.

## Dataset separation and attempts

See `datasets/PROVENANCE.md`. The organic hold-out is separate from the design set and was not used to tune inference rules. The white-box boundary suite is fixed before execution, each case is run once per profile, and no decision feedback is used to rewrite or retry cases.

## Release provenance

- Artifact release: `v1.4-r3c2`.
- `SHA256SUMS.txt` contains content checksums.
- A Git commit/tag is created in the packaged repository after the final generated results are frozen.


## Reviewer-3 validation commands and provenance

```bash
python scripts/run_reviewer3_validation.py
python -m pytest -q
```

The reviewer-3 script emits `results/reviewer3_validation_raw.json`, `results/reviewer3_validation_summary.json`, and `results/REVIEWER3_VALIDATION_SUMMARY.md`. The official-server audit is a review-driven mechanism audit, not a blind hold-out. The MCPTox challenge is external-provenance but not blinded; source case IDs are retained in the dataset. See `datasets/PROVENANCE.md` for the interpretation boundary.

The proxy-routing check covers only calls actually routed through the configured enforcement proxy. Direct or alternative client-to-server call paths can bypass the gate and are not claimed to be intercepted.

## Reviewer 3 Comment 2 closure

```bash
python scripts/run_reviewer3_comment2_validation.py
```

This writes `results/reviewer3_comment2_validation.json` and `results/REVIEWER3_COMMENT2_VALIDATION.md`, covering configured-path interception/bypass rejection, policy faithfulness, independently implemented declared-capability comparison, and scripted workflow authorization replay (not executed task completion).
