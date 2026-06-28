# AgentHarness — Governed BFSI Agentic AI Platform

AgentHarness is a demo-grade BFSI agent platform that shows how a bank can run multiple AI agents through a common governance and observability control plane.

The repository contains:

- `Backend/agent_harness`: generic reusable harness framework.
- `Backend/banking_agents`: bank-specific agents, guardrails, YAML manifests, domain data, and FastAPI routes.
- `Frontend`: React/Vite UI for Policy Assistant, Loan Assessment, Collections Intelligence, and Control Panel.
- `docs`: client-facing demo story and walkthrough material.

The current demo focuses on three bank use cases:

1. Policy Assistant
2. Loan Assessment / Loan Eligibility
3. Collections Intelligence Workflow

The important architecture principle is strict dependency direction:

```text
Frontend
  -> Backend/banking_agents FastAPI app
      -> Backend/banking_agents bank-specific runtime and agents
          -> Backend/agent_harness generic framework
```

`banking_agents` may import `agent_harness`.  
`agent_harness` must not import `banking_agents`.

---

## What this demo proves

This is not just a chatbot demo. It demonstrates a governed operating model for agents in a regulated BFSI environment:

- YAML-driven agent onboarding.
- Generic agent contracts and adapters.
- Pre-policy and post-output guardrail checks.
- Audit persistence.
- Control-plane event logging.
- Kill switch and degradation monitoring.
- Optional LangSmith nested tracing.
- Backend-driven UI data.
- Collections workflow with persisted account data, scoring, trust gating, and next-best-action rules.

---

## Current high-level architecture

```text
React / Vite Frontend
  ├─ Policy Assistant
  ├─ Loan Assessment
  ├─ Collections Intelligence
  └─ Control Panel
        │
        ▼
FastAPI backend: banking_agents.main
        │
        ├─ Legacy business APIs
        │  ├─ POST /api/v1/chat
        │  └─ POST /api/v1/loan/assess
        │
        └─ Agent Control Plane APIs
           └─ /api/v1/control/*
                │
                ▼
        banking_agents/harness/runtime.py
                │
                ├─ loads YAML manifests
                ├─ validates agent status and input schema
                ├─ runs policy checks
                ├─ invokes generic adapter
                ├─ persists run/audit events
                ├─ evaluates degradation
                └─ applies kill switch logic
                │
                ▼
        Bank-specific agents/plugins
                ├─ Policy Assistant
                ├─ Loan Assessment
                └─ Collections Workflow
```

---

## Repository structure

```text
.
├─ Backend/
│  ├─ agent_harness/                 # Generic reusable harness framework
│  │  ├─ contracts.py
│  │  ├─ registry.py
│  │  ├─ adapters.py
│  │  ├─ policy.py
│  │  ├─ store.py
│  │  ├─ tracing.py
│  │  ├─ redaction.py
│  │  ├─ degradation_monitor.py
│  │  └─ exceptions.py
│  │
│  ├─ banking_agents/                # Bank-specific app layer
│  │  ├─ agents/
│  │  │  ├─ domain/                  # Policy and Loan domain agents
│  │  │  ├─ reusable/                # Intent classifier, decomposer, orchestrator
│  │  │  └─ control_plane_plugins/   # Harness plugin entrypoints
│  │  ├─ collections_domain/         # Collections workflow, scoring, data and rules
│  │  ├─ config/agents/              # YAML agent manifests
│  │  ├─ guardrails/
│  │  ├─ policy/
│  │  ├─ prompts/
│  │  ├─ control_routes.py
│  │  └─ main.py
│  │
│  ├─ data_ingestion/
│  │  └─ policy_documents/
│  └─ data/                          # Local runtime DBs; ignored for new generated files
│
├─ Frontend/
│  └─ src/
│     ├─ pages/
│     ├─ pages/control/
│     ├─ services/controlPlaneApi.js
│     └─ api.js
│
└─ docs/
   └─ bfsi-agentic-ai-demo-story.md
```

---

## Agent onboarding

Agents are registered from YAML manifests:

```text
Backend/banking_agents/config/agents/
```

Current key manifests:

```text
policy_assistant.yaml
loan_assessment.yaml
collections_workflow.yaml
sample_external_rest_agent.yaml
sample_github_wrapped_agent.yaml
```

Adding a future agent should normally require:

1. A YAML manifest.
2. A Python function, LangGraph, REST, webhook, or wrapper entrypoint.
3. Input/output schema.
4. Allowed actions and data scopes.
5. Guardrail and observability declarations.

It should not require editing the generic framework.

---

## Data sources

### Policy and loan knowledge

Policy documents live under:

```text
Backend/data_ingestion/policy_documents/
```

