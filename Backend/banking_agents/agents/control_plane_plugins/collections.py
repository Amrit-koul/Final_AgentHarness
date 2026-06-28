"""Thin control-plane wrapper around the bank-owned Collections domain."""
from banking_agents.collections_domain import run_account_workflow


def run_collections_workflow(payload, trace_id=""):
    if not isinstance(payload, dict) or not payload.get("account_id"):
        raise ValueError("account_id is required")
    result = run_account_workflow(
        account_id=payload["account_id"],
        override_persona=payload.get("override_persona"),
        new_claims=payload.get("new_claims"),
    )
    steps = [
        {"step": "account_context", "status": "completed", "summary": f"Loaded {result['account_id']}"},
        {"step": "five_score_engine", "status": "completed", "summary": "Calculated five evidence scores"},
        {"step": "persona_classification", "status": "completed", "summary": result.get("persona")},
        {"step": "trust_gate", "status": "completed", "summary": result.get("trust_gate", {}).get("status")},
        {"step": "policy_and_nba", "status": "completed", "summary": result.get("next_best_action")},
    ]
    from banking_agents.harness.runtime import control_plane
    for step in steps:
        control_plane.store.add_event("COLLECTIONS_STEP_COMPLETED", trace_id, "collections_workflow_agent", step)
    return {**result, "workflow_status": "completed", "execution_trace": steps, "trace_id": trace_id}
