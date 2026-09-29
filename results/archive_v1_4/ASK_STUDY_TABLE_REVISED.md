# Revised ASK-path results

`simulated_approval` is deterministic and contains no artificial human-think delay.

| Mode | ASK n | Approval | ASR | BCAR | F1 | Approval-policy eval ms |
|---|---:|---:|---:|---:|---:|---:|
| auto_deny | 13 | 0.0% | 0.00% | 66.67% | 88.00% | 0.0002 |
| auto_allow | 13 | 100.0% | 90.91% | 100.00% | 16.67% | 0.0002 |
| simulated_approval | 13 | 23.1% | 0.00% | 100.00% | 100.00% | 0.0125 |
