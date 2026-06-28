"""Evaluates the Trust score based on Commitment Reliability and Statement Credibility."""
from typing import Any, Dict, List, Tuple
from datetime import datetime

def _count_ptp(ptp_history: List[Dict[str, Any]], scoring: Dict[str, Any]) -> Tuple[int, int, int]:
    """Return honored count, broken count, and broken within velocity window count."""
    honored = 0
    broken = 0
    velocity_broken = 0
    velocity_days_threshold = scoring.get("velocity_days_threshold", 60)
    
    now = datetime.utcnow()
    
    for p in ptp_history:
        status = str(p.get("status", "")).upper()
        if status == "HONORED":
            honored += 1
        elif status == "BROKEN":
            broken += 1
            # Check velocity
            ptp_date_str = p.get("ptp_date")
            if ptp_date_str:
                try:
                    if isinstance(ptp_date_str, datetime):
                        p_date = ptp_date_str
                    else:
                        p_date = datetime.fromisoformat(str(ptp_date_str).replace('Z', '+00:00'))
                        
                    # Remove timezone info for comparison if now is naive
                    if p_date.tzinfo is not None:
                        p_date = p_date.replace(tzinfo=None)
                        
                    days_ago = (now - p_date).days
                    if 0 <= days_ago <= velocity_days_threshold:
                        velocity_broken += 1
                except (ValueError, TypeError):
                    pass
                    
    return honored, broken, velocity_broken

def evaluate_trust(account_data: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate the comprehensive Trust score."""
    pos, neg = [], []
    scoring = cfg.get("scoring", {}).get("trust", {})
    
    # 1. Commitment Reliability (CR)
    honored, broken, velocity_broken = _count_ptp(account_data.get("ptp_history", []), scoring)
    
    cr = float(scoring.get("cr_base", 50))
    if honored:
        bonus = honored * scoring.get("honored_ptp_cr_bonus", 15)
        cr += bonus
        pos.append(f"{honored} honored PTPs (+{bonus})")
    
    if broken:
        penalty = broken * scoring.get("broken_ptp_cr_penalty", 20)
        cr -= penalty
        neg.append(f"{broken} broken PTPs (-{penalty})")
        
    velocity_count_threshold = scoring.get("velocity_count_threshold", 2)
    if velocity_broken >= velocity_count_threshold:
        vel_penalty = scoring.get("velocity_penalty", 10)
        cr -= vel_penalty
        neg.append(f"Velocity risk: {velocity_broken} broken PTPs in last {scoring.get('velocity_days_threshold', 60)} days (-{vel_penalty})")
        
    cr = max(0, min(100, cr))
    
    # 2. Statement Credibility (SC)
    claims = account_data.get("claims", [])
    sc = float(scoring.get("sc_base", 50))
    
    verified = 0
    contradicted = 0
    rejected = 0
    unverified = 0
    
    for claim in claims:
        state = (claim.get("verification_state") or "CLAIMED").upper()
        if state == "VERIFIED":
            verified += 1
        elif state == "CONTRADICTED":
            contradicted += 1
        elif state == "REJECTED":
            rejected += 1
        elif state in ["CLAIMED", "UNDER_REVIEW", "EVIDENCE_SUBMITTED"]:
            unverified += 1
            
    if verified:
        bonus = verified * scoring.get("verified_claim_sc_bonus", 15)
        sc += bonus
        pos.append(f"{verified} verified claims (+{bonus})")
        
    if contradicted:
        penalty = contradicted * scoring.get("contradicted_claim_sc_penalty", 25)
        sc -= penalty
        neg.append(f"{contradicted} contradicted claims (-{penalty})")
        
    if rejected:
        penalty = rejected * scoring.get("rejected_claim_sc_penalty", 15)
        sc -= penalty
        neg.append(f"{rejected} rejected claims (-{penalty})")
        
    if unverified > 0:
        neg.append(f"{unverified} unverified claims pending review")
        
    sc = max(0, min(100, sc))
    
    # 3. Combine with Confidence reduction for unverified claims
    w_cr = scoring.get("commitment_reliability_weight", 0.6)
    w_sc = scoring.get("statement_credibility_weight", 0.4)
    
    score = (cr * w_cr) + (sc * w_sc)
    
    confidence = 0.30
    if honored or broken:
        confidence = 0.75
    if claims:
        confidence = max(confidence, 0.85)
        
    # Unverified claim confidence reduction (instead of SC cap)
    unverified_claim_conf_reduction = scoring.get("unverified_claim_conf_reduction", 0.20)
    if unverified >= 2:
        conf_reduction = unverified_claim_conf_reduction
        confidence -= conf_reduction
        neg.append(f"Confidence reduced by {conf_reduction} due to multiple unverified claims")
        
    confidence = max(0.0, min(1.0, confidence))
    
    return {
        "score": round(score),
        "trust_score": round(score),
        "commitment_reliability": round(cr),
        "statement_credibility": round(sc),
        "confidence": round(confidence, 2),
        "signal_coverage": 1.0 if claims or account_data.get("ptp_history") else 0.0,
        "model_version": "v2.0",
        "positive_factors": pos,
        "negative_factors": neg,
        "reasons": pos + neg, # backwards compatibility
    }


