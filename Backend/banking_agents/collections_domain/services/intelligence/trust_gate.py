"""
Trust Gate — evaluates post-call signals and returns a structured gate decision.

ALLOW  → evidence consistent, trust score high enough, updates can be applied.
REVIEW → claim unverified or trust borderline — human ops review required.
BLOCK  → contradiction detected or trust too low — no sensitive update applied.

Key rules enforced here:
- Life-event claims (hospitalization, job loss, etc.) → always REVIEW unless
  there is strong existing evidence (verified claim + high trust).
- Broken PTP history + new hardship claim → REVIEW or BLOCK.
- No persona or NBA update crosses the gate without evaluation.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

# Life-event claim types that always need human verification
_LIFE_EVENT_CLAIM_TYPES = {
    "hospitalization", "medical", "job_loss", "family_emergency",
    "income_disruption", "natural_disaster", "business_loss", "hardship",
}

# Actions that are sensitive and require ALLOW gate status
_SENSITIVE_ACTIONS = {
    "trigger_ots", "trigger_restructure", "escalate_to_legal",
}

# Personas that require a trust gate pass before auto-commit
_TRUST_DEPENDENT_PERSONAS = {
    "temporarily_distressed", "genuinely_distressed",
    "forgetful_payer", "the_negotiator", "reluctant_avoider",
}


def _gate_cfg(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Pull trust_gate config from merged config, supporting both old and new key paths."""
    # Try new path (trust_rules.yaml)
    tg = cfg.get("trust_gate", {})
    if tg:
        return tg
    # Fallback: old path (trust_gating.yaml / scoring.yaml)
    signals = cfg.get("signals", {}).get("trust_gate", {})
    return {
        "allow_threshold": signals.get("allow_min_score", 60),
        "review_threshold": signals.get("review_min_score", 35),
        "block_threshold": signals.get("review_min_score", 35),
        "low_confidence_threshold": signals.get("low_confidence_threshold", 0.50),
    }


