# BFSI Agentic AI Demo Story

Technical client walkthrough for a bank / NBFC audience  
Role: Big 4 Agentic AI Engineer  
Demo system: Bandhan Bank Agentic AI Platform, Agent Harness, Collections Intelligence, Policy Assistant, Loan Assessment

---

## 1. Executive story

This demo is positioned as a governed agentic AI control plane for BFSI operations.

The story is not “we built a chatbot.” The story is:

> We have created a reusable agent harness that allows a bank to onboard, govern, observe, and safely operate multiple AI agents across business functions such as policy assistance, loan assessment, and collections intelligence.

The demo shows three things a technical client should care about:

1. How agents are onboarded through configuration, not hardcoded one-off scripts.
2. How every agent run is governed through contracts, policy checks, guardrails, audit logs, traces, degradation monitoring, and kill switch controls.
3. How a bank-specific domain agent, the Collections Agent, uses real seeded account data, deterministic rules, scoring, trust gating, and next-best-action logic to support a collections user without exposing unsafe automation.

The business angle:

> In BFSI, the challenge is not only making AI answer questions. The challenge is making AI auditable, explainable, controllable, and safe enough to sit inside regulated operations.

---

## 2. Demo narrative: the client-facing storyline

### Scene setup

“Imagine the bank has multiple AI use cases coming from different business units:

- Retail policy teams want a Policy Assistant.
- Credit teams want a Loan Assessment Agent.
- Collections teams want an intelligence workflow for overdue accounts.
- Tomorrow, another team may bring an external open-source or vendor-hosted agent.

If each of these is built separately, the bank ends up with fragmented governance, inconsistent logs, no common kill switch, and no unified risk view.

So our architecture separates two layers:

- `agent_harness`: the reusable enterprise framework.
- `banking_agents`: the bank-specific application layer.

This separation is important because the bank can reuse the harness across future agents while keeping business logic, policies, and domain rules inside the banking layer.”

---

## 3. The architecture in one view

```text
Frontend UI
  ├─ Policy Assistant
  ├─ Loan Assessment
  ├─ Collections Intelligence
  └─ Control Panel
        │
        ▼
FastAPI Backend
  └─ /api/v1/control/*
        │
        ▼
Bank-specific runtime
  └─ banking_agents/harness/runtime.py
        │
        ▼
Generic reusable harness
  ├─ contracts
  ├─ registry
  ├─ adapter factory
  ├─ policy interface
  ├─ tracing
  ├─ audit store
  ├─ degradation monitor
  └─ kill switch
        │
        ▼
Banking agents
  ├─ Policy Assistant
  ├─ Loan Assessment
  └─ Collections Workflow
        │
        ▼
Data sources
  ├─ policy documents / RAG collections
  ├─ loan policy documents
  ├─ seeded collections account data
  ├─ control_plane.db
  └─ collections_domain.db
```

Key message:

> The harness is generic. The banking domain logic is pluggable. The UI is only a consumer of backend-generated decisions and traces.

---

## 4. Where the data is coming from

### 4.1 Policy and loan documents

Policy and lending knowledge is sourced from document files under:

```text
Backend/data_ingestion/policy_documents/
```

Examples:

```text
01_Customer_Onboarding_Policy.docx
02_KYC_Policy.docx
09_Retail_Credit_Policy.docx
12_Home_Loan_Policy.docx
13_Personal_Loan_Policy.docx
Loan_Eligibility_Validation_Policy.docx
```

The ingestion entrypoint is:

```text
Backend/data_ingestion/ingest_docs.py
```

The Policy Assistant and Loan Assessment agents use RAG collections:

```python
self.rag = BaseRAG(collection_name="policy_docs")
self.rag = BaseRAG(collection_name="loan_docs")
```

Talk track:

> “For policy and loan assessment, the agent is not inventing rules from the model. It retrieves context from bank policy documents and then generates an answer using that grounded context.”

### 4.2 Collections account data

Collections demo account data starts as seeded JSON:

```text
Backend/banking_agents/collections_domain/data/accounts.json
```

The repository seeds this into a collections-specific SQLite database:

```text
Backend/data/collections_domain.db
```

The code that performs this load is:

```text
Backend/banking_agents/collections_domain/repository.py
```

Important snippet:

