"""Stable application-facing facade over the ported Collections intelligence pipeline."""
from .repository import load_account
from .services.intelligence.pipeline import run_intelligence_pipeline
from .services.intelligence.scoring_engine import scores_to_flat
from agent_harness.redaction import safe_summary
from agent_harness.tracing import get_tracer


_ACTION_MAP = {
    "send_payment_link": "suppress_all",
    "offer_restructure": "trigger_restructure",
    "establish_contact": "continue_monitoring",
    "trigger_ots": "trigger_ots",
    "escalate_to_field": "escalate_to_field",
    "escalate_to_legal": "escalate_to_legal",
    "request_verification": "request_verification",
}


def run_account_workflow(account_id, override_persona=None, new_claims=None):
    tracer = get_tracer()
    with tracer.span("Collections Workflow", inputs={"account_id": account_id, "override_persona": override_persona, "new_claim_count": len(new_claims or [])}) as workflow:
        with tracer.span("load_account_context", inputs={"account_id": account_id}, run_type="tool") as span:
            account = load_account(account_id)
            span.set_output({"account_id": account_id, "customer_id": account.get("customer_id"), "bucket": account.get("bucket"), "dpd": account.get("dpd"), "interaction_count": len(account.get("interactions", []))})
        with tracer.span("account_data_normalization", inputs={"account_id": account_id}) as span:
            if override_persona:
                account["persona"] = override_persona
            normalized = {"account_id": account_id, "bucket": account.get("bucket"), "dpd": account.get("dpd"), "persona_before": account.get("persona"), "claim_count": len(account.get("claims", []))}
            span.set_output(normalized)
        result = run_intelligence_pipeline(account, current_persona=account.get("persona"), new_claims=new_claims)
        persona = result["persona"]
        trust_gate = result["trust_gate"]
        policy = result["policy"]
        proposed = persona.get("dominant_persona", persona.get("segment", account.get("persona")))
        routing = policy.get("policy_nba_routing") or trust_gate.get("recommended_next_action") or "establish_contact"
        with tracer.span("next_best_action", inputs={"policy_route": routing, "trust_gate": trust_gate.get("status")}) as span:
            next_action = _ACTION_MAP.get(routing, routing)
            span.set_output({"nba_action": next_action, "policy_route": routing})
        flat_scores = scores_to_flat(result["scores"])
        with tracer.span("human_approval_decision", inputs={"trust_gate": trust_gate.get("status"), "nba_action": next_action}) as span:
            human_approval_required = trust_gate.get("status") in {"REVIEW", "BLOCK"} or next_action in {"trigger_ots", "trigger_restructure", "escalate_to_legal"}
            span.set_output({"human_approval_required": human_approval_required, "reason": policy.get("reason")})
        with tracer.span("response_normalization", inputs={"account_id": account_id}) as span:
            response = {
        "account_id": account_id,
        "customer": {"name": account.get("name"), "city": account.get("city"), "product": account.get("product")},
        "account": {"dpd": account.get("dpd"), "bucket": account.get("bucket"), "outstanding": account.get("outstanding"), "emi": account.get("emi")},
        "scoring": {"flat": flat_scores, "details": result["scores"]},
        "persona": proposed,
        "persona_confidence": persona.get("confidence", 0.0),
        "trust_gate": trust_gate,
        "next_best_action": next_action,
        "human_approval_required": human_approval_required,
        "claims": account.get("claims", []),
        "policy": policy,
        "confidence": persona.get("confidence", 0.0),
        "source": "banking_agents.collections_domain",
            }
            span.set_output({"account_id": account_id, "persona": proposed, "trust_gate": trust_gate.get("status"), "nba_action": next_action, "human_approval_required": human_approval_required, "confidence": response["confidence"]})
        workflow.set_output(safe_summary(response))
        return response
