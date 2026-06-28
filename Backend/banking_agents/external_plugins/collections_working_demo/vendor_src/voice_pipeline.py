"""
Voice Pipeline — migrated from CollectionAgent-trust-layer.

Free-first voice pipeline: Groq Whisper STT → LLaMA Chat → Orpheus TTS.
Falls back to template + labelled-fallback when Groq is unavailable.

Architecture (LangGraph, parallel Brain A/B):
  START → stt → llm + intel (parallel) → tts → END
                └→ intelligence →┘

Brain A: Conversational dialogue (LLaMA 3.1 8B)
Brain B: ConversationIntelligenceAgent — scans for signals while A is reasoning

This module uses banking_agents.collections_domain.* (already ported)
rather than duplicating agents.
"""
from __future__ import annotations

import base64
import os
import tempfile
from typing import Any, Dict, List, Optional, TypedDict

import httpx
from langgraph.graph import END, START, StateGraph

from banking_agents.collections_domain.agents.conversation_intelligence import (
    ConversationIntelligenceAgent,
)

GROQ_BASE = "https://api.groq.com/openai/v1"
WHISPER_MODEL = "whisper-large-v3-turbo"
LLM_MODEL = "llama-3.1-8b-instant"
TTS_MODEL = "canopylabs/orpheus-v1-english"
TTS_VOICE = "hannah"
TTS_MAX_CHARS = 200

PERSONA_TONE = {
    "forgetful_payer": "warm and friendly — customer usually pays on time; secure a specific payment date.",
    "temporarily_distressed": "deeply empathetic — listen first, acknowledge hardship, then explore realistic options.",
    "genuinely_distressed": "patient and supportive — focus on understanding situation before any payment ask.",
    "hostile_defaulter": "firm, professional, factual — no threats; document responses calmly.",
    "reluctant_avoider": "clear and respectful — state importance of contact; offer simple next step.",
    "the_negotiator": "neutral and deal-focused — acknowledge willingness to settle within policy.",
}

PERSONA_LABEL = {
    "forgetful_payer": "Forgetful Payer",
    "temporarily_distressed": "Temporarily Distressed",
    "genuinely_distressed": "Genuinely Distressed",
    "hostile_defaulter": "Hostile Defaulter",
    "reluctant_avoider": "Reluctant Avoider",
    "the_negotiator": "The Negotiator",
}


def groq_configured() -> bool:
    return bool(os.getenv("GROQ_API_KEY", "").strip())


def build_voice_prompt(acc: dict) -> str:
    persona = acc.get("pending_persona") or acc.get("persona", "forgetful_payer")
    name = acc.get("name", "Customer")
    first = name.split()[0] if name else "Customer"
    emi = acc.get("emi", 0)
    dpd = acc.get("dpd", 0)
    product = acc.get("product", "Personal Loan")
    outstanding = acc.get("outstanding", 0)
    scores = acc.get("scores") or {}
    atp = scores.get("ability_to_pay", "—")
    itp = scores.get("intent_to_pay", "—")
    next_action = (acc.get("next_action") or "follow_up").replace("_", " ")
    tone = PERSONA_TONE.get(persona, PERSONA_TONE["forgetful_payer"])
    label = PERSONA_LABEL.get(persona, persona.replace("_", " ").title())

    return f"""You are ARIA, an AI collections voice assistant for the bank. You are on a live phone call with {name}.

Account context (use naturally, do not read as a list):
- Product: {product}
- EMI due: {emi:,}
- Days past due (DPD): {dpd}
- Outstanding: {outstanding:,}
- Persona: {label}
- Ability to pay score: {atp} | Intent to pay score: {itp}
- Recommended next action from NBA engine: {next_action}

Tone for this borrower: {tone}

Call structure:
1. Open — confirm identity, state purpose briefly, be respectful.
2. Probe — listen for payment commitment, hardship, objection, or negotiation.
3. Close — confirm any promise date, or empathetic next step if hardship is disclosed.

RULES (mandatory):
- Speak ONLY in clear, professional English (no Hindi, no Hinglish).
- Maximum 2 short sentences per reply — this is voice, not email.
- Never mention legal action, court, police, or SARFAESI.
- Never use coercive or threatening language.
- If the customer mentions hospital, job loss, family emergency, or financial crisis — pause collection talk, express empathy, ask how you can help.
- If they give a payment date — confirm it warmly and say outreach will pause until then.
- Address the customer as {first} when appropriate.
"""


def template_greeting(acc: dict) -> str:
    """English opening when Groq LLM is unavailable."""
    first = (acc.get("name") or "there").split()[0]
    emi = acc.get("emi", 0)
    product = acc.get("product", "loan")
    dpd = acc.get("dpd", 0)
    prev = acc.get("previous_contact", False)
    if dpd <= 0:
        reason = f"your upcoming EMI of {emi:,} on your {product}"
    else:
        reason = f"your EMI of {emi:,} on your {product}, which is {dpd} days past due"

    if prev:
        return (
            f"Hello, may I speak with {first}? "
            f"Hi {first}, this is ARIA calling from the bank about {reason}. "
            "We spoke recently but I wanted to follow up. Is everything okay?"
        )
    else:
        return (
            f"Hello, may I speak with {first}? "
            f"Hi {first}, this is ARIA calling from the bank about {reason}. "
            "I just wanted to check in quickly to see if everything is alright?"
        )


