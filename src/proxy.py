"""
Enforcement Proxy
-----------------
Thin mediation layer that:
  1. Receives a tool call
  2. Asks the PermissionChecker for a decision
  3. Logs the decision via AuditLogger
  4. Returns Allow / Deny / Ask to the caller

In the full system this component also speaks the MCP protocol.
For the Master's prototype we expose a clean Python API that can
later be wrapped by an MCP transport (stdio / HTTP).
"""

from __future__ import annotations

from typing import Any, Callable

from models import ToolCall, Decision, DecisionRecord, Policy
from policy_manager import PolicyManager
from checker import PermissionChecker
from audit import AuditLogger
from inference import InferenceConfig


class EnforcementProxy:
    """
    Main entry point of the Runtime Permission Enforcement Layer.

    Usage (programmatic):
        proxy = EnforcementProxy(
            policy_path="policies/read_only.yaml",
            log_path="logs/decisions.jsonl",
        )
        decision, record = proxy.handle_tool_call(
            name="read_file",
            arguments={"path": "src/main.py"},
        )
    """

    def __init__(
        self,
        policy_path: str,
        log_path: str = "logs/decisions.jsonl",
        ask_handler: Callable[[ToolCall, DecisionRecord], bool] | None = None,
        inference_config: InferenceConfig | None = None,
        use_domain_allow_list: bool = True,
        force_default_allow: bool = False,
        checker: PermissionChecker | None = None,
    ) -> None:
        """
        Parameters
        ----------
        policy_path : str
            Path to the YAML policy file.
        log_path : str
            Path for the JSON Lines audit log.
        ask_handler : callable, optional
            Function called when decision is ASK.
            It receives (tool_call, record) and must return True (approve)
            or False (reject). If None, ASK is treated as DENY.
        inference_config : InferenceConfig, optional
            Ablation flags for category inference.
        use_domain_allow_list : bool
            If False, ignore allow_domains (ablation).
        force_default_allow : bool
            If True, missing/unknown categories default to ALLOW (ablation).
        checker : PermissionChecker, optional
            Inject a custom checker (tests / baselines).
        """
        self.policy_manager = PolicyManager()
        self.policy_manager.load(policy_path)

        self.checker = checker or PermissionChecker(
            inference_config=inference_config,
            use_domain_allow_list=use_domain_allow_list,
            force_default_allow=force_default_allow,
        )
        self.logger = AuditLogger(log_path)
        self.ask_handler = ask_handler

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def handle_tool_call(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
        server: str | None = None,
    ) -> tuple[Decision, DecisionRecord]:
        """
        Evaluate a tool call and return (decision, audit_record).

        Decision is one of: ALLOW, DENY, ASK.
        If the decision is ASK and an ask_handler is configured,
        the handler is invoked; its boolean result converts ASK
        into ALLOW or DENY.
        """
        tool_call = ToolCall(
            name=name,
            arguments=arguments or {},
            server=server,
        )

        policy: Policy = self.policy_manager.get_current()
        decision, record = self.checker.evaluate(tool_call, policy)

        # Handle ASK path
        if decision == Decision.ASK:
            if self.ask_handler is not None:
                approved = self.ask_handler(tool_call, record)
                decision = Decision.ALLOW if approved else Decision.DENY
                # update the record so the log reflects the final outcome
                record.final_decision = decision
            else:
                # no handler → fail closed
                decision = Decision.DENY
                record.final_decision = Decision.DENY

        # Always log the final decision
        self.logger.log(record)

        return decision, record

    def reload_policy(self) -> None:
        """Reload the policy from disk (useful during experiments)."""
        self.policy_manager.reload()

    def get_audit_records(self) -> list[dict]:
        """Return all logged records (for evaluation)."""
        return self.logger.read_all()

    def clear_audit_log(self) -> None:
        """Clear the audit log."""
        self.logger.clear()


# ------------------------------------------------------------------
# Simple terminal ask handler (for prototype / demos)
# ------------------------------------------------------------------

def terminal_ask_handler(tool_call: ToolCall, record: DecisionRecord) -> bool:
    """
    Simple but clearer confirmation prompt for the ASK path.
    Returns True if the user types 'y' or 'yes'.
    """
    print("\n" + "=" * 50)
    print("  PERMISSION REQUEST (Approval Required)")
    print("=" * 50)
    print(f"  Tool        : {tool_call.name}")
    if tool_call.server:
        print(f"  Server      : {tool_call.server}")
    print(f"  Arguments   : {tool_call.arguments}")
    print(f"  Categories  : {', '.join(sorted(record.inferred_categories))}")
    print(f"  High risk   : {record.high_risk}")
    print(f"  Policy      : {record.policy_name}")
    print("=" * 50)
    try:
        answer = input("  Allow this tool call? [y/N]: ").strip().lower()
    except EOFError:
        answer = "n"
    approved = answer in ("y", "yes")
    print(f"  → {'APPROVED' if approved else 'REJECTED'}\n")
    return approved


def always_deny_ask_handler(tool_call: ToolCall, record: DecisionRecord) -> bool:
    """Used in automated evaluation — treats every ASK as DENY."""
    return False


def always_allow_ask_handler(tool_call: ToolCall, record: DecisionRecord) -> bool:
    """Used in automated evaluation — treats every ASK as ALLOW."""
    return True
