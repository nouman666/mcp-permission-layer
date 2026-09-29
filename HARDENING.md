# Hardening revision — 2026-09-29

## Reproduce (Linux / Python 3.12)

```sh
python -m pip install -r requirements-lock.txt
python -m pytest -q
python scripts/run_revision_evaluation.py
python scripts/run_reviewer3_validation.py
python scripts/run_reviewer3_comment2_validation.py
python scripts/run_hardening_validation.py
```

Observed: 79 tests pass. `results/hardening_validation.json` records 12 actual
stdio assertions, audit entries and independent upstream receipts. Two benign
workflows verify actual read/read and write/read outcomes. This is a controlled
local fixture, not an autonomous-agent benchmark or a generalization estimate.
`results/reviewer2_revision_evaluation.json` is the authoritative current full
security/utility replay. `results/archive_v1_4/` retains the original supplied
results. The historical reviewer1 result and ASK files are not fresh runs.
The original unmodified packaged source was rerun separately and matches all
current splits, baselines and ablations (security/utility numbers). Several
original saved organic/ablation entries were stale; the manuscript corrects them.
`results/environment_freeze.txt` records the full installed environment; the
project lock pins the four direct dependencies, not every transitive package.

## Trusted launch

`enforced_launcher.py --config CONFIG --manifest MANIFEST --server NAME`
validates every entry before launching the selected proxy. The manifest contains:

- `approved_config`: exact administrator-approved mcpServers object;
- `interpreter_sha256`: SHA256 of the approved Python interpreter;
- `sha256`: mapping of repository-relative file names to SHA256 digests.

Include the proxy script, all src/*.py files, launcher, selected policy files,
and approved local server files. File names are relative to this repository.
Client entries must use the approved Python interpreter and exact proxy script;
no -c/-m interpreter forms, remote entries, environment overrides, shell wrappers
or automatic ASK approval are accepted. Relative script paths resolve at the
repository root. Policies must be repository-local and listed in the manifest.
Provision the manifest once after review and keep it, configuration, executable,
launcher and code administrator-controlled/read-only. Do not regenerate trusted
hashes on every production launch. The integration harness creates a fresh
manifest only for its isolated test fixture. Upstream dependencies selected by
an external command must be independently pinned and trusted; verifying proxy
files does not establish their provenance.

## Boundary and filesystem semantics

The launcher is mandatory for the supported verified launch path; it cannot
force an independent program to use it. No operating-system process/network
confinement is implemented or claimed. A client with independent launch or
network privileges can use another route. Hashes do not defeat an adversary
who can modify the manifest/interpreter or race administrator-owned files.

The live checker resolves filesystem paths relative to the proxy/upstream
working directory. The offline lexical inference/replay remains unchanged.
Custom sensitive_paths are enforced. Resolution catches existing symlink
aliases but is not a race-free protection for arbitrary third-party servers.
The supplied POSIX reference file helpers additionally traverse by directory
file descriptors with O_NOFOLLOW, rejecting symlinks at open time under a
trusted root. They do not sandbox malicious server code, protect hard-link
aliases globally, or support equivalent Windows execution guarantees.

## Evidence interpretation

- Six valid configurations / four raw variants / 12 audit calls are legacy
  configuration and in-process checks, not proof of complete interception.
- Eight malformed/bypass specifications are separately rejected in hardening.
- Live stdio assertions test allowed outputs, denial side effects and receipts,
  upstream error propagation, ASK denial, symlink write refusal, upstream crash.
- The 20 workflows remain authorization replay only. Legacy JSON key names
  retain compatibility; they must not be read as executed task-success rates.
- The declared-capability comparator is now independently implemented without
  checker/inference helper calls. It remains an in-process lexical comparator,
  not a deployed server-side ACL, AGT, or AgentBound reproduction.
- Historical Table 8 transport values and ASK timings are explicitly archived;
  the new stdio fixture does not rerun the original npm/network experiment.
- Wider task utility, adversarial concurrent path replacement, proxy-process
  crash recovery and OS confinement remain unevaluated.

The base source commit is recorded in HARDENING_RELEASE.json. The GitHub commit
containing the published archive identifies this package. See PUBLICATION_STATUS.md
for the status of later exploratory additions.

## Final protocol-outcome verification

The proxy overwrites its own `_meta.mcp_permission_layer` namespace after each
upstream response. The live evaluator distinguishes authorization DENY, allowed
upstream error, allowed successful protocol response, and transport/unknown
outcomes. It never infers denial from a text substring. Unknown outcomes are
excluded from authorization-rate denominators and reported with coverage.
Protocol success is not claimed as semantic task completion. Metadata is trusted
only on the verified proxy route. Two additional regression tests cover upstream
marker replacement and unverified/inconsistent responses. Current verification:
`results/final_pytest.txt` (79 passed), `results/hardening_validation.json`
(12 passed assertions), `results/final_environment_freeze.txt` (installed pins).
The prior measured performance run is retained; final changes affect live
outcome classification, not offline inference or authorization replay.