```python
SEED_PATH = Path(__file__).parent / "data" / "accounts.json"

def ensure_seeded():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(LoanAccount).first():
            return
        for raw in json.loads(SEED_PATH.read_text(encoding="utf-8")):
            customer_id = f"CUST-{uuid.uuid4().hex[:8].upper()}"
            db.add(Customer(...))
            db.add(LoanAccount(...))
            db.add(AIProfile(...))
            db.add(Interaction(...))
            db.add(PTPHistory(...))
            db.add(Claim(...))
        db.commit()
    finally:
        db.close()
```

The database connection is configured here:

```text
Backend/banking_agents/collections_domain/db/database.py
```

```python
BACKEND_ROOT = Path(__file__).resolve().parents[3]
DB_PATH = BACKEND_ROOT / "data" / "collections_domain.db"
engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
```

Talk track:

> “For the Collections Agent, this is not fake UI state. The UI requests a live portfolio from the backend. The backend reads persisted seeded account records from a domain SQLite database, enriches them, runs scoring and trust logic, and then persists execution events into the control-plane database.”

### 4.3 Control plane database

The control plane persists agent runs, events, policy decisions, guardrail events, kill switch events, and degradation signals in:

```text
Backend/data/control_plane.db
```

This store is created by the generic harness:

```text
Backend/agent_harness/store.py
```

It is wired into the bank runtime here:

```text
Backend/banking_agents/harness/runtime.py
```

```python
self.store = ControlPlaneStore(DATA_DIR / "control_plane.db")
self.services.store = self.store
```

Talk track:

> “The control panel does not show hardcoded demo logs. It reads from backend persisted runs and events. Every control-plane invocation writes a trace ID, start/end status, policy decision, and run outcome.”

---

## 5. Agent onboarding: YAML-driven, not hardcoded

Agents are registered from YAML manifests under:

```text
Backend/banking_agents/config/agents/
```

Current important manifests:

```text
policy_assistant.yaml
loan_assessment.yaml
collections_workflow.yaml
sample_external_agent.yaml
```

Collections manifest:

```yaml
agent_id: collections_workflow_agent
name: Collections Workflow Agent
owner: Collections Operations
business_function: Collections
agent_type: workflow
execution_mode: workflow
adapter_type: python_function
entrypoint: banking_agents.agents.control_plane_plugins.collections.run_collections_workflow
skills: [account_enrichment, persona_scoring, trust_gating, next_best_action]
tools: [collections_account_store, collections_rules]
guardrails:
  - customer_data_access
  - pii_leakage
  - payment_authorization
  - collections_conduct
  - prompt_injection
  - business_scope
status: active
```

Talk track:

> “This is how the bank onboards an agent. We are not editing the core harness every time a new use case arrives. We add a manifest, point to an adapter entrypoint, declare schemas, permissions, tools, skills, guardrails, and observability hooks.”

For a future external or open-source API agent:

1. Add a new YAML manifest.
2. Set `adapter_type` to the REST/API adapter supported by the harness.
3. Provide endpoint and authentication metadata.
4. Define input/output contract.
5. Add allowed actions and data scopes.
6. Let the existing registry, adapter, policy, audit, and tracing pipeline handle it.

---

## 6. Agent harness: what each part does

### Generic framework layer

Located at:

```text
Backend/agent_harness/
```

Core responsibilities:

| Harness part | File | Purpose |
|---|---|---|
| Contracts | `contracts.py` | Defines the standard shape of an agent contract. |
| Contract validation | `contract_validator.py` | Validates YAML manifests and schema expectations. |
| Registry | `registry.py` | Loads agents and keeps their runtime status. |
| Base adapter | `base_adapter.py` | Shared adapter interface. |
| Built-in adapters | `adapters.py` | Python function, LangGraph, REST, webhook adapters. |
| Store | `store.py` | SQLite persistence for runs, events, policies, degradation and kill switch records. |
| Policy interface | `policy.py` | Generic policy abstractions. |
| Tracing | `tracing.py` | LangSmith-aware root trace and nested span management. |
| Redaction | `redaction.py` | Sanitizes sensitive values before tracing/logging. |
| Degradation monitor | `degradation_monitor.py` | Detects declining agent performance. |
| Exceptions | `exceptions.py` | Common typed errors for control-plane behavior. |

Talk track:

> “The harness is the reusable platform layer. It knows what an agent is, how to register it, invoke it, observe it, and govern it. It does not know banking-specific logic.”

### Bank-specific layer

Located at:

```text
Backend/banking_agents/
```

Responsibilities:

