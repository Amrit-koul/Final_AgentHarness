"""
Field Visit Planner Agent
Plans and optimizes field visits based on account characteristics
"""
from typing import Dict, Any, Optional, List
from banking_agents.collections_domain.agents.base import BaseAgent, AgentDecision


class FieldVisitPlannerAgent(BaseAgent):
    """
    Plans field visits considering priority, location, and recovery potential
    """
    
    def __init__(self):
        super().__init__(
            agent_id="field_visit_planner",
            name="Field Visit Planner Agent",
        )
    
    async def reason(
        self,
        account_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> AgentDecision:
        """
        Plan field visit strategy
        """
        persona = account_data.get("persona", "forgetful_payer")
        dpd = account_data.get("dpd", 0)
        outstanding = account_data.get("outstanding", 0)
        city = account_data.get("city", "Unknown")
        
        # Check if field visit justified
        field_justified = (
            dpd > 30 or
            outstanding > 200000 or
            persona in ("hostile_defaulter", "reluctant_avoider") or
            account_data.get("status") == "Escalated"
        )
        
        if not field_justified:
            return self._field_not_justified(dpd, outstanding, persona)
        
        scores = account_data.get("scores", {})
        
        system_prompt, prompt = self._render_prompt(
            "collections_field_visit_planner",
            persona=persona,
            dpd=dpd,
            outstanding=f"{outstanding:,}",
            emi=f"{account_data.get('emi', 0):,}",
            city=city,
            status=account_data.get("status", "Unknown"),
            ability_to_pay=scores.get("ability_to_pay", "N/A"),
            intent_to_pay=scores.get("intent_to_pay", "N/A"),
            contactability=scores.get("contactability", "N/A"),
            call_history=account_data.get("call_history", []),
            field_visit_count=len(account_data.get("field_visit_history", [])),
            current_strategy=account_data.get("next_action", "Unknown"),
        )
        try:
            result = await self._llm_json_reason(prompt, system_prompt, temperature=0.2)
            
            confidence = float(result.get("confidence", 0.8))
            reasoning = result.get("reasoning", [])
            
            data = {
                "visit_justified": result.get("visit_justified", True),
                "visit_priority": result.get("visit_priority", "High"),
                "recommended_timing": result.get("recommended_timing", {}),
                "visit_approach": result.get("visit_approach", "firm"),
                "agent_profile": result.get("agent_profile", "experienced"),
                "team_size": result.get("team_size", 1),
                "pre_visit_briefing": result.get("pre_visit_briefing", ""),
                "talking_points": result.get("talking_points", []),
                "recovery_targets": result.get("recovery_targets", {}),
                "safety_considerations": result.get("safety_considerations", []),
                "expected_outcome": result.get("expected_outcome", "Payment"),
                "success_probability": result.get("success_probability", 0.6),
                "cost_estimate": result.get("cost_estimate", 220.0),
                "roi_estimate": result.get("roi_estimate", 2.0),
                "raw_llm_output": result,
            }
            
            # Store planning pattern
            self.memory.add_learning(
                f"field_plan_{persona}_{city}",
                {
                    "approach": data["visit_approach"],
                    "success_prob": data["success_probability"],
                    "roi": data["roi_estimate"],
                }
            )
            
            return AgentDecision(
                action="field_visit_planned",
                confidence=confidence,
                reasoning=reasoning,
                data=data,
                next_agent="settlement_negotiation",
            )
        
        except Exception as e:
            return await self._fallback_planning(account_data, str(e))
    
    def _field_not_justified(self, dpd: int, outstanding: float, persona: str) -> AgentDecision:
        return AgentDecision(
            action="field_visit_not_justified",
            confidence=1.0,
            reasoning=[
                f"Field visit not justified: DPD {dpd}, Outstanding ₹{outstanding:,}",
                f"Persona {persona} better served by digital/voice channels",
                "Recommendation: Continue with digital strategy",
            ],
            data={
                "visit_justified": False,
                "alternative": "Continue digital/voice outreach",
            },
        )
    
    async def _fallback_planning(self, account_data: Dict[str, Any], error: str) -> AgentDecision:
        """Fallback field planning"""
        dpd = account_data.get("dpd", 0)
        outstanding = account_data.get("outstanding", 0)
        persona = account_data.get("persona", "forgetful_payer")
        
        # Simple planning
        visit_approach = "firm" if persona in ("hostile_defaulter", "reluctant_avoider") else "soft"
        priority = "Critical" if dpd > 60 else "High"
        
        ots_eligible = dpd > 90 and outstanding > 50000
        waiver_ceiling = 0.20 if ots_eligible else 0.0
        
        briefing = {
            "pre_visit_briefing": f"Customer is {dpd} DPD. Focus on establishing direct contact.",
            "ots_decision": {
                "eligible": ots_eligible,
                "max_waiver_pct": waiver_ceiling,
                "suggested_action": "Offer OTS" if ots_eligible else "Attempt standard recovery"
            }
        }
        
        return AgentDecision(
            action="field_visit_planned",
            confidence=0.6,
            reasoning=[
                f"Fallback field planning for {persona}",
                f"⚠️ LLM planning failed: {error}",
                "Using rule-based briefing engine",
            ],
            data={
                "visit_justified": True,
                "visit_priority": priority,
                "visit_approach": visit_approach,
                "pre_visit_briefing": briefing.get("pre_visit_briefing", ""),
                "talking_points": briefing.get("talking_points", []),
                "ots_decision": briefing.get("ots_decision", {}),
                "fallback": True,
            },
            escalate=True,
            escalation_reason="Field planning LLM unavailable",
        )


