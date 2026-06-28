"""
Transcript Extraction Service
Server-side extraction of structured evidence from raw call transcript text.

The frontend should send only the transcript text.
This service uses ConversationIntelligenceAgent (LLM-backed) to extract:
  - intent (PTP, hardship, dispute, settlement...)
  - sentiment / stress_score
  - life_event_detected + type + details
  - ptp_date / ptp_amount (from key_entities)
  - negotiation_detected, hostile_signal
  - compliance_flags
  - persona_shift_recommended

Falls back to keyword analysis when LLM is unavailable or times out.
Response always includes extraction_method and evidence_source so callers
can render the right label to users and auditors.
"""
from __future__ import annotations

import asyncio
import os
import re
from typing import Any, Dict, Optional

from banking_agents.collections_domain.agents.conversation_intelligence import (
    ConversationIntelligenceAgent,
)


def _llm_error_type(exc: Exception) -> str:
    name = exc.__class__.__name__.lower()
    message = str(exc).lower()
    if "timeout" in name or "timeout" in message:
        return "timeout"
    if "api_key" in message or "not configured" in message or "unauthorized" in message:
        return "configuration"
    if "json" in name or "parse" in message or "schema" in message:
        return "invalid_response"
    return exc.__class__.__name__

# Keyword sets for fallback extraction
_HARDSHIP_KW = {
    "hospital", "surgery", "medical", "accident", "job loss", "laid off",
    "fired", "unemployed", "icu", "critical", "passed away", "death",
    "family emergency", "lost my job", "income stopped", "no salary",
    "business closed", "flood", "natural disaster", "cancer", "treatment",
}
_HOSTILE_KW = {
    "won't pay", "wont pay", "never pay", "refuse", "harassment", "stop calling",
    "police", "lawyer", "court", "legal action", "complaint", "consumer forum",
    "don't call", "dont call", "lodging complaint",
}
_NEGOTIATION_KW = {
    "settlement", "ots", "one time settlement", "discount", "settle",
    "waiver", "reduce", "negotiate", "offer", "concession",
}
_PTP_KW = {
    "will pay", "i'll pay", "i will pay", "paying on", "pay on", "pay by",
    "tomorrow", "next week", "this week", "end of month", "month end",
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    "next month", "30th", "31st", "salary", "salary day", "payday",
}
_PTP_DATE_PATTERNS = [
    re.compile(r"\b(\d{1,2}(?:st|nd|rd|th)?\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*)\b", re.I),
    re.compile(r"\b((?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\s+\d{1,2}(?:st|nd|rd|th)?)\b", re.I),
    re.compile(r"\b(\d{1,2}[\/\-]\d{1,2}(?:[\/\-]\d{2,4})?)\b"),
    re.compile(r"\b(end of (?:this |next )?month|month end|salary day|payday|next (?:monday|tuesday|wednesday|thursday|friday))\b", re.I),
    re.compile(r"\b(tomorrow)\b", re.I),
    re.compile(r"\b(next week)\b", re.I),
    re.compile(r"\b(\d{4}-\d{2}-\d{2})\b"),
]
_AMOUNT_PATTERN = re.compile(r"(?:rs\.?|inr|rupees?)\s*(\d[\d,]*)", re.I)


