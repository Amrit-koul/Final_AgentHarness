"""Bank-specific policy composition over generic harness contracts."""
import json
import uuid

from agent_harness.kill_switch import KillSwitchService
from agent_harness.policy import PolicyDecision
from agent_harness.redaction import safe_summary
from agent_harness.tracing import get_tracer
from banking_agents.guardrails.business import BankingBusinessGuardrails


class BankPolicyEngine:
    def __init__(self, registry, store, guardrail_rules=None): self.registry, self.store, self.guardrails = registry, store, BankingBusinessGuardrails(guardrail_rules)
    def check(self, agent_id, action, context=None, trace_id=None):
        context, trace_id = context or {}, trace_id or str(uuid.uuid4()); contract = self.registry.get_contract(agent_id); permissions = contract.policy_permissions
        context = {**context, "permissions": permissions, "business_function": contract.business_function}
        tracer = get_tracer()
        with tracer.span("pre_guardrail_check", inputs={"agent_id": agent_id, "action": action, "request": safe_summary(context)}, metadata={"trace_id": trace_id}) as guardrail_span:
            events = self.guardrails.evaluate(agent_id, action, context, trace_id)
            guardrail_span.set_output({"decisions": [event.to_dict() for event in events] or [{"decision": "ALLOW", "reason": "No guardrail matched"}]})
        if contract.status.value in {"disabled", "quarantined"}: decision, reason = "BLOCK", f"Agent status is {contract.status.value}"
        elif any(event.decision == "BLOCK" for event in events): decision, reason = "BLOCK", next(event.reason for event in events if event.decision == "BLOCK")
        elif contract.status.value == "review" or any(event.decision == "REVIEW" for event in events):
            override = context.get("human_override") or {}
            if contract.status.value == "review" and override.get("approved") and override.get("approved_by") and override.get("reason"):
                decision, reason = "ALLOW", "Human override approved for review-state agent"
            else: decision, reason = "REVIEW", "Human review is required; provide an approved human_override to execute"
        else: decision, reason = "ALLOW", "Policy and guardrail checks passed"
        approval = action in permissions.get("requires_human_approval_for", [])
        if approval and decision == "ALLOW": decision, reason = "REVIEW", "Manifest requires human approval"
        result = PolicyDecision(str(uuid.uuid4()), trace_id, agent_id, action, decision, decision == "ALLOW", reason, [event.to_dict() for event in events], approval)
        with tracer.span("audit_persist", inputs={"event": "POLICY_DECISION", "decision": decision}) as audit_span:
            cursor = self.store.execute("INSERT INTO policy_decisions(trace_id,agent_id,action,decision,reason,payload_json) VALUES(?,?,?,?,?,?)", (trace_id, agent_id, action, decision, reason, json.dumps(result.to_dict())))
            for event in events: self.store.execute("INSERT INTO guardrail_events(trace_id,agent_id,guardrail_id,decision,severity,reason,matched_rule,suggested_action) VALUES(?,?,?,?,?,?,?,?)", (trace_id, agent_id, event.guardrail_id, event.decision, event.severity, event.reason, event.matched_rule, event.suggested_action))
            audit_span.set_output({"stored": True, "policy_event_id": cursor.lastrowid, "guardrail_event_count": len(events)})
        return result


class BankKillSwitchService(KillSwitchService):
    """Interprets bank guardrail sources without leaking them into the framework."""
    def apply_guardrail(self, agent_id, event):
        gid, severity = event.get("guardrail_id"), event.get("severity")
        if gid == "GRD-INJECT-001": return None
        trace_id = event.get("trace_id")
        if gid == "GRD-SQL-001" and severity == "CRITICAL": return self.change_status(agent_id, "quarantined", "unsafe_sql", event["reason"], trace_id=trace_id, severity=severity)
        if gid == "GRD-PII-001" and severity == "CRITICAL": return self.change_status(agent_id, "review", "pii_leakage", event["reason"], trace_id=trace_id, severity=severity)
        return None
