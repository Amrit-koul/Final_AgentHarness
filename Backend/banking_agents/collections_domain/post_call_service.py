"""Safe API-facing persistence boundary for recorded Collections calls.

This module intentionally accepts a recorded/sample transcript and evidence.
It does not integrate with a telephony provider or expose transcripts in its
read models.
"""
import uuid
from datetime import datetime
from typing import Any

from banking_agents.collections_domain.agents.orchestrator import get_orchestrator
from banking_agents.collections_domain.db.database import SessionLocal
from banking_agents.collections_domain.db.models import CallHistory, Claim, LoanAccount, ReviewCase, ScoreHistory, TrustAuditLog
from banking_agents.collections_domain.repository import ensure_seeded, load_account


def process_recorded_call(account_id: str, transcript: str, evidence: dict[str, Any]) -> dict[str, Any]:
    """Persist a recorded call, run post-call intelligence, and return safe proof."""
    if not isinstance(transcript, str) or not transcript.strip():
        raise ValueError("transcript is required")
    if not isinstance(evidence, dict):
        raise ValueError("evidence must be an object")

    ensure_seeded()
    account_data = load_account(account_id)
    db = SessionLocal()
    try:
        account_row = db.query(LoanAccount).filter(LoanAccount.id == account_id).first()
        if not account_row:
            raise ValueError(f"Unknown Collections account_id '{account_id}'")

        call_id = f"CALL-{uuid.uuid4().hex[:8].upper()}"
        call = CallHistory(
            id=call_id,
            account_id=account_id,
            timestamp=datetime.utcnow(),
            provider="recorded_sample",
            transcript=transcript,
            summary=evidence.get("summary", ""),
            sentiment=evidence.get("sentiment", "neutral"),
            stress_score=evidence.get("stress_score", 50),
            persona_before=account_data.get("persona", "unknown_insufficient_data"),
            persona_after=account_data.get("persona", "unknown_insufficient_data"),
            ptp_detected=bool(evidence.get("ptp_date")),
            ptp_date=evidence.get("ptp_date"),
            ptp_amount=evidence.get("ptp_amount"),
            life_event_detected=bool(evidence.get("life_event_detected")),
            life_event_type=evidence.get("life_event_type"),
            negotiation_signal=bool(evidence.get("negotiation_detected") or evidence.get("settlement_request")),
            objection_detected=bool(evidence.get("hostility_detected")),
            compliance_flags=evidence.get("compliance_flags", []),
        )
        db.add(call)
        db.flush()

        result = _run_async(get_orchestrator().execute_post_call(account_data, evidence, db, account_row))
        call.summary = result["call_outcome"]["summary"] or call.summary
        call.persona_after = result["persona_applied"]
        call.persona_shift = result["proposed_persona"] != call.persona_before
        call.next_action = result["recommended_action_code"]
        call.follow_up_actions = [result["recommended_action"]]
        call.trust_gate_status = result["_internal"]["trust_gate_status"]

        if result.get("review_case_id"):
            case = db.query(ReviewCase).filter(ReviewCase.id == result["review_case_id"]).first()
            if case:
                case.call_id = call_id
        for claim in db.query(Claim).filter(Claim.account_id == account_id, Claim.created_from_transcript_id.is_(None)).all():
            claim.created_from_transcript_id = call_id
        db.commit()
        return {**result, "call_id": call_id, "transcript_stored": True, "transcript_access": "restricted"}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def account_post_call_history(account_id: str) -> dict[str, Any]:
    """Return operational evidence without returning a raw customer transcript."""
    ensure_seeded()
    db = SessionLocal()
    try:
        if not db.query(LoanAccount).filter(LoanAccount.id == account_id).first():
            raise ValueError(f"Unknown Collections account_id '{account_id}'")
        calls = db.query(CallHistory).filter(CallHistory.account_id == account_id).order_by(CallHistory.timestamp.desc()).all()
        cases = db.query(ReviewCase).filter(ReviewCase.account_id == account_id).order_by(ReviewCase.created_at.desc()).all()
        scores = db.query(ScoreHistory).filter(ScoreHistory.account_id == account_id).order_by(ScoreHistory.timestamp.desc()).limit(10).all()
        audits = db.query(TrustAuditLog).filter(TrustAuditLog.account_id == account_id).order_by(TrustAuditLog.timestamp.desc()).limit(10).all()
        return {
            "account_id": account_id,
            "calls": [{"call_id": c.id, "timestamp": c.timestamp, "summary": c.summary, "sentiment": c.sentiment, "ptp_detected": c.ptp_detected, "ptp_date": c.ptp_date, "ptp_amount": c.ptp_amount, "life_event_detected": c.life_event_detected, "next_action": c.next_action, "transcript_access": "restricted"} for c in calls],
            "review_cases": [{"case_id": c.id, "call_id": c.call_id, "status": c.status, "case_type": c.case_type, "review_reason": c.review_reason, "proposed_persona": c.proposed_persona, "proposed_nba": c.proposed_nba, "created_at": c.created_at} for c in cases],
            "score_history": [{"timestamp": s.timestamp, "ability_to_pay": s.atp_score, "intent_to_pay": s.itp_score, "contactability": s.contactability_score, "self_cure": s.self_cure_score, "trust": s.trust_score, "trust_gate_status": s.trust_gate_status} for s in scores],
            "trust_audit": [{"timestamp": a.timestamp, "gate_status": a.gate_status, "final_persona": a.final_persona, "final_nba": a.final_nba, "pipeline_stage": a.pipeline_stage} for a in audits],
        }
    finally:
        db.close()


def _run_async(coro):
    """The FastAPI route is async, but this service keeps DB work synchronous."""
    import asyncio
    return asyncio.run(coro)
