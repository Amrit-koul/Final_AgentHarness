"""Enterprise scoring engine (ATP, ITP, Contactability, Self-Cure).
Trust has been moved to trust_evaluator.py.
"""
from typing import Any, Dict, List, Tuple
from datetime import datetime

from banking_agents.collections_domain.config.loader import get_config
from banking_agents.collections_domain.services.intelligence.interaction_parser import parse_interactions
from banking_agents.collections_domain.services.intelligence.occupation_mapper import get_occupation_score
from banking_agents.collections_domain.services.intelligence.interaction_recency import calculate_recency_weight, evaluate_channel_escalation
from agent_harness.tracing import get_tracer

def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))

def _score_result(
    score: float, 
    confidence: float, 
    positive_factors: List[str], 
    negative_factors: List[str],
    signal_coverage: float = 1.0,
    model_version: str = "v2.0"
) -> Dict[str, Any]:
    return {
        "score": round(_clamp(score)),
        "confidence": round(max(0.0, min(1.0, confidence)), 2),
        "signal_coverage": round(signal_coverage, 2),
        "model_version": model_version,
        "positive_factors": positive_factors,
        "negative_factors": negative_factors,
        "reasons": positive_factors + negative_factors, # For backwards compatibility
    }

def calculate_atp(account_data: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate Ability to Pay (ATP) score."""
    scoring = cfg.get("scoring", {}).get("atp", {})
    cibil = account_data.get("cibil", 600) or 600
    job = account_data.get("job", "")
    dpd = account_data.get("dpd", 0) or 0
    
    pos, neg = [], []
    
    # 1. Bureau Health (CIBIL base)
    floor = scoring.get("cibil_floor", 300)
    span = scoring.get("cibil_range", 600)
    base_score = ((cibil - floor) / span) * 100
    if cibil >= 750:
        pos.append(f"Strong bureau health (CIBIL {cibil})")
    elif cibil < 600:
        neg.append(f"Weak bureau health (CIBIL {cibil})")
        
    score = base_score
    
    # 2. Occupation Stability
    job_info = get_occupation_score(job)
    job_stab = job_info["stability"]
    if job_stab > 0:
        pos.append(f"Stable occupation category: {job_info['category']}")
    elif job_stab < 0:
        neg.append(f"High-risk occupation category: {job_info['category']}")
    score += job_stab
    
    # 3. Delinquency Trend Impact on Ability
    if dpd > 90:
        neg.append(f"Severe delinquency (DPD {dpd}) suggests sustained inability")
        score -= 20
    elif dpd > 30:
        neg.append(f"Moderate delinquency (DPD {dpd})")
        score -= 10
        
    # 4. Partial Payment Ratio (Proxy for capacity)
    interactions = account_data.get("interactions", [])
    signals = parse_interactions(interactions)
    if signals.partial_payment or signals.payment_attempted:
        pos.append("Recent partial payment demonstrates partial capacity")
        score += 15
        
    confidence = 0.85 if cibil else 0.50
    signal_cov = 1.0 if (cibil and job) else 0.6
    
    return _score_result(score, confidence, pos, neg, signal_cov)

def calculate_itp(account_data: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate Intent to Pay (ITP) score."""
    pos, neg = [], []
    score = 50.0
    dpd = account_data.get("dpd", 0) or 0
    
    # 1. Delinquency Bands (Replaces capped penalty)
    if dpd == 0:
        pos.append("Current account (DPD 0)")
        score += 15
    elif dpd <= 30:
        neg.append(f"Early delinquency (DPD {dpd})")
        score -= 10
    elif dpd <= 60:
        neg.append(f"Mid delinquency (DPD {dpd})")
        score -= 20
    elif dpd <= 90:
        neg.append(f"Late delinquency (DPD {dpd})")
        score -= 30
    else:
        neg.append(f"Severe delinquency (DPD {dpd})")
        score -= 40
        
    # 2. Interaction Recency & Engagement
    interactions_raw = account_data.get("interactions", [])
    # In a real app we'd parse timestamps from interaction objects, here we approximate
    # for demo purposes.
    signals = parse_interactions(interactions_raw)
    
    if signals.voice_pickups > 0:
        pos.append("Recent voice engagement")
        score += 10
    elif signals.voice_no_pickup > 2:
        neg.append("Repeatedly ignored voice calls")
        score -= 15
        
    if signals.customer_callbacks:
        pos.append("Customer initiated contact")
        score += 20
        
    # 3. Channel Escalation Signals
    # For now, we mock interaction objects to pass to evaluator
    mock_ix = []
    if signals.voice_no_pickup:
        mock_ix.append({"type": "voice_call", "status": "no pickup"})
    if signals.field_refused:
        mock_ix.append({"type": "field_visit", "status": "refused"})
        
    escalation = evaluate_channel_escalation(mock_ix)
    if escalation["escalation_risk"] > 0:
        neg.append(f"Avoidance escalation detected: {escalation['pattern']}")
        score -= escalation["escalation_risk"]
        
    # PTP Recency (simplified)
    ptp_history = account_data.get("ptp_history", [])
    if ptp_history:
        pos.append("History of establishing payment plans")
        
    confidence = 0.90 if len(interactions_raw) >= 3 else 0.65
    signal_cov = 1.0 if interactions_raw else 0.4
    
    return _score_result(score, confidence, pos, neg, signal_cov)

def calculate_contactability(account_data: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate Contactability score using observed behavior with decay."""
    pos, neg = [], []
    interactions_raw = account_data.get("interactions", [])
    
    if not interactions_raw:
        neg.append("No interaction history available")
        return _score_result(50.0, 0.20, pos, neg, 0.0)
        
    signals = parse_interactions(interactions_raw)
    score = 0.0
    
    voice_rate = (signals.voice_pickups / signals.voice_attempts) if signals.voice_attempts else 0
    if voice_rate > 0.5:
        pos.append(f"High voice pickup rate ({voice_rate:.0%})")
        score += 40
    elif voice_rate > 0:
        pos.append(f"Moderate voice pickup rate ({voice_rate:.0%})")
        score += 20
    elif signals.voice_attempts > 0:
        neg.append("Zero voice pickups observed")
        
    if signals.customer_callbacks:
        pos.append("Customer initiates callbacks")
        score += 30
        
    wa_rate = (signals.whatsapp_read / signals.whatsapp_sent) if signals.whatsapp_sent else 0
    if wa_rate > 0.5:
        pos.append(f"High WhatsApp engagement ({wa_rate:.0%})")
        score += 20
        
    # Recency decay would apply here to individual interaction objects
    # but we're working with aggregate signals mostly. 
    
    # Normalize score
    score = score if score > 0 else 20.0 # Floor if we have negative interactions
    if score > 100: score = 100.0
    
    confidence = 0.85 if len(interactions_raw) >= 3 else 0.60
    
    return _score_result(score, confidence, pos, neg, 1.0)

def calculate_self_cure(
    account_data: Dict[str, Any],
    atp: Dict[str, Any],
    itp: Dict[str, Any],
    trust: Dict[str, Any],
    cfg: Dict[str, Any],
) -> Dict[str, Any]:
    """Calculate Self Cure Probability based on Bucket Scoring."""
    pos, neg = [], []
    dpd = account_data.get("dpd", 0) or 0
    bucket = account_data.get("bucket", "X1")
    
    atp_val = atp.get("score", 50)
    itp_val = itp.get("score", 50)
    trust_val = trust.get("score", 50)
    
    # Base cure rate defined by bucket
    bucket_baselines = cfg.get("scoring", {}).get("self_cure", {}).get("bucket_baselines", {
        "pre_due": 95.0,
        "X1": 80.0,
        "X2": 45.0,
        "X3": 15.0,
        "legal": 5.0
    })
    
    score = bucket_baselines.get(bucket, 50.0)
    pos.append(f"Base bucket rate ({bucket}): {score}%")
    
    # Modifiers based on fundamental scores
    if atp_val > 70 and itp_val > 70:
        pos.append("High ATP + High ITP indicates strong capability to cure")
        score += 15
    elif atp_val < 40:
        neg.append("Low ATP severely restricts cure probability")
        score -= 20
        
    if trust_val < 40:
        neg.append("Low trust undermines intent signals")
        score -= 10
        
    status = str(account_data.get("status", "")).lower()
    if "escalat" in status:
        neg.append("Account is currently escalated")
        score -= 15
        
    confidence = min(atp.get("confidence", 0.5), itp.get("confidence", 0.5))
    
    return _score_result(score, confidence, pos, neg, 1.0)

def run_five_score_engine(account_data: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate all scores (Trust is now injected from evaluator).
    This function is primarily for backward compatibility or parallel pipeline execution.
    Usually trust should be calculated first.
    """
    cfg = get_config()
    from banking_agents.collections_domain.services.intelligence.trust_evaluator import evaluate_trust

    tracer = get_tracer()
    signal_meta = {"account_id": account_data.get("id"), "dpd_band": account_data.get("bucket"), "interaction_count": len(account_data.get("interactions", []))}
    with tracer.span("five_score_engine", inputs=signal_meta, metadata={"model_version": "v2.0"}) as parent:
        with tracer.span("ability_to_pay_score", inputs=signal_meta) as span:
            atp = calculate_atp(account_data, cfg); span.set_output(_trace_score(atp))
        with tracer.span("intent_to_pay_score", inputs=signal_meta) as span:
            itp = calculate_itp(account_data, cfg); span.set_output(_trace_score(itp))
        with tracer.span("trust_score", inputs=signal_meta) as span:
            trust = evaluate_trust(account_data, cfg); span.set_output(_trace_score(trust))
        with tracer.span("contactability_score", inputs=signal_meta) as span:
            contactability = calculate_contactability(account_data, cfg); span.set_output(_trace_score(contactability))
        with tracer.span("self_cure_score", inputs=signal_meta) as span:
            self_cure = calculate_self_cure(account_data, atp, itp, trust, cfg); span.set_output(_trace_score(self_cure))
        parent.set_output({"scores": {"ability_to_pay": atp["score"], "intent_to_pay": itp["score"], "trust": trust.get("score", trust.get("trust_score")), "contactability": contactability["score"], "self_cure": self_cure["score"]}})

    return {
        "ability_to_pay": atp,
        "intent_to_pay": itp,
        "trust": trust,
        "contactability": contactability,
        "self_cure": self_cure,
    }


def _trace_score(result: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "score": result.get("score", result.get("trust_score")),
        "confidence": result.get("confidence"),
        "model_version": result.get("model_version"),
        "positive_factor_count": len(result.get("positive_factors", [])),
        "negative_factor_count": len(result.get("negative_factors", [])),
    }

def scores_to_flat(scores: Dict[str, Any]) -> Dict[str, float]:
    """Flatten nested score objects to simple numeric values."""
    return {
        "ability_to_pay": scores["ability_to_pay"]["score"],
        "intent_to_pay": scores["intent_to_pay"]["score"],
        "trust": scores["trust"]["score"] if "score" in scores["trust"] else scores["trust"].get("trust_score", 50),
        "contactability": scores["contactability"]["score"],
        "self_cure": scores["self_cure"]["score"],
    }

