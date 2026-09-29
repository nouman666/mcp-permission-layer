# MCP Permission Layer — Revised Reproducibility Artifact

The repository root contains the revised source code, datasets, evaluation scripts, pinned direct dependencies and supporting results. Clone this repository and run the commands below from its root.

```sh
python -m pip install -r requirements-lock.txt
python -m pytest -q
python scripts/run_revision_evaluation.py
python scripts/run_reviewer3_validation.py
python scripts/run_reviewer3_comment2_validation.py
python scripts/run_hardening_validation.py
```

See [HARDENING.md](HARDENING.md) for reproduction details and tested scope, [PUBLICATION_STATUS.md](PUBLICATION_STATUS.md) for evidence status, and [HARDENING_RELEASE.json](HARDENING_RELEASE.json) for source provenance. The enclosing GitHub commit pins this source snapshot.

A self-contained [downloadable package](artifacts/MCP_Hardened_Code.zip) is also available. It contains the same revised implementation and evidence; its README and checksum manifest reflect archive packaging. Archive SHA-256: `f72de2223ff6738ce4d2e67aa602528ff97d4a21e02fd5e4c6f80eb69993292d`.

Historical measurements remain identified separately from subsequent evaluations. Publication and source synchronization do not constitute a fresh experimental run.
