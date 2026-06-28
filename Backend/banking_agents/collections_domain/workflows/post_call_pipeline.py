"""Post-call intelligence workflow.

KEY INVARIANT: This pipeline NEVER directly writes ai.persona.
Persona changes are proposed and stored as ReviewCase records.
Only the supervisor approval endpoint applies persona changes.
"""
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from banking_agents.collections_domain.db.models import AIProfile, Claim, ReviewCase, ScoreHistory, PTPHistory, TrustAuditLog
from banking_agents.collections_domain.services.intelligence.account_context import enrich_account_data
from banking_agents.collections_domain.services.intelligence.claim_manager import ClaimManager
from banking_agents.collections_domain.services.intelligence.pipeline import run_intelligence_pipeline
from banking_agents.collections_domain.services.intelligence.scoring_engine import scores_to_flat


# ── Business language persona labels ─────────────────────────────
_PERSONA_LABELS = {
    "forgetful_payer": "Forgetful Payer",
    "temporarily_distressed": "Temporarily Distressed",
    "genuinely_distressed": "Genuinely Distressed",
    "hostile_defaulter": "Hostile Defaulter",
    "reluctant_avoider": "Reluctant Avoider",
    "the_negotiator": "The Negotiator",
    "unknown_insufficient_data": "Unclassified",
}

# ── NBA → business action label ───────────────────────────────────
_NBA_LABELS = {
    "trigger_ots": "Initiate Settlement Discussion",
    "escalate_to_field": "Escalate to Field Recovery",
    "escalate_to_legal": "Refer to Legal Recovery",
    "request_verification": "Request Supporting Documentation",
    "suppress_all": "Pause Outreach — PTP Active",
    "follow_up": "Schedule Follow-up Call",
    "continue_monitoring": "Continue Monitoring",
    "trigger_restructure": "Initiate Restructuring Discussion",
}

# ── Trust gate → business status ─────────────────────────────────
_GATE_LABELS = {
    "ALLOW": "Approved",
    "REVIEW": "Requires Verification",
    "BLOCK": "Escalated",
}

# ── Personas that ALWAYS require review on classification change ──
_ALWAYS_REVIEW_PERSONAS = {
    "temporarily_distressed",
    "genuinely_distressed",
    "hostile_defaulter",
    "reluctant_avoider",
    "the_negotiator",
}


