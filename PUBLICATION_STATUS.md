# Published package status

This archive contains the revised implementation and supporting evidence, plus exploratory scripts. The GitHub commit containing this archive identifies the published package; the earlier source commit identifies only its base, not all later additions.

The recorded final automated run contains 79 passing tests and the controlled stdio validation contains 12 passing assertions. A later additional sandbox test does not establish operating-system confinement. No new test execution is claimed by this publication step.

The external_generalization output contains extracted manifests/policy examples, not an independently labelled tool-call benchmark; it must not be used as validation of generalization. The fresh filesystem run contains unknown outcomes for unavailable non-filesystem servers and is not a complete rerun of all live workflows. The sandbox launcher is experimental, is not integrated into the verified launch path, and has not demonstrated confinement on this host.

Historical transport and ASK timing records remain historical. See HARDENING.md for the tested scope and reproduction commands.