- Bank-specific FastAPI routes.
- Policy Assistant implementation.
- Loan Assessment implementation.
- Collections workflow and scoring rules.
- Bank guardrails.
- Bank YAML manifests.
- Domain data and demo endpoints.

Talk track:

> “The bank-specific layer imports from the harness. The harness does not import from the banking layer. That keeps the architecture clean and reusable.”

---

## 7. Backend request flow

The frontend calls the control-plane API:

```text
POST /api/v1/control/demo/run-collections
```

The route is defined in:

```text
Backend/banking_agents/control_routes.py
```

```python
@router.post("/demo/run-collections")
async def demo_collections(body: dict):
    return await _invoke_control_plane(
        "collections_workflow_agent",
        body or {"account_id": "ACC-DEMO-01"},
        trace_name="Collections Workflow Demo Run",
        request_source="demo_endpoint",
    )
```

The route calls the runtime:

```text
Backend/banking_agents/harness/runtime.py
```

Important runtime flow:

```python
with tracer.trace(run_name, inputs=safe_summary(payload), metadata=metadata, tags=tags) as root:
    with tracer.span("load_agent_contract", inputs={"agent_id": agent_id}):
        ...
    with tracer.span("check_agent_status", inputs={"agent_id": agent_id}):
        ...
    with tracer.span("pre_policy_check", inputs={...}):
        policy = self.policy.check(agent_id, action, policy_context, trace_id)
    ...
    with tracer.span("audit_persist", inputs={"event": "RUN_STARTED"}):
        self.store.start_run(...)
    ...
    with tracer.span("adapter_invoke", inputs={...}):
        result = await adapter.invoke_async(validated, trace_id)
    ...
    with tracer.span("post_guardrail_check", inputs={...}):
        post_policy = self.policy.check(...)
    ...
    self.store.finish_run(...)
```

The important point:

> Every agent invocation is wrapped in the same governance lifecycle before and after business execution.

---

## 8. Collections Agent internal flow

The Collections Agent entrypoint is:

```text
Backend/banking_agents/agents/control_plane_plugins/collections.py
```

```python
def run_collections_workflow(payload, trace_id=""):
    if not isinstance(payload, dict) or not payload.get("account_id"):
        raise ValueError("account_id is required")

    result = run_account_workflow(
        account_id=payload["account_id"],
        override_persona=payload.get("override_persona"),
        new_claims=payload.get("new_claims"),
    )

    steps = [
        {"step": "account_context", "status": "completed"},
        {"step": "five_score_engine", "status": "completed"},
        {"step": "persona_classification", "status": "completed"},
        {"step": "trust_gate", "status": "completed"},
        {"step": "policy_and_nba", "status": "completed"},
    ]

    for step in steps:
        control_plane.store.add_event(
            "COLLECTIONS_STEP_COMPLETED",
            trace_id,
            "collections_workflow_agent",
            step,
        )

    return {
        **result,
        "workflow_status": "completed",
        "execution_trace": steps,
        "trace_id": trace_id,
    }
```

The domain workflow itself is:

```text
Backend/banking_agents/collections_domain/service.py
```

```python
def run_account_workflow(account_id, override_persona=None, new_claims=None):
    with tracer.span("Collections Workflow", inputs={...}) as workflow:
        with tracer.span("load_account_context", inputs={"account_id": account_id}):
            account = load_account(account_id)

        with tracer.span("account_data_normalization", inputs={"account_id": account_id}):
            ...

        result = run_intelligence_pipeline(
            account,
            current_persona=account.get("persona"),
            new_claims=new_claims,
        )

        with tracer.span("next_best_action", inputs={...}):
            next_action = _ACTION_MAP.get(routing, routing)

        with tracer.span("human_approval_decision", inputs={...}):
            human_approval_required = ...

        with tracer.span("response_normalization", inputs={"account_id": account_id}):
            response = {...}

        return response
```

Collections intelligence pipeline:

```text
Backend/banking_agents/collections_domain/services/intelligence/pipeline.py
Backend/banking_agents/collections_domain/services/intelligence/scoring_engine.py
Backend/banking_agents/collections_domain/services/intelligence/trust_gate.py
Backend/banking_agents/collections_domain/services/intelligence/policy_engine.py
```

The five scores shown in the UI are:

- Ability to Pay
- Intent to Pay
- Trust
- Contactability
- Self Cure

Talk track:

> “For Collections, the agent is not blindly calling a model and generating a recommendation. It loads a customer account, normalizes context, calculates evidence scores, evaluates persona, checks trust gates, routes through policy, decides next best action, and flags whether human approval is required.”

