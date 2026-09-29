# Evaluation provenance

## Organic hold-out
- `organic_holdout.json` contains 90 hand-authored, non-template cases (50 malicious, 40 benign).
- Labels were assigned at case construction from the intended scenario: `beneficial=false` for calls intentionally representing credential access/exfiltration/execution/destructive or otherwise attacker-directed behaviour, and `beneficial=true` for ordinary project reads, directory listings, and allow-listed documentation/API fetches. The labels are scenario labels, not outputs of the defence.
- The file was kept separate from `datasets/holdout/pilot_87.json` and was not used to choose the six-category taxonomy, NAME_RULES, sensitive-path patterns, domain allow-list, or policy matrices. It is author-created and author-labelled; it is not blinded or independently labelled.

## White-box boundary/adaptive suite
- `adaptive_boundaries_v2.json` contains 16 malicious boundary families repeated three times (48 malicious cases) and 8 benign boundary families repeated three times (24 benign cases). It was created only after the corrected inference/checker logic was frozen.
- The case author had white-box knowledge of the published inference rules and Reviewer-1 boundary findings. There was no iterative attack loop: each fixed case was evaluated once per policy profile in the reported run, with no per-case retries, hill-climbing, model feedback, or decision feedback used to rewrite a case after execution.
- This is therefore best interpreted as a white-box boundary suite, not as a statistically powered adaptive-agent benchmark.

## Targeted Reviewer-2 regression
- `reviewer2_targeted_cases.json` contains the requested renamed write tool with an ordinary path and no other risk indicator.

## External-schema and stress sources
- `external_schema_cases.json`: case shapes derived from the official Model Context Protocol filesystem server schemas at https://github.com/modelcontextprotocol/servers/blob/main/src/filesystem/index.ts (inspected 2026-09-22).
- `large_dataset.jsonl`: deterministically reconstructed by `scripts/generate_stress_dataset.py`; no random seed is required.

## Reviewer-3 direct mechanism audit (official reference-server semantics)
- `reviewer3_official_mechanism_audit.json` contains 27 calls derived from the documented semantics of the official Model Context Protocol reference servers: filesystem, git, fetch, and Everything/get-env (inspected 2026-09-22).
- The expected category labels are specified independently of any YAML profile: filesystem/git inspection operations are labelled `fs.read`; documented mutating filesystem/git operations are labelled `fs.write`; `fetch` is `net.http`; and `get-env` is `env.read`.
- This set is a **review-driven mechanism audit**, not a blind hold-out. It exposed missing Git semantics and URL/path ambiguity during revision, after which the inference rules were corrected. The final 27-case audit is therefore used to verify the corrected mechanism rather than to claim unseen generalization.

## Reviewer-3 external-provenance challenge (MCPTox)
- `reviewer3_mcptox_external_challenge.json` instantiates 16 concrete harmful tool calls from externally authored cases in the upstream MCPTox benchmark (`zhiqiangwang4/MCPTox-Benchmark`, `pure_tool.json`; inspected 2026-09-22). Source case identifiers are retained in every record.
- Labels in this file are **minimum required behavioural capabilities**, not an exhaustive annotation of every side effect. Consequently, the reported primary metric is required-capability coverage/recall; additional conservative inferred categories are reported but are not counted as errors.
- This set has external provenance but is **not blinded**: the authors had access to MCPTox during revision. It is used to reduce same-source bias, not as proof of population-level generalization.

## Reviewer-3 policy and interception checks
- `scripts/run_reviewer3_validation.py` separately tests the published four-profile category matrix plus three path/domain restriction cases (27 expected decisions total).
- The same script verifies one-for-one audit accounting for calls that are actually presented to the configured proxy. This does **not** establish interception completeness for direct or alternative routes that bypass the configured proxy; such calls remain outside the enforcement boundary by construction.
