"""
Agent Orchestrator using LangGraph
Manages agent workflows, inter-agent communication, and decision routing.
"""
from typing import Any, Dict, Optional, TypedDict

from langgraph.graph import StateGraph, START, END

from banking_agents.collections_domain.agents.next_best_action import NextBestActionAgent
from banking_agents.collections_domain.services.intelligence.account_context import enrich_account_data
from banking_agents.collections_domain.services.intelligence.pipeline import run_intelligence_pipeline
from banking_agents.collections_domain.services.intelligence.scoring_engine import scores_to_flat
from banking_agents.collections_domain.workflows.post_call_pipeline import PostCallPipeline


class AgentState(TypedDict):
    account_id: str
    account_data: Dict[str, Any]
    context: Dict[str, Any]
    scores: Optional[Dict[str, Any]]
    persona_decision: Optional[Dict[str, Any]]
    trust_gate: Optional[Dict[str, Any]]
    policy: Optional[Dict[str, Any]]
    nba_decision: Optional[Dict[str, Any]]
    escalate: bool


class AgentOrchestrator:
    """LangGraph orchestrator for pre-call and post-call intelligence."""

    def __init__(self):
        self.n_agent = NextBestActionAgent()
        self.post_call = PostCallPipeline()
        self.graph = self._build_graph()

    def _build_graph(self):
        workflow = StateGraph(AgentState)

        workflow.add_node("intelligence", self._intelligence_node)
        workflow.add_node("nba_engine", self._nba_node)

        workflow.add_edge(START, "intelligence")
        workflow.add_edge("intelligence", "nba_engine")
        workflow.add_edge("nba_engine", END)

        return workflow.compile()

    async def _intelligence_node(self, state: AgentState):
        acc = state["account_data"]
        pipeline = run_intelligence_pipeline(acc, current_persona=acc.get("persona"))

        context = state.get("context", {})
        persona = pipeline["persona"]
        context["persona_discovery_decision"] = {
            "data": {
                "persona": persona["segment"],
                "persona_label": persona["segment"].replace("_", " ").title(),
            },
            "confidence": persona["confidence"],
            "reasoning": persona.get("reasoning", []),
            "confidence_band": persona.get("confidence_band"),
        }

        flat_scores = scores_to_flat(pipeline["scores"])
        acc_with_scores = {**acc, "scores": flat_scores}

        return {
            "scores": pipeline["scores"],
            "persona_decision": persona,
            "trust_gate": pipeline["trust_gate"],
            "policy": pipeline["policy"],
            "account_data": acc_with_scores,
            "context": context,
        }

    async def _nba_node(self, state: AgentState):
        acc = state["account_data"]
        context = state.get("context", {})

        policy = state.get("policy", {})
        if policy.get("policy_nba_routing"):
            context["policy_routing"] = policy["policy_nba_routing"]

        n_dec = await self.n_agent.reason(acc, context)

        return {
            "nba_decision": n_dec.data,
            "escalate": state.get("escalate", False) or n_dec.escalate or policy.get("policy_escalate", False),
        }

    async def execute_pre_call(self, account_data: Dict[str, Any]) -> Dict[str, Any]:
        """Pre-call context package: scores, persona, trust gate, policy, NBA."""
        initial_state = {
            "account_id": account_data.get("id"),
            "account_data": account_data,
            "context": {},
            "escalate": False,
        }
        final_state = await self.graph.ainvoke(initial_state)

        persona = final_state.get("persona_decision", {})
        return {
            "scores": final_state.get("scores"),
            "persona_decision": {
                "persona": persona.get("segment"),
                "persona_label": persona.get("segment", "").replace("_", " ").title(),
                "confidence": persona.get("confidence"),
                "confidence_band": persona.get("confidence_band"),
                "reasoning": persona.get("reasoning", []),
                "active_signals": persona.get("active_signals", []),
            },
            "trust_gate": final_state.get("trust_gate"),
            "policy": final_state.get("policy"),
            "nba_decision": final_state.get("nba_decision"),
            "escalate": final_state.get("escalate", False),
            "context": final_state.get("context", {}),
        }

    async def execute_graph(self, account_data: Dict[str, Any]) -> Dict[str, Any]:
        """Backward-compatible alias used by main.py endpoints."""
        return await self.execute_pre_call(account_data)

    async def execute_post_call(
        self,
        account_data: Dict[str, Any],
        call_evidence: Dict[str, Any],
        db=None,
        account_row=None,
    ) -> Dict[str, Any]:
        return await self.post_call.run(
            account_data,
            call_evidence,
            db=db,
            account_row=account_row,
            persist=db is not None,
        )


_orchestrator: Optional[AgentOrchestrator] = None


def get_orchestrator() -> AgentOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = AgentOrchestrator()
    return _orchestrator


