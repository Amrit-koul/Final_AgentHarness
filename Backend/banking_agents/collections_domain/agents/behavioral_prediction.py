"""
Behavioral Prediction Agent
Predicts borrower behavior patterns, optimal contact times, channel preferences
"""
from typing import Dict, Any, Optional
from banking_agents.collections_domain.agents.base import BaseAgent, AgentDecision


class BehavioralPredictionAgent(BaseAgent):
    """
    Predicts borrower behavior using historical patterns and persona insights
    """
    
    def __init__(self):
        super().__init__(
            agent_id="behavioral_prediction",
            name="Behavioral Prediction Agent",
        )
    
    def _extract_behavioral_history(self, account_data: Dict[str, Any]) -> str:
        """Extract behavioral patterns from account history"""
        patterns = []
        
        # Call history analysis
        call_history = account_data.get("call_history", [])
        if call_history:
            patterns.append("**Interaction History:**")
            for h in call_history[-5:]:
                patterns.append(f"- {h}")
        
        # Response patterns
        if "Read ✓" in str(call_history):
            patterns.append("\n**Observed Pattern:** Customer reads messages but doesn't always act")
        if "no click" in str(call_history).lower():
            patterns.append("**Observed Pattern:** Low engagement with payment links")
        if "silence" in str(call_history).lower():
            patterns.append("**Observed Pattern:** Silent period detected - avoidance behavior")
        
        # Field visit history
        if account_data.get("field_visit_history"):
            patterns.append("\n**Field Visit History:**")
            for visit in account_data.get("field_visit_history", [])[-3:]:
                patterns.append(f"- Outcome: {visit.get('outcome')}, Notes: {visit.get('notes', 'N/A')}")
        
        # PTP history
        if account_data.get("persona_history"):
            patterns.append("\n**Persona Evolution:**")
            for h in account_data.get("persona_history", [])[-3:]:
                patterns.append(f"- {h.get('from')} → {h.get('to')}: {h.get('reason', '')}")
        
        return "\n".join(patterns) if patterns else "No significant behavioral history available"
    
    async def reason(
        self,
        account_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> AgentDecision:
        """
        Predict behavioral patterns and optimal engagement strategy
        """
        # Get persona from previous agent
        persona_decision = context.get("persona_discovery_decision", {}) if context else {}
        persona = persona_decision.get("data", {}).get("persona", account_data.get("persona", "forgetful_payer"))
        
        behavioral_history = self._extract_behavioral_history(account_data)
        scores = account_data.get("scores", {})
        
        system_prompt, prompt = self._render_prompt(
            "collections_behavioral_prediction",
            persona=persona,
            dpd=account_data.get("dpd", 0),
            outstanding=f"{account_data.get('outstanding', 0):,}",
            job_age=f"{account_data.get('job')} (age {account_data.get('age')})",
            contactability=scores.get("contactability", "N/A"),
            intent_to_pay=scores.get("intent_to_pay", "N/A"),
            behavioral_history=behavioral_history,
            persona_confidence=persona_decision.get("confidence", "N/A"),
            persona_reasoning=persona_decision.get("reasoning", []),
        )
        try:
            result = await self._llm_json_reason(prompt, system_prompt, temperature=0.3)
            
            confidence = float(result.get("confidence", 0.75))
            reasoning = result.get("reasoning", [])
            
            # Build prediction data
            data = {
                "primary_channel": result.get("primary_channel", "whatsapp"),
                "fallback_channel": result.get("fallback_channel", "sms"),
                "best_contact_time": result.get("best_contact_time", "10:00 IST"),
                "best_day": result.get("best_day", "Monday"),
                "predicted_response_rate": result.get("predicted_response_rate", 0.7),
                "communication_tone": result.get("communication_tone", "empathetic"),
                "behavioral_triggers": result.get("behavioral_triggers", []),
                "engagement_strategy": result.get("engagement_strategy", ""),
                "raw_llm_output": result,
            }
            
            # Store learned pattern in memory
            self.memory.add_learning(
                f"pattern_{persona}_{account_data.get('id')}",
                {
                    "channel": data["primary_channel"],
                    "time": data["best_contact_time"],
                    "predicted_rate": data["predicted_response_rate"],
                }
            )
            
            return AgentDecision(
                action="behavior_predicted",
                confidence=confidence,
                reasoning=reasoning,
                data=data,
                next_agent="next_best_action",
            )
        
        except Exception as e:
            # Fallback to rule-based predictions
            return await self._fallback_prediction(account_data, persona, str(e))
    
    async def _fallback_prediction(
        self,
        account_data: Dict[str, Any],
        persona: str,
        error: str,
    ) -> AgentDecision:
        """Fallback behavioral prediction"""
        # Default channel mappings
        channel_map = {
            "forgetful_payer": ("whatsapp", "sms"),
            "temporarily_distressed": ("tele_inhouse", "whatsapp"),
            "genuinely_distressed": ("tele_inhouse", "field_visit"),
            "hostile_defaulter": ("field_visit", "tele_agency"),
            "reluctant_avoider": ("tele_agency", "field_visit"),
            "the_negotiator": ("tele_inhouse", "whatsapp"),
        }
        
        channels = channel_map.get(persona, ("whatsapp", "sms"))
        
        data = {
            "primary_channel": channels[0],
            "fallback_channel": channels[1],
            "best_contact_time": "10:30 IST",
            "best_day": "Monday",
            "predicted_response_rate": 0.65,
            "communication_tone": "empathetic",
            "behavioral_triggers": [],
            "engagement_strategy": f"Standard approach for {persona}",
            "fallback": True,
        }
        
        return AgentDecision(
            action="behavior_predicted",
            confidence=0.6,
            reasoning=[
                f"Fallback prediction for {persona}",
                f"⚠️ LLM prediction failed: {error}",
                "Using rule-based channel mapping",
            ],
            data=data,
            escalate=True,
            escalation_reason="LLM behavioral prediction unavailable",
            next_agent="next_best_action",
        )


