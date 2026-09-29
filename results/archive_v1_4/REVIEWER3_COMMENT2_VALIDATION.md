# Reviewer 3 Comment 2 validation

- Configured-path completeness: sealed client config valid with **6** enforced server entries; **4/4** injected direct-upstream bypass configurations rejected; **12/12** routed calls intercepted and audited.
- Policy faithfulness: **27/27** expected decisions matched (100.00%).
- Controlled server-side ACL comparison on 27 benign official-reference calls + 16 malicious external-provenance calls:
  - read_only: B4 ASR/BCAR 0.00%/55.56%; ACL ASR/BCAR 0.00%/55.56%; decision agreement 43/43 (100.00%).
  - limited_network: B4 ASR/BCAR 0.00%/59.26%; ACL ASR/BCAR 0.00%/59.26%; decision agreement 43/43 (100.00%).
  - no_code_exec: B4 ASR/BCAR 37.50%/96.30%; ACL ASR/BCAR 43.75%/96.30%; decision agreement 42/43 (97.67%).
  - approval_gated: B4 ASR/BCAR 6.25%/62.96%; ACL ASR/BCAR 12.50%/62.96%; decision agreement 42/43 (97.67%).
- Task-level scripted-agent workflow completion (12 benign + 8 malicious workflows; a task succeeds only if every required tool step is ALLOW):
  - read_only: benign task completion 4/12 (33.33%); malicious workflow success 0/8 (0.00%).
  - limited_network: benign task completion 6/12 (50.00%); malicious workflow success 0/8 (0.00%).
  - no_code_exec: benign task completion 9/12 (75.00%); malicious workflow success 2/8 (25.00%).
  - approval_gated: benign task completion 6/12 (50.00%); malicious workflow success 1/8 (12.50%).
