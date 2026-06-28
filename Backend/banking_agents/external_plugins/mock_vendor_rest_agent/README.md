# Mock Vendor REST Agent

This is a deliberately separate FastAPI process used to demonstrate that an
external vendor agent is governed by the same control-plane contract. It is
not loaded into the banking backend.

From `Backend/`, start it with:

```powershell
uvicorn banking_agents.external_plugins.mock_vendor_rest_agent.app:app --port 9001 --reload
```

Then invoke it through the banking control plane, not directly:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8010/api/v1/control/agents/demo_vendor_rest_agent/invoke -ContentType 'application/json' -Body '{"query":"Summarize this customer request"}'
```

The service intentionally has no authentication. Production vendor integrations
must configure authenticated transport, secret rotation, and vendor-specific
availability controls.
