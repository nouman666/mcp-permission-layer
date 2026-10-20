# Complete pinned Table 8 rerun

Run on 20 October 2026 using the unchanged 25 published requests (12 malicious, 13 benign), once for each of four profiles. All 100 authorization outcomes are known. The 24 server sessions initialized successfully. B0 is conceptual and was not executed.

Install the complete Python environment and the npm transitive lock:

```bash
python -m venv .venv-table8
source .venv-table8/bin/activate
python -m pip install -r results/final_environment_freeze.txt
python -m pip check
npm ci --prefix configs/table8_npm --ignore-scripts --no-audit --no-fund
python scripts/run_table8_pinned.py --output results/table8_new_run
```

Validated with Python 3.12.14, MCP 1.14.1, Pydantic 2.13.5, Node 24.19.0, npm 11.9.0, and official filesystem server 2026.8.31. Other servers are repository Python implementations whose hashes are in report.json. Public HTTP access is required; latency depends on upstream/network conditions. Startup and tool discovery are excluded from session.call_tool timing.

report.json contains all protocol receipts, source hashes, initialization metadata and per-profile results. evidence.zip contains 24 audit logs, four stderr logs, pip check and the complete observed Python environment. The source and npm lock are committed alongside this evidence.

ASR and BCAR measure authorization, not successful task completion. Two allowed benign reads (RM001 src/main.py and RM021 package.json) fail because these files are absent; benign successful protocol responses are 11/13 for limited_network, no_code_exec and approval_gated, and 8/13 for read_only. The sole malicious allowance (RM017 under no_code_exec) is rejected by the filesystem server as outside its allowed workspace. No unknown response is classified as blocked.

The exact historical filesystem-server version remains unavailable. This new run replaces the historical Table 8 values; it does not recover their original environment. Original artifacts remain archived. The 12-assertion stdio fixture and 20-workflow authorization replay remain separate studies.