---

## 9. UI walkthrough

Frontend key files:

```text
Frontend/src/pages/CollectionsAgentPage.jsx
Frontend/src/pages/ChatPage.jsx
Frontend/src/pages/LoanAssessmentPage.jsx
Frontend/src/pages/DashboardPage.jsx
Frontend/src/services/controlPlaneApi.js
Frontend/src/api.js
Frontend/src/components/control/AppShell.jsx
```

### Collections UI

The Collections page loads real backend portfolio data:

```javascript
controlPlaneApi.listCollectionsAccounts()
```

Service definition:

```javascript
listCollectionsAccounts: () => request('/demo/collections/accounts'),
runCollections: (body = {}) => post('/demo/run-collections', body),
```

The page lets the user:

1. Select an account from the live portfolio.
2. Review customer/account context.
3. Optionally add new evidence claims.
4. Run the governed workflow.
5. See five scores, persona, trust gate, next best action, human approval, policy decisions, guardrail events, and execution trace.

Talk track:

> “The UI is intentionally not making decisions. It is a control surface. The backend returns the decision, evidence, trace ID, policy decisions, and guardrail events.”

### Control Panel UI

The Control Panel uses:

```text
Frontend/src/services/controlPlaneApi.js
Frontend/src/hooks/useControlData.js
Frontend/src/pages/control/
```

It calls backend APIs such as:

```text
GET /api/v1/control/agents
GET /api/v1/control/runs
GET /api/v1/control/events
GET /api/v1/control/policy/decisions
GET /api/v1/control/guardrails/events
GET /api/v1/control/kill-switch/events
GET /api/v1/control/degradation/events
```

Talk track:

> “This is the operational layer a bank technology, risk, or operations team would care about. They can see registered agents, recent runs, guardrail events, policy decisions, kill switch state, and degradation signals.”

---

## 10. Live demo script

### Opening, 60 seconds

“Today I’ll show a governed agentic AI platform for BFSI. The key idea is that each AI agent is treated like an enterprise system component, not like an isolated prompt.

We have a reusable harness that manages contracts, registry, adapters, policies, guardrails, tracing, audit, degradation monitoring, and kill switch. On top of that, we have bank-specific agents for Policy Assistance, Loan Assessment, and Collections Intelligence.”

### Step 1: Show navigation

Open the UI and point out:

- Policy Assistant
- Loan Assessment
- Collections Agent
- Control Panel

Say:

“These are business-facing tabs, but underneath they are all going through the same control-plane lifecycle.”

### Step 2: Show Collections portfolio

Go to Collections Agent.

Say:

“This page first loads the persisted collections portfolio from the backend. The data comes from a seeded account dataset that is persisted into `collections_domain.db`. We are not rendering static cards.”

Point to:

- Number of accounts.
- Total outstanding.
- High/critical accounts.
- DPD 30+.

### Step 3: Select a customer

Select `ACC-DEMO-01` or another account.

Say:

“When we select an account, the UI is showing customer/account context: DPD, bucket, outstanding amount, EMI, priority, and the currently known persona. This is the input context for the workflow.”

### Step 4: Add optional new evidence

Use optional claim JSON:

```json
[
  {
    "claim_type": "medical",
    "verification_state": "CLAIMED",
    "claim_details": "Customer claims hospitalization caused delayed payment"
  }
]
```

Say:

“This simulates new evidence from a call, branch note, WhatsApp interaction, or field officer update. The trust gate should treat this as a claim that may require verification.”

### Step 5: Run Five-Stage Assessment

Click Run.

Say:

“Now the request goes to `/api/v1/control/demo/run-collections`. The control plane loads the agent contract, checks the agent status, runs pre-policy checks, persists the run start, invokes the adapter, executes business logic, runs post-guardrail checks, persists completion, and updates degradation and kill switch evaluation.”

### Step 6: Explain output

Walk through the output cards:

- Customer / Account Summary
- Five Scores
- Persona Result
- Trust Gate
- Next Best Action
- Human Approval
- Policy Decisions
- Guardrail Events
- Execution Trace

Say:

“This is the difference between a useful BFSI agent and a generic LLM demo. The output is structured, explainable, and operationally governed. We can see why the agent recommended an action and whether the action requires human approval.”

### Step 7: Open Control Panel

Go to Control Panel.

Say:

“Now we can see that the run appeared in the backend control-plane records. This is important for auditability. A bank can ask: Which agent ran? What contract did it use? What was the policy decision? Were any guardrails triggered? What was the latency? What is the trace ID?”

