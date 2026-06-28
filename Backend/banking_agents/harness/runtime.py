"""Thin bank-specific bootstrap for the reusable control-plane framework."""
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
import os
import uuid

from agent_harness.config_loader import load_named_config
from agent_harness.degradation_monitor import DegradationMonitor
from agent_harness.registry import AgentRegistry, agent_registry as legacy_registry
from agent_harness.store import ControlPlaneStore
from agent_harness.redaction import contract_summary, safe_summary
from agent_harness.trace_provider import LangSmithTraceProvider, LocalTraceProvider
from agent_harness.tracing import get_tracer
from agent_harness.usage import UsageMeter, configure_usage_meter, usage_context
from agent_harness.primitives import HookDispatcher, PrimitiveCatalog
from banking_agents.policy.control_plane import BankKillSwitchService, BankPolicyEngine
from banking_agents.policy.tool_authorization import ToolAuthorizationService


BANKING_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = BANKING_ROOT / "config"
DATA_DIR = BANKING_ROOT.parent / "data"


class Services: pass


class ControlPlaneRuntime:
    def __init__(self):
        self.store = ControlPlaneStore(DATA_DIR / "control_plane.db")
        self.services = Services(); self.services.store = self.store; self.services.tracer = get_tracer(); self.services.trace_provider = LangSmithTraceProvider(LocalTraceProvider(self.store), self.services.tracer)
        self.services.usage_meter = UsageMeter(self.store, CONFIG_DIR / "model_pricing.yaml")
        configure_usage_meter(self.services.usage_meter)
        self.registry = AgentRegistry(self.services); self.registry.load(CONFIG_DIR / "agents")
        self.primitives = PrimitiveCatalog(CONFIG_DIR, BANKING_ROOT / "prompts", self.registry)
        self.hooks = HookDispatcher(self.store, self.primitives)
        guardrail_config = load_named_config(CONFIG_DIR, "guardrails.yaml", {}) or {}
        self.policy = BankPolicyEngine(self.registry, self.store, guardrail_config.get("business_guardrails", {}))
        self.kill_switch = BankKillSwitchService(self.registry, self.store)
        degradation_rules = load_named_config(CONFIG_DIR, "degradation_rules.yaml", {}) or {}
        self.degradation = DegradationMonitor(self.registry, self.store, self.kill_switch, degradation_rules)
        self.services.policy = self.policy
        action_policies = load_named_config(CONFIG_DIR, "banking_action_policies.yaml", {}) or {}
        
        # Initialize LLM Risk Judge lazily without failing if not configured
        from banking_agents.policy.llm_risk_judge import LLMRiskJudge
        self.llm_judge = LLMRiskJudge(CONFIG_DIR, BANKING_ROOT / "prompts")
        
        self.tool_authorization = ToolAuthorizationService(
            self.registry, self.store, self.primitives, action_policies, self.policy.guardrails, self.llm_judge
        )
        self.services.tool_authorization = self.tool_authorization

    async def invoke(self, agent_id, payload, action="invoke", trace_id=None, *, trace_name=None, request_source="generic_invoke"):
        trace_id = trace_id or str(uuid.uuid4())
        contract = self.registry.get_contract(agent_id)
        status_before = contract.status.value
        session_id = payload.get("session_id") or payload.get("user_id")
        metadata = {
            **contract_summary(contract), "trace_id": trace_id, "status_before": status_before,
            "status_after": status_before, "request_source": request_source, "environment": os.getenv("APP_ENV", "local_demo"),
            "client": "Bandhan Bank", "session_id": session_id, "backend_version": os.getenv("BACKEND_VERSION", "local"),
        }
        tags = ["agent_harness", "control_plane", "banking", agent_id, contract.business_function, contract.adapter_type]
        if request_source == "demo_endpoint": tags.append("demo")
        run_name = trace_name or f"Agent Control Plane Run — {agent_id}"
        tracer = self.services.tracer
        with tracer.trace(run_name, inputs=safe_summary(payload), metadata=metadata, tags=tags) as root:
            try:
                self.hooks.emit("pre_invoke", {"trace_id": trace_id, "agent_id": agent_id, "request_source": request_source})
                with tracer.span("load_agent_contract", inputs={"agent_id": agent_id}, metadata={"trace_id": trace_id}) as span:
                    span.set_output(contract_summary(contract))
                with tracer.span("check_agent_status", inputs={"agent_id": agent_id}) as span:
                    span.set_output({"status": contract.status.value})
                policy_context = {**payload, "input_text": str(safe_summary(payload))}
                with tracer.span("pre_policy_check", inputs={"agent_id": agent_id, "action": action, "data_scope": payload.get("data_scope")}) as span:
                    policy = self.policy.check(agent_id, action, policy_context, trace_id)
                    span.set_output({"decision": policy.decision, "reason": policy.reason, "human_approval_required": policy.human_approval_required})
                if policy.decision != "ALLOW":
                    self.hooks.emit("on_policy_block", {"trace_id": trace_id, "agent_id": agent_id, "reason": policy.reason})
                    injection = any(event["guardrail_id"] == "GRD-INJECT-001" for event in policy.guardrail_events)
                    if not injection: self.registry.record_block(agent_id)
                    with tracer.span("kill_switch_evaluation", inputs={"critical_events": policy.guardrail_events}) as span:
                        actions = [result for event in policy.guardrail_events if (result := self.kill_switch.apply_guardrail(agent_id, event))]
                        span.set_output({"action": actions or "no_action"})
                    with tracer.span("degradation_evaluation", inputs={"agent_id": agent_id}) as span:
                        result = None if injection else self.degradation.evaluate(agent_id)
                        span.set_output({"status_change": result or "no_change"})
                    status = self.registry.get_contract(agent_id).status.value
                    reason = "agent_quarantined" if status == "quarantined" else "agent_disabled" if status == "disabled" else policy.reason
                    evidence = {
                        "decision": policy.decision, "reason": reason, "agent_id": agent_id,
                        "status": status, "adapter_invoked": False, "trace_id": trace_id,
                        "policy_decision": policy.to_dict(),
                    }
                    self.store.add_event("INVOCATION_BLOCKED", trace_id, agent_id, evidence)
                    self.hooks.emit("on_policy_block", {**evidence, "reason": policy.reason})
                    root.set_output(evidence)
                    return evidence

                if contract.status.value == "review" and payload.get("human_override", {}).get("approved"):
                    self.store.add_event("HUMAN_OVERRIDE_USED", trace_id, agent_id, {"approved_by": payload["human_override"].get("approved_by"), "reason": payload["human_override"].get("reason"), "status": "review"})

                adapter = self.registry.get_adapter(agent_id)
                validated = adapter.validate_input(payload)
                started_at = datetime.now(timezone.utc).isoformat(); started = perf_counter()
                with tracer.span("audit_persist", inputs={"event": "RUN_STARTED", "trace_id": trace_id}) as span:
                    self.store.start_run(trace_id, agent_id, validated, started_at)
                    self.services.trace_provider.emit("RUN_STARTED", trace_id, agent_id, {"trace_id": trace_id})
                    span.set_output({"stored": True, "trace_id": trace_id})
                try:
                    with tracer.span("adapter_invoke", inputs={"adapter_type": contract.adapter_type, "payload": safe_summary(validated)}, metadata={"entrypoint": contract.entrypoint}) as span:
                        with usage_context(trace_id=trace_id, run_id=trace_id, agent_id=agent_id, agent_name=contract.name, business_function=contract.business_function):
                            result = await adapter.invoke_async(validated, trace_id)
                        latency = int((perf_counter() - started) * 1000)
                        # Deterministic and external agents do not expose LLM usage; retain useful latency telemetry.
                        if not self.store.query("SELECT usage_id FROM usage_events WHERE trace_id=? LIMIT 1", (trace_id,)):
                            self.services.usage_meter.record_usage({"trace_id": trace_id, "run_id": trace_id, "agent_id": agent_id, "agent_name": contract.name, "business_function": contract.business_function, "provider": "external" if contract.adapter_type in {"rest_api", "webhook"} else "unknown", "model": "unknown", "usage_source": "unknown", "estimated_method": "unavailable", "latency_ms": latency, "status": "success", "metadata": {"adapter_type": contract.adapter_type}})
                        self.hooks.emit("on_cost_record", {"trace_id": trace_id, "agent_id": agent_id})
                        span.set_output({"success": True, "latency_ms": latency, "response": safe_summary(result)})
                    with tracer.span("post_guardrail_check", inputs={"output": safe_summary(result)}) as span:
                        post_policy = self.policy.check(agent_id, "output_review", {"output_text": str(safe_summary(result))}, trace_id)
                        span.set_output({"decision": post_policy.decision, "reason": post_policy.reason, "guardrails": post_policy.guardrail_events})
                    if post_policy.decision == "BLOCK":
                        raise PermissionError(post_policy.reason)
                    confidence = result.get("confidence") if isinstance(result, dict) else None
                    with tracer.span("audit_persist", inputs={"event": "RUN_COMPLETED", "trace_id": trace_id}) as span:
                        self.store.finish_run(trace_id, "completed", datetime.now(timezone.utc).isoformat(), latency, result, confidence=confidence)
                        self.registry.record_run(agent_id, True, latency, confidence)
                        self.services.trace_provider.emit("RUN_COMPLETED", trace_id, agent_id, {"latency_ms": latency})
                        span.set_output({"stored": True, "status": "completed"})
                    with tracer.span("degradation_evaluation", inputs={"agent_id": agent_id, "latency_ms": latency, "confidence": confidence}) as span:
                        degradation = self.degradation.evaluate(agent_id)
                        span.set_output({"status_change": degradation or "no_change"})
                    with tracer.span("kill_switch_evaluation", inputs={"critical_events": []}) as span:
                        span.set_output({"action": "no_action"})
                    response = {"trace_id": trace_id, "agent_id": agent_id, "result": result}
                    self.hooks.emit("post_invoke", {"trace_id": trace_id, "agent_id": agent_id, "status": "completed"})
                    root.set_output(response)
                    return response
                except Exception as exc:
                    latency = int((perf_counter() - started) * 1000)
                    # External/deterministic adapters may fail before they can report model
                    # usage. Preserve a failed latency record so vendor outages remain visible.
                    if not self.store.query("SELECT usage_id FROM usage_events WHERE trace_id=? LIMIT 1", (trace_id,)):
                        self.services.usage_meter.record_usage({"trace_id": trace_id, "run_id": trace_id, "agent_id": agent_id, "agent_name": contract.name, "business_function": contract.business_function, "provider": "external" if contract.adapter_type in {"rest_api", "external_webhook"} else "unknown", "model": "unknown", "usage_source": "unknown", "estimated_method": "unavailable", "latency_ms": latency, "status": "failed", "metadata": {"adapter_type": contract.adapter_type, "error_type": type(exc).__name__}})
                    with tracer.span("audit_persist", inputs={"event": "RUN_FAILED", "trace_id": trace_id}) as span:
                        self.store.finish_run(trace_id, "failed", datetime.now(timezone.utc).isoformat(), latency, error=str(exc))
                        self.registry.record_run(agent_id, False, latency)
                        self.services.trace_provider.emit("RUN_FAILED", trace_id, agent_id, {"error": str(exc)})
                        span.set_output({"stored": True, "status": "failed"})
                    with tracer.span("degradation_evaluation", inputs={"agent_id": agent_id, "failed": True}) as span:
                        span.set_output({"status_change": self.degradation.evaluate(agent_id) or "no_change"})
                    raise
            finally:
                root.add_metadata({"status_after": self.registry.get_contract(agent_id).status.value})


def _register_existing_runtime_agents():
    definitions = {
        "orchestrator": ("Orchestrator Agent", "reusable", False), "classify_intent": ("Intent Classifier", "reusable", False), "decompose_task": ("Task Decomposer", "reusable", False),
        "consult_policy_expert": ("Policy RAG Agent", "domain", True), "consult_loan_expert": ("Loan Eligibility Agent", "domain", True),
    }
    for name, (display, kind, killable) in definitions.items(): legacy_registry.register_runtime_agent(name, {"display_name": display, "type": kind, "model": "configured-by-banking-app", "description": display, "killable": killable, "enabled": True})


_register_existing_runtime_agents()
control_plane = ControlPlaneRuntime()
