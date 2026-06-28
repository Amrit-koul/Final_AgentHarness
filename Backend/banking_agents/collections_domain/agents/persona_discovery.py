"""
Persona Discovery Agent
Analyzes account signals and discovers persona through LLM reasoning
Replaces deterministic persona_engine.py with agentic workflow
"""
from typing import Dict, Any, Optional, List
from banking_agents.collections_domain.agents.base import BaseAgent, AgentDecision
class PersonaDiscoveryAgent(BaseAgent):
    """
    Discovers and classifies borrower personas using multi-signal analysis
    Uses LLM reasoning instead of hardcoded rules
    """
    
    def __init__(self):
        super().__init__(
            agent_id="persona_discovery",
            name="Persona Discovery Agent",
        )
    
    def _build_signal_summary(self, account_data: Dict[str, Any]) -> str:
        """Build comprehensive signal summary for LLM"""
        scores = account_data.get("scores", {})
        
        signals = []
        signals.append(f"- Account ID: {account_data.get('id')}")
        signals.append(f"- Name: {account_data.get('name')}")
        signals.append(f"- Age: {account_data.get('age')}, Job: {account_data.get('job')}")
        signals.append(f"- Days Past Due (DPD): {account_data.get('dpd', 0)}")
        signals.append(f"- Product: {account_data.get('product')}")
        signals.append(f"- EMI: ₹{account_data.get('emi', 0):,}")
        signals.append(f"- Outstanding: ₹{account_data.get('outstanding', 0):,}")
        signals.append(f"- CIBIL Score: {account_data.get('cibil', 'N/A')}")
        signals.append(f"\nComposite Scores:")
        signals.append(f"- Ability to Pay: {scores.get('ability_to_pay', 'N/A')}/100")
        signals.append(f"- Intent to Pay: {scores.get('intent_to_pay', 'N/A')}/100")
        signals.append(f"- Trust Score: {scores.get('trust_score', scores.get('trust', 'N/A'))}/100")
        signals.append(f"- Contactability: {scores.get('contactability', 'N/A')}/100")
        signals.append(f"- Self-cure Probability: {scores.get('self_cure_probability', scores.get('self_cure', 'N/A'))}/100")
        
        # Call history
        if account_data.get("call_history"):
            signals.append(f"\nInteraction History:")
            for h in account_data.get("call_history", [])[:5]:
                signals.append(f"- {h}")
        
        # Recent notes
        if account_data.get("notes"):
            signals.append(f"\nRecent Notes:")
            for note in account_data.get("notes", [])[-3:]:
                signals.append(f"- {note.get('summary', note.get('notes', ''))}")
        
        # Persona history (if re-classifying)
        if account_data.get("persona_history"):
            signals.append(f"\nPersona History:")
            for h in account_data.get("persona_history", [])[-3:]:
                signals.append(f"- {h.get('from')} → {h.get('to')}: {h.get('reason', '')}")
        
        return "\n".join(signals)
    
    async def reason(
        self,
        account_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> AgentDecision:
        """
        Discover persona deterministically through the ScoringEngine.
        """
        from banking_agents.collections_domain.services.intelligence.pipeline import run_intelligence_pipeline

        pipeline = run_intelligence_pipeline(account_data, current_persona=account_data.get("persona"))
        persona_result = pipeline["persona"]
        persona = persona_result.get("segment", "unknown_insufficient_data")

        reasoning = persona_result.get("reasoning", [])
        reasoning.append(f"Active signals: {', '.join(persona_result.get('active_signals', []))}")

        data = {
            "persona": persona,
            "persona_label": persona.replace("_", " ").title(),
            "primary_indicators": persona_result.get("active_signals", []),
            "confidence_band": persona_result.get("confidence_band"),
            "trust_gate": pipeline.get("trust_gate"),
            "policy": pipeline.get("policy"),
        }

        return AgentDecision(
            action="persona_classified",
            confidence=persona_result.get("confidence", 0.0),
            reasoning=reasoning,
            data=data,
            escalate=pipeline.get("policy", {}).get("policy_escalate", False),
            escalation_reason=pipeline.get("policy", {}).get("block_reason"),
            next_agent="behavioral_prediction",
        )
    
    async def _fallback_classification(
        self,
        account_data: Dict[str, Any],
        error: str,
    ) -> AgentDecision:
        # No longer needed since it's deterministic, but kept for interface compatibility
        return await self.reason(account_data, None)