### Step 8: Show LangSmith / trace story

If LangSmith is configured, show:

```text
Collections Workflow Demo Run
├─ load_agent_contract
├─ check_agent_status
├─ pre_policy_check
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

Say:

“The trace gives engineering and risk teams a nested, step-by-step view of the run. We see both the generic harness steps and the domain-specific Collections workflow inside one parent trace.”

---

## 11. Technical deep dive script

### 11.1 Why the harness exists

“In many AI pilots, governance is added later. Here, the harness makes governance part of the execution path.

Every agent goes through:

1. Contract lookup.
2. Status check.
3. Input validation.
4. Policy check.
5. Adapter invocation.
6. Business execution.
7. Output guardrail review.
8. Audit persistence.
9. Degradation evaluation.
10. Kill switch evaluation.”

### 11.2 Why YAML onboarding matters

“For the next agent, we do not want to edit the core framework. The bank should be able to add a manifest and an adapter entrypoint.

That means agent onboarding is close to a platform operation, not a custom software project every time.”

### 11.3 Why Collections is rules-first

“Collections is a sensitive domain. The agent should not autonomously promise waivers, restructure loans, or trigger legal escalation without governance.

So the workflow is deterministic-rules-first:

- Score evidence.
- Evaluate trust.
- Route through policy.
- Decide if human approval is required.
- Persist the full trace.”

### 11.4 Why control-plane data matters

“The UI is not enough. A bank needs backend records:

- Runs table.
- Events table.
- Policy decisions.
- Guardrail events.
- Kill switch events.
- Degradation events.

This enables audit, compliance review, technology operations, and incident reconstruction.”

---

## 12. Important code snippets to show

### 12.1 Runtime creates one governed execution

File:

```text
Backend/banking_agents/harness/runtime.py
```

```python
async def invoke(self, agent_id, payload, action="invoke", trace_id=None, *, trace_name=None, request_source="generic_invoke"):
    trace_id = trace_id or str(uuid.uuid4())
    contract = self.registry.get_contract(agent_id)
    ...
    with tracer.trace(run_name, inputs=safe_summary(payload), metadata=metadata, tags=tags) as root:
        ...
        policy = self.policy.check(agent_id, action, policy_context, trace_id)
        ...
        result = await adapter.invoke_async(validated, trace_id)
        ...
        post_policy = self.policy.check(agent_id, "output_review", ...)
        ...
        self.store.finish_run(...)
```

Client explanation:

> “This is the common execution envelope around every agent.”

### 12.2 Collections plugin adapts domain logic to the harness

File:

```text
Backend/banking_agents/agents/control_plane_plugins/collections.py
```

```python
def run_collections_workflow(payload, trace_id=""):
    result = run_account_workflow(
        account_id=payload["account_id"],
        override_persona=payload.get("override_persona"),
        new_claims=payload.get("new_claims"),
    )
    ...
    return {**result, "workflow_status": "completed", "trace_id": trace_id}
```

Client explanation:

> “This is a thin bank-owned plugin. The harness stays generic; the plugin owns Collections-specific workflow behavior.”

### 12.3 Collections workflow loads account data and runs intelligence

File:

```text
Backend/banking_agents/collections_domain/service.py
```

```python
with tracer.span("load_account_context", inputs={"account_id": account_id}):
    account = load_account(account_id)

result = run_intelligence_pipeline(
    account,
    current_persona=account.get("persona"),
    new_claims=new_claims,
)
```

Client explanation:

> “This is where account context becomes an intelligence workflow.”

### 12.4 Frontend calls the backend control plane

File:

```text
Frontend/src/services/controlPlaneApi.js
```

```javascript
runCollections: (body = {}) => post('/demo/run-collections', body),
listCollectionsAccounts: () => request('/demo/collections/accounts'),
listRuns: () => request('/runs'),
listPolicyDecisions: () => request('/policy/decisions'),
listGuardrailEvents: () => request('/guardrails/events'),
```

Client explanation:

> “The UI is thin. It calls governed backend endpoints and renders backend-generated evidence.”

### 12.5 Collections UI renders backend evidence

File:

```text
Frontend/src/pages/CollectionsAgentPage.jsx
```

```javascript
const response = await controlPlaneApi.runCollections(submitted);
const traceId = response?.trace_id || response?.result?.trace_id;

