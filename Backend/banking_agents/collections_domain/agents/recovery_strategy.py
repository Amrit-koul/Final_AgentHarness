"""
Recovery Strategy Agent
Determines overall recovery approach across all channels
"""
from typing import Dict, Any, Optional
from banking_agents.collections_domain.agents.base import BaseAgent, AgentDecision


class RecoveryStrategyAgent(BaseAgent):
    """
    Synthesizes all agent inputs into comprehensive recovery strategy
    """
    
    def __init__(self):
        super().__init__(
            agent_id="recovery_strategy",
            name="Recovery Strategy Agent",
        )
    
    async def reason(
        self,
        account_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> AgentDecision:
        """
        Synthesize comprehensive recovery strategy from all agents
        """
        # Extract decisions from previous agents
        persona_data = context.get("persona_discovery_decision", {}).get("data", {}) if context else {}
        behavioral_data = context.get("behavioral_prediction_decision", {}).get("data", {}) if context else {}
        nba_data = context.get("next_best_action_decision", {}).get("data", {}) if context else {}
        settlement_data = context.get("settlement_negotiation_decision", {}).get("data", {}) if context else {}
        field_data = context.get("field_visit_planner_decision", {}).get("data", {}) if context else {}
        
        persona = persona_data.get("persona", account_data.get("persona", "forgetful_payer"))
        dpd = account_data.get("dpd", 0)
        outstanding = account_data.get("outstanding", 0)
        
        system_prompt, prompt = self._render_prompt(
            "collections_recovery_strategy",
            persona=persona,
            dpd=dpd,
            outstanding=f"{outstanding:,}",
            persona_data=persona_data,
            behavioral_data=behavioral_data,
            nba_data=nba_data,
            settlement_data=settlement_data if settlement_data else "N/A",
            field_data=field_data if field_data else "N/A",
        )
        try:
            result = await self._llm_json_reason(prompt, system_prompt, temperature=0.3)
            
            confidence = float(result.get("confidence", 0.8))
            reasoning = result.get("reasoning", [])
            
            data = {
                "strategy_summary": result.get("strategy_summary", ""),
                "immediate_actions": result.get("immediate_actions", []),
                "short_term_plan": result.get("short_term_plan", {}),
                "long_term_plan": result.get("long_term_plan", {}),
                "success_metrics": result.get("success_metrics", {}),
                "cost_benefit_analysis": result.get("cost_benefit_analysis", {}),
                "monitoring_checkpoints": result.get("monitoring_checkpoints", []),
                "risk_flags": result.get("risk_flags", []),
                "raw_llm_output": result,
            }
            
            return AgentDecision(
                action="recovery_strategy_complete",
                confidence=confidence,
                reasoning=reasoning,
                data=data,
            )
        
        except Exception as e:
            return await self._fallback_strategy(account_data, nba_data, str(e))
    
    async def _fallback_strategy(
        self,
        account_data: Dict[str, Any],
        nba_data: Dict[str, Any],
        error: str,
    ) -> AgentDecision:
        """Fallback strategy synthesis"""
        action = nba_data.get("action", "continue_monitoring")
        channel = nba_data.get("WHEN", {}).get("channel", "whatsapp")
        
        data = {
            "strategy_summary": f"Execute {action} via {channel}",
            "immediate_actions": [
                {
                    "action": action,
                    "timeline": "within 24h",
                    "expected_outcome": "Response",
                }
            ],
            "fallback": True,
        }
        
        return AgentDecision(
            action="recovery_strategy_complete",
            confidence=0.6,
            reasoning=[
                "Fallback strategy synthesis",
                f"⚠️ LLM strategy failed: {error}",
                "Using NBA decision as primary strategy",
            ],
            data=data,
            escalate=True,
            escalation_reason="Strategy synthesis LLM unavailable",
        )


