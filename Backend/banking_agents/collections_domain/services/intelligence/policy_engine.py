"""Policy decisions for persona transitions, trust gating enforcement, and NBA routing."""
from typing import Any, Dict, List, Optional

# Trust dependent personas are now loaded from config

def evaluate_policy(
    current_persona: str,
    persona_result: Dict[str, Any],
    trust_gate: Dict[str, Any],
    cfg: Dict[str, Any],
) -> Dict[str, Any]:
    # Support new Persona Evidence Model format
    recommended = persona_result.get("dominant_persona", persona_result.get("segment", "unknown_insufficient_data"))
    confidence = persona_result.get("confidence", 0.0)
    confidence_band = persona_result.get("confidence_band", "INSUFFICIENT")
    gate_status = trust_gate.get("trust_gate_status", "REVIEW")

    transition_required = (
        current_persona != recommended
        and recommended != "unknown_insufficient_data"
    )

    policy_cfg = cfg.get("policy", {})
    verification_cfg = policy_cfg.get("verification", {})
    trust_dependent_personas = set(policy_cfg.get("trust_dependent_personas", []))

    transition_blocked = False
    verification_required = False
    block_reason: Optional[str] = None
    
    # Trust enforcement logic
    if transition_required and recommended in trust_dependent_personas:
        if gate_status == "BLOCK":
            transition_blocked = True
            reasons = trust_gate.get("reasons", [])
            if reasons and isinstance(reasons[0], dict):
                block_reason = reasons[0].get("message", "Transition blocked by trust gate.")
            else:
                block_reason = "Trust gate blocked transition to leniency/waiver persona."
        elif gate_status == "REVIEW":
            verification_required = True

    routing_map = policy_cfg.get("nba_routing", {})
    escalate_personas = set(policy_cfg.get("escalate_on_trust_block_with_persona", []))

    route_entry = routing_map.get(recommended)
    
    # NBA determination
    nba_routing = None
    
    if transition_blocked:
        # If blocked, use the fallback route defined for trust_block
        if isinstance(route_entry, dict):
            nba_routing = route_entry.get("trust_block")
    elif verification_required:
        # If under REVIEW, override NBA to request verification
        nba_routing = "request_verification"
    else:
        # Standard routing
        if isinstance(route_entry, dict):
            nba_routing = route_entry.get("default")
        else:
            nba_routing = route_entry

    policy_escalate = gate_status == "BLOCK" and recommended in escalate_personas
    if policy_escalate and not nba_routing:
        nba_routing = "escalate_to_legal"

    if recommended == "unknown_insufficient_data":
        nba_routing = routing_map.get("unknown_insufficient_data", "establish_contact")

    reasons_list: List[str] = []
    if transition_blocked:
        reasons_list.append(block_reason or "Transition blocked by trust gate")
    elif verification_required:
        reasons_list.append(f"Transition to {recommended} placed in PENDING state for verification.")
    elif not transition_required:
        reasons_list.append("No persona transition required")
    else:
        reasons_list.append(f"Transition allowed: {current_persona} → {recommended}")

    if confidence_band in ("LOW", "INSUFFICIENT"):
        reasons_list.append(f"Persona confidence {confidence:.2f} ({confidence_band}) — flag for review")

    if transition_blocked:
        decision = verification_cfg.get("block_decision", "Transition Blocked")
    elif verification_required:
        decision = verification_cfg.get("review_decision", "Verification Required")
    else:
        decision = verification_cfg.get("allow_decision", "Approved")

    policy_reason = reasons_list[0] if reasons_list else verification_cfg.get(
        "review_reason", "Policy review completed"
    )

    return {
        "trust_gate_status": gate_status,
        "transition_blocked": transition_blocked,
        "transition_required": transition_required,
        "verification_required": verification_required,
        "decision": decision,
        "reason": policy_reason,
        "block_reason": block_reason,
        # Under verification, we don't approve the persona yet
        "policy_approved_persona": current_persona if (transition_blocked or verification_required) else recommended,
        "pending_persona": recommended if verification_required else None,
        "policy_nba_routing": nba_routing,
        "policy_escalate": policy_escalate,
        "reasons": reasons_list,
    }


