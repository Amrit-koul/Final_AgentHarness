"""Adapters around existing agents. Their business logic remains unchanged."""
from banking_agents.communication.message import CustomerLoanProfile


def policy_assistant(payload, trace_id=""):
    from banking_agents import main
    from banking_agents.harness.runtime import control_plane
    main._require_runtime()
    query = payload["query"]
    agent = main.orchestrator.tool_instances["consult_policy_expert"]
    session_id = payload.get("session_id") or trace_id
    result = agent.answer_with_evaluation(query, session_id=session_id, trace_id=trace_id)
    answer = result["answer"]
    control_plane.store.add_rag_evaluation(trace_id, "policy_assistant_agent", query, result["rag_evaluation"])
    control_plane.store.add_event("POLICY_RESPONSE_GENERATED", trace_id, "policy_assistant_agent", {"query_length": len(query), "answer_length": len(answer), "evaluator_method": result["rag_evaluation"]["evaluator_method"]})
    return {**result, "session_id": session_id, "confidence": 1.0 if answer else 0.0}


def loan_assessment(payload, trace_id=""):
    from banking_agents import main
    from banking_agents.harness.runtime import control_plane
    main._require_runtime()
    profile = payload.get("profile")
    profile_obj = CustomerLoanProfile(**profile) if isinstance(profile, dict) else profile
    query = payload.get("query") or "Assess this applicant against the bank loan eligibility policy."
    agent = main.loan_agent
    session_id = payload.get("session_id") or trace_id
    result = agent.answer_with_evaluation(query, loan_profile=profile_obj, session_id=session_id, trace_id=trace_id)
    answer = result["eligibility_assessment"]
    control_plane.store.add_rag_evaluation(trace_id, "loan_assessment_agent", query, result["rag_evaluation"])
    control_plane.store.add_event("LOAN_ASSESSMENT_GENERATED", trace_id, "loan_assessment_agent", {"loan_type": profile_obj.loan_type, "assessment_length": len(answer), "evaluator_method": result["rag_evaluation"]["evaluator_method"]})
    return {**result, "profile_used": profile_obj.model_dump() if hasattr(profile_obj, "model_dump") else profile, "confidence": 1.0 if answer else 0.0}
