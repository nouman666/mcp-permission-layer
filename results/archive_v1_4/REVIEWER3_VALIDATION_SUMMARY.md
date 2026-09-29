# Reviewer 3 mechanism-validation summary

- Official reference-server mechanism audit: **27 cases**, exact-set accuracy **100.00%**, required-capability coverage **100.00%**, micro precision/recall/F1 **100.00% / 100.00% / 100.00%**.
- MCPTox external-provenance challenge: **16 cases**, minimum-required-capability case coverage **100.00%**, required-label micro recall **100.00%**; 3 additional conservative labels were inferred.
- Policy-faithfulness matrix: **27/27** expected category/profile or restriction decisions matched (**100.00%**).
- Declared-capability/ACL oracle comparator: B4 agrees on **108/108** official-case/profile decisions (**100.00%**). This is an idealized declaration comparator, not an AgentBound/AGT reimplementation.
- Routed-gate accounting: **12/12** calls presented to the configured proxy produced audit records (**100.00%**). This is not a claim that alternate routes cannot bypass the proxy.

## Interpretation boundaries

1. The official audit is review-driven and not a blind hold-out.
2. MCPTox is external-provenance but not blinded because the authors had access to the benchmark during revision.
3. MCPTox labels here are minimum required capabilities; over-approximate extra categories are not treated as errors.
4. The study does not claim complete interception of calls that are not routed through the configured proxy.
5. The study still does not measure full LLM-agent task completion; BCAR remains a call-level utility metric.
