"""Full intelligence pipeline: scores → persona → trust → policy.

Trust gate sits above persona transitions and NBA recommendations.
No persona or NBA update is committed without passing through the gate.
"""
from typing import Any, Dict, List, Optional

from banking_agents.collections_domain.config.loader import get_config
from banking_agents.collections_domain.services.intelligence.persona_engine import run_persona_classification
from banking_agents.collections_domain.services.intelligence.policy_engine import evaluate_policy
from banking_agents.collections_domain.services.intelligence.scoring_engine import run_five_score_engine
from banking_agents.collections_domain.services.intelligence.trust_gate import evaluate_trust_gate
from agent_harness.tracing import get_tracer


def run_intelligence_pipeline(
    account_data: Dict[str, Any],
    current_persona: Optional[str] = None,
    new_claims: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Execute Evidence → Scores → Trust → Persona → Policy.

    The trust gate receives full context — proposed persona, current persona,
    new claims — so it can enforce claim-handling rules before policy commits.
    """
    cfg = get_config()
    current = current_persona or account_data.get("persona", "unknown")
    tracer = get_tracer()

    # 1. Score all five dimensions
    scores = run_five_score_engine(account_data)

    # 2. Determine proposed persona from scores alone (not yet committed)
    with tracer.span("persona_engine", inputs={"account_id": account_data.get("id"), "persona_before": current}) as span:
        persona_result = run_persona_classification(scores, account_data)
        span.set_output({"persona_before": current, "persona_after": persona_result.get("dominant_persona"), "confidence": persona_result.get("confidence"), "confidence_band": persona_result.get("confidence_band")})
    proposed_persona = persona_result.get("dominant_persona", persona_result.get("segment"))

    with tracer.span("claim_analysis", inputs={"account_id": account_data.get("id"), "new_claim_count": len(new_claims or [])}) as span:
        claim_summary = {"claim_count": len(new_claims or account_data.get("claims", [])), "claim_types": [claim.get("claim_type", claim.get("type", "unknown")) for claim in (new_claims or account_data.get("claims", []))]}
        span.set_output(claim_summary)

    # 3. Trust gate — evaluates with full context before any commit
    with tracer.span("trust_evaluator", inputs={"account_id": account_data.get("id"), "persona_before": current, "persona_proposed": proposed_persona}) as span:
        span.set_output({"trust_score": scores["trust"].get("score", scores["trust"].get("trust_score")), "confidence": scores["trust"].get("confidence"), "positive_factor_count": len(scores["trust"].get("positive_factors", [])), "negative_factor_count": len(scores["trust"].get("negative_factors", []))})
    with tracer.span("trust_gate", inputs={"persona_before": current, "persona_proposed": proposed_persona, **claim_summary}) as span:
        trust_gate = evaluate_trust_gate(
            scores["trust"], cfg, proposed_persona=proposed_persona, current_persona=current,
            new_claims=new_claims or account_data.get("new_claims", []), nba_action=None,
        )
        span.set_output({"decision": trust_gate.get("status"), "trust_score": trust_gate.get("trust_score"), "verification_required": trust_gate.get("verification_required"), "contradiction_detected": trust_gate.get("contradiction_detected"), "gate_version": trust_gate.get("gate_version")})

    # 4. Policy — respects trust gate status
    with tracer.span("policy_routing", inputs={"persona_before": current, "persona_proposed": proposed_persona, "trust_gate": trust_gate.get("status")}) as span:
        policy = evaluate_policy(current, persona_result, trust_gate, cfg)
        span.set_output({"decision": policy.get("decision"), "route": policy.get("policy_nba_routing"), "verification_required": policy.get("verification_required"), "reason_count": len(policy.get("reasons", []))})

    # 5. Re-evaluate trust gate with NBA action now known (for NBA-specific blocks)
    nba_routing = policy.get("policy_nba_routing")
    if nba_routing:
        with tracer.span("trust_gate", inputs={"phase": "nba_validation", "nba_action": nba_routing}) as span:
            trust_gate = evaluate_trust_gate(scores["trust"], cfg, proposed_persona=proposed_persona, current_persona=current, new_claims=new_claims or account_data.get("new_claims", []), nba_action=nba_routing)
            span.set_output({"decision": trust_gate.get("status"), "verification_required": trust_gate.get("verification_required"), "blocked_updates": trust_gate.get("blocked_updates")})

    return {
        "scores": scores,
        "persona": persona_result,
        "trust_gate": trust_gate,
        "policy": policy,
    }