def _keyword_extract(transcript: str, current_persona: str) -> Dict[str, Any]:
    """Keyword-based fallback extraction when LLM is unavailable."""
    text = transcript.lower()

    has_hardship = any(kw in text for kw in _HARDSHIP_KW)
    has_hostile = any(kw in text for kw in _HOSTILE_KW)
    has_negotiation = any(kw in text for kw in _NEGOTIATION_KW)
    has_ptp = any(kw in text for kw in _PTP_KW)

    # Sentiment / stress
    if has_hostile:
        sentiment = "Hostile"
        stress_score = 85
        intent = "Objection / Refusal"
    elif has_hardship:
        sentiment = "Distressed"
        stress_score = 78
        intent = "Hardship Disclosure"
    elif has_negotiation:
        sentiment = "Negotiating"
        stress_score = 45
        intent = "Settlement Request"
    elif has_ptp:
        sentiment = "Cooperative"
        stress_score = 30
        intent = "Promise to Pay"
    else:
        sentiment = "Neutral"
        stress_score = 40
        intent = "General Response"

    # Life event detection
    life_event_type = None
    if has_hardship:
        if any(kw in text for kw in {"hospital", "surgery", "medical", "icu", "treatment", "cancer"}):
            life_event_type = "medical"
        elif any(kw in text for kw in {"job loss", "laid off", "fired", "unemployed", "lost my job", "no salary"}):
            life_event_type = "job_loss"
        elif any(kw in text for kw in {"death", "passed away", "family emergency"}):
            life_event_type = "family_emergency"
        elif any(kw in text for kw in {"business closed", "business loss"}):
            life_event_type = "business_loss"
        else:
            life_event_type = "hardship"

    # PTP date extraction
    ptp_date = None
    for pattern in _PTP_DATE_PATTERNS:
        m = pattern.search(transcript)
        if m:
            ptp_date = m.group(1)
            break

    # PTP amount extraction
    ptp_amount = None
    amt_match = _AMOUNT_PATTERN.search(transcript)
    if amt_match:
        try:
            ptp_amount = float(amt_match.group(1).replace(",", ""))
        except ValueError:
            pass

    # Suggested persona shift
    suggested_shift = None
    if has_hostile and current_persona != "hostile_defaulter":
        suggested_shift = "hostile_defaulter"
    elif has_negotiation and current_persona != "the_negotiator":
        suggested_shift = "the_negotiator"
    elif has_hardship and current_persona not in ("temporarily_distressed", "genuinely_distressed"):
        suggested_shift = "temporarily_distressed"

    return {
        "intent": intent,
        "sentiment": sentiment,
        "stress_score": stress_score,
        "life_event_detected": has_hardship,
        "life_event_type": life_event_type,
        "life_event_details": None,
        "ptp_signal": has_ptp,
        "ptp_date": ptp_date,
        "ptp_amount": ptp_amount,
        "ptp_confidence": 0.6 if ptp_date else 0.0,
        "negotiation_signal": has_negotiation,
        "hostile_signal": has_hostile,
        "compliance_flags": [],
        "persona_shift_recommended": suggested_shift is not None,
        "recommended_persona": suggested_shift,
        "shift_confidence": 0.65,
        "agent_guidance": _build_guidance(intent, has_hardship, has_hostile, has_ptp),
        "extraction_method": "keyword_fallback",
        "evidence_source": "keyword_fallback",
        "confidence": 0.60,
    }


def _build_guidance(intent: str, hardship: bool, hostile: bool, ptp: bool) -> str:
    if hostile:
        return "Customer is showing hostility. Document interaction, do not escalate pressure. Refer to supervisor."
    if hardship:
        return "Customer has disclosed a hardship event. Pause collection pressure, verify claim, consider restructure."
    if ptp:
        return "Customer has offered a payment commitment. Confirm date, update records, suppress outreach until PTP date."
    if intent == "Settlement Request":
        return "Customer is open to negotiation. Do not commit to waiver — refer to settlements team."
    return "No strong signal detected. Follow up with standard outreach."


