const API_BASE = (import.meta.env.VITE_API_BASE || '').replace(/\/$/, '');

function getErrorMessage(payload, fallback) {
  if (payload && typeof payload === 'object' && payload.detail) {
    return typeof payload.detail === 'string'
      ? payload.detail
      : JSON.stringify(payload.detail);
  }
  return fallback;
}

async function apiFetch(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      Accept: 'application/json',
      ...(options.body ? { 'Content-Type': 'application/json' } : {}),
      ...options.headers,
    },
  });
  if (!res.ok) {
    const payload = await res.json().catch(() => null);
    throw new Error(getErrorMessage(payload, `${res.status} ${res.statusText}`));
  }
  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  health: () => apiFetch('/health'),

  chat: async (query, session_id) => {
    const run = await apiFetch('/api/v1/control/demo/run-policy-agent', {
      method: 'POST',
      body: JSON.stringify({ query, session_id }),
    });

    const traceId = run?.trace_id;
    const events = traceId
      ? await apiFetch(`/api/v1/control/events/${encodeURIComponent(traceId)}`).catch(() => ({ events: [] }))
      : { events: [] };

    // Policy-blocked flat shape has no `result` key at all.
    const isBlocked = !!run && typeof run === 'object' && !('result' in run) && 'decision' in run;
    if (isBlocked) {
      const parts = [`Request blocked by harness policy: ${run.reason || 'no reason returned by backend'}`];
      if (run.decision) parts.push(`Decision: ${run.decision}`);
      if (run.status) parts.push(`Agent status: ${run.status}`);
      return {
        final: parts.join(' '),
        session_id: session_id,
        intent: 'POLICY',
        audit_trail: events.events || [],
        trace_id: traceId,
        rag_evaluation: undefined,
        citations: undefined,
      };
    }

    const result = run?.result;
    const final =
      result?.answer ?? result?.response ?? result?.message ??
      run?.answer ?? run?.response ?? run?.message ??
      'No answer was returned by the backend for this request.';

    return {
      final,
      session_id: result?.session_id || session_id,
      intent: 'POLICY',
      audit_trail: events.events || [],
      trace_id: traceId,
      rag_evaluation: result?.rag_evaluation,
      citations: result?.citations,
    };
  },

  loanAssess: async (profile, query = '', session_id = null) => {
    const run = await apiFetch('/api/v1/control/demo/run-loan-assessment', {
      method: 'POST',
      body: JSON.stringify({ profile, query, session_id }),
    });
    return { ...run.result, session_id: session_id || run.trace_id, trace_id: run.trace_id };
  },

  agents: () => apiFetch('/api/v1/harness/agents'),

  toggleAgent: (agentName, enabled) =>
    apiFetch(`/api/v1/harness/agents/${encodeURIComponent(agentName)}/toggle`, {
      method: 'POST',
      body: JSON.stringify({ enabled, triggered_by: 'react-dashboard' }),
    }),

  audit: (limit = 20) => apiFetch(`/api/v1/harness/audit?limit=${limit}`),

  auditSession: (sessionId) =>
    apiFetch(`/api/v1/harness/audit/${encodeURIComponent(sessionId)}`),

  metrics: () => apiFetch('/api/v1/harness/metrics'),

  governance: () => apiFetch('/api/v1/harness/governance'),

  toolsAuthorization: (limit = 100) => apiFetch(`/api/v1/control/tools/authorization-events?limit=${limit}`),

  logs: (n = 20) => apiFetch(`/api/v1/harness/logs?n=${n}`),

  killSwitchLog: (limit = 10) =>
    apiFetch(`/api/v1/harness/kill-switch-log?limit=${limit}`),
};

export { API_BASE };