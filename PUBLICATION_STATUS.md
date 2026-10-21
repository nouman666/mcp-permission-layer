# Follow-up resource-resolution revision — 2026-10-16

The latest [HTTP path correction](HTTP_PATH_REVISION.md) removes generic-path route inference, passes 128 tests, and updates stress/boundary authorization results.

The complete pinned Table 8 live rerun (100 known authorization outcomes) is available in [results/table8_pinned_rerun](results/table8_pinned_rerun/README.md), with exact installation commands, receipts, audit logs and execution-error disclosures. It supersedes the historical Table 8 measurements.

The source on this revision branch includes fixes for per-resource filesystem uncertainty and mixed resolved/unresolved network destinations. The full validated dependency freeze was installed in a fresh Python 3.12.14 environment; pip check passes. The automated suite passes 109 tests, including 29 new regressions, and the controlled stdio fixture passes 12 assertions. Capability audits and all existing replay ASR/BCAR/F1 results were reproduced without change. Boundary coverage is 16 distinct malicious and 8 distinct benign calls, repeated three times; no population bound is inferred from these repetitions.

The ZIP under artifacts/MCP_Hardened_Code.zip is the earlier archived package and does not contain this follow-up. Reproduce this revision by cloning/checking out the enclosing source commit and following README.md.

## Prior package status (historical)

# Published package status

This archive contains the revised implementation and supporting evidence, plus exploratory scripts. The GitHub commit containing this archive identifies the published package; the earlier source commit identifies only its base, not all later additions.

The recorded final automated run contains 79 passing tests and the controlled stdio validation contains 12 passing assertions. A later additional sandbox test does not establish operating-system confinement. No new test execution is claimed by this publication step.

The external_generalization output contains extracted manifests/policy examples, not an independently labelled tool-call benchmark; it must not be used as validation of generalization. The fresh filesystem run contains unknown outcomes for unavailable non-filesystem servers and is not a complete rerun of all live workflows. The sandbox launcher is experimental, is not integrated into the verified launch path, and has not demonstrated confinement on this host.

Historical transport and ASK timing records remain historical. See HARDENING.md for the tested scope and reproduction commands.
