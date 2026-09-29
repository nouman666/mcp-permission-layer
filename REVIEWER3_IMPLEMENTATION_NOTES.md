# Reviewer 3 implementation notes

## Comment 1 — validate the permission-inference mechanism independently of policy profiles
Implemented. The revised artifact separates inference validity from YAML-policy effectiveness.

- `datasets/reviewer3_official_mechanism_audit.json`: 27 documented calls from official MCP reference-server semantics with capability labels defined before policy lookup.
- `scripts/run_reviewer3_validation.py`: computes exact-set accuracy, required-capability coverage, and micro category metrics directly on `infer_categories()` outputs.
- Final audit: 27/27 exact category sets; micro precision/recall/F1 = 100%/100%/100%.

The official audit is explicitly described as a review-driven mechanism audit, not a blind hold-out, because it was used to identify and correct missing Git semantics and URL/path ambiguity.

## Comment 2 — mechanism completeness, enforcement faithfulness, alternatives, and task impact
Implemented with a dedicated closure experiment rather than scope-only wording.

- **Configured-path interception completeness:** `src/deployment_guard.py` validates that every MCP server entry exposed to the client launches `mcp_enforcement_proxy.py`. The six-entry sealed client configuration passes; four injected direct-upstream bypass configurations (filesystem, fetch, Git, shell) are rejected; 12/12 routed calls generate proxy audit decisions.
- **Policy faithfulness:** 27/27 published category/profile and resource-restriction decisions match expected outcomes.
- **Alternative authorization comparison:** `baselines/server_side_acl.py` implements a controlled server-declared capability/ACL baseline that receives explicit capability declarations instead of inferring them. On 27 benign official-reference calls plus 16 malicious external-provenance calls, B4 and the ACL comparator agree on 43/43 decisions under limited-network (B4 and ACL both 0% ASR, 59.26% BCAR). Across all four profiles, agreement is 170/172 decisions.
- **Task-level impact:** `datasets/reviewer3_task_workflows.json` contains 12 benign and 8 malicious multi-step scripted-agent workflows. A task succeeds only if every required call is ALLOW. Under limited-network, benign task completion is 6/12 (50.00%) and malicious workflow success is 0/8. The other profiles are also reported in the machine-readable result file.

Reproduce with `python scripts/run_reviewer3_comment2_validation.py`. Results are in `results/reviewer3_comment2_validation.json`.

## Comment 3 — external validity
Implemented with an additional external-provenance challenge while preserving provenance caveats.

- `datasets/reviewer3_mcptox_external_challenge.json`: 16 concrete harmful actions instantiated from upstream MCPTox case descriptions, with source case IDs retained.
- Final result: 100% case-level coverage of the minimum required capabilities and 100% required-label micro recall; three additional conservative categories are inferred.
- This set is external-provenance but not blinded, because the authors had access to MCPTox during revision. No population-level generalization claim is made.

## Verification

```text
pytest -q
58 passed

python scripts/run_reviewer3_validation.py
Official audit: 27/27 exact category sets
MCPTox challenge: 16/16 minimum-capability coverage
Policy faithfulness: 27/27
Declared-capability oracle agreement: 108/108
Routed audit accounting: 12/12
```
