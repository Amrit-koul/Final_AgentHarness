# Backend Architecture Structure

This document captures the current backend boundary after the control-plane consolidation.

---

## Core boundary

```text
Backend/agent_harness   -> generic reusable framework
Backend/banking_agents  -> bank-specific application and agents
```

Dependency direction:

```text
banking_agents imports agent_harness
agent_harness does not import banking_agents
```

This boundary is intentional. The harness should be reusable for another BFSI client or business domain. Banking-specific logic belongs in `banking_agents`.

---

## Generic framework: `Backend/agent_harness`

The generic layer owns framework concepts only:

| Area | Files |
|---|---|
| Agent contract model | `contracts.py`, `contract_validator.py` |
| Adapter interface and built-ins | `base_adapter.py`, `adapters.py` |
| Registry and plugin loading | `registry.py`, `plugin_loader.py` |
| Config loading | `config_loader.py` |
| Generic policy abstractions | `policy.py` |
| Persistence | `store.py` |
| Tracing and redaction | `tracing.py`, `trace_provider.py`, `redaction.py` |
| Kill switch / degradation | `kill_switch.py`, `degradation_monitor.py` |
| State and memory abstractions | `state.py`, `memory.py` |
| Exceptions | `exceptions.py` |
| Legacy/facade modules | `audit.py`, `observability.py`, `catalog.py`, `fleet.py`, `graph.py`, `control.py`, `governance.py` |

The generic layer must not import:

- Collections code
- Policy Assistant implementation
- Loan Assessment implementation
- Bandhan-specific YAML
- Banking guardrail logic
- Banking data models

---

## Bank-specific app: `Backend/banking_agents`

The bank layer owns:

- FastAPI app and routes.
- Policy Assistant.
- Loan Assessment / Loan Eligibility.
- Intent Classifier, Task Decomposer and legacy Orchestrator components.
- Collections Intelligence workflow.
- Bank-specific YAML manifests.
- Bank-specific guardrails and policy composition.
- Bank prompts and prompt manager usage.
- Domain data and local demo seed data.

Important files:

```text
banking_agents/main.py
banking_agents/control_routes.py
banking_agents/harness/runtime.py
banking_agents/policy/control_plane.py
banking_agents/config/agents/*.yaml
banking_agents/agents/control_plane_plugins/*.py
banking_agents/agents/domain/*.py
banking_agents/collections_domain/
banking_agents/prompts/
banking_agents/guardrails/
```

---

## Bank runtime composition

`banking_agents/harness/runtime.py` is intentionally a thin bank-specific composition layer. It wires together:

- `ControlPlaneStore`
- `AgentRegistry`
- YAML manifests under `banking_agents/config/agents`
- `BankPolicyEngine`
- `BankKillSwitchService`
- `DegradationMonitor`
- `TraceManager`

It should not duplicate generic registry, adapter, policy, tracing, or store logic. It composes those generic services with bank-specific policies and routes.

---

## YAML-driven onboarding

Agent manifests live here:

```text
Backend/banking_agents/config/agents/
```

Current manifests include:

```text
policy_assistant.yaml
loan_assessment.yaml
collections_workflow.yaml
sample_external_rest_agent.yaml
sample_github_wrapped_agent.yaml
```

The manifest declares:

- `agent_id`
- `name`
- `business_function`
- `adapter_type`
- `entrypoint` or endpoint metadata
- input/output/state/memory schemas
- skills and tools
- prompts
- policy permissions
- guardrails
- observability hooks
- status

---

## Collections domain

Collections is a bank-specific plugin and domain workflow.

Key paths:

```text
banking_agents/agents/control_plane_plugins/collections.py
banking_agents/collections_domain/service.py
banking_agents/collections_domain/repository.py
banking_agents/collections_domain/data/accounts.json
banking_agents/collections_domain/db/
banking_agents/collections_domain/services/intelligence/
```

The Collections workflow:

1. Loads account context.
2. Normalizes account data.
3. Calculates five evidence scores.
4. Evaluates persona.
5. Analyzes claims.
6. Runs trust gating.
7. Applies policy routing.
8. Produces next best action.
9. Flags human approval when required.
10. Returns structured evidence and execution trace.

---

## Control-plane API

Control-plane APIs are in:

```text
banking_agents/control_routes.py
```

The current prefix is:

```text
/api/v1/control
```

The frontend Control Panel and Collections demo use these routes directly.

---

## Data stores

```text
Backend/data/control_plane.db        # control-plane runs/events/policy/guardrail/degradation
Backend/data/collections_domain.db   # Collections domain seeded portfolio
Backend/data/audit.db                # legacy audit store
Backend/logs/*.jsonl                 # local runtime logs
```

These are generated local artifacts. They are useful for local demos but should not be treated as source code.

---

## Optional LangSmith tracing

`agent_harness/tracing.py` creates one root trace per API invocation and nests internal spans underneath it.

Expected root traces:

```text
Policy Assistant Demo Run
Loan Assessment Demo Run
Collections Workflow Demo Run
```

Project name:

```text
aria-agent-harness-demo
```

