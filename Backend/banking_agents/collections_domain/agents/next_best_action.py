"""
Next Best Action Agent
Determines the next best action based on persona, behavior, and business rules
"""
from typing import Dict, Any, Optional
from banking_agents.collections_domain.agents.base import BaseAgent, AgentDecision


class NextBestActionAgent(BaseAgent):
    """
    Determines next best action using WHO-WHAT-WHEN framework
    """
    
    def __init__(self):
        super().__init__(
            agent_id="next_best_action",
            name="Next Best Action Agent",
        )
    
    async def reason(
        self,
        account_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> AgentDecision:
        """
        Determine next best action using WHO-WHAT-WHEN framework
        """
        # Get insights from previous agents
        persona_decision = context.get("persona_discovery_decision", {}) if context else {}
        behavioral_decision = context.get("behavioral_prediction_decision", {}) if context else {}
        
        persona = persona_decision.get("data", {}).get("persona", account_data.get("persona", "forgetful_payer"))
        persona_confidence = persona_decision.get("confidence", 0.7)
        
        channel = behavioral_decision.get("data", {}).get("primary_channel", "whatsapp")
        contact_time = behavioral_decision.get("data", {}).get("best_contact_time", "10:00 IST")
        tone = behavioral_decision.get("data", {}).get("communication_tone", "empathetic")
        
        dpd = account_data.get("dpd", 0)
        outstanding = account_data.get("outstanding", 0)
        scores = account_data.get("scores", {})
        
        system_prompt, prompt = self._render_prompt(
            "collections_next_best_action",
            account_id=account_data.get("id"),
            persona=persona,
            persona_confidence=f"{persona_confidence:.2f}",
            dpd=dpd,
            outstanding=f"{outstanding:,}",
            emi=f"{account_data.get('emi', 0):,}",
            cibil=account_data.get("cibil", "N/A"),
            ability_to_pay=scores.get("ability_to_pay", "N/A"),
            intent_to_pay=scores.get("intent_to_pay", "N/A"),
            self_cure=scores.get("self_cure_probability", scores.get("self_cure", "N/A")),
            channel=channel,
            contact_time=contact_time,
            tone=tone,
            predicted_response_rate=behavioral_decision.get("data", {}).get("predicted_response_rate", "N/A"),
            status=account_data.get("status", "Unknown"),
            last_action=account_data.get("next_action", "None"),
            persona_reasoning=persona_decision.get("reasoning", []),
            behavioral_strategy=behavioral_decision.get("data", {}).get("engagement_strategy", ""),
        )
        try:
            result = await self._llm_json_reason(prompt, system_prompt, temperature=0.2)
            
            confidence = float(result.get("confidence", 0.8))
            reasoning = result.get("reasoning", [])
            
            # Build NBA data
            data = {
                "action": result.get("action", "continue_monitoring"),
                "action_label": result.get("action_label", "Continue Monitoring"),
                "priority": result.get("priority", "Medium"),
                "WHO": result.get("WHO", {}),
                "WHAT": result.get("WHAT", {}),
                "WHEN": result.get("WHEN", {}),
                "expected_outcome": result.get("expected_outcome", ""),
                "cost_estimate": result.get("cost_estimate", 0),
                "roi_estimate": result.get("roi_estimate", ""),
                "compliance_check": result.get("compliance_check", "passed"),
                "raw_llm_output": result,
            }
            
            # Store learning for outcome tracking
            self.memory.add_learning(
                f"nba_{account_data.get('id')}_{persona}",
                {
                    "action": data["action"],
                    "dpd": dpd,
                    "outstanding": outstanding,
                    "confidence": confidence,
                }
            )
            
            # Check if compliance review needed
            escalate = False
            escalation_reason = None
            if data["compliance_check"] == "review_needed":
                escalate = True
                escalation_reason = "Compliance review required before action"
            
            return AgentDecision(
                action=data["action"],
                confidence=confidence,
                reasoning=reasoning,
                data=data,
                escalate=escalate,
                escalation_reason=escalation_reason,
            )
        
        except Exception as e:
            # Fallback to rule-based NBA
            return await self._fallback_nba(account_data, persona, channel, contact_time, tone, str(e))
    
    async def _fallback_nba(
        self,
        account_data: Dict[str, Any],
        persona: str,
        channel: str,
        contact_time: str,
        tone: str,
        error: str,
    ) -> AgentDecision:
        """Fallback NBA logic"""
        dpd = account_data.get("dpd", 0)
        
        # Simple rule-based actions
        action_map = {
            "forgetful_payer": "suppress_all",
            "temporarily_distressed": "trigger_ots",
            "genuinely_distressed": "trigger_ots",
            "hostile_defaulter": "escalate_to_field",
            "reluctant_avoider": "escalate_to_field",
            "the_negotiator": "trigger_ots",
        }
        
        action = action_map.get(persona, "continue_monitoring")
        
        # Adjust based on DPD
        if dpd > 90:
            action = "escalate_to_legal"
        elif dpd > 60:
            action = "escalate_to_field"
        
        priority = "Critical" if dpd > 60 else "High" if dpd > 30 else "Medium"
        
        data = {
            "action": action,
            "action_label": action.replace("_", " ").title(),
            "priority": priority,
            "WHO": {
                "persona": persona,
                "priority_level": priority,
                "risk_flags": ["High DPD"] if dpd > 60 else [],
            },
            "WHAT": {
                "objective": "PTP" if persona == "forgetful_payer" else "Settlement",
                "tone": tone,
                "message_strategy": f"Standard {persona} approach",
                "offer": "None",
            },
            "WHEN": {
                "channel": channel,
                "timing": contact_time,
                "frequency": "once",
            },
            "fallback": True,
        }
        
        return AgentDecision(
            action=action,
            confidence=0.6,
            reasoning=[
                f"Fallback NBA for {persona} at DPD {dpd}",
                f"⚠️ LLM reasoning failed: {error}",
                "Using rule-based action mapping",
            ],
            data=data,
            escalate=True,
            escalation_reason="LLM NBA reasoning unavailable",
        )