The ingestion script is:

```text
Backend/data_ingestion/ingest_docs.py
```

Policy and loan agents use RAG collections such as `policy_docs` and `loan_docs`.

### Collections data

Collections demo accounts start from:

```text
Backend/banking_agents/collections_domain/data/accounts.json
```

They are seeded into:

```text
Backend/data/collections_domain.db
```

The control plane stores runs, policy decisions, guardrail events, degradation events, and kill-switch events in:

```text
Backend/data/control_plane.db
```

Runtime DBs and logs are local artifacts and should not be pushed as source.

---

## Main APIs

### Control-plane APIs

```text
GET  /api/v1/control/agents
GET  /api/v1/control/agents/{agent_id}
GET  /api/v1/control/agents/{agent_id}/contract
GET  /api/v1/control/agents/{agent_id}/status
GET  /api/v1/control/agents/{agent_id}/health
POST /api/v1/control/agents/{agent_id}/invoke
POST /api/v1/control/agents/{agent_id}/heartbeat

GET  /api/v1/control/runs
GET  /api/v1/control/runs/{trace_id}
GET  /api/v1/control/events
POST /api/v1/control/events/ingest
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

### Legacy app APIs still present

```text
POST /api/v1/chat
POST /api/v1/loan/assess
GET  /health
```

---

## Frontend routes

```text
/                  Policy Assistant
/loan-assessment   Loan Assessment
/collections       Collections Intelligence
/control/tower     Control Panel landing page
/control/agents    Agent Registry
/control/*         Control Panel sub-pages
/dashboard         Redirects to /control/tower
```

The frontend uses backend-generated data from `/api/v1/control/*`; the Control Panel and Collections page are not static mock dashboards.

---

## Run locally

### Backend

```powershell
cd demo-agent-harness\Backend
.\.venv\Scripts\python.exe -m uvicorn banking_agents.main:app --host 127.0.0.1 --port 8010
```

Or, if using a freshly created environment:

```powershell
cd demo-agent-harness\Backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python data_ingestion\ingest_docs.py
python -m uvicorn banking_agents.main:app --host 127.0.0.1 --port 8010
```

Required for Policy/Loan LLM calls:

```powershell
$env:GROQ_API_KEY="<your-key>"
```

### Frontend

```powershell
cd demo-agent-harness\Frontend
npm install
npm run dev
```

If the backend runs on a custom origin, set:

```powershell
$env:VITE_API_BASE="http://127.0.0.1:8010"
```

---

## Optional LangSmith tracing

LangSmith is optional. Local control-plane storage remains the operational source of truth.

```powershell
$env:LANGCHAIN_TRACING_V2="true"
$env:LANGCHAIN_API_KEY="<your-langsmith-key>"
$env:LANGCHAIN_PROJECT="aria-agent-harness-demo"
```

Expected top-level traces:

```text
Policy Assistant Demo Run
Loan Assessment Demo Run
Collections Workflow Demo Run
```

Internal prompt, adapter, policy, guardrail, scoring, and business spans are nested under the active parent run.

---

## Useful smoke checks

```powershell
Invoke-RestMethod http://127.0.0.1:8010/health
Invoke-RestMethod http://127.0.0.1:8010/api/v1/control/agents
Invoke-RestMethod http://127.0.0.1:8010/api/v1/control/demo/collections/accounts
Invoke-RestMethod -Method Post -ContentType application/json -Uri http://127.0.0.1:8010/api/v1/control/demo/run-collections -Body '{"account_id":"ACC-DEMO-01"}'
Invoke-RestMethod -Method Post -ContentType application/json -Uri http://127.0.0.1:8010/api/v1/control/demo/run-unsafe-sql -Body '{"agent_id":"collections_workflow_agent","sql":"DROP TABLE customers; -- malicious"}'
```

Run backend tests:

```powershell
cd demo-agent-harness\Backend
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Build frontend:

```powershell
cd demo-agent-harness\Frontend
npm run build
```

---

## Documentation

- [Control Plane README](Backend/CONTROL_PLANE_README.md)
- [Architecture Structure](Backend/ARCHITECTURE_STRUCTURE.md)
- [Harness Layer README](Backend/HARNESS_LAYER_README.md)
- [Current Implementation and Gaps](Backend/CURRENT_IMPLEMENTATION_AND_GAPS.md)
- [Frontend README](Frontend/README.md)
- [BFSI Demo Story](docs/bfsi-agentic-ai-demo-story.md)

---

## Source hygiene

Do not commit:

- `.env`
- `node_modules/`
- `Frontend/dist/`
- generated runtime DBs under `Backend/data/`
- generated logs under `Backend/logs/`
