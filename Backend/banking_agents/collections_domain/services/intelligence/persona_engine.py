"""Evidence-based persona classification using the comprehensive Persona Evidence Model."""
from typing import Any, Dict, List, Tuple

from banking_agents.collections_domain.config.loader import get_config
from banking_agents.collections_domain.services.intelligence.scoring_engine import scores_to_flat

def _check_data_sufficiency(account_data: Dict[str, Any], cfg: Dict[str, Any]) -> Tuple[bool, List[str]]:
    rules = cfg.get("signals", {}).get("data_sufficiency", {})
    min_interactions = rules.get("min_interactions", 3)
    interaction_count = account_data.get("interaction_count", len(account_data.get("interactions", [])))
    ptp_history = account_data.get("ptp_history", [])
    claims = account_data.get("claims", [])

    reasons = []
    if interaction_count >= min_interactions:
        reasons.append(f"Interactions {interaction_count} ≥ {min_interactions}")
        return True, reasons

    reasons.append(f"Interactions {interaction_count} < {min_interactions}")

    if rules.get("or_has_ptp_history") and ptp_history:
        reasons.append("PTP history present — sufficiency override")
        return True, reasons

    if rules.get("or_has_claims") and claims:
        reasons.append("Claims present — sufficiency override")
        return True, reasons

    return False, reasons


def _activate_signals(flat_scores: Dict[str, float], cfg: Dict[str, Any]) -> Dict[str, bool]:
    thresholds = cfg.get("signals", {})
    atp = flat_scores["ability_to_pay"]
    itp = flat_scores["intent_to_pay"]
    trust = flat_scores["trust"]
    contact = flat_scores["contactability"]
    self_cure = flat_scores["self_cure"]

    atp_low = thresholds.get("atp_low_threshold", 40)
    atp_high = thresholds.get("atp_high_threshold", 65)
    itp_low = thresholds.get("itp_low_threshold", 40)
    itp_high = thresholds.get("itp_high_threshold", 65)
    trust_low = thresholds.get("trust_low_threshold", 40)
    trust_high = thresholds.get("trust_high_threshold", 65)
    contact_low = thresholds.get("contactability_low_threshold", 35)
    contact_high = thresholds.get("contactability_high_threshold", 60)
    sc_low = thresholds.get("self_cure_low_threshold", 35)
    sc_high = thresholds.get("self_cure_high_threshold", 65)

    return {
        "low_atp": atp < atp_low,
        "medium_atp": atp_low <= atp <= atp_high,
        "high_atp": atp > atp_high,
        "low_itp": itp < itp_low,
        "medium_itp": itp_low <= itp <= itp_high,
        "high_itp": itp > itp_high,
        "low_trust": trust < trust_low,
        "medium_trust": trust_low <= trust <= trust_high,
        "high_trust": trust > trust_high,
        "low_contactability": contact < contact_low,
        "medium_contactability": contact_low <= contact <= contact_high,
        "high_contactability": contact > contact_high,
        "low_self_cure": self_cure < sc_low,
        "medium_self_cure": sc_low <= self_cure <= sc_high,
        "high_self_cure": self_cure > sc_high,
    }


def _confidence_band(value: float, cfg: Dict[str, Any]) -> str:
    bands = cfg.get("signals", {}).get("persona_confidence_bands", {})
    if value >= bands.get("high", 0.75):
        return "HIGH"
    if value >= bands.get("medium", 0.60):
        return "MEDIUM"
    if value >= bands.get("low", 0.45):
        return "LOW"
    return "INSUFFICIENT"


def _score_persona(
    persona_key: str,
    model: Dict[str, Any],
    active: Dict[str, bool],
    required_penalty: int,
) -> Tuple[float, List[str]]:
    raw = 0.0
    reasoning: List[str] = []

    for signal, weight in (model.get("positive") or {}).items():
        if active.get(signal):
            raw += weight
            reasoning.append(f"+{weight} {signal} (positive)")

    for signal, weight in (model.get("negative") or {}).items():
        if active.get(signal):
            raw += weight
            reasoning.append(f"{weight} {signal} (negative)")

    for req in model.get("required") or []:
        if not active.get(req):
            raw -= required_penalty
            reasoning.append(f"−{required_penalty} missing required signal: {req}")

    return raw, reasoning


def run_persona_classification(
    scores: Dict[str, Any],
    account_data: Dict[str, Any],
) -> Dict[str, Any]:
    """Execute the Persona Evidence Model."""
    cfg = get_config()
    sufficient, sufficiency_reasons = _check_data_sufficiency(account_data, cfg)

    flat = scores_to_flat(scores)

    if not sufficient:
        return {
            "segment": "unknown_insufficient_data",
            "dominant_persona": "unknown_insufficient_data",
            "confidence": 0.0,
            "confidence_band": "INSUFFICIENT",
            "data_sufficient": False,
            "sufficiency_reasons": sufficiency_reasons,
            "active_signals": [],
            "persona_distribution": {},
            "persona_scores": {},
            "reasoning": sufficiency_reasons + ["Skipped evidence model — insufficient data"],
        }

    active = _activate_signals(flat, cfg)
    active_list = [k for k, v in active.items() if v]

    persona_models = cfg.get("personas", {})
    required_penalty = cfg.get("signals", {}).get("required_signal_penalty", 15)

    raw_scores: Dict[str, float] = {}
    all_reasoning: Dict[str, List[str]] = {}

    for persona_key, model in persona_models.items():
        if persona_key == "unknown_insufficient_data":
            continue
        raw, reasoning = _score_persona(persona_key, model, active, required_penalty)
        raw_scores[persona_key] = max(0.0, raw)
        all_reasoning[persona_key] = reasoning

    total = sum(raw_scores.values())
    if total <= 0:
        dominant_persona = "unknown_insufficient_data"
        confidence = 0.0
        distribution = {}
    else:
        dominant_persona = max(raw_scores, key=raw_scores.get)
        confidence = raw_scores[dominant_persona] / total
        distribution = {k: round(v / total, 3) for k, v in raw_scores.items()}

    band = _confidence_band(confidence, cfg)

    return {
        "segment": dominant_persona,  # Maintain backwards compatibility
        "dominant_persona": dominant_persona,
        "confidence": round(confidence, 3),
        "confidence_band": band,
        "data_sufficient": True,
        "sufficiency_reasons": sufficiency_reasons,
        "active_signals": active_list,
        "persona_distribution": distribution,
        "persona_scores": distribution,  # Backwards compatibility
        "raw_persona_scores": raw_scores,
        "reasoning": all_reasoning.get(dominant_persona, []),
        "all_reasoning": all_reasoning,
    }


