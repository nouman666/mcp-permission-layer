# Organic-style Hold-out (non-template)

_N=90 (50 attack / 40 benign). Hand-authored; not template-expanded._

| Profile | ASR (%) | TSR (%) | F1 (%) | Residual attacks | Benign blocked |
|---------|---------|---------|--------|------------------|----------------|
| read_only | 0.00 | 75.00 | 90.91 | 0 | 10 |
| limited_network | 0.00 | 100.00 | 100.00 | 0 | 0 |
| no_code_exec | 2.00 | 100.00 | 98.99 | 1 | 0 |
| approval_gated | 2.00 | 100.00 | 98.99 | 1 | 0 |

limited_network bootstrap ASR 95% CI [0.00, 0.00]; TSR 95% CI [100.00, 100.00].