async def _groq_chat(
    client: httpx.AsyncClient,
    api_key: str,
    messages: List[dict],
    max_tokens: int = 120,
) -> str:
    r = await client.post(
        f"{GROQ_BASE}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": LLM_MODEL,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.65,
        },
        timeout=30.0,
    )
    if r.status_code != 200:
        raise RuntimeError(f"Groq LLM error ({r.status_code}): {r.text}")
    return r.json()["choices"][0]["message"]["content"].strip()


async def _groq_tts(client: httpx.AsyncClient, api_key: str, text: str) -> str:
    snippet = text.strip()[:TTS_MAX_CHARS]
    if not snippet:
        return ""
    r = await client.post(
        f"{GROQ_BASE}/audio/speech",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": TTS_MODEL,
            "input": snippet,
            "voice": TTS_VOICE,
            "response_format": "wav",
        },
        timeout=30.0,
    )
    if r.status_code != 200:
        return ""
    return base64.b64encode(r.content).decode()


async def _groq_stt(client: httpx.AsyncClient, api_key: str, audio_path: str) -> str:
    with open(audio_path, "rb") as audio_file:
        r = await client.post(
            f"{GROQ_BASE}/audio/transcriptions",
            headers={"Authorization": f"Bearer {api_key}"},
            data={
                "model": WHISPER_MODEL,
                "response_format": "json",
                "language": "en",
                "temperature": "0",
            },
            files={"file": ("audio.webm", audio_file, "audio/webm")},
            timeout=45.0,
        )
    if r.status_code != 200:
        raise RuntimeError(f"Groq STT error ({r.status_code}): {r.text}")
    return (r.json().get("text") or "").strip()


