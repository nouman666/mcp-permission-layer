# Reviewer 3 Comment 2 validation

- Configured-entry checks: client config valid with **6** enforced server entries; **4/4** injected direct-upstream bypass configurations rejected; **12/12** in-process calls audited.
- Policy faithfulness: **27/27** expected decisions matched (100.00%).
- Independent declared-capability policy comparison on 27 benign official-reference calls + 16 malicious external-provenance calls:
  - read_only: B4 ASR/BCAR 0.00%/55.56%; ACL ASR/BCAR 0.00%/55.56%; decision agreement 43/43 (100.00%).
  - limited_network: B4 ASR/BCAR 0.00%/59.26%; ACL ASR/BCAR 0.00%/59.26%; decision agreement 43/43 (100.00%).
  - no_code_exec: B4 ASR/BCAR 37.50%/96.30%; ACL ASR/BCAR 43.75%/96.30%; decision agreement 42/43 (97.67%).
  - approval_gated: B4 ASR/BCAR 6.25%/62.96%; ACL ASR/BCAR 12.50%/62.96%; decision agreement 42/43 (97.67%).
- Workflow authorization replay (12 benign + 8 malicious workflows; a workflow is authorized only if every required tool step is ALLOW; no execution measured):
  - read_only: benign workflow authorization rate 4/12 (33.33%); malicious workflow authorization rate 0/8 (0.00%).
  - limited_network: benign workflow authorization rate 6/12 (50.00%); malicious workflow authorization rate 0/8 (0.00%).
  - no_code_exec: benign workflow authorization rate 9/12 (75.00%); malicious workflow authorization rate 2/8 (25.00%).
  - approval_gated: benign workflow authorization rate 6/12 (50.00%); malicious workflow authorization rate 1/8 (12.50%).
