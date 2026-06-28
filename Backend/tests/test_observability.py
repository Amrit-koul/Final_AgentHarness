import os
import asyncio
import unittest
from unittest.mock import Mock, patch

from agent_harness.redaction import safe_summary
from agent_harness.tracing import TraceManager
from banking_agents.agents.domain.loan_eligibility_rag_agent import LoanEligibilityRAGAgent
from banking_agents.agents.domain.policy_rag_agent import PolicyRAGAgent
from banking_agents.communication.message import CustomerLoanProfile
from banking_agents.prompts import PromptManager


class _Completion:
    def __init__(self, text):
        self.choices = [Mock(message=Mock(content=text))]


class _FakeRun:
    def add_metadata(self, _metadata): pass
    def add_tags(self, _tags): pass
    def end(self, **_kwargs): pass


class _FakeTraceContext:
    def __enter__(self): return _FakeRun()
    def __exit__(self, *_args): return None


class ObservabilityTests(unittest.TestCase):
    def test_redaction_masks_sensitive_values(self):
        safe = safe_summary({"account_id": "ACC-1", "name": "Customer Name", "phone": "9876543210", "query": "private question", "authorization": "Bearer secret"})
        self.assertEqual(safe["account_id"], "ACC-1")
        self.assertEqual(safe["name"], "[REDACTED_NAME]")
        self.assertEqual(safe["phone"], "[REDACTED]")
        self.assertEqual(safe["query"], "[REDACTED]")

    def test_tracing_is_noop_without_configuration(self):
        old = os.environ.pop("LANGCHAIN_API_KEY", None)
        try:
            tracer = TraceManager()
            with tracer.trace("No-op Trace Validation", inputs={"phone": "9876543210"}) as span:
                span.set_output({"ok": True})
        finally:
            if old is not None: os.environ["LANGCHAIN_API_KEY"] = old

    def test_local_prompt_loading(self):
        prompt = PromptManager().get_prompt("system", "v1")
        self.assertEqual(prompt.source, "local")
        self.assertEqual(prompt.version, "v1")
        self.assertIn("policy", prompt.template.lower())

    def test_langsmith_prompt_override_and_local_fallback(self):
        with patch.dict(os.environ, {"LANGSMITH_PROMPTS_ENABLED": "true", "LANGCHAIN_API_KEY": "test-key"}, clear=False):
            with patch("langsmith.Client.pull_prompt", return_value=Mock(template="Hub template")):
                prompt = PromptManager(environment="staging").get_prompt("system", "v1")
                self.assertEqual((prompt.source, prompt.template), ("langsmith", "Hub template"))
            with patch("langsmith.Client.pull_prompt", side_effect=ConnectionError("offline")):
                fallback = PromptManager(environment="staging").get_prompt("system", "v1")
                self.assertEqual(fallback.source, "local")

    def test_policy_agent_uses_versioned_prompt(self):
        names = []
        agent = object.__new__(PolicyRAGAgent)
        agent.model_id, agent.fallback_model_id, agent.rag_guard = "primary", "fallback", None
        agent.rag = Mock(query=Mock(return_value={"documents": [["KYC requires verification."]], "metadatas": [[{"source": "kyc.md"}]], "distances": [[0.1]]}))
        agent.client = Mock(); agent.client.chat.completions.create.return_value = _Completion("Direct answer\nSources: kyc.md")
        with patch.dict(os.environ, {"LANGCHAIN_TRACING_V2": "true", "LANGCHAIN_API_KEY": "test-key"}, clear=False), patch("langsmith.run_helpers.trace", side_effect=lambda name, **_kwargs: (names.append(name) or _FakeTraceContext())):
            with TraceManager().trace("Policy Assistant Demo Run"):
                answer = agent.answer("What are KYC requirements?", "session-test")
        self.assertIn("kyc.md", answer)
        self.assertTrue({"Policy Assistant Demo Run", "policy_assistant_flow", "receive_policy_query", "classify_intent", "retrieve_policy_context", "prompt_template_load", "prompt_render", "generate_policy_answer", "final_answer"}.issubset(names))

    def test_loan_agent_structured_path(self):
        names = []
        agent = object.__new__(LoanEligibilityRAGAgent)
        agent.model_id, agent.rag_guard = "loan-model", None
        agent.rag = Mock(query=Mock(return_value={"documents": [["Policy threshold source."]], "metadatas": [[{"source": "loan.md"}]], "distances": [[0.1]]}))
        agent.client = Mock(); agent.client.chat.completions.create.return_value = _Completion("Indicative outcome: Refer for Review\nPolicy sources: loan.md")
        profile = CustomerLoanProfile(loan_type="PERSONAL", applicant_age=35, monthly_income=100000, employment_type="SALARIED", cibil_score=720, existing_emi_amount=10000, loan_amount_requested=500000, loan_tenure_months=36, annual_interest_rate_percent=12)
        with patch.dict(os.environ, {"LANGCHAIN_TRACING_V2": "true", "LANGCHAIN_API_KEY": "test-key"}, clear=False), patch("langsmith.run_helpers.trace", side_effect=lambda name, **_kwargs: (names.append(name) or _FakeTraceContext())):
            with TraceManager().trace("Loan Assessment Demo Run"):
                answer = agent.answer("Assess the application", profile, "session-test")
        self.assertIn("Refer for Review", answer)
        self.assertTrue({"Loan Assessment Demo Run", "receive_loan_application", "validate_application_fields", "compute_eligibility_factors", "risk_assessment", "policy_rule_check", "prompt_template_load", "prompt_render", "generate_recommendation", "final_loan_decision"}.issubset(names))

    def test_control_and_collections_trace_names(self):
        names = []
        def fake_trace(name, **_kwargs):
            names.append(name)
            return _FakeTraceContext()
        with patch.dict(os.environ, {"LANGCHAIN_TRACING_V2": "true", "LANGCHAIN_API_KEY": "test-key"}, clear=False), patch("langsmith.run_helpers.trace", side_effect=fake_trace):
            from banking_agents.harness.runtime import control_plane
            control_plane.registry.set_status("collections_workflow_agent", "active")
            result = asyncio.run(control_plane.invoke("collections_workflow_agent", {"account_id": "ACC-DEMO-01"}, trace_name="Collections Workflow Demo Run", request_source="demo_endpoint"))
        self.assertEqual(result["result"]["workflow_status"], "completed")
        expected = {"Collections Workflow Demo Run", "load_agent_contract", "check_agent_status", "pre_policy_check", "pre_guardrail_check", "audit_persist", "adapter_invoke", "python_function_call", "Collections Workflow", "five_score_engine", "ability_to_pay_score", "intent_to_pay_score", "trust_score", "contactability_score", "self_cure_score", "claim_analysis", "trust_evaluator", "persona_engine", "trust_gate", "policy_routing", "next_best_action", "human_approval_decision", "response_normalization", "post_guardrail_check", "degradation_evaluation", "kill_switch_evaluation"}
        self.assertTrue(expected.issubset(set(names)), expected.difference(names))


if __name__ == "__main__":
    unittest.main()
