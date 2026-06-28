"""Semantic contradiction detection for claims."""
from typing import Dict, Any, List

def _are_claims_contradictory(new_claim: str, old_claim: str) -> bool:
    """Check if two claim types are semantically incompatible."""
    incompatible_pairs = [
        ({"employed", "job"}, {"unemployed", "job_loss"}),
        ({"single", "unmarried"}, {"married", "spouse"}),
    ]
    
    n = str(new_claim).lower()
    o = str(old_claim).lower()
    
    for set_a, set_b in incompatible_pairs:
        n_in_a = any(t in n for t in set_a)
        n_in_b = any(t in n for t in set_b)
        o_in_a = any(t in o for t in set_a)
        o_in_b = any(t in o for t in set_b)
        
        if (n_in_a and o_in_b) or (n_in_b and o_in_a):
            return True
            
    return False

def check_contradictions(new_claim: Dict[str, Any], existing_claims: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Check a new claim against history for contradictions."""
    contradictions = []
    
    new_type = new_claim.get("claim_type", "")
    
    for old_claim in existing_claims:
        old_type = old_claim.get("claim_type", "")
        
        if _are_claims_contradictory(new_type, old_type):
            contradictions.append({
                "old_claim_id": old_claim.get("id"),
                "reason": f"New claim '{new_type}' contradicts prior claim '{old_type}'"
            })
            
    return contradictions


