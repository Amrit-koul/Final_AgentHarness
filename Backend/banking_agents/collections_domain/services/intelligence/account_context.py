"""Build enriched account context for intelligence engines."""
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from banking_agents.collections_domain.db.models import Claim, Interaction, LoanAccount, PTPHistory


def _interaction_text(ix: Interaction) -> str:
    return (ix.message or ix.summary or ix.transcript or "").strip()


def enrich_account_data(
    account_data: Dict[str, Any],
    db: Optional[Session] = None,
    account_row: Optional[LoanAccount] = None,
) -> Dict[str, Any]:
    """Attach interactions, PTP history, and claims needed by scoring engines."""
    enriched = dict(account_data)

    if db and account_row:
        interactions = [
            _interaction_text(ix)
            for ix in db.query(Interaction)
            .filter(Interaction.account_id == account_row.id)
            .all()
            if _interaction_text(ix)
        ]
        enriched["interactions"] = interactions
        enriched["interaction_count"] = len(interactions)

        ptp_rows = (
            db.query(PTPHistory)
            .filter(PTPHistory.account_id == account_row.id)
            .all()
        )
        enriched["ptp_history"] = [
            {"status": row.status, "ptp_date": row.ptp_date, "ptp_amount": row.ptp_amount}
            for row in ptp_rows
        ]

        claim_rows = (
            db.query(Claim).filter(Claim.account_id == account_row.id).all()
        )
        enriched["claims"] = [
            {
                "claim_type": row.claim_type,
                "verification_state": row.verification_state,
                "claim_confidence": row.claim_confidence,
            }
            for row in claim_rows
        ]
    else:
        enriched.setdefault("interactions", account_data.get("interactions", []))
        enriched.setdefault("interaction_count", len(enriched["interactions"]))
        enriched.setdefault("ptp_history", account_data.get("ptp_history", []))
        enriched.setdefault("claims", account_data.get("claims", []))

    enriched.setdefault("job", account_data.get("job", ""))
    enriched.setdefault("status", account_data.get("status", ""))
    return enriched


