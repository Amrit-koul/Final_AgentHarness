const API_BASE = (import.meta.env.VITE_API_BASE || '').replace(/\/$/, '');
const PREFIX = '/api/v1/control';

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${PREFIX}${path}`, {
    ...options,
    headers: {
      Accept: 'application/json',
      ...(options.body ? { 'Content-Type': 'application/json' } : {}),
      ...options.headers,
    },
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new Error(payload?.detail || `${response.status} ${response.statusText}`);
  }
  return response.status === 204 ? null : response.json();
}

const post = (path, body = {}) => request(path, { method: 'POST', body: JSON.stringify(body) });

export const controlPlaneApi = {
  listAgents: () => request('/agents'),
  getAgent: (id) => request(`/agents/${encodeURIComponent(id)}`),
  getContract: (id) => request(`/agents/${encodeURIComponent(id)}/contract`),
  getStatus: (id) => request(`/agents/${encodeURIComponent(id)}/status`),
  getHealth: (id) => request(`/agents/${encodeURIComponent(id)}/health`),
  invokeAgent: (id, body = {}) => post(`/agents/${encodeURIComponent(id)}/invoke`, body),
  listRuns: () => request('/runs'),
  getRun: (traceId) => request(`/runs/${encodeURIComponent(traceId)}`),
  listEvents: () => request('/events'),
  listEvaluations: () => request('/evaluations'),
  getTraceEvents: (traceId) => request(`/events/${encodeURIComponent(traceId)}`),
  listPolicyDecisions: () => request('/policy/decisions'),
  listGuardrails: () => request('/guardrails'),
  listGuardrailEvents: () => request('/guardrails/events'),
  listToolAuthorizationEvents: () => request('/tools/authorization-events'),
  authorizeToolAction: (body = {}) => post('/tools/authorize', body),
  listKillSwitchEvents: () => request('/kill-switch/events'),
  listDegradationEvents: () => request('/degradation/events'),
  runUnsafeSql: (body = {}) => post('/demo/run-unsafe-sql', body),
  changeAgentStatus: (id, body = {}) => post(`/kill-switch/${encodeURIComponent(id)}`, body),
  simulateDegradation: (body = {}) => post('/demo/simulate-degradation', body),
  runPolicyAgent: (body = {}) => post('/demo/run-policy-agent', body),
  runLoanAssessment: (body = {}) => post('/demo/run-loan-assessment', body),
  // Collections — multi-mode, server-side extraction
  runCollections: (body = {}) => post('/demo/run-collections', body),
  runCollectionsPreCall: (accountId) =>
    post('/demo/run-collections', { mode: 'pre_call', account_id: accountId }),
  runCollectionsPostCall: (accountId, transcript, capturedId) =>
    post('/demo/run-collections', {
      mode: 'post_call',
      account_id: accountId,
      ...(capturedId ? { captured_transcript_id: capturedId } : {}),
      ...(transcript ? { transcript } : {}),
    }),
  runCollectionsFullLifecycle: (accountId, capturedId, transcript) =>
    post('/demo/run-collections', {
      mode: 'full_lifecycle',
      account_id: accountId,
      ...(capturedId ? { captured_transcript_id: capturedId } : {}),
      ...(transcript ? { transcript } : {}),
    }),
  runCollectionsVoiceGreet: (accountId) =>
    post('/demo/run-collections', { mode: 'voice_greet', account_id: accountId }),
  getCollectionsVoiceStatus: () => request('/collections/voice/status'),
  startCollectionsVoice: (accountId) => post('/collections/voice/start', { account_id: accountId }),
  runCollectionsVoiceTurn: (body = {}) => post('/collections/voice/turn', body),
  finalizeCollectionsVoice: (body = {}) => post('/collections/voice/finalize', body),
  listCollectionsAccounts: () => request('/demo/collections/accounts'),
  getCollectionsTranscripts: () => request('/collections/transcripts'),
  getCollectionsHistory: (accountId) =>
    request(`/collections/${encodeURIComponent(accountId)}/history`),
  getUsageSummary: () => request('/usage/summary'),
  listUsageEvents: () => request('/usage/events'),
  listSkills: () => request('/skills'),
  listTools: () => request('/tools'),
  getPrimitiveValidation: () => request('/primitives/validation'),
  listMemoryContracts: () => request('/memory/contracts'),
  listMemoryEvents: () => request('/memory/events'),
  listHooks: () => request('/hooks'),
  listHookEvents: () => request('/hooks/events'),
  getObservabilityStatus: () => request('/observability/status'),  // ← added
  listPrompts: () => request('/prompts'),
  listEvaluators: () => request('/evaluators'),
};

export { API_BASE };
