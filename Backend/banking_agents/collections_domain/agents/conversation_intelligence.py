"""
Conversation Intelligence Agent
Real-time analysis of voice conversations with persona shift detection
"""
from typing import Dict, Any, Optional, List
from banking_agents.collections_domain.agents.base import BaseAgent, AgentDecision


class ConversationIntelligenceAgent(BaseAgent):
    """
    Analyzes conversation transcripts in real-time
    Detects intent, sentiment, life events, and persona shifts
    """
    
    def __init__(self):
        super().__init__(
            agent_id="conversation_intelligence",
            name="Conversation Intelligence Agent",
        )
    
    async def reason(
        self,
        account_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> AgentDecision:
        """
        Analyze conversation transcript and detect signals
        
        Context should contain:
        - transcript: Current customer utterance
        - conversation_history: Full conversation so far
        - current_persona: Current persona classification
        """
        if not context:
            return self._no_context_decision()
        
        transcript = context.get("transcript", "")
        if not transcript:
            return self._no_context_decision()
        
        conversation_history = context.get("conversation_history", [])
        current_persona = account_data.get("persona", "forgetful_payer")
        
        # Build conversation context
        conv_text = ""
        for turn in conversation_history[-5:]:
            role = turn.get("role", "user")
            content = turn.get("content", "")
            speaker = "Customer" if role == "user" else "Agent"
            conv_text += f"{speaker}: {content}\n"
        
        system_prompt, prompt = self._render_prompt(
            "collections_conversation_intelligence",
            current_persona=current_persona,
            dpd=account_data.get("dpd", 0),
            outstanding=f"{account_data.get('outstanding', 0):,}",
            conversation_text=conv_text,
            transcript=transcript,
        )
        try:
            result = await self._llm_json_reason(prompt, system_prompt, temperature=0.2)
            
            confidence = float(result.get("confidence", 0.85))
            reasoning = result.get("reasoning", [])
            
            # Build intelligence data
            data = {
                "intent": result.get("intent", "general_response"),
                "sentiment": result.get("sentiment", "neutral"),
                "stress_score": result.get("stress_score", 50),
                "life_event_detected": result.get("life_event_detected", False),
                "life_event_type": result.get("life_event_type"),
                "life_event_details": result.get("life_event_details"),
                "key_entities": result.get("key_entities", {}),
                "persona_shift_recommended": result.get("persona_shift_recommended", False),
                "recommended_persona": result.get("recommended_persona"),
                "shift_confidence": result.get("shift_confidence", 0),
                "shift_reasoning": result.get("shift_reasoning", []),
                "agent_guidance": result.get("agent_guidance", ""),
                "compliance_flags": result.get("compliance_flags", []),
                "ptp_signal": result.get("intent") == "promise_to_pay",
                "negotiation_signal": result.get("intent") == "settlement_request",
                "hostile_signal": result.get("sentiment") == "hostile",
                "raw_llm_output": result,
            }
            
            # Store pattern in memory
            self.memory.add_learning(
                f"conv_pattern_{current_persona}",
                {
                    "intent": data["intent"],
                    "sentiment": data["sentiment"],
                    "life_event": data["life_event_detected"],
                }
            )
            
            # Escalate if compliance issues or persona shift
            escalate = False
            escalation_reason = None
            if data["compliance_flags"] and data["compliance_flags"] != ["none"]:
                escalate = True
                escalation_reason = f"Compliance flags: {', '.join(data['compliance_flags'])}"
            elif data["persona_shift_recommended"] and data["shift_confidence"] > 0.7:
                # Don't escalate persona shifts, but flag for review
                reasoning.append(f"⚠️ Persona shift suggested: {data['recommended_persona']}")
            
            return AgentDecision(
                action="conversation_analyzed",
                confidence=confidence,
                reasoning=reasoning,
                data=data,
                escalate=escalate,
                escalation_reason=escalation_reason,
                next_agent="call_copilot" if not escalate else None,
            )
        
        except Exception as e:
            # Fallback to rule-based analysis
            return await self._fallback_analysis(transcript, current_persona, str(e))
    
    def _no_context_decision(self) -> AgentDecision:
        """Return when no conversation context provided"""
        return AgentDecision(
            action="no_conversation",
            confidence=1.0,
            reasoning=["No conversation transcript provided"],
            data={"error": "No transcript in context"},
        )
    
    async def _fallback_analysis(
        self,
        transcript: str,
        current_persona: str,
        error: str,
    ) -> AgentDecision:
        """Simple keyword-based fallback analysis"""
        text_lower = transcript.lower()
        stress_score = 30
        if "delay" in text_lower or "salary" in text_lower:
            stress_score = 65
        if "lose job" in text_lower or "can't pay" in text_lower:
            stress_score = 85
            
        sentiment = "Neutral"
        if stress_score > 60:
            sentiment = "Anxious"
        if "won't pay" in text_lower or "don't call" in text_lower:
            sentiment = "Hostile"
            
        suggested_shift = None
        if sentiment == "Hostile":
            suggested_shift = "hostile_defaulter"
        elif "lose job" in text_lower or "can't pay" in text_lower or "hospital" in text_lower or "medical" in text_lower:
            suggested_shift = "temporarily_distressed"

        result = {
            "sentiment": sentiment,
            "stress_score": stress_score,
            "intent_detected": "Payment Delay Request" if stress_score > 50 else "Promise to Pay",
            "key_entities": ["salary delay"] if "salary" in text_lower else [],
            "hostile_signal": sentiment == "Hostile",
            "suggested_persona_shift": suggested_shift if suggested_shift != current_persona else None
        }
        
        return AgentDecision(
            action="conversation_analyzed",
            confidence=0.65,
            reasoning=[
                "Fallback keyword-based analysis",
                f"⚠️ LLM analysis failed: {error}",
            ],
            data={
                **result,
                "fallback": True,
            },
            escalate=True if result.get("hostile_signal") else False,
            escalation_reason="Hostile signal detected (fallback mode)" if result.get("hostile_signal") else None,
        )


