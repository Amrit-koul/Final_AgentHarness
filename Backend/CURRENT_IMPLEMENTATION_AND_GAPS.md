# Current Implementation and Gaps

**Snapshot date:** 25 June 2026  
**Scope:** `Backend/agent_harness`, `Backend/banking_agents`, FastAPI control routes, Collections domain workflow, prompt/tracing support, and React control UI.

---

## 1. Executive summary

The repository currently implements a local BFSI agent platform with a generic reusable harness and a bank-specific app layer.

Implemented demo use cases:

- Policy Assistant
- Loan Assessment / Loan Eligibility
- Collections Intelligence Workflow
- Agent Control Panel

The current primary integration path is the config-driven Agent Control Plane:

```text
/api/v1/control/*
```

The system is suitable for local demos, architecture walkthroughs, and technical client validation. It is not production-ready until authentication, authorization, durable shared state, production telemetry, deployment packaging, CI, and security hardening are added.

---

## 2. Current architecture

```text
React UI
  -> FastAPI banking app
      -> /api/v1/control routes
          -> banking_agents/harness/runtime.py
              -> generic agent_harness registry/adapters/store/tracing
              -> bank-specific policy engine and guardrails
              -> bank-specific agent plugin
                  -> Policy Assistant
                  -> Loan Assessment
                  -> Collections Workflow
```

Strict boundary:

```text
banking_agents -> agent_harness
```

The generic harness should remain reusable and domain-blind.

---

## 3. Implemented capabilities

| Area | Status | Current implementation |
|---|---|---|
| Generic harness | Implemented | Contracts, adapters, registry, config loading, store, policy abstractions, tracing, redaction, degradation, exceptions. |
| Bank runtime composition | Implemented | `banking_agents/harness/runtime.py` wires generic harness components to bank-specific policy and routes. |
| YAML onboarding | Implemented | Agent manifests under `banking_agents/config/agents`. |
| Policy Assistant | Implemented | Existing Policy RAG agent exposed through control-plane plugin and prompt manager. |
| Loan Assessment | Implemented | Existing loan eligibility agent exposed through control-plane plugin and prompt manager. |
| Collections Workflow | Implemented | Seeded account data, five-score engine, persona engine, claim analysis, trust gate, policy routing, NBA and human approval flag. |
| Control-plane API | Implemented | `/api/v1/control/*` routes for agents, runs, events, policy, guardrails, kill switch, degradation, and demos. |
| Control-plane persistence | Implemented locally | SQLite `control_plane.db` stores runs, events, policy decisions, guardrails, kill switch and degradation data. |
| Collections persistence | Implemented locally | SQLite `collections_domain.db` seeded from `collections_domain/data/accounts.json`. |
| Redaction | Implemented | Sensitive values summarized/redacted before traces/logs. |
| LangSmith tracing | Optional/implemented | One root trace per demo run with nested child spans when configured. |
| Prompt management | Implemented | Bank-owned versioned prompt YAML with optional LangSmith prompt override and local fallback. |
| Frontend | Implemented | Policy, Loan, Collections, and Control Panel routes using backend control-plane APIs. |
| Tests | Basic | Backend observability/unit tests exist; frontend build has been used for validation. |

---

## 4. Current API surface

