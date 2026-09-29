# Live Real MCP Deployment Results

_Path: `client -> enforcement proxy -> real upstream MCP server`_

_Servers: filesystem, fetch, git, terminal, env, process_

| Defense | ASR (%) | Block (%) | TSR (%) | F1 (%) | Latency ms |
|---------|---------|-----------|---------|--------|------------|
| B0_no_defense | 100.00 | 0.00 | 100.00 | 0.00 | n/a |
| B4_limited_network | 0.00 | 100.00 | 100.00 | 100.00 | 54.761 |
| B4_read_only | 0.00 | 100.00 | 76.92 | 88.89 | 8.715 |
| B4_no_code_exec | 16.67 | 83.33 | 100.00 | 90.91 | 34.048 |
| B4_approval_gated | 8.33 | 91.67 | 100.00 | 95.65 | 35.273 |
