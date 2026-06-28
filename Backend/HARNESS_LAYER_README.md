# Agent Harness Layer

`Backend/agent_harness` is the generic reusable framework layer for the demo. It should stay domain-blind.

It provides the common mechanics needed to onboard and operate agents:

- Contracts
- Adapters
- Registry
- Config loading
- Policy abstractions
- Persistence
- Tracing
- Redaction
- Kill switch primitives
- Degradation monitoring
- Memory/state abstractions
- Typed exceptions

---

## What belongs in `agent_harness`

Use this package for reusable platform code:

```text
agent_harness/
├─ contracts.py
├─ contract_validator.py
├─ base_adapter.py
├─ adapters.py
├─ registry.py
├─ plugin_loader.py
├─ config_loader.py
├─ policy.py
├─ store.py
├─ tracing.py
├─ trace_provider.py
├─ redaction.py
├─ kill_switch.py
├─ degradation_monitor.py
├─ memory.py
├─ state.py
└─ exceptions.py
```

The harness must not contain:

- Collections business rules.
- Policy Assistant prompts.
- Loan Assessment calculations.
- Bank-specific YAML paths.
- Bank-specific guardrail decisions.
- FastAPI demo routes.

---

## How the bank app uses it

`banking_agents/harness/runtime.py` composes the harness into a bank runtime:

```python
self.store = ControlPlaneStore(DATA_DIR / "control_plane.db")
self.registry = AgentRegistry(self.services)
self.registry.load(CONFIG_DIR / "agents")
self.policy = BankPolicyEngine(...)
self.kill_switch = BankKillSwitchService(...)
self.degradation = DegradationMonitor(...)
```

The generic harness supplies the reusable mechanics. The bank runtime supplies business policy and domain-specific execution.

---

## Adapter model

Adapters let different kinds of agents sit behind one contract-driven invocation interface.

Supported adapter styles include:

- `python_function`
- `langgraph`
- `rest_api`
- `external_webhook`

This makes future agent onboarding config-driven:

1. Add a YAML manifest.
2. Point to an entrypoint or endpoint.
3. Declare schema, permissions and guardrails.
4. Let the registry and adapter factory handle runtime invocation.

---

## Runtime trace lifecycle

`agent_harness/tracing.py` is designed so each API invocation creates one root trace. Internal spans only attach to an active parent; they do not create independent LangSmith root traces.

Example Collections trace:

```text
Collections Workflow Demo Run
├─ load_agent_contract
├─ check_agent_status
├─ pre_policy_check
│  ├─ pre_guardrail_check
│  └─ audit_persist
├─ audit_persist
├─ adapter_invoke
│  └─ python_function_call
│     └─ Collections Workflow
│        ├─ load_account_context
│        ├─ account_data_normalization
│        ├─ five_score_engine
│        ├─ persona_engine
│        ├─ claim_analysis
│        ├─ trust_evaluator
│        ├─ trust_gate
│        ├─ policy_routing
│        ├─ next_best_action
│        ├─ human_approval_decision
│        └─ response_normalization
├─ post_guardrail_check
├─ audit_persist
├─ degradation_evaluation
└─ kill_switch_evaluation
```

---

## Persistence model

`agent_harness/store.py` persists control-plane data into SQLite for the local demo:

- agent runs
- observability events
- policy decisions
- guardrail events
- kill-switch events
- degradation events

The store is currently local/demo-oriented. For production, move this to a managed database with migrations, retention, encryption, and access controls.

---

## Redaction

`agent_harness/redaction.py` sanitizes sensitive values before tracing/logging. It is not a replacement for full enterprise DLP, but it prevents obvious PII/secrets from being pushed into observability payloads during the demo.

---

## Production hardening still required

Before real deployment, add:

- Authentication and RBAC.
- Restricted CORS.
- Centralized durable runtime state.
- Managed audit database.
- Secret scanning and environment validation.
- Rate limiting and request size limits.
- Stronger DLP/PII controls.
- CI tests and deployment packaging.