### Main control-plane routes

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
```

### Demo routes

```text
POST /api/v1/control/demo/run-policy-agent
POST /api/v1/control/demo/run-loan-assessment
POST /api/v1/control/demo/run-collections
GET  /api/v1/control/demo/collections/accounts
POST /api/v1/control/demo/run-unsafe-sql
POST /api/v1/control/demo/simulate-degradation
```

### Legacy routes still present

```text
POST /api/v1/chat
POST /api/v1/loan/assess
GET  /health
```

---

## 5. Current UI surface

```text
/                  Policy Assistant
/loan-assessment   Loan Assessment
/collections       Collections Intelligence
/dashboard         Control Panel
```

The current Collections page uses:

- `GET /api/v1/control/demo/collections/accounts`
- `POST /api/v1/control/demo/run-collections`
- trace-specific events
- policy decisions
- guardrail events

The Control Panel uses `/api/v1/control/*` endpoints, not static mock data.

---

## 6. Known gaps and risks

### P0 before production exposure

1. **No authentication or authorization.** Administrative APIs, control-plane APIs, demo routes, audit records, kill-switch actions and guardrail data are not protected.
2. **Permissive local CORS.** Production needs explicit origin allowlists.
3. **Local SQLite storage.** `control_plane.db`, `collections_domain.db`, and `audit.db` are local demo stores, not production multi-user stores.
4. **No production-grade secrets management.** Environment variables are used locally; production needs vault/injection policy.
5. **No enterprise PII lifecycle.** Redaction exists, but there is no full DLP, encryption, retention, deletion, consent, or access policy.
6. **Kill switch state is demo/local.** Production should persist control states centrally and make enforcement fail closed.
7. **Runtime initialization still affects Policy/Loan demos.** Existing heavy RAG/model startup can cause Policy/Loan demo routes to report initialization errors until the runtime is ready.

### P1 reliability and operability

1. **SQLite limits concurrency and scaling.** Move to a managed relational store with migrations.
2. **Metrics are demo-level.** Add OpenTelemetry/Prometheus-style metrics with trace/log correlation.
3. **Logs are local.** Move to centralized log aggregation for production.
4. **No robust retry/recovery for runtime initialization.**
5. **External agent adapter examples need full operational hardening.**
6. **LangSmith is optional and not a compliance source of truth.** Local control-plane store remains authoritative for demo.

### P2 maintainability and product completeness

1. **Legacy app APIs and newer control-plane APIs coexist.** This is useful for demo continuity but should be rationalized for production.
2. **Some older harness facade modules remain for compatibility.**
3. **Prompt files are versioned locally, but prompt lifecycle governance is still light.**
4. **Collections includes richer voice/call copilot modules, but the active demo flow is currently the governed account intelligence workflow.**
5. **No container/deployment manifests are included.**

---

## 7. Current tests

Implemented backend tests include:

- redaction behavior
- no-op tracing when LangSmith is not configured
- local prompt loading
- LangSmith prompt override fallback
- Policy and Loan prompt/span usage with mocked model calls
- Collections/control trace name coverage

Run:

```powershell
cd Backend
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Remaining test gaps:

- Full API contract tests for every `/api/v1/control` route.
- Frontend component/E2E tests.
- Security tests.
- Concurrency tests.
- Persistence/restart tests.
- Real external agent adapter integration tests.
- CI pipeline with backend tests and frontend build.

---

## 8. Recommended delivery sequence

### Phase 1: demo hardening

- Clean startup readiness behavior for Policy/Loan demos.
- Add deterministic smoke scripts for all demo endpoints.
- Keep runtime DB/log artifacts out of commits.
- Add documentation screenshots or demo recording steps.

### Phase 2: enterprise security baseline

- Add auth/RBAC.
- Restrict CORS.
- Add rate limits and request body limits.
- Add secrets validation and fail-fast configuration.
- Define PII retention and redaction policy.

### Phase 3: production operations

- Move control-plane persistence to managed DB.
- Add migrations.
- Add centralized logs and metrics.
- Add liveness/readiness/dependency health endpoints.
- Persist kill-switch and degradation state centrally.

### Phase 4: platform extensibility

- Formalize external agent onboarding.
- Add agent evaluation/supervisor workflows.
- Add human approval workflow UI for high-risk actions.
- Add CI/CD and deployment packaging.

---

## 9. Production readiness definition

This repository should not be described as production-ready until:

- administrative APIs are authenticated and authorized,
- sensitive data has an approved lifecycle,
- runtime state is durable and shared,
- kill switch state is centrally enforced,
- observability is centralized,
- dependencies and runtime startup are validated,
- deterministic automated tests run in CI,
- deployment is repeatable.

