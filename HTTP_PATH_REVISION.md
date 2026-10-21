# HTTP route and filesystem path correction

The reviewer example previously inferred net.http only and was allowed. The correction removes generic `path` from route recognition. An HTTP name and sibling URL/host are insufficient to resolve a generic path. Recognized download/write operations require fs.write; other unresolved generic paths retain fs.read plus the existing high-risk code.exec uncertainty surrogate. This surrogate denotes uncertainty, not evidence of actual code execution.

The supported explicit route convention uses `route` or `request_path`, an HTTP-request name, an absolute single-slash route and a destination in the same argument object. Download/write name signals override this convention. A separate output_path or unresolved path is checked independently; an allowed route cannot mask it. These are explicit name/argument semantics, not introspection of hidden server behavior. Existing generic host+path calls are intentionally treated conservatively, including benign calls with unresolved intent.

## Verification

The full automated suite passes 128 tests (109 previous cases plus 19 additions). Targeted coverage includes the exact reviewer example, write-name variants, flat/nested/list structures, generic paths under URL/host context, explicit route controls, download/route conflicts, separate output destinations, unrelated sibling objects and mixtures of explicit routes with unresolved paths. Previously allowed generic-path controls are retained as denied ambiguity cases; explicit-route controls remain allowed.

The seven fixed datasets retain their inputs and labels. Replay compares 20,289 calls across four profiles (81,156 profile comparisons) against the pre-correction source. Inference and decisions are unchanged on pilot, organic hold-out, external-schema, targeted renamed-write and real-MCP-style sets. Stress and boundary changes are reported in results/http_path_revision_summary.json; full per-case differences are in results/http_path_revision_evidence.zip. This is authorization replay, not fresh live execution or latency. Table 8's pinned live measurements retain their original source provenance; all 100 corresponding authorization decisions are unchanged in replay.

Limited-network stress BCAR changes from 75.01% to 66.68%, and boundary BCAR from 100% to 75% (6/8 distinct benign inputs; 18/24 executions). ASR remains zero on both. These reductions disclose the benign-allowance cost of rejecting unresolved generic paths; no dataset labels or inputs were changed to recover the prior rates.

## Reproduction

```bash
python -m pip install -r results/final_environment_freeze.txt
python -m pip check
python -m pytest -q
# Baseline is the published pre-correction source.
git show 4d41cc4f58223039a9de90af83cfabedb530e02d:src/inference.py > /tmp/http_path_baseline.py
python scripts/verify_http_path_revision.py --baseline /tmp/http_path_baseline.py --output /tmp/http_path_comparison.json
```

The example inference/decision records are in results/http_path_revision_examples.json, and the automated test log is results/http_path_revision_pytest.txt. Existing historical evidence files are retained with their prior scope; use this note and the new summary for the corrected stress/boundary results.