def generate_fallback_response(acc: dict, transcript: str) -> str:
    t = transcript.lower() if transcript else ""
    first = (acc.get("name") or "there").split()[0]

    hardship_kws = ["hospital", "surgery", "medical", "accident", "job loss", "laid off", "fired", "unemployed", "icu", "critical", "passed away", "death", "family emergency"]
    if any(k in t for k in hardship_kws):
        return f"I am very sorry to hear that, {first}. Please take care of your family first, and we can discuss the payment later. Wishing you all the best."

    ptp_kws = ["will pay", "i'll pay", "pay on", "paying on", "tomorrow", "next week", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    if any(k in t for k in ptp_kws):
        return f"Thank you for confirming, {first}. I have noted down the promise to pay. We will update your records and pause outreach until then."

    hostile_kws = ["won't pay", "never pay", "refuse", "harassment", "stop calling", "police", "lawyer"]
    if any(k in t for k in hostile_kws):
        return f"I understand your perspective, {first}. I will document your feedback in our system and escalate it for review."

    negotiation_kws = ["settlement", "ots", "discount", "settle"]
    if any(k in t for k in negotiation_kws):
        return f"I note that you would like to discuss a settlement option, {first}. I will refer this request to our team to check for available options."

    return f"I understand, {first}. Could you please confirm when you might be able to clear the outstanding EMI?"


async def generate_greeting(
    acc: dict,
    system_prompt: Optional[str] = None,
) -> Dict[str, Any]:
    prompt = system_prompt or build_voice_prompt(acc)
    api_key = os.getenv("GROQ_API_KEY", "").strip()

    if not api_key:
        text = template_greeting(acc)
        return {
            "aria_text": text,
            "audio_b64": "",
            "provider": "template",
            "voice_status": "groq_key_missing",
            "prompt": prompt,
        }

    messages = [
        {"role": "system", "content": prompt},
        {
            "role": "user",
            "content": (
                "Generate ONLY your opening line for this outbound collections call. "
                "English only. Maximum 2 sentences. Do not include labels or stage names."
            ),
        },
    ]
    async with httpx.AsyncClient(verify=False) as client:
        try:
            aria_text = await _groq_chat(client, api_key, messages, max_tokens=100)
            audio_b64 = await _groq_tts(client, api_key, aria_text)
            return {
                "aria_text": aria_text,
                "audio_b64": audio_b64,
                "provider": "groq",
                "voice_status": "active",
                "prompt": prompt,
            }
        except Exception as exc:
            text = template_greeting(acc)
            return {
                "aria_text": text,
                "audio_b64": "",
                "provider": "template",
                "voice_status": f"groq_error: {exc}",
                "prompt": prompt,
            }


# ── LangGraph Voice Turn ──────────────────────────────────────────────────────

class VoiceTurnState(TypedDict):
    acc: dict
    audio_b64: str
    conversation: List[dict]
    system_prompt: str
    tmp_audio: Optional[str]
    transcript: str
    aria_text: str
    audio_out_b64: str
    intelligence: dict
    api_key: str


async def _stt_node(state: VoiceTurnState):
    client = httpx.AsyncClient(verify=False)
    try:
        transcript = await _groq_stt(client, state["api_key"], state["tmp_audio"])
        return {"transcript": transcript}
    except Exception as exc:
        return {"transcript": f"[STT unavailable: {exc}]"}
    finally:
        await client.aclose()


async def _llm_node(state: VoiceTurnState):
    transcript = state.get("transcript", "")
    if not transcript or "[STT unavailable" in transcript:
        first = (state["acc"].get("name") or "there").split()[0]
        return {"aria_text": f"I'm sorry, {first}, I didn't quite catch that. Could you please repeat?"}

    client = httpx.AsyncClient(verify=False)
    try:
        messages = [{"role": "system", "content": state["system_prompt"]}]
        for turn in state["conversation"][-8:]:
            role = turn.get("role", "user")
            if role not in ("user", "assistant"):
                continue
            messages.append({"role": role, "content": turn.get("content", "")})
        messages.append({"role": "user", "content": transcript})
        aria_text = await _groq_chat(client, state["api_key"], messages, max_tokens=150)
        return {"aria_text": aria_text}
    except Exception as exc:
        return {"aria_text": generate_fallback_response(state["acc"], transcript)}
    finally:
        await client.aclose()


async def _tts_node(state: VoiceTurnState):
    client = httpx.AsyncClient(verify=False)
    try:
        audio_out = await _groq_tts(client, state["api_key"], state["aria_text"])
        return {"audio_out_b64": audio_out}
    except Exception:
        return {"audio_out_b64": ""}
    finally:
        await client.aclose()


async def _intel_node(state: VoiceTurnState):
    transcript = state.get("transcript", "")
    acc = state["acc"]
    try:
        agent = ConversationIntelligenceAgent()
        context = {
            "transcript": transcript,
            "conversation_history": state["conversation"],
        }
        c_dec = await agent.reason(acc, context)
        return {"intelligence": c_dec.data}
    except Exception:
        # Keyword fallback inline
        from banking_agents.collections_domain.services.transcript_extraction import _keyword_extract
        intel = _keyword_extract(transcript, acc.get("persona", "forgetful_payer"))
        intel["fallback"] = True
        return {"intelligence": intel}


def _build_voice_graph() -> StateGraph:
    workflow = StateGraph(VoiceTurnState)
    workflow.add_node("stt", _stt_node)
    workflow.add_node("llm", _llm_node)
    workflow.add_node("tts", _tts_node)
    workflow.add_node("intel", _intel_node)

    workflow.add_edge(START, "stt")
    workflow.add_edge("stt", "llm")
    workflow.add_edge("stt", "intel")  # Brain B runs in parallel with Brain A
    workflow.add_edge("llm", "tts")
    workflow.add_edge("tts", END)
    workflow.add_edge("intel", END)
    return workflow.compile()


_voice_graph = _build_voice_graph()


async def process_voice_turn(
    acc: dict,
    audio_b64: str,
    conversation: List[dict],
    system_prompt: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Process one voice turn: STT → LLM + Intelligence (parallel) → TTS.

    Args:
        acc: Account dict
        audio_b64: Base64-encoded audio (webm format from browser MediaRecorder)
        conversation: Prior conversation turns [{role, content}]
        system_prompt: Optional override for ARIA system prompt

    Returns:
        {transcript, aria_text, audio_b64, intelligence}

    Note:
        Requires GROQ_API_KEY in environment.
        Frontend microphone wiring (MediaRecorder) is required to send audio_b64.
        Backend pipeline is complete; frontend browser integration is pending.
    """
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        raise ValueError("GROQ_API_KEY not configured — voice processing unavailable")

    prompt = system_prompt or build_voice_prompt(acc)
    audio_bytes = base64.b64decode(audio_b64)
    tmp_audio = None

    try:
        with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as f:
            f.write(audio_bytes)
            tmp_audio = f.name

        initial_state: VoiceTurnState = {
            "acc": acc,
            "audio_b64": audio_b64,
            "conversation": conversation,
            "system_prompt": prompt,
            "tmp_audio": tmp_audio,
            "api_key": api_key,
            "transcript": "",
            "aria_text": "",
            "audio_out_b64": "",
            "intelligence": {},
        }

        final_state = await _voice_graph.ainvoke(initial_state)
        return {
            "transcript": final_state.get("transcript", ""),
            "aria_text": final_state.get("aria_text", ""),
            "audio_b64": final_state.get("audio_out_b64", ""),
            "intelligence": final_state.get("intelligence", {}),
        }
    finally:
        if tmp_audio:
            try:
                os.unlink(tmp_audio)
            except OSError:
                pass