const [tracePayload, policyPayload, guardrailPayload] = await Promise.all([
  traceId ? controlPlaneApi.getTraceEvents(traceId).catch(() => []) : [],
  traceId ? controlPlaneApi.listPolicyDecisions().catch(() => []) : [],
  traceId ? controlPlaneApi.listGuardrailEvents().catch(() => []) : [],
]);
```

Client explanation:

> “After the workflow runs, the page fetches the trace events, policy decisions, and guardrail events for the same trace ID.”

---

## 13. Suggested live demo order

Use this order for a technical BFSI audience:

1. Start at the UI navigation.
2. Open Collections Intelligence.
3. Explain portfolio data source.
4. Select a customer account.
5. Run five-stage assessment.
6. Explain five scores and trust gate.
7. Explain next-best-action and human approval.
8. Open Control Panel.
9. Show runs/events/policy decisions/guardrails.
10. Show code manifest for Collections.
11. Show runtime control-plane flow.
12. Show Collections service flow.
13. If available, show LangSmith nested trace.
14. Close with onboarding story for future agents.

---

## 14. Questions the client may ask, and answers

### Q: Is the Collections data fake?

Answer:

“It is seeded demo data, but it is not hardcoded frontend data. It is loaded from `accounts.json`, persisted into `collections_domain.db`, read by backend repository code, enriched, processed, and returned through APIs.”

### Q: Is the control panel real?

Answer:

“Yes. It reads backend APIs backed by `control_plane.db`: runs, events, policy decisions, guardrail events, kill switch records, and degradation events.”

### Q: Can we add a new agent?

Answer:

“Yes. Add a YAML manifest and adapter entrypoint. The core harness does not need to change for every new agent.”

### Q: Can we onboard an external open-source API agent?

Answer:

“Yes. The harness supports adapter-driven invocation. For an external API agent, the manifest declares the endpoint, auth environment variable, input/output contract, allowed actions, and data scope. The same policy, audit, tracing, and degradation controls apply.”

### Q: Can the agent directly approve settlements or waivers?

Answer:

“The manifest and policy layer restrict that. Collections actions such as settlement, waiver, restructure, and legal escalation are marked for human approval.”

### Q: Where is PII handled?

Answer:

“The harness includes redaction before tracing/logging, and banking guardrails include PII leakage controls. In a production rollout, this would be integrated with enterprise DLP, masking, IAM, and data classification.”

### Q: Is LangSmith mandatory?

Answer:

“No. LangSmith is optional observability. The local control-plane database remains the operational source of truth. LangSmith provides richer nested trace visualization when configured.”

---

## 15. Close-out message

“The value of this platform is not just the Collections Agent or the Policy Assistant in isolation. The value is that we have a repeatable operating model for agents in the bank.

Each agent has:

- A contract.
- A registry entry.
- An adapter.
- A policy envelope.
- Guardrails.
- Audit.
- Observability.
- Degradation handling.
- Kill switch control.
- A UI surface that reflects backend truth.

That is what moves this from an AI prototype to an enterprise BFSI agent platform.”

---

## 16. Appendix: key paths

### Backend

```text
Backend/agent_harness/
Backend/banking_agents/control_routes.py
Backend/banking_agents/harness/runtime.py
Backend/banking_agents/config/agents/
Backend/banking_agents/agents/control_plane_plugins/
Backend/banking_agents/collections_domain/
Backend/banking_agents/policy/control_plane.py
Backend/banking_agents/guardrails/
Backend/data/control_plane.db
Backend/data/collections_domain.db
Backend/data_ingestion/policy_documents/
```

### Frontend

```text
Frontend/src/services/controlPlaneApi.js
Frontend/src/api.js
Frontend/src/pages/CollectionsAgentPage.jsx
Frontend/src/pages/ChatPage.jsx
Frontend/src/pages/LoanAssessmentPage.jsx
Frontend/src/pages/DashboardPage.jsx
Frontend/src/pages/control/
Frontend/src/components/control/
```

### Run commands

Backend:

```powershell
cd demo-agent-harness/Backend
.\.venv\Scripts\python.exe -m uvicorn banking_agents.main:app --host 127.0.0.1 --port 8010
```

Frontend:

```powershell
cd demo-agent-harness/Frontend
npm run dev
```

Optional LangSmith:

```powershell
$env:LANGCHAIN_TRACING_V2="true"
$env:LANGCHAIN_API_KEY="<your-langsmith-key>"
$env:LANGCHAIN_PROJECT="aria-agent-harness-demo"
```