class PostCallPipeline:
    """
    Evidence → Resolve PTPs → Claims → Scores → Trust → Persona → Policy → Case Decision → Persist

    Never writes ai.persona directly.
    Creates ReviewCase when a change requires human approval.
    """

    def __init__(self):
        self.claim_manager = ClaimManager()

    # ── Public entry point ─────────────────────────────────────────

    async def run(
        self,
        account_data: Dict[str, Any],
        call_evidence: Dict[str, Any],
        db: Optional[Session] = None,
        account_row=None,
        persist: bool = True,
    ) -> Dict[str, Any]:

        # 1. Resolve expired PTPs before enriching
        if db and account_row and persist:
            self._resolve_expired_ptps(db, account_row)

        enriched = enrich_account_data(account_data, db, account_row)

        # 2. Process new claims (contradiction engine)
        new_claims = self._extract_claims(call_evidence)
        existing_claims = enriched.get("claims", [])

        for claim in new_claims:
            processed = self.claim_manager.process_new_claim(claim, existing_claims)
            contradictions = processed.pop("new_contradictions_found", [])

            if db and account_row and persist:
                for contra in contradictions:
                    old_id = contra.get("old_claim_id")
                    if old_id:
                        old_claim = db.query(Claim).filter(Claim.id == old_id).first()
                        if old_claim:
                            old_claim.verification_state = "CONTRADICTED"
                            old_claim.contradicted_flag = True
                            old_claim.contradiction_reason = contra.get("reason")

            enriched.setdefault("claims", []).append(processed)

            if db and account_row and persist:
                db.add(Claim(
                    id=processed["id"],
                    account_id=account_row.id,
                    claim_type=processed.get("claim_type", "hardship"),
                    claim_details=processed.get("claim_details", ""),
                    verification_state=processed.get("verification_state", "CLAIMED"),
                    claim_confidence=processed.get("claim_confidence", 0.5),
                    source_quote=call_evidence.get("life_event_details", ""),
                    timestamp=datetime.utcnow(),
                ))

        if call_evidence.get("ptp_date"):
            enriched.setdefault("ptp_history", []).append(
                {"status": "PENDING", "ptp_date": call_evidence["ptp_date"]}
            )

        # 3. Run pipeline (scores → trust → persona → policy)
        # Pass new_claims so trust gate can enforce life-event handling rules
        result = run_intelligence_pipeline(
            enriched,
            current_persona=enriched.get("persona"),
            new_claims=new_claims,
        )

        policy = result["policy"]
        persona = result["persona"]
        trust_gate = result["trust_gate"]

        proposed_persona = persona.get("dominant_persona", persona.get("segment"))
        current_persona = enriched.get("persona", "unknown")
        approved_persona = policy.get("policy_approved_persona", current_persona)

        nba_hint = policy.get("policy_nba_routing")
        nba_action = self._route_to_action(nba_hint, approved_persona)

        # 4. Decide: auto-commit or create review case
        review_required, review_triggers = self._should_create_review_case(
            current_persona=current_persona,
            proposed_persona=proposed_persona,
            call_evidence=call_evidence,
            new_claims=new_claims,
            policy=policy,
            trust_gate=trust_gate,
        )

        review_case_id: Optional[str] = None

        if db and account_row and persist:
            review_case_id = self._persist_results(
                db=db,
                account_row=account_row,
                result=result,
                current_persona=current_persona,
                proposed_persona=proposed_persona,
                approved_persona=approved_persona,
                policy=policy,
                trust_gate=trust_gate,
                nba_action=nba_action,
                call_evidence=call_evidence,
                new_claims=new_claims,
                review_required=review_required,
                review_triggers=review_triggers,
            )

        # 5. Build business-language post-call summary (no internals)
        business_assessment = self._generate_business_assessment(
            current_persona=current_persona,
            proposed_persona=proposed_persona,
            call_evidence=call_evidence,
            new_claims=new_claims,
            review_required=review_required,
            review_triggers=review_triggers,
            policy=policy,
            trust_gate=trust_gate,
        )

        return {
            # Call outcome (business language only)
            "call_outcome": {
                "sentiment": call_evidence.get("sentiment", "neutral"),
                "ptp_detected": bool(call_evidence.get("ptp_date")),
                "ptp_date": call_evidence.get("ptp_date"),
                "ptp_amount": call_evidence.get("ptp_amount"),
                "claims_extracted": len(new_claims),
                "summary": call_evidence.get("summary", ""),
            },
            # Business assessment
            "business_assessment": business_assessment,
            # Review workflow
            "review_required": review_required,
            "review_case_id": review_case_id,
            "review_triggers": review_triggers,
            # Recommended action (business label)
            "recommended_action": _NBA_LABELS.get(nba_action, "Schedule Follow-up Call"),
            "recommended_action_code": nba_action,
            # Classification
            "current_persona": current_persona,
            "current_persona_label": _PERSONA_LABELS.get(current_persona, current_persona),
            "proposed_persona": proposed_persona if review_required else approved_persona,
            "proposed_persona_label": _PERSONA_LABELS.get(proposed_persona, proposed_persona),
            "persona_applied": approved_persona if not review_required else current_persona,
            # Internal (kept for backend use, not surfaced to business users)
            "_internal": {
                "nba_action": nba_action,
                "trust_gate_status": _GATE_LABELS.get(trust_gate.get("trust_gate_status", ""), ""),
                "claims_created": new_claims,
            },
        }

    # ── Review case trigger logic ──────────────────────────────────

    def _should_create_review_case(
        self,
        current_persona: str,
        proposed_persona: str,
        call_evidence: Dict[str, Any],
        new_claims: List[Dict[str, Any]],
        policy: Dict[str, Any],
        trust_gate: Dict[str, Any],
    ) -> Tuple[bool, List[str]]:
        """
        Returns (review_required, list_of_trigger_reasons).
        Auto-commit ONLY when: no claims, no hardship, no persona change,
        no trust review, no settlement/waiver/escalation.
        """
        triggers = []

        # 1. Persona classification change
        persona_changed = (
            proposed_persona
            and proposed_persona != current_persona
            and proposed_persona != "unknown_insufficient_data"
        )
        if persona_changed:
            from_label = _PERSONA_LABELS.get(current_persona, current_persona)
            to_label = _PERSONA_LABELS.get(proposed_persona, proposed_persona)
            triggers.append(f"Classification change proposed: {from_label} → {to_label}")

        # 2. Any new unverified claims
        if new_claims:
            claim_types = ", ".join(c.get("claim_type", "hardship") for c in new_claims)
            triggers.append(f"Unverified claim detected: {claim_types}")

        # 3. Hardship / life event discussed
        if call_evidence.get("life_event_detected"):
            triggers.append(f"Hardship disclosed: {call_evidence.get('life_event_type', 'financial hardship')}")

        # 4. Contradiction detected
        if call_evidence.get("contradiction_detected"):
            triggers.append("Contradictory statement detected")

        # 5. Settlement or waiver request
        if call_evidence.get("negotiation_detected") or call_evidence.get("settlement_request"):
            triggers.append("Settlement or restructuring request raised by customer")

        # 6. Policy escalation
        if policy.get("policy_escalate"):
            triggers.append("Account flagged for escalation by policy engine")

        # 7. Trust review state
        gate_status = trust_gate.get("trust_gate_status", "ALLOW")
        if gate_status in ("REVIEW", "BLOCK"):
            triggers.append(f"Verification required: {_GATE_LABELS.get(gate_status, gate_status)}")

        # 8. Proposed persona in sensitive group even without explicit change
        if proposed_persona in _ALWAYS_REVIEW_PERSONAS and persona_changed:
            if f"Classification change proposed" not in " ".join(triggers):
                triggers.append(f"Sensitive classification: {_PERSONA_LABELS.get(proposed_persona, proposed_persona)}")

        return len(triggers) > 0, triggers

    # ── Business language assessment ───────────────────────────────

    def _generate_business_assessment(
        self,
        current_persona: str,
        proposed_persona: str,
        call_evidence: Dict[str, Any],
        new_claims: List[Dict[str, Any]],
        review_required: bool,
        review_triggers: List[str],
        policy: Dict[str, Any],
        trust_gate: Dict[str, Any],
    ) -> str:
        """Generates a natural-language business assessment paragraph. No internal signals."""
        lines = []
        sentiment = call_evidence.get("sentiment", "neutral")
        current_label = _PERSONA_LABELS.get(current_persona, current_persona)
        proposed_label = _PERSONA_LABELS.get(proposed_persona, proposed_persona) if proposed_persona else None

        # Sentiment context
        if sentiment in ("positive", "cooperative"):
            lines.append("Customer was cooperative during the interaction.")
        elif sentiment in ("negative", "hostile"):
            lines.append("Customer exhibited resistance during the interaction.")
        elif sentiment == "neutral":
            lines.append("Customer maintained a neutral tone throughout the interaction.")

        # PTP
        if call_evidence.get("ptp_date"):
            lines.append(f"A commitment to pay was secured for {call_evidence.get('ptp_date')}.")

        # Claims / hardship
        if new_claims or call_evidence.get("life_event_detected"):
            event = call_evidence.get("life_event_type", "hardship")
            lines.append(
                f"Customer disclosed a {event.replace('_', ' ')} during the call. "
                "This claim has not yet been verified and requires documentation before any classification change is applied."
            )

        # Settlement
        if call_evidence.get("negotiation_detected"):
            lines.append("Customer raised a request for settlement or restructuring. This requires supervisor review.")

        # Classification change
        if proposed_label and proposed_label != current_label:
            if review_required:
                lines.append(
                    f"Based on the interaction, a reclassification from {current_label} to {proposed_label} has been proposed. "
                    "This change has been placed under review and requires supervisor approval before it is applied."
                )
            else:
                lines.append(
                    f"Customer profile has been updated to {proposed_label} based on interaction evidence."
                )
        elif not review_required:
            lines.append(f"No classification change required. Account remains as {current_label}.")

        # Review summary
        if review_required:
            lines.append(
                "A review case has been created. No changes will be applied until a supervisor reviews and approves this case."
            )

        return " ".join(lines) if lines else "Interaction completed. No significant changes detected."

    # ── Persist results ────────────────────────────────────────────

    def _persist_results(
        self,
        db: Session,
        account_row,
        result: Dict[str, Any],
        current_persona: str,
        proposed_persona: str,
        approved_persona: str,
        policy: Dict[str, Any],
        trust_gate: Dict[str, Any],
        nba_action: str,
        call_evidence: Dict[str, Any],
        new_claims: List[Dict[str, Any]],
        review_required: bool,
        review_triggers: List[str],
    ) -> Optional[str]:
        """
        Persists scores, NBA, and audit logs.
        NEVER writes ai.persona — that only happens via ReviewCase approval.
        Returns review_case_id if one was created, else None.
        """
        scores = result["scores"]
        flat = scores_to_flat(scores)
        persona = result["persona"]

        ai: Optional[AIProfile] = account_row.ai_profile
        if not ai:
            ai = AIProfile(
                id=f"AIP-{uuid.uuid4().hex[:8].upper()}",
                account_id=account_row.id,
            )
            db.add(ai)

        # ── DO NOT write ai.persona here — only supervisor approval does this ──
        # Store pending persona for reference only
        if review_required:
            ai.pending_persona = proposed_persona
        else:
            # Safe auto-commit: no review triggers → apply immediately
            ai.persona = approved_persona
            ai.pending_persona = None

        ai.persona_confidence = persona.get("confidence", 0.0)
        ai.trust_score = flat["trust"]
        ai.atp_score = flat["ability_to_pay"]
        ai.itp_score = flat["intent_to_pay"]
        ai.contactability_score = flat["contactability"]
        ai.scores = flat
        ai.next_action = nba_action

        # A newly captured promise must become part of the persisted account
        # history.  Previously it influenced only this in-memory scoring run.
        ptp_date = self._parse_ptp_date(call_evidence.get("ptp_date"))
        if ptp_date:
            db.add(PTPHistory(
                id=f"PTP-{uuid.uuid4().hex[:8].upper()}",
                account_id=account_row.id,
                ptp_date=ptp_date,
                ptp_amount=call_evidence.get("ptp_amount") or 0,
                status="PENDING",
                timestamp=datetime.utcnow(),
            ))

        if policy.get("policy_escalate"):
            account_row.investigation_flag = True

        # Score history (internal — never surfaced to business users)
        db.add(ScoreHistory(
            id=f"SCR-{uuid.uuid4().hex[:8].upper()}",
            account_id=account_row.id,
            timestamp=datetime.utcnow(),
            atp_score=flat["ability_to_pay"],
            atp_confidence=scores["ability_to_pay"].get("confidence", 0.5),
            atp_reasons=scores["ability_to_pay"].get("reasons", []),
            itp_score=flat["intent_to_pay"],
            itp_confidence=scores["intent_to_pay"].get("confidence", 0.5),
            itp_reasons=scores["intent_to_pay"].get("reasons", []),
            contactability_score=flat["contactability"],
            contactability_confidence=scores["contactability"].get("confidence", 0.5),
            contactability_reasons=scores["contactability"].get("reasons", []),
            self_cure_score=flat["self_cure"],
            self_cure_confidence=scores["self_cure"].get("confidence", 0.5),
            self_cure_reasons=scores["self_cure"].get("reasons", []),
            trust_score=flat["trust"],
            trust_confidence=scores["trust"].get("confidence", 0.5),
            trust_reasons=scores["trust"].get("reasons", []),
            trust_gate_status=trust_gate.get("trust_gate_status"),
            model_version=scores["trust"].get("model_version", "v2.0"),
        ))

        # Trust audit log (internal)
        db.add(TrustAuditLog(
            id=f"TAL-{uuid.uuid4().hex[:8].upper()}",
            account_id=account_row.id,
            timestamp=datetime.utcnow(),
            requested_persona=proposed_persona,
            final_persona=approved_persona if not review_required else current_persona,
            requested_nba=policy.get("policy_nba_routing"),
            final_nba=policy.get("policy_nba_routing"),
            gate_status=trust_gate.get("trust_gate_status"),
            reasons=trust_gate.get("reasons", []),
            trust_score=flat["trust"],
            trust_confidence=scores["trust"].get("confidence", 0.5),
            gate_version=trust_gate.get("gate_version", "v2.0"),
            model_version=scores["trust"].get("model_version", "v2.0"),
            pipeline_stage="POST_CALL",
        ))

        db.commit()

        # Create review case if required
        if review_required:
            return self._create_review_case(
                db=db,
                account_row=account_row,
                current_persona=current_persona,
                proposed_persona=proposed_persona,
                nba_action=nba_action,
                call_evidence=call_evidence,
                new_claims=new_claims,
                review_triggers=review_triggers,
                policy=policy,
            )

        return None

    def _create_review_case(
        self,
        db: Session,
        account_row,
        current_persona: str,
        proposed_persona: str,
        nba_action: str,
        call_evidence: Dict[str, Any],
        new_claims: List[Dict[str, Any]],
        review_triggers: List[str],
        policy: Dict[str, Any],
    ) -> str:
        """Creates a ReviewCase record. Returns the case ID."""
        # Determine case type from triggers
        case_type = self._determine_case_type(call_evidence, new_claims, policy, current_persona, proposed_persona)

        # Build business-language review reason
        review_reason = "; ".join(review_triggers) if review_triggers else "Supervisor review required."

        # Build audit timeline seed
        now = datetime.utcnow()
        audit_timeline = [
            {
                "timestamp": now.isoformat(),
                "event": "Case Created",
                "detail": "Post-call pipeline created this review case.",
                "actor": "System",
            }
        ]
        for trigger in review_triggers:
            audit_timeline.append({
                "timestamp": now.isoformat(),
                "event": "Review Trigger",
                "detail": trigger,
                "actor": "System",
            })

        case_id = f"CASE-{uuid.uuid4().hex[:8].upper()}"

        current_nba = account_row.ai_profile.next_action if account_row.ai_profile else None

        review_case = ReviewCase(
            id=case_id,
            account_id=account_row.id,
            status="OPEN",
            case_type=case_type,
            current_persona=current_persona,
            proposed_persona=proposed_persona,
            current_nba=current_nba,
            proposed_nba=nba_action,
            review_reason=review_reason,
            claims_extracted=[
                {
                    "claim_type": c.get("claim_type", "hardship"),
                    "claim_details": c.get("claim_details", ""),
                    "verification_state": c.get("verification_state", "CLAIMED"),
                    "source_quote": call_evidence.get("life_event_details", ""),
                    "evidence_required": self._evidence_required_for(c.get("claim_type", "hardship")),
                }
                for c in new_claims
            ],
            ptp_extracted={
                "detected": bool(call_evidence.get("ptp_date")),
                "date": call_evidence.get("ptp_date"),
                "amount": call_evidence.get("ptp_amount"),
            },
            sentiment=call_evidence.get("sentiment", "neutral"),
            objections_extracted=self._extract_objections(call_evidence),
            call_summary=call_evidence.get("summary", ""),
            audit_timeline=audit_timeline,
            created_at=now,
        )

        db.add(review_case)
        db.commit()
        return case_id

    def _determine_case_type(
        self,
        call_evidence: Dict[str, Any],
        new_claims: List[Dict[str, Any]],
        policy: Dict[str, Any],
        current_persona: str,
        proposed_persona: str,
    ) -> str:
        if policy.get("policy_escalate"):
            return "ESCALATION"
        if call_evidence.get("negotiation_detected") or call_evidence.get("settlement_request"):
            return "SETTLEMENT"
        if new_claims or call_evidence.get("life_event_detected"):
            return "UNVERIFIED_CLAIM"
        if proposed_persona and proposed_persona != current_persona:
            return "CLASSIFICATION_CHANGE"
        return "CLASSIFICATION_CHANGE"

    def _evidence_required_for(self, claim_type: str) -> str:
        return {
            "medical": "Medical certificate, hospital discharge summary, or doctor's letter",
            "job_loss": "Termination letter, payslip gap evidence, or HR communication",
            "business_loss": "Business closure documentation or financial statements",
            "hardship": "Supporting documentation describing the financial hardship",
            "natural_disaster": "Government or insurance documentation",
        }.get(claim_type, "Supporting documentation required")

    # ── Helpers ───────────────────────────────────────────────────

    def _resolve_expired_ptps(self, db: Session, account_row) -> None:
        now = datetime.utcnow()
        for ptp in db.query(PTPHistory).filter(
            PTPHistory.account_id == account_row.id,
            PTPHistory.status == "PENDING"
        ).all():
            if ptp.ptp_date and ptp.ptp_date < now:
                ptp.status = "BROKEN"
        db.commit()

    @staticmethod
    def _parse_ptp_date(value: Any) -> Optional[datetime]:
        """Accept ISO dates from the demo API; ignore non-actionable text."""
        if isinstance(value, datetime):
            return value
        if not isinstance(value, str) or not value.strip():
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            return None

    def _extract_claims(self, evidence: Dict[str, Any]) -> List[Dict[str, Any]]:
        claims = []
        if evidence.get("life_event_detected"):
            claims.append({
                "claim_type": evidence.get("life_event_type", "hardship"),
                "claim_details": evidence.get("life_event_details", evidence.get("summary", "")),
                "confidence": evidence.get("life_event_confidence", 0.6),
            })
        return claims

    def _extract_objections(self, evidence: Dict[str, Any]) -> List[str]:
        objections = []
        if evidence.get("hostility_detected"):
            objections.append("Customer expressed refusal or objection to repayment")
        if evidence.get("negotiation_detected"):
            objections.append("Customer requested settlement or discount")
        return objections

    def _route_to_action(self, routing: Optional[str], persona: str) -> str:
        mapping = {
            "escalate_to_legal": "escalate_to_legal",
            "escalate_to_field": "escalate_to_field",
            "establish_contact": "continue_monitoring",
            "offer_restructure": "trigger_restructure",
            "send_payment_link": "suppress_all",
            "trigger_ots": "trigger_ots",
            "request_verification": "request_verification",
        }
        return mapping.get(routing or "", "follow_up")

