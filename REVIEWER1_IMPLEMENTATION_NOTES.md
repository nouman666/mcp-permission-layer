# Reviewer 1 implementation map

This file maps the reviewer-driven code changes to the active revised artifact.

- **Comment 1 / Review Part A:** `src/inference.py`, `src/checker.py`, `tests/test_inference.py`, `tests/test_checker.py` — recursive structured-argument traversal; canonical paths/domains; split hosts; unfamiliar write intent; sensitive path variants; unresolved restricted resources fail closed.
- **Comment 2:** manuscript/threat-model clarification; no code can make a client-call gate sandbox arbitrary hidden upstream-server behavior.
- **Comment 3:** `scripts/build_reviewer_boundary_sets.py`, `datasets/adaptive_boundaries_v2.json`, `datasets/external_schema_cases.json`, `datasets/PROVENANCE.md`.
- **Comment 4:** `scripts/run_ask_study.py`, `datasets/simulated_approval_protocol.md` — deterministic simulated approval; no artificial 50 ms human-latency claim.
- **Comment 5:** `scripts/metrics.py` and revised reporting — BCAR replaces task-success terminology.
- **Comment 6:** `scripts/run_revision_evaluation.py` — controlled baseline interpretation and repeated baseline/ablation runs on organic hold-out.
- **Comment 7:** `scripts/metrics.py` and `scripts/run_revision_evaluation.py` — class-stratified bootstrap and one-sided zero-event bounds.
- **Comment 8:** `scripts/generate_stress_dataset.py`, `requirements-lock.txt`, `results/raw/`, `REPRODUCIBILITY.md`, `RELEASE_ID.txt`, `SHA256SUMS.txt`; timing boundaries are separated.
- **Comment 9:** manuscript novelty positioning; no runtime-proxy novelty claim is encoded in the artifact README.

Reviewer markers are placed immediately above the relevant implementation blocks. In particular, `src/inference.py` and `src/checker.py` contain the explicit marker **“Review Part A is implemented (Reviewer 1 Comment 1(a)-(f))”** before the corrected logic.
