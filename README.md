# MCP Permission Layer — Revised Reproducibility Package

The current revised implementation, datasets, evaluation scripts, dependency specifications and supporting results are distributed together in **[MCP_Hardened_Code.zip](artifacts/MCP_Hardened_Code.zip)**.

Download and extract this archive before reproducing the revised experiments. The existing source directories outside the archive retain the earlier artifact; use the archive for this revision.

```sh
unzip artifacts/MCP_Hardened_Code.zip
cd mcp-permission-layer-reviewer3-revised
python -m pip install -r requirements-lock.txt
python -m pytest -q
python scripts/run_revision_evaluation.py
python scripts/run_reviewer3_validation.py
python scripts/run_reviewer3_comment2_validation.py
python scripts/run_hardening_validation.py
```

See [HARDENING.md](HARDENING.md) for the tested scope and [PUBLICATION_STATUS.md](PUBLICATION_STATUS.md) for the status of recorded and exploratory evidence. Source provenance is documented in [HARDENING_RELEASE.json](HARDENING_RELEASE.json). The GitHub commit containing this archive identifies the published version.

Archive SHA-256: `f72de2223ff6738ce4d2e67aa602528ff97d4a21e02fd5e4c6f80eb69993292d`.

The archive excludes Git history and Python caches and includes per-file checksums. This publication step verifies packaging and checksums; it does not claim a fresh experimental run.
