"""
Promise-to-Pay Validation Agent
Validates PTP commitments and assesses likelihood of honor
"""
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from banking_agents.collections_domain.agents.base import BaseAgent, AgentDecision


class PromiseToPayValidationAgent(BaseAgent):
    """
    Validates PTP commitments and predicts honor likelihood
    """
    
    def __init__(self):
        super().__init__(
            agent_id="ptp_validation",
            name="Promise-to-Pay Validation Agent",
        )
    
    async def reason(
        self,
        account_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> AgentDecision:
        """
        Validate PTP and predict honor probability
        
        Context should contain:
        - ptp_date: Committed payment date
        - ptp_amount: Committed amount (optional)
        - conversation_context: How PTP was secured
        """
        if not context or not context.get("ptp_date"):
            return self._no_ptp_decision()
        
        ptp_date = context.get("ptp_date")
        ptp_amount = context.get("ptp_amount", account_data.get("emi", 0))
        conversation_context = context.get("conversation_context", "")
        
        # Get conversation intelligence if available
        conv_intel = context.get("conversation_intelligence_decision", {})
        intel_data = conv_intel.get("data", {})
        
        persona = account_data.get("persona", "forgetful_payer")
        scores = account_data.get("scores", {})
        
        # Historical PTP performance
        persona_history = account_data.get("persona_history", [])
        ptp_history = [h for h in persona_history if "ptp" in str(h).lower()]
        
        system_prompt, prompt = self._render_prompt(
            "collections_ptp_validation",
            persona=persona,
            dpd=account_data.get("dpd", 0),
            outstanding=f"{account_data.get('outstanding', 0):,}",
            ability_to_pay=scores.get("ability_to_pay", "N/A"),
            intent_to_pay=scores.get("intent_to_pay", "N/A"),
            ptp_date=ptp_date,
            ptp_amount=f"{ptp_amount:,}",
            conversation_context=conversation_context if conversation_context else "Standard PTP capture",
            sentiment=intel_data.get("sentiment", "N/A"),
            stress_score=intel_data.get("stress_score", "N/A"),
            life_event=intel_data.get("life_event_type", "None"),
            ptp_history_count=len(ptp_history),
            status=account_data.get("status", "Unknown"),
        )
        try:
            result = await self._llm_json_reason(prompt, system_prompt, temperature=0.2)
            
            confidence = float(result.get("confidence", 0.8))
            reasoning = result.get("reasoning", [])
            honor_prob = float(result.get("honor_probability", 0.7))
            
            data = {
                "ptp_valid": result.get("ptp_valid", True),
                "ptp_date": result.get("ptp_date", ptp_date),
                "ptp_amount": result.get("ptp_amount", ptp_amount),
                "honor_probability": honor_prob,
                "risk_level": result.get("risk_level", "Medium"),
                "validation_factors": result.get("validation_factors", {}),
                "recommended_actions": result.get("recommended_actions", []),
                "suppression_period": result.get("suppression_period", "until_ptp_date"),
                "fallback_plan": result.get("fallback_plan", ""),
                "raw_llm_output": result,
            }
            
            # Store learning
            self.memory.add_learning(
                f"ptp_{account_data.get('id')}_{ptp_date}",
                {
                    "honor_probability": honor_prob,
                    "persona": persona,
                    "validation_factors": data["validation_factors"],
                }
            )
            
            # Escalate if high risk or low honor probability
            escalate = False
            escalation_reason = None
            if data["risk_level"] == "High" or honor_prob < 0.4:
                escalate = True
                escalation_reason = f"High risk PTP: {honor_prob:.0%} honor probability"
            
            return AgentDecision(
                action="ptp_validated",
                confidence=confidence,
                reasoning=reasoning,
                data=data,
                escalate=escalate,
                escalation_reason=escalation_reason,
                next_agent="compliance" if not escalate else None,
            )
        
        except Exception as e:
            return await self._fallback_validation(ptp_date, ptp_amount, persona, str(e))
    
    def _no_ptp_decision(self) -> AgentDecision:
        return AgentDecision(
            action="no_ptp_to_validate",
            confidence=1.0,
            reasoning=["No PTP date provided in context"],
            data={"error": "Missing PTP date"},
        )
    
    async def _fallback_validation(
        self,
        ptp_date: str,
        ptp_amount: float,
        persona: str,
        error: str,
    ) -> AgentDecision:
        """Simple rule-based PTP validation"""
        # Parse date
        try:
            ptp_dt = datetime.fromisoformat(ptp_date.replace("th", "").replace("st", "").replace("nd", "").replace("rd", ""))
            days_until = (ptp_dt - datetime.now()).days
        except:
            days_until = 7  # default
        
        # Simple honor probability
        persona_rates = {
            "forgetful_payer": 0.85,
            "temporarily_distressed": 0.65,
            "genuinely_distressed": 0.35,
            "hostile_defaulter": 0.20,
            "reluctant_avoider": 0.25,
            "the_negotiator": 0.55,
        }
        honor_prob = persona_rates.get(persona, 0.6)
        
        # Adjust for date
        if days_until < 2:
            honor_prob *= 0.9  # rushed
        elif days_until > 30:
            honor_prob *= 0.8  # too far
        
        risk_level = "Low" if honor_prob > 0.7 else "Medium" if honor_prob > 0.4 else "High"
        
        return AgentDecision(
            action="ptp_validated",
            confidence=0.6,
            reasoning=[
                f"Fallback PTP validation for {persona}",
                f"⚠️ LLM validation failed: {error}",
                f"Rule-based honor probability: {honor_prob:.0%}",
            ],
            data={
                "ptp_valid": True,
                "ptp_date": ptp_date,
                "ptp_amount": ptp_amount,
                "honor_probability": honor_prob,
                "risk_level": risk_level,
                "fallback": True,
            },
            escalate=risk_level == "High",
            escalation_reason=f"High risk PTP (fallback mode)" if risk_level == "High" else None,
        )


