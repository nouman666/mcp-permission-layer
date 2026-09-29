"""Proxy-owned outcome metadata; authoritative only on the trusted proxy route.
Successful protocol responses do not establish semantic task completion.
"""
KEY = "mcp_permission_layer"


def stamp_result(result, decision, execution):
    # Overwrite any upstream claim in this namespace before returning it.
    result.meta = {**(result.meta or {}), KEY: {
        "schema": 1, "decision": decision, "execution": execution}}
    return result


def classify_result(result):
    marker = (result.meta or {}).get(KEY, {})
    if not isinstance(marker, dict) or marker.get("schema") != 1:
        return {"authorization": "unknown", "execution": "unverified_response", "is_error": result.isError}
    decision, execution = marker.get("decision"), marker.get("execution")
    valid = ((decision == "deny" and execution == "not_forwarded" and result.isError) or
             (decision == "allow" and execution in {"upstream_ok", "upstream_error", "transport_error"} and
              result.isError == (execution != "upstream_ok")))
    if not valid:
        return {"authorization": "unknown", "execution": "invalid_proxy_metadata", "is_error": result.isError}
    return {"authorization": decision, "execution": execution, "is_error": result.isError}
