# Optional trusted HTTP contract study

This optional experiment restores legitimate split-host HTTP route allowance by adding a verified reference implementation. It does not change the default inference results, recover a historical server, or silently replace the original automatic-inference experiment.

## Results

The original benchmark inputs, labels and dataset hashes are unchanged. The new deployment assignment routes exact `http_request` calls containing `host` and `path` either at the root or under `request` to the approved reference adapter. This syntactic assignment does not inspect beneficial labels, expected outcomes or destination allow-lists. Other calls retain the default checker. Assignment covers 1,667 stress records and 12 boundary records, including malicious requests.

| Limited-network evaluation | Default corrected BCAR | Contract-enabled BCAR | Contract-enabled ASR |
| --- | ---: | ---: | ---: |
| Stress, 10,000 benign / 10,000 malicious | 66.68% | 75.01% (7,501/10,000) | 0% |
| Boundary, 8 distinct benign / 16 distinct malicious | 75% | 100% (8/8; 24/24 executions) | 0% |

All four profiles recover their pre-HTTP-path-correction stress/boundary aggregate rates in this new configured experiment. The complete results, including malicious allowances under more permissive profiles, are reported in `results/trusted_contract_study/summary.json`. This is not evidence that every profile has zero ASR. All default metrics match the seven-dataset corrected baseline exactly. Both configurations are retained; the original automatic-inference baseline must not be relabeled as contract-enabled retroactively.

Per-call differences for every profile are retained in `results/trusted_contract_study/decision_changes.zip`; the evaluation script also regenerates the individual JSON files.

## Binding and enforcement

- `servers/contract_http_server.py` is a new narrow reference implementation. It maps a DNS host plus a route to an HTTPS GET. It never interprets the route as a filesystem destination, never writes downloaded content to a path, and rejects redirects.
- The administrator supplies the approved source hash in `configs/approved_http_route_reference.json`. The binding checks the bytes before loading, retains that verified implementation snapshot and rechecks the on-disk hash on use. The MCP endpoint executes the same bound snapshot whose semantics justify the inference exemption.
- Only exact tool identity `http_request` qualifies. The schema permits exactly `{host, path}` or `{request: {host, path}}`. Other fields, nested extra destinations, lists in place of scalar paths, origin-changing routes, userinfo and malformed hosts are rejected.
- The binding is trusted constructor/launch configuration, not client arguments, a caller-provided server label, an upstream tool description or a benchmark label. Contract failure forces DENY even under a permissive category policy.
- `http_request_download` with the reviewer's URL and `/tmp/output.json` still requires fs.write and is denied by limited-network. An unbound generic host/path request still receives fail-closed uncertainty handling. A separately bound, verified route implementation can accept the same path string because its actual behavior is an HTTP GET.
- The schema and hash are part of the experimental trusted computing base. Protect the manifest, reference code, checker code and dependencies from untrusted modification. This does not authenticate an arbitrary remote server, prevent compromise of trusted process memory, or provide OS confinement. Do not apply this binding to another tool implementation merely because its name is `http_request`.

## Verification and execution scope

The full suite passes **154 tests**, comprising the existing 128 and 26 new contract-related cases. Tests cover the reviewer example, unbound fallbacks, positive flat/nested route controls, exact tool identity, bad and changed hashes, schema mismatch, extra local outputs, unresolved destinations, origin manipulation, denied requests not reaching the HTTP implementation, and a controlled GET with no local output file. MCP tests verify advertised schema and rejection of unknown/invalid requests.

A separate real MCP smoke request to `https://docs.python.org/3/` returned `authorization=allow`, `execution=upstream_ok`. Its receipt and audit record are retained. The first attempt failed DNS because MCP's default child environment omitted the host's proxy settings; the retry explicitly passed the existing network/proxy environment. The earlier failed attempt is retained in the JSON. This single live check does not establish end-to-end success for the benchmark suite. The benchmark comparison is deterministic authorization replay, not live execution of all 20,289 cases, a fresh latency study, or independent random sampling.

## Reproduction

This optional experiment extends the default HTTP-path correction in revision `f6a918c4aa5eb5fde0133878acc1e1c082f7e3f6`. Check out the enclosing source commit to reproduce both configurations. The changed core files are `src/checker.py` and `src/inference.py`; all other feature files are additions. No existing dataset is rewritten.

```bash
python -m pip install -r results/final_environment_freeze.txt
python -m pip check
python -m pytest -q
python scripts/evaluate_trusted_http_contract.py
# Optional live request; public HTTPS access is required.
python scripts/smoke_approved_http.py
```

To run the optional MCP endpoint, provide the approved manifest explicitly:

```bash
python scripts/serve_approved_http.py --manifest configs/approved_http_route_reference.json --policy policies/limited_network.yaml --log results/approved_http_session.jsonl
```

Clients needing an HTTP proxy must provide their existing proxy environment to the child process. Do not regenerate or replace the approved hash from an untrusted server announcement.

## Manuscript wording

An additional, explicitly configured experiment binds split-host HTTP requests to an administrator-approved reference implementation whose source hash and strict argument schema are verified. The bound implementation treats path exclusively as an HTTPS route and rejects local-output fields. With unchanged benchmark inputs and labels, this configuration restores limited-network BCAR to 75.01% on stress and 100% on the boundary suite, while observed ASR remains 0% on both. The automatic-inference configuration retains BCAR of 66.68% and 75%, respectively. The recovery depends on trusted deployment information and must be reported as a separate configuration, not as an unchanged result of automatic inference alone.