def _llm_result_to_extraction(llm_data: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize ConversationIntelligenceAgent output to our extraction schema."""
    entities = llm_data.get("key_entities", {})
    if isinstance(entities, dict):
        ptp_date = entities.get("ptp_date") or entities.get("date")
        ptp_amount = entities.get("ptp_amount") or entities.get("amount")
    else:
        ptp_date, ptp_amount = None, None

    return {
        "intent": llm_data.get("intent", "general_response"),
        "sentiment": llm_data.get("sentiment", "neutral"),
        "stress_score": llm_data.get("stress_score", 50),
        "life_event_detected": bool(llm_data.get("life_event_detected", False)),
        "life_event_type": llm_data.get("life_event_type"),
        "life_event_details": llm_data.get("life_event_details"),
        "ptp_signal": bool(llm_data.get("ptp_signal", False)),
        "ptp_date": ptp_date,
        "ptp_amount": float(ptp_amount) if ptp_amount else None,
        "ptp_confidence": llm_data.get("shift_confidence", 0.0) if llm_data.get("ptp_signal") else 0.0,
        "negotiation_signal": bool(llm_data.get("negotiation_signal", False)),
        "hostile_signal": bool(llm_data.get("hostile_signal", False)),
        "compliance_flags": llm_data.get("compliance_flags", []),
        "persona_shift_recommended": bool(llm_data.get("persona_shift_recommended", False)),
        "recommended_persona": llm_data.get("recommended_persona"),
        "shift_confidence": llm_data.get("shift_confidence", 0.0),
        "agent_guidance": llm_data.get("agent_guidance", ""),
        "extraction_method": "llm",
        "evidence_source": "llm_extraction",
        "confidence": llm_data.get("confidence", 0.85),
        "raw_llm_output": llm_data.get("raw_llm_output"),
    }


async def extract_async(
    transcript: str,
    account_data: Dict[str, Any],
    conversation_history: Optional[list] = None,
) -> Dict[str, Any]:
    """
    Extract evidence from transcript using LLM, falling back to keyword analysis.

    This is the authoritative server-side extraction — the frontend must NOT send
    pre-extracted fields such as sentiment, ptp_date, life_event_detected, etc.

    Args:
        transcript: Raw call transcript text
        account_data: Account dict (needs .get('persona'), .get('dpd'), etc.)
        conversation_history: Optional list of prior conversation turns

    Returns:
        Extraction dict with extraction_method indicating 'llm' or 'keyword_fallback'
    """
    if not transcript or not transcript.strip():
        return {
            "intent": "no_transcript",
            "sentiment": "unknown",
            "stress_score": 0,
            "life_event_detected": False,
            "life_event_type": None,
            "ptp_signal": False,
            "ptp_date": None,
            "ptp_amount": None,
            "negotiation_signal": False,
            "hostile_signal": False,
            "compliance_flags": [],
            "persona_shift_recommended": False,
            "recommended_persona": None,
            "extraction_method": "no_transcript",
            "evidence_source": "none",
            "confidence": 0.0,
        }

    current_persona = account_data.get("persona", "unknown")

    if not os.getenv("GROQ_API_KEY", "").strip():
        result = _keyword_extract(transcript, current_persona)
        result["fallback_reason"] = "llm_not_configured"
        return result

    try:
        agent = ConversationIntelligenceAgent()
        context = {
            "transcript": transcript,
            "conversation_history": conversation_history or [],
        }
        decision = await agent.reason(account_data, context)
        if decision.action == "no_conversation" or decision.data.get("error"):
            raise ValueError("Agent returned no_conversation")
        return _llm_result_to_extraction(decision.data)

    except Exception as exc:  # noqa: BLE001
        # Label fallback explicitly — never hide it
        result = _keyword_extract(transcript, current_persona)
        result["llm_error"] = str(exc)
        result["llm_error_type"] = _llm_error_type(exc)
        result["fallback_reason"] = "llm_failed"
        return result


def extract(
    transcript: str,
    account_data: Dict[str, Any],
    conversation_history: Optional[list] = None,
) -> Dict[str, Any]:
    """Synchronous wrapper around extract_async for non-async call sites."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # We're inside an async context (FastAPI) — schedule as task
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, extract_async(transcript, account_data, conversation_history))
                return future.result(timeout=30)
        else:
            return loop.run_until_complete(extract_async(transcript, account_data, conversation_history))
    except Exception as exc:  # noqa: BLE001
        result = _keyword_extract(transcript, account_data.get("persona", "unknown"))
        result["llm_error"] = str(exc)
        result["llm_error_type"] = _llm_error_type(exc)
        result["fallback_reason"] = "llm_failed"
        return result
