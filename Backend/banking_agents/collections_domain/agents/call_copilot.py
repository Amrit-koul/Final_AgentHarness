"""
Call Copilot Agent
Provides real-time guidance to agents during calls
"""
from typing import Dict, Any, Optional
from banking_agents.collections_domain.agents.base import BaseAgent, AgentDecision


class CallCopilotAgent(BaseAgent):
    """
    Real-time copilot for voice agents
    Suggests responses, handles objections, guides negotiation
    """
    
    def __init__(self):
        super().__init__(
            agent_id="call_copilot",
            name="Call Copilot Agent",
        )
    
    async def reason(
        self,
        account_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> AgentDecision:
        """
        Provide real-time guidance based on conversation intelligence
        
        Context should contain conversation_intelligence_decision
        """
        if not context:
            return self._no_context_decision()
        
        conv_intel = context.get("conversation_intelligence_decision", {})
        if not conv_intel:
            return self._no_context_decision()
        
        intel_data = conv_intel.get("data", {})
        intent = intel_data.get("intent", "general_response")
        sentiment = intel_data.get("sentiment", "neutral")
        life_event = intel_data.get("life_event_detected", False)
        agent_guidance = intel_data.get("agent_guidance", "")
        
        persona = account_data.get("persona", "forgetful_payer")
        dpd = account_data.get("dpd", 0)
        
        system_prompt, prompt = self._render_prompt(
            "collections_call_copilot",
            persona=persona,
            dpd=dpd,
            outstanding=f"{account_data.get('outstanding', 0):,}",
            emi=f"{account_data.get('emi', 0):,}",
            intent=intent,
            sentiment=sentiment,
            stress_score=intel_data.get("stress_score", 50),
            life_event=intel_data.get("life_event_type", "None") if life_event else "None",
            key_entities=intel_data.get("key_entities", {}),
            agent_guidance=agent_guidance,
        )
        try:
            result = await self._llm_json_reason(prompt, system_prompt, temperature=0.3)
            
            confidence = float(result.get("confidence", 0.8))
            reasoning = result.get("reasoning", [])
            
            data = {
                "suggested_response": result.get("suggested_response", ""),
                "response_rationale": result.get("response_rationale", ""),
                "alternative_responses": result.get("alternative_responses", []),
                "objection_handling": result.get("objection_handling", {}),
                "negotiation_guidance": result.get("negotiation_guidance", {}),
                "compliance_check": result.get("compliance_check", "passed"),
                "escalation_recommendation": result.get("escalation_recommendation", False),
                "next_best_question": result.get("next_best_question", ""),
                "raw_llm_output": result,
            }
            
            escalate = data["escalation_recommendation"]
            
            return AgentDecision(
                action="copilot_guidance_provided",
                confidence=confidence,
                reasoning=reasoning,
                data=data,
                escalate=escalate,
                escalation_reason="Copilot recommends escalation" if escalate else None,
                next_agent="promise_to_pay_validation" if intent == "promise_to_pay" else None,
            )
        
        except Exception as e:
            return await self._fallback_guidance(intent, sentiment, life_event, str(e))
    
    def _no_context_decision(self) -> AgentDecision:
        return AgentDecision(
            action="no_conversation_intelligence",
            confidence=1.0,
            reasoning=["No conversation intelligence data available"],
            data={"error": "Missing conversation intelligence context"},
        )
    
    async def _fallback_guidance(
        self,
        intent: str,
        sentiment: str,
        life_event: bool,
        error: str,
    ) -> AgentDecision:
        """Fallback copilot guidance"""
        # Simple scripted responses
        guidance_map = {
            "promise_to_pay": "Confirm the specific date: 'Thank you! Just to confirm, you'll make the payment on [DATE]?'",
            "settlement_request": "Acknowledge: 'I understand you'd like to discuss settlement options. Let me check what's available for your account.'",
            "hardship_disclosure": "Show empathy: 'I'm sorry to hear that. Let's see how we can help you through this situation.'",
            "objection": "Acknowledge: 'I understand your concern. Let's discuss what options might work better for you.'",
            "dispute": "Document: 'I've noted your concern. Let me escalate this for review.'",
        }
        
        suggested_response = guidance_map.get(intent, "Continue the conversation with empathy and professionalism.")
        
        if life_event:
            suggested_response = "Express empathy first: 'I'm really sorry to hear about that situation. Your well-being is important. How can we support you right now?'"
        
        return AgentDecision(
            action="copilot_guidance_provided",
            confidence=0.5,
            reasoning=[
                "Fallback scripted guidance",
                f"⚠️ LLM copilot failed: {error}",
            ],
            data={
                "suggested_response": suggested_response,
                "response_rationale": "Template-based response",
                "fallback": True,
            },
            escalate=True,
            escalation_reason="Copilot LLM unavailable, using templates",
        )


