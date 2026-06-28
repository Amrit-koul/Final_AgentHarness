"""Bank-specific deterministic guardrails."""
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import re


@dataclass
class GuardrailResult:
    guardrail_id: str
    decision: str
    severity: str
    reason: str
    matched_rule: str
    suggested_action: str
    trace_id: str
    agent_id: str
    timestamp: str
    def to_dict(self): return asdict(self)


class BankingBusinessGuardrails:
    def __init__(self, rules=None): self.rules = rules or {}
    def evaluate(self, agent_id, action, context, trace_id):
        text = " ".join(str(context.get(key, "")) for key in ("input_text", "output_text", "action_input", "query", "sql")); lowered = text.lower(); results = []
        checks = [
            ("unsafe_sql", "GRD-SQL-001", r"\b(drop\s+table|truncate\s+table|delete\s+from|alter\s+table|union\s+select)", "BLOCK", "CRITICAL", "Unsafe database mutation or injection pattern", "Use a read-only, parameterized query."),
            ("prompt_injection", "GRD-INJECT-001", r"(ignore (all |the )?(previous|prior|system) instructions|reveal (the )?system prompt|developer mode|jailbreak)", "BLOCK", "HIGH", "Prompt-injection attempt detected", "Reject this request and log a security event."),
            ("pii_leakage", "GRD-PII-001", r"\b\d{4}[ -]?\d{4}[ -]?\d{4}\b|\b[A-Z]{5}\d{4}[A-Z]\b|\b(?:\d[ -]*?){13,16}\b", "BLOCK", "CRITICAL", "Sensitive identifier detected", "Redact PII before returning output."),
            ("collections_conduct", "GRD-CONDUCT-001", r"(threaten|harass|publicly shame|contact your employer|seize.*without notice)", "BLOCK", "HIGH", "Prohibited collections conduct", "Use respectful, regulator-compliant language."),
            ("regulatory_advice", "GRD-REG-001", r"(guaranteed legal advice|definitely legal|no legal risk)", "REVIEW", "HIGH", "Definitive regulatory/legal advice", "Request specialist review."),
        ]
        for key, default_id, pattern, decision, severity, reason, suggestion in checks:
            config = self.rules.get(key, {})
            if config.get("enabled", True) and re.search(pattern, lowered, re.I): results.append(self._result(config.get("id", default_id), decision, severity, reason, pattern, suggestion, trace_id, agent_id))
        permissions = context.get("permissions", {}); data_scope = context.get("data_scope")
        if data_scope and data_scope not in permissions.get("allowed_data_scopes", []): results.append(self._result("GRD-CUST-DATA-001", "BLOCK", "HIGH", "Requested data scope is not authorized", data_scope, "Request the minimum authorized data scope.", trace_id, agent_id))
        high_risk = action in {"payment", "waiver", "settlement", "trigger_legal", "execute_sql"}; allowed = permissions.get("allowed_actions", permissions.get("allowed_tools", []))
        if high_risk and action not in allowed: results.append(self._result("GRD-PAY-001", "BLOCK", "HIGH", "High-risk banking action is not authorized", action, "Obtain policy permission or human approval.", trace_id, agent_id))
        if context.get("requested_business_function") and context.get("business_function", "").lower() != context["requested_business_function"].lower(): results.append(self._result("GRD-SCOPE-001", "REVIEW", "MEDIUM", "Request is outside the agent business scope", context["requested_business_function"], "Route to the matching business function.", trace_id, agent_id))
        return results
    @staticmethod
    def _result(gid, decision, severity, reason, matched, suggestion, trace_id, agent_id): return GuardrailResult(gid, decision, severity, reason, matched, suggestion, trace_id, agent_id, datetime.now(timezone.utc).isoformat())
