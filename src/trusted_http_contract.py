"""Opt-in, administrator-pinned local HTTP adapter contract.

Bindings are constructor configuration, never accepted from tool arguments or
server-advertised descriptions. One binding owns one verified source snapshot.
This does not authenticate an arbitrary remote MCP server or confine hostile code.
"""
from dataclasses import dataclass
import hashlib
from pathlib import Path
from types import ModuleType


class ContractMismatch(ValueError):
    pass


@dataclass(frozen=True)
class ApprovedHttpRouteBinding:
    source_path: Path
    expected_sha256: str
    _implementation: ModuleType

    @classmethod
    def load(cls, source_path, expected_sha256):
        path = Path(source_path).resolve()
        source = path.read_bytes()
        if hashlib.sha256(source).hexdigest() != expected_sha256:
            raise ContractMismatch('Approved source hash mismatch')
        module = ModuleType('approved_http_route_adapter')
        exec(compile(source, str(path), 'exec'), module.__dict__)
        return cls(path, expected_sha256, module)

    def route_paths(self, tool_name, arguments):
        if tool_name != 'http_request':
            return frozenset()
        try:
            if hashlib.sha256(self.source_path.read_bytes()).hexdigest() != self.expected_sha256:
                raise ContractMismatch('Approved source changed')
            self._implementation.resolve_request(arguments)
        except (OSError, ValueError, TypeError, AttributeError) as exc:
            raise ContractMismatch(str(exc)) from exc
        return frozenset({('request', 'path') if set(arguments) == {'request'} else ('path',)})

    def invoke(self, tool_name, arguments):
        if tool_name != 'http_request':
            raise ContractMismatch('Unsupported tool for bound adapter')
        self.route_paths(tool_name, arguments)
        return self._implementation.http_request(arguments)


class ApprovedHttpRouteService:
    """Local reference dispatcher: decision and execution use the same binding."""
    def __init__(self, binding, policy):
        from checker import PermissionChecker
        self.binding = binding
        self.policy = policy
        self.checker = PermissionChecker(trusted_http_route=binding)

    def call(self, tool_name, arguments):
        from models import Decision, ToolCall
        if tool_name != 'http_request':
            raise ContractMismatch('Unsupported tool for bound adapter')
        decision, record = self.checker.evaluate(ToolCall(name=tool_name, arguments=arguments), self.policy)
        if decision != Decision.ALLOW:
            return decision, record, None
        # Revalidation precedes execution of the originally verified snapshot.
        return decision, record, self.binding.invoke(tool_name, arguments)
