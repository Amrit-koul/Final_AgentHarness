# AgentHarness Frontend

React 18 + Vite frontend for the BFSI AgentHarness demo.

The UI contains four business-facing routes:

| Route | Page | Purpose |
|---|---|---|
| `/` | Policy Assistant | Policy RAG assistant routed through the control-plane demo endpoint. |
| `/loan-assessment` | Loan Assessment | Structured loan eligibility assessment through the control plane. |
| `/collections` | Collections Intelligence | Backend-driven Collections portfolio, five-score workflow, trust gate and NBA output. |
| `/control/tower` | Control Panel landing page | Executive control tower with backend-driven agent and run data. |
| `/control/agents` | Agent Registry | Registered agents, status, contracts and health. |
| `/control/observability` | Observability | Runs, traces and control-plane events. |
| `/control/policy-guardrails` | Policy / Guardrails | Policy decisions and guardrail events. |
| `/control/kill-switch` | Kill Switch / Degradation | Kill-switch and degradation event views. |
| `/control/audit-logs` | Audit Logs | Run/event audit views. |
| `/control/onboarding` | Agent Onboarding | YAML-driven onboarding explanation. |
| `/dashboard` | Redirect | Redirects to `/control/tower` for backward compatibility. |

---

## Backend integration

The frontend uses backend APIs from the FastAPI app.

Primary control-plane service:

```text
src/services/controlPlaneApi.js
```

It calls:

```text
/api/v1/control/*
```

Legacy business wrappers are still centralized in:

```text
src/api.js
```

The current UI is backend-driven. Collections data, run records, policy decisions, guardrail events, degradation events and kill-switch events are fetched from the backend.

---

## Important source files

```text
src/main.jsx
src/api.js
src/services/controlPlaneApi.js

src/pages/ChatPage.jsx
src/pages/LoanAssessmentPage.jsx
src/pages/CollectionsAgentPage.jsx
src/pages/DashboardPage.jsx

src/pages/control/
src/components/control/
src/hooks/useControlData.js
src/components/Primitives.jsx
src/globals.css
```

---

## Local setup

Install dependencies:

```powershell
cd demo-agent-harness\Frontend
npm install
```

Run dev server:

```powershell
npm run dev
```

Default Vite URL:

```text
http://localhost:5173
```

If the backend is hosted separately or on a custom port, set:

```powershell
$env:VITE_API_BASE="http://127.0.0.1:8010"
```

For local same-origin/proxy development, `VITE_API_BASE` can be left blank if the Vite config proxies `/api` and `/health` to the backend.

---

## Build

```powershell
cd demo-agent-harness\Frontend
npm run build
```

Preview build:

```powershell
npm run preview
```

---

## Control Panel pages

The Control Panel under `/control/*` is composed from:

```text
src/pages/control/ControlTower.jsx
src/pages/control/AgentRegistry.jsx
src/pages/control/AgentOnboarding.jsx
src/pages/control/PolicyGuardrails.jsx
src/pages/control/Observability.jsx
src/pages/control/AuditLogs.jsx
src/pages/control/KillSwitchDegradation.jsx
```

Shared control UI pieces live in:

```text
src/components/control/
```

---

## Collections page

`src/pages/CollectionsAgentPage.jsx` loads persisted backend accounts through:

```javascript
controlPlaneApi.listCollectionsAccounts()
```

It runs the governed backend workflow through:

```javascript
controlPlaneApi.runCollections(submitted)
```

After execution, it fetches trace-specific events, policy decisions and guardrail events for the returned trace ID.

---

## Source hygiene

Do not commit:

- `.env`
- `node_modules/`
- `dist/`
