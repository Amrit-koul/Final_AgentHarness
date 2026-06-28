"""Map occupation to stability and income multipliers."""

def get_occupation_score(job_profile: str) -> dict:
    """Return stability score and risk multiplier for a given job."""
    if not job_profile:
        return {"stability": 0, "risk_multiplier": 1.0, "category": "unknown"}
        
    job_lower = str(job_profile).lower()
    
    if "govt" in job_lower or "government" in job_lower or "psu" in job_lower:
        return {"stability": 25, "risk_multiplier": 0.8, "category": "government"}
        
    if "sr." in job_lower or "senior" in job_lower or "manager" in job_lower or "director" in job_lower or "vp" in job_lower:
        return {"stability": 20, "risk_multiplier": 0.85, "category": "senior_corporate"}
        
    if "engineer" in job_lower or "software" in job_lower or "doctor" in job_lower or "ca" in job_lower:
        return {"stability": 15, "risk_multiplier": 0.9, "category": "professional"}
        
    if "clerk" in job_lower or "associate" in job_lower or "executive" in job_lower or "employee" in job_lower:
        return {"stability": 10, "risk_multiplier": 1.0, "category": "salaried"}
        
    if "business" in job_lower or "owner" in job_lower or "entrepreneur" in job_lower or "founder" in job_lower:
        return {"stability": 5, "risk_multiplier": 1.1, "category": "business"}
        
    if "contractor" in job_lower or "freelance" in job_lower or "gig" in job_lower:
        return {"stability": -5, "risk_multiplier": 1.2, "category": "contract"}
        
    if "worker" in job_lower or "labor" in job_lower or "driver" in job_lower:
        return {"stability": -10, "risk_multiplier": 1.3, "category": "wage_worker"}
        
    if "unemployed" in job_lower or "student" in job_lower or "retired" in job_lower:
        return {"stability": -20, "risk_multiplier": 1.5, "category": "high_risk"}
        
    return {"stability": 0, "risk_multiplier": 1.0, "category": "other"}


