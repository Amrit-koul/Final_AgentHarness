# Config-Driven Agent Control Plane

The backend control plane exposes registered agents through a common governance and observability lifecycle.

The current control-plane API prefix is:

```text
/api/v1/control
```

This is the primary API consumed by the current React Control Panel and demo pages.

---

## Boundary rule

The backend uses a strict dependency direction:

```text
banking_agents -> agent_harness
```

- `Backend/agent_harness` is generic framework code.
- `Backend/banking_agents` is the bank-specific app layer.
- `agent_harness` must not import `banking_agents`.

---

## Consolidated structure

```text
Backend/
├─ agent_harness/                  # reusable framework
│  ├─ contracts.py
│  ├─ base_adapter.py
│  ├─ adapters.py
│  ├─ plugin_loader.py
│  ├─ contract_validator.py
│  ├─ config_loader.py
│  ├─ registry.py
│  ├─ policy.py
│  ├─ store.py
│  ├─ tracing.py
│  ├─ redaction.py
│  ├─ trace_provider.py
│  ├─ kill_switch.py
│  ├─ degradation_monitor.py
│  ├─ exceptions.py
│  ├─ audit.py
│  ├─ memory.py
│  └─ state.py
│
├─ banking_agents/                 # bank-specific application layer
│  ├─ agents/
│  │  ├─ domain/                   # Policy and Loan agents
│  │  ├─ reusable/                 # classifier/decomposer/orchestrator
│  │  └─ control_plane_plugins/    # harness-facing wrappers
│  ├─ collections_domain/          # Collections workflow and data model
│  ├─ config/agents/               # YAML contracts
│  ├─ guardrails/
│  ├─ policy/control_plane.py
│  ├─ prompts/
│  ├─ harness/runtime.py           # thin bootstrap/composition layer
│  ├─ control_routes.py            # /api/v1/control routes
│  └─ main.py                      # FastAPI app
│
├─ data/                           # local runtime stores
└─ data_ingestion/
```

---

## Registered agents

Current YAML-driven agents:

| Agent ID | Manifest | Purpose |
|---|---|---|
| `policy_assistant_agent` | `banking_agents/config/agents/policy_assistant.yaml` | Policy RAG assistant exposed through the control plane. |
| `loan_assessment_agent` | `banking_agents/config/agents/loan_assessment.yaml` | Loan eligibility / assessment flow. |
| `collections_workflow_agent` | `banking_agents/config/agents/collections_workflow.yaml` | Collections scoring, persona, trust gate and NBA workflow. |
| `sample_external_agent` / samples | `sample_external_*.yaml` | Examples for future REST/API or wrapped external agents. |

Onboarding a future agent should normally mean adding a YAML manifest plus an adapter entrypoint or endpoint. The generic registry, policy, adapter, tracing, and store logic should not be edited for each new agent.

---

## Runtime invocation lifecycle

`banking_agents/harness/runtime.py` composes the generic harness pieces with bank-specific policy services.

Each agent execution follows this flow:

```text
control route
  -> ControlPlaneRuntime.invoke()
      -> create root trace
      -> load_agent_contract
      -> check_agent_status
      -> pre_policy_check
          -> pre_guardrail_check
          -> audit policy decision
      -> validate input
      -> audit RUN_STARTED
      -> adapter_invoke
          -> python_function_call / rest_api_call / graph call
          -> business workflow spans
      -> post_guardrail_check
      -> audit RUN_COMPLETED or RUN_FAILED
      -> degradation_evaluation
      -> kill_switch_evaluation
```

---

## Control-plane API surface

```text
GET  /api/v1/control/agents
GET  /api/v1/control/agents/{agent_id}
GET  /api/v1/control/agents/{agent_id}/contract
GET  /api/v1/control/agents/{agent_id}/status
GET  /api/v1/control/agents/{agent_id}/health
POST /api/v1/control/agents/{agent_id}/invoke

GET  /api/v1/control/runs
GET  /api/v1/control/runs/{trace_id}
GET  /api/v1/control/events
GET  /api/v1/control/events/{trace_id}

POST /api/v1/control/policy/check
GET  /api/v1/control/policy/decisions
GET  /api/v1/control/guardrails
GET  /api/v1/control/guardrails/events

POST /api/v1/control/kill-switch/{agent_id}
GET  /api/v1/control/kill-switch/events
GET  /api/v1/control/degradation/events

POST /api/v1/control/demo/run-policy-agent
POST /api/v1/control/demo/run-loan-assessment
POST /api/v1/control/demo/run-collections
GET  /api/v1/control/demo/collections/accounts
POST /api/v1/control/demo/run-unsafe-sql
POST /api/v1/control/demo/simulate-degradation
```

---

## Local data stores

| Store | Path | Purpose |
|---|---|---|
| Control plane | `Backend/data/control_plane.db` | Runs, events, policy decisions, guardrail events, kill switch and degradation records. |
| Collections domain | `Backend/data/collections_domain.db` | Seeded Collections customers, accounts, AI profiles, interactions, PTP history, claims, review cases. |
| Audit legacy store | `Backend/data/audit.db` | Legacy app audit records for older endpoints. |

These generated DBs are local runtime artifacts and should not be committed as source changes.

---

## Collections workflow check

```powershell
Invoke-RestMethod http://127.0.0.1:8010/api/v1/control/demo/collections/accounts

Invoke-RestMethod `
  -Method Post `
  -ContentType application/json `
  -Uri http://127.0.0.1:8010/api/v1/control/demo/run-collections `
  -Body '{"account_id":"ACC-DEMO-01"}'
```

---

## Guardrail / kill switch checks

Unsafe SQL governance test:

```powershell
Invoke-RestMethod `
  -Method Post `
  -ContentType application/json `
  -Uri http://127.0.0.1:8010/api/v1/control/demo/run-unsafe-sql `
  -Body '{"agent_id":"collections_workflow_agent","sql":"DROP TABLE customers; -- malicious"}'
```

Degradation simulation:

```powershell
Invoke-RestMethod `
  -Method Post `
  -ContentType application/json `
  -Uri http://127.0.0.1:8010/api/v1/control/demo/simulate-degradation `
  -Body '{"agent_id":"sample_external_agent","failed_runs":5}'
```

---

## Optional LangSmith tracing

```powershell
$env:LANGCHAIN_TRACING_V2="true"
$env:LANGCHAIN_API_KEY="<your-langsmith-key>"
$env:LANGCHAIN_PROJECT="aria-agent-harness-demo"
```

Expected root trace names:

```text
Policy Assistant Demo Run
Loan Assessment Demo Run
Collections Workflow Demo Run
```

Prompt spans, adapter spans, guardrail spans, and business spans should appear as children of the active agent execution, not as separate top-level traces.

