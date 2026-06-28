"""
Pydantic schemas for Trust Gate API responses.
All fields are optional-tolerant for backward compatibility.
"""
from __future__ import annotations
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class TrustGateReason(BaseModel):
    code: str
    message: str


class TrustGateResult(BaseModel):
    """Full trust gate decision output — returned post-call and on AI profile."""
    # Core decision
    status: Literal["ALLOW", "REVIEW", "BLOCK"] = "REVIEW"
    trust_gate_status: Literal["ALLOW", "REVIEW", "BLOCK"] = "REVIEW"

    # Scores
    trust_score: float = Field(default=50.0, ge=0, le=100)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)

    # Flags
    verification_required: bool = False
    contradiction_detected: bool = False

    # Update permissions
    allowed_updates: List[str] = Field(default_factory=list)
    blocked_updates: List[str] = Field(default_factory=list)

    # Reasoning
    reasons: List[TrustGateReason] = Field(default_factory=list)
    evidence: Dict[str, Any] = Field(default_factory=dict)

    # Action
    recommended_next_action: str = "request_verification"

    # Versioning
    gate_version: str = "v2.2"

    # Persona tracking
    proposed_persona: Optional[str] = None
    final_persona: Optional[str] = None

    class Config:
        extra = "allow"

    def to_api_dict(self) -> Dict[str, Any]:
        _labels = {"ALLOW": "Approved", "REVIEW": "Requires Verification", "BLOCK": "Escalated"}
        return {
            "trust_gate_status": self.status,
            "trust_gate_label": _labels.get(self.status, self.status),
            "trust_score": round(self.trust_score),
            "confidence": round(self.confidence, 2),
            "verification_required": self.verification_required,
            "contradiction_detected": self.contradiction_detected,
            "allowed_updates": self.allowed_updates,
            "blocked_updates": self.blocked_updates,
            "trust_reasons": [r.message for r in self.reasons],
            "recommended_next_action": self.recommended_next_action,
            "proposed_persona": self.proposed_persona,
            "final_persona": self.final_persona,
        }


