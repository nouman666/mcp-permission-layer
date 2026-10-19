# Resource-resolution follow-up verification

Date: 2026-10-16. Base: cf1a210bbf50ce387aa6c1283bd2d931b24e1c99.

- Installed results/final_environment_freeze.txt in a fresh Python 3.12.14 virtual environment; pip check passed.
- 109 tests passed: 80 existing tests plus 29 new regressions in tests/test_revision_resource_resolution.py.
- download with a local destination infers fs.write; unrelated network-name matches cannot suppress ambiguous filesystem intent.
- Explicit HTTP routes are distinguished using the request operation and a destination-bearing sibling in the same object.
- Scheme-relative URLs are canonicalized; every destination retains a location and resolved/unresolved status. Allowed leaves cannot mask unresolved or denied leaves, including nested/list forms.
- run_revision_evaluation.py rerun: all existing split/profile, baseline and ablation ASR/BCAR/F1 values are unchanged from the base commit. Raw rows and timing metadata are refreshed.
- Official audit 27/27 exact sets; external-provenance challenge 16/16 coverage with 3 extra labels; policy matrix 27/27; mixed comparator 170/172; limited-network workflow authorization 6/12 benign and 0/8 malicious.
- run_hardening_validation.py: 12/12 controlled live assertions passed.
- Boundary: 16 distinct malicious and 8 distinct benign inputs; 48/24 executions. Observed limited-network malicious allowance 0/16 distinct inputs (0/48 executions), benign allowance 8/8 (24/24). No population confidence bound is reported.
- Earlier ZIP and historical timing results are explicitly identified as historical.
