"""Calculate recency-weighted scores for interactions."""
from datetime import datetime
from typing import Dict, Any, List

def calculate_recency_weight(event_date: datetime, current_date: datetime = None) -> float:
    """Calculate exponential decay weight based on days ago."""
    if not current_date:
        current_date = datetime.utcnow()
        
    if not event_date:
        return 0.0
        
    days_ago = (current_date - event_date).days
    
    if days_ago < 0:
        return 1.0 # Future dates (e.g. pending PTPs)
        
    if days_ago <= 30:
        return 1.0
    elif days_ago <= 90:
        return 0.75
    elif days_ago <= 180:
        return 0.5
    elif days_ago <= 365:
        return 0.25
    else:
        return 0.1
        
def evaluate_channel_escalation(interactions: List[Dict[str, Any]]) -> dict:
    """Detect avoidance escalation patterns (e.g. Voice ignored -> Field ignored)."""
    if not interactions:
        return {"escalation_risk": 0, "pattern": "none"}
        
    # Simplified logic for now, expecting interactions sorted newest first
    has_voice_miss = False
    has_field_miss = False
    has_legal = False
    
    for ix in interactions:
        itype = ix.get("type", "").lower()
        status = ix.get("status", "").lower()
        
        if itype == "legal_notice":
            has_legal = True
        elif itype == "field_visit" and "refus" in status or "not present" in status:
            has_field_miss = True
        elif itype == "voice_call" and "no pickup" in status:
            has_voice_miss = True
            
    if has_legal and has_field_miss and has_voice_miss:
        return {"escalation_risk": 30, "pattern": "severe_avoidance"}
    if has_field_miss and has_voice_miss:
        return {"escalation_risk": 20, "pattern": "strong_avoidance"}
    if has_field_miss:
        return {"escalation_risk": 15, "pattern": "field_avoidance"}
    if has_voice_miss:
        return {"escalation_risk": 5, "pattern": "voice_avoidance"}
        
    return {"escalation_risk": 0, "pattern": "responsive"}


