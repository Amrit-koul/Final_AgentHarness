"""
Settlement Negotiation Agent
Determines optimal settlement offers and negotiation boundaries
"""
from typing import Dict, Any, Optional
from banking_agents.collections_domain.agents.base import BaseAgent, AgentDecision


class SettlementNegotiationAgent(BaseAgent):
    """
    Determines settlement strategy and negotiation boundaries
    """
    
    def __init__(self):
        super().__init__(
            agent_id="settlement_negotiation",
            name="Settlement Negotiation Agent",
        )
    
    async def reason(
        self,
        account_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> AgentDecision:
        """
        Determine settlement/OTS strategy
        """
        persona = account_data.get("persona", "forgetful_payer")
        dpd = account_data.get("dpd", 0)
        outstanding = account_data.get("outstanding", 0)
        emi = account_data.get("emi", 0)
        scores = account_data.get("scores", {})
        
        # Check OTS eligibility
        ots_eligible = dpd >= 30 and outstanding > 100000
        
        system_prompt, prompt = self._render_prompt(
            "collections_settlement_negotiation",
            persona=persona,
            dpd=dpd,
            outstanding=f"{outstanding:,}",
            emi=f"{emi:,}",
            product=account_data.get("product", "Loan"),
            ability_to_pay=scores.get("ability_to_pay", "N/A"),
            intent_to_pay=scores.get("intent_to_pay", "N/A"),
            self_cure=scores.get("self_cure_probability", scores.get("self_cure", "N/A")),
            status=account_data.get("status", "Unknown"),
            previous_action=account_data.get("next_action", "None"),
            dpd_eligible="Yes" if dpd >= 30 else "No",
            outstanding_eligible="Yes" if outstanding > 100000 else "No",
        )
        try:
            result = await self._llm_json_reason(prompt, system_prompt, temperature=0.2)
            
            confidence = float(result.get("confidence", 0.8))
            reasoning = result.get("reasoning", [])
            
            data = {
                "ots_eligible": result.get("ots_eligible", ots_eligible),
                "settlement_recommended": result.get("settlement_recommended", False),
                "negotiation_strategy": result.get("negotiation_strategy", {}),
                "negotiation_tactics": result.get("negotiation_tactics", []),
                "offer_validity": result.get("offer_validity", "72 hours"),
                "payment_terms": result.get("payment_terms", "full_upfront"),
                "fallback_options": result.get("fallback_options", []),
                "expected_acceptance_rate": result.get("expected_acceptance_rate", 0.6),
                "recovery_estimate": result.get("recovery_estimate", outstanding * 0.9),
                "raw_llm_output": result,
            }
            
            # Store negotiation pattern
            self.memory.add_learning(
                f"settlement_{persona}_{dpd}",
                {
                    "strategy": data["negotiation_strategy"],
                    "acceptance_rate": data["expected_acceptance_rate"],
                }
            )
            
            return AgentDecision(
                action="settlement_strategy_determined",
                confidence=confidence,
                reasoning=reasoning,
                data=data,
                next_agent="recovery_strategy",
            )
        
        except Exception as e:
            return await self._fallback_settlement(account_data, ots_eligible, str(e))
    
    async def _fallback_settlement(
        self,
        account_data: Dict[str, Any],
        ots_eligible: bool,
        error: str,
    ) -> AgentDecision:
        """Fallback settlement logic"""
        dpd = account_data.get("dpd", 0)
        outstanding = account_data.get("outstanding", 0)
        
        # Simple waiver calculation
        if dpd < 30:
            max_waiver = 0.05
        elif dpd < 60:
            max_waiver = 0.10
        elif dpd < 90:
            max_waiver = 0.15
        else:
            max_waiver = 0.25
        
        settlement_amount = outstanding * (1 - max_waiver)
        
        data = {
            "ots_eligible": ots_eligible,
            "settlement_recommended": ots_eligible,
            "negotiation_strategy": {
                "opening_offer": {
                    "waiver_percentage": max_waiver * 50,  # Start at half
                    "settlement_amount": outstanding * (1 - max_waiver * 0.5),
                },
                "maximum_concession": {
                    "waiver_percentage": max_waiver * 100,
                    "settlement_amount": settlement_amount,
                },
            },
            "fallback": True,
        }
        
        return AgentDecision(
            action="settlement_strategy_determined",
            confidence=0.6,
            reasoning=[
                f"Fallback settlement for DPD {dpd}",
                f"⚠️ LLM negotiation failed: {error}",
                f"Rule-based waiver: {max_waiver:.0%}",
            ],
            data=data,
            escalate=True,
            escalation_reason="Settlement LLM unavailable",
        )


