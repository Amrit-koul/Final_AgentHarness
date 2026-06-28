"""Generic policy decision model and evaluator protocol."""
from dataclasses import asdict, dataclass
from typing import Protocol


@dataclass
class PolicyDecision:
    policy_trace_id: str
    trace_id: str
    agent_id: str
    action: str
    decision: str
    allowed: bool
    reason: str
    guardrail_events: list
    human_approval_required: bool = False
    def to_dict(self): return asdict(self)


class PolicyEvaluator(Protocol):
    def check(self, agent_id: str, action: str, context: dict | None = None, trace_id: str | None = None) -> PolicyDecision: ...
