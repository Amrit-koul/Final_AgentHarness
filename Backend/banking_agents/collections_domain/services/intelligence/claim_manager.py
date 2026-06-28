from typing import Dict, Any, List
import uuid
from banking_agents.collections_domain.services.intelligence.claim_contradiction import check_contradictions

class ClaimManager:
    """
    Manages the lifecycle of customer claims.
    Valid states: CLAIMED, UNDER_REVIEW, EVIDENCE_SUBMITTED, VERIFIED, 
    PARTIALLY_VERIFIED, INSUFFICIENT_EVIDENCE, CONTRADICTED, REJECTED
    """
    
    def __init__(self):
        pass
        
    def process_new_claim(self, claim_data: Dict[str, Any], existing_claims: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Process a newly extracted claim from a conversation, checking for contradictions."""
        if existing_claims is None:
            existing_claims = []
            
        contradictions = check_contradictions(claim_data, existing_claims)
        
        return {
            "id": f"CLM-{uuid.uuid4().hex[:8].upper()}",
            "claim_type": claim_data.get("claim_type"),
            "claim_details": claim_data.get("claim_details"),
            "verification_state": "CLAIMED",
            "contradicted_flag": False,
            "contradiction_reason": None,
            "claim_confidence": claim_data.get("confidence", 0.5),
            "new_contradictions_found": contradictions # Signal to pipeline to update old claims
        }
        
    def review_claim(self, claim: Dict[str, Any]) -> Dict[str, Any]:
        claim["verification_state"] = "UNDER_REVIEW"
        return claim

    def submit_evidence(self, claim: Dict[str, Any], evidence: Any) -> Dict[str, Any]:
        claim["verification_state"] = "EVIDENCE_SUBMITTED"
        claim["evidence_provided"] = evidence
        return claim
        
    def verify_claim(self, claim: Dict[str, Any]) -> Dict[str, Any]:
        claim["verification_state"] = "VERIFIED"
        return claim
        
    def partially_verify_claim(self, claim: Dict[str, Any]) -> Dict[str, Any]:
        claim["verification_state"] = "PARTIALLY_VERIFIED"
        return claim
        
    def insufficient_evidence(self, claim: Dict[str, Any]) -> Dict[str, Any]:
        claim["verification_state"] = "INSUFFICIENT_EVIDENCE"
        return claim
        
    def mark_contradicted(self, claim: Dict[str, Any], reason: str) -> Dict[str, Any]:
        claim["verification_state"] = "CONTRADICTED"
        claim["contradicted_flag"] = True
        claim["contradiction_reason"] = reason
        return claim
        
    def reject_claim(self, claim: Dict[str, Any], reason: str) -> Dict[str, Any]:
        claim["verification_state"] = "REJECTED"
        return claim


