# MCP Permission Layer — Revised Reproducibility Artifact

The [HTTP path correction](HTTP_PATH_REVISION.md) preserves fail-closed default handling of generic paths. The additional [optional trusted HTTP contract study](TRUSTED_HTTP_CONTRACT_STUDY.md) evaluates an administrator-approved reference adapter separately; the full suite now passes 154 tests. Default and contract-enabled results are reported separately.

The complete pinned Table 8 live rerun (100 known authorization outcomes) is available in [results/table8_pinned_rerun](results/table8_pinned_rerun/README.md), with exact installation commands, receipts, audit logs and execution-error disclosures. It supersedes the historical Table 8 measurements.

The repository root contains the revised source code, datasets, evaluation scripts, pinned direct dependencies and supporting results. Clone this repository and run the commands below from its root.

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install -r results/final_environment_freeze.txt
python -m pip check
python -m pytest -q
python scripts/run_revision_evaluation.py
python scripts/run_reviewer3_validation.py
python scripts/run_reviewer3_comment2_validation.py
python scripts/run_hardening_validation.py
```

See [HARDENING.md](HARDENING.md) for reproduction details and tested scope, [PUBLICATION_STATUS.md](PUBLICATION_STATUS.md) for evidence status, and [HARDENING_RELEASE.json](HARDENING_RELEASE.json) for source provenance. The enclosing GitHub commit pins this source snapshot.

A self-contained [downloadable package](artifacts/MCP_Hardened_Code.zip) is also available. It is the earlier archived implementation and does not contain the follow-up resource-resolution fixes. Use the enclosing source commit and the commands above for this revision. Archive SHA-256: `f72de2223ff6738ce4d2e67aa602528ff97d4a21e02fd5e4c6f80eb69993292d`.

Historical measurements remain identified separately from subsequent evaluations. Publication and source synchronization do not constitute a fresh experimental run.

The official installation uses the complete validated environment in `results/final_environment_freeze.txt` (including Pydantic 2.13.5). `requirements-lock.txt` pins only four direct dependencies and is not a complete environment lock.