def evaluate_trust_gate(
    trust_score_result: Dict[str, Any],
    cfg: Dict[str, Any],
    *,
    proposed_persona: Optional[str] = None,
    current_persona: Optional[str] = None,
    new_claims: Optional[List[Dict[str, Any]]] = None,
    nba_action: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Main trust gate evaluator.

    Args:
        trust_score_result: Output from trust_evaluator.evaluate_trust().
        cfg: Merged config dict from config/loader.py.
        proposed_persona: Persona the pipeline wants to transition to.
        current_persona: Current persona on the account.
        new_claims: Claims extracted in this call (from call_evidence).
        nba_action: Proposed NBA action code.

    Returns:
        Dict matching TrustGateResult schema, plus raw keys for backward compat.
    """
    gate = _gate_cfg(cfg)

    score = trust_score_result.get("trust_score",
            trust_score_result.get("score", 50))
    confidence = trust_score_result.get("confidence", 0.5)
    negative_factors = trust_score_result.get("negative_factors", [])

    allow_threshold = gate.get("allow_threshold", 60)
    review_threshold = gate.get("review_threshold", 35)
    low_conf = gate.get("low_confidence_threshold", 0.50)

    reasons: List[Dict[str, str]] = []
    verification_required = False
    contradiction_detected = False
    allowed_updates: List[str] = []
    blocked_updates: List[str] = []

    # ── 1. Base status from score ──────────────────────────────────────────
    if score >= allow_threshold:
        status = "ALLOW"
        reasons.append({"code": "SCORE_ALLOW",
                        "message": f"Trust score {score} meets ALLOW threshold ({allow_threshold}+)"})
    elif score >= review_threshold:
        status = "REVIEW"
        reasons.append({"code": "SCORE_REVIEW",
                        "message": f"Trust score {score} in REVIEW band ({review_threshold}–{allow_threshold - 1})"})
    else:
        status = "BLOCK"
        reasons.append({"code": "SCORE_BLOCK",
                        "message": f"Trust score {score} below minimum threshold ({review_threshold})"})

    # ── 2. Confidence override ─────────────────────────────────────────────
    if confidence < low_conf:
        if status == "ALLOW":
            status = "REVIEW"
            reasons.append({"code": "CONFIDENCE_DOWNGRADE",
                            "message": f"Low confidence ({confidence:.2f}) — ALLOW downgraded to REVIEW"})
        elif status == "REVIEW":
            status = "BLOCK"
            reasons.append({"code": "CONFIDENCE_DOWNGRADE",
                            "message": f"Low confidence ({confidence:.2f}) with borderline score — REVIEW downgraded to BLOCK"})

    # ── 3. Propagate negative factors from trust evaluator ─────────────────
    for neg in negative_factors:
        low = neg.lower()
        if "velocity risk" in low:
            reasons.append({"code": "VELOCITY_RISK", "message": neg})
        elif "broken" in low:
            reasons.append({"code": "BROKEN_PTP", "message": neg})
        elif "unverified" in low:
            reasons.append({"code": "UNVERIFIED_CLAIMS", "message": neg})
        elif "contradict" in low:
            contradiction_detected = True
            reasons.append({"code": "CONTRADICTION", "message": neg})

    # ── 4. Contradiction check from trust evaluator ────────────────────────
    statement_credibility = trust_score_result.get("statement_credibility", 50)
    if statement_credibility < 30 or contradiction_detected:
        contradiction_detected = True
        if status == "ALLOW":
            status = "BLOCK"
            reasons.append({"code": "CONTRADICTION_DOWNGRADE",
                            "message": "Statement credibility critically low — contradictions detected, gate downgraded to BLOCK"})

    # ── 5. Life-event claim handling ───────────────────────────────────────
    # Life-event claims are NEVER auto-approved — always require verification.
    claims = new_claims or []
    life_event_claims = [c for c in claims
                         if c.get("claim_type", "") in _LIFE_EVENT_CLAIM_TYPES]

    if life_event_claims:
        verification_required = True
        claim_types_str = ", ".join(c.get("claim_type", "hardship") for c in life_event_claims)
        reasons.append({"code": "LIFE_EVENT_CLAIM",
                        "message": f"Life-event claim detected ({claim_types_str}) — human verification required before persona change"})
        # Life-event claims with already-ALLOW gate → downgrade to REVIEW (never auto-commit)
        if status == "ALLOW":
            status = "REVIEW"
            reasons.append({"code": "LIFE_EVENT_DOWNGRADE",
                            "message": "Gate downgraded ALLOW → REVIEW: unverified life-event claim present"})

    # ── 6. Persona transition sensitivity ─────────────────────────────────
    if proposed_persona and proposed_persona in _TRUST_DEPENDENT_PERSONAS:
        if proposed_persona != (current_persona or ""):
            if status == "BLOCK":
                blocked_updates.append("persona_transition")
                reasons.append({"code": "PERSONA_BLOCKED",
                                "message": f"Persona transition to '{proposed_persona}' blocked — trust gate BLOCK"})
            elif status == "REVIEW":
                verification_required = True
                reasons.append({"code": "PERSONA_REVIEW",
                                "message": f"Persona transition to '{proposed_persona}' requires supervisor review"})

    # ── 7. NBA action sensitivity ──────────────────────────────────────────
    if nba_action and nba_action in _SENSITIVE_ACTIONS:
        if status == "BLOCK":
            blocked_updates.append(f"nba:{nba_action}")
            reasons.append({"code": "NBA_BLOCKED",
                            "message": f"NBA action '{nba_action}' blocked — trust gate BLOCK"})
        elif status == "REVIEW":
            reasons.append({"code": "NBA_REVIEW",
                            "message": f"NBA action '{nba_action}' flagged for review"})

    # ── 8. Allowed updates (positive list) ────────────────────────────────
    if status == "ALLOW":
        allowed_updates = ["score_update", "persona_transition", "nba_update"]
    elif status == "REVIEW":
        allowed_updates = ["score_update"]
        blocked_updates_base = ["persona_transition"]
        if nba_action in _SENSITIVE_ACTIONS:
            blocked_updates_base.append(f"nba:{nba_action}")
        blocked_updates = list(set(blocked_updates + blocked_updates_base))
    else:  # BLOCK
        allowed_updates = []
        blocked_updates = list(set(blocked_updates + ["score_update", "persona_transition", "nba_update"]))

    # ── 9. Recommended next action ─────────────────────────────────────────
    if status == "ALLOW":
        recommended_next_action = nba_action or "continue_monitoring"
    elif status == "REVIEW":
        recommended_next_action = "request_verification"
    else:
        recommended_next_action = "escalate_to_field" if "hostile" in (current_persona or "") else "request_verification"

    # ── 10. Evidence summary ───────────────────────────────────────────────
    evidence = {
        "trust_score": score,
        "confidence": confidence,
        "statement_credibility": statement_credibility,
        "commitment_reliability": trust_score_result.get("commitment_reliability", 50),
        "positive_factors": trust_score_result.get("positive_factors", []),
        "negative_factors": negative_factors,
        "life_event_claims_count": len(life_event_claims),
        "contradiction_detected": contradiction_detected,
        "proposed_persona": proposed_persona,
        "current_persona": current_persona,
    }

    return {
        # Primary fields (new schema)
        "status": status,
        "trust_score": round(score),
        "confidence": round(confidence, 2),
        "verification_required": verification_required,
        "contradiction_detected": contradiction_detected,
        "allowed_updates": allowed_updates,
        "blocked_updates": list(set(blocked_updates)),
        "reasons": reasons,
        "evidence": evidence,
        "recommended_next_action": recommended_next_action,
        "gate_version": "v2.2",
        "proposed_persona": proposed_persona,
        "final_persona": (
            proposed_persona if status == "ALLOW" and "persona_transition" in allowed_updates
            else current_persona
        ),
        # Backward-compat aliases
        "trust_gate_status": status,
        "trust_confidence": round(confidence, 2),
    }


