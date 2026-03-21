from dataclasses import dataclass
from typing import Iterable

from .identity import ActorIdentity


SENSITIVE_INTENTS = {"database_write", "export_external", "send_email"}


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    requires_interrupt: bool
    reason: str


def evaluate_tool_call(
    identity: ActorIdentity, tool_name: str, declared_intent: str, allowed_tools: Iterable[str]
) -> PolicyDecision:
    if tool_name not in set(allowed_tools):
        return PolicyDecision(
            allowed=False,
            requires_interrupt=False,
            reason=f"Tool not in allowlist: {tool_name}",
        )

    if declared_intent != identity.intent:
        return PolicyDecision(
            allowed=False,
            requires_interrupt=False,
            reason="Declared intent mismatch",
        )

    if declared_intent in SENSITIVE_INTENTS:
        return PolicyDecision(
            allowed=False,
            requires_interrupt=True,
            reason=f"Sensitive intent requires approval: {declared_intent}",
        )

    return PolicyDecision(allowed=True, requires_interrupt=False, reason="Allowed")
