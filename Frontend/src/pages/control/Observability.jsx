import React, { useCallback, useMemo, useState } from 'react';
import PageHeader from '../../components/control/PageHeader';
import { Chip, DecisionChip, SeverityChip, RiskChip } from '../../components/control/Chips';
import { LoadingState, SectionCard, asArray, display, fmtTime } from '../../components/control/Common';
import { useControlData } from '../../hooks/useControlData';
import { controlPlaneApi } from '../../services/controlPlaneApi';
import { SourceBadge, EnforcementBadge, LLMJudgeBadge, renderMissingField } from '../../utils/evidenceLabels';
// ─── Data truth label chip ────────────────────────────────────────────────────
// Every column or section in this page is labelled with where the data comes from.
const TRUTH_COLOURS = {
  RUNTIME:             { bg: 'rgba(6,118,71,0.12)',   border: 'rgba(6,118,71,0.3)',   text: '#067647' },
  DISPLAY_MAPPING:     { bg: 'rgba(46,111,216,0.10)', border: 'rgba(46,111,216,0.25)', text: '#2E6FD8' },
  CONFIG_STATUS:       { bg: 'rgba(220,130,0,0.12)',  border: 'rgba(220,130,0,0.3)',  text: '#B45309' },
  NOT_EMITTED_BY_PLUGIN:{ bg: 'rgba(100,100,100,0.10)', border: 'rgba(100,100,100,0.25)', text: 'var(--text-muted)' },
};

function TruthBadge({ level }) {
  const c = TRUTH_COLOURS[level] || TRUTH_COLOURS.NOT_EMITTED_BY_PLUGIN;
  return (
    <span style={{ fontSize: 10, fontWeight: 700, fontFamily: 'var(--font-mono)', padding: '1px 6px', borderRadius: 3, background: c.bg, border: `1px solid ${c.border}`, color: c.text, whiteSpace: 'nowrap' }}>
      {level}
    </span>
  );
}

const TABS = [
  ['runtime', 'Runtime Events'],
  ['hooks',   'Hook Events'],
  ['latency', 'Latency / Usage'],
  ['langsmith','LangSmith'],
];

export default function Observability() {
  const [tab, setTab] = useState('runtime');
  const [filter, setFilter] = useState('all');

  // ── Main data fetch ──────────────────────────────────────────────────────────
  const fetchData = useCallback(async () => {
    const [runs, events, hookEvents, usageEvents] = await Promise.all([
      controlPlaneApi.listRuns(),
      controlPlaneApi.listEvents(),
      controlPlaneApi.listHookEvents(),
      controlPlaneApi.listUsageEvents(),
    ]);
    return {
      runs:        asArray(runs,        'runs'),
      events:      asArray(events,      'events'),
      hookEvents:  asArray(hookEvents,  'events'),
      usageEvents: asArray(usageEvents, 'events'),
    };
  }, []);
  const state = useControlData(fetchData, [], 5000);
  const data = state.data || { runs: [], events: [], hookEvents: [], usageEvents: [] };

  // ── LangSmith status fetch (separate, lower frequency) ──────────────────────
  const fetchLs = useCallback(() => controlPlaneApi.getObservabilityStatus(), []);
  const lsState = useControlData(fetchLs, [], 30000);
  const ls = lsState.data || null;

  // ── Filter helpers ───────────────────────────────────────────────────────────
  const applyFilter = (items) => {
    if (filter === 'today') {
      const today = new Date().toDateString();
      return items.filter(r => new Date(r.timestamp || r.started_at || 0).toDateString() === today);
    }
    if (filter === 'runtime') return items.filter(r => !['admin_validation','manual_validation','simulation'].includes(String(r.source || '').toLowerCase()));
    return items;
  };

  // Non-hook runtime events (hook events shown in separate tab)
  const runtimeEvents = useMemo(() =>
    applyFilter(data.events.filter(e => !String(e.event_type || '').toUpperCase().startsWith('HOOK_')))
  , [data.events, filter]);

  const hookEvents = useMemo(() => applyFilter(data.hookEvents), [data.hookEvents, filter]);
  const runs       = useMemo(() => applyFilter(data.runs),       [data.runs,       filter]);
  const usage      = useMemo(() => applyFilter(data.usageEvents),[data.usageEvents, filter]);

  return (
    <>
      <PageHeader
        title="Observability"
        subtitle="Technical runtime telemetry for engineers and administrators. Business-readable audit evidence is on the Audit Trail page."
        right={
          <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
            <select className="cc-input" value={filter} onChange={e => setFilter(e.target.value)}>
              <option value="all">All records</option>
              <option value="today">Today only</option>
              <option value="runtime">Exclude admin/test</option>
            </select>
            <button className="cc-button" onClick={() => { state.reload(); lsState.reload(); }}>Refresh</button>
          </div>
        }
      />

      {/* Page-level data source notice */}
      <div style={{ margin: '0 0 16px 0', padding: '10px 14px', borderRadius: 6, background: 'var(--surface-inset)', border: '1px solid var(--border)', fontSize: 12, color: 'var(--text-muted)', display: 'flex', gap: 16, flexWrap: 'wrap', alignItems: 'center' }}>
        <span><TruthBadge level="RUNTIME" /> events, runs, hooks — read from observability_events / agent_runs tables.</span>
        <span><TruthBadge level="CONFIG_STATUS" /> LangSmith — integration status read from env / SDK at startup.</span>
        <span style={{ marginLeft: 'auto', fontStyle: 'italic' }}>This page is technical. HOOK_* names are shown as emitted — see Audit Trail for mapped business labels.</span>
      </div>

      <div className="cc-tabs">
        {TABS.map(([id, label]) => (
          <button key={id} className={`cc-tab${tab === id ? ' active' : ''}`} onClick={() => setTab(id)}>{label}</button>
        ))}
      </div>

      <LoadingState loading={state.loading} error={state.error} />

      {!state.loading && !state.error && <>
        {tab === 'runtime'   && <RuntimeEvents   rows={runtimeEvents} runs={runs} />}
        {tab === 'hooks'     && <HookEvents      rows={hookEvents} />}
        {tab === 'latency'   && <LatencyUsage    runs={runs} usage={usage} />}
        {tab === 'langsmith' && <LangSmithPanel  ls={ls} loading={lsState.loading} error={lsState.error} />}
      </>}
    </>
  );
}

// ─── Section A: Runtime Events ────────────────────────────────────────────────
function RuntimeEvents({ rows, runs }) {
  return (
    <>
      <SectionCard
        title="Agent Runs"
        subtitle={<><TruthBadge level="RUNTIME" /> Execution records from agent_runs table. One row per harness invocation.</>}
      >
        {!runs.length
          ? <div className="cc-empty">No agent runs recorded yet. Run any agent to populate this view.</div>
          : <div className="cc-table-scroll"><table className="cc-table">
              <thead><tr><th>Started</th><th>Trace ID</th><th>Agent</th><th>Status</th><th>Latency</th><th>Error</th></tr></thead>
              <tbody>{runs.map(r => (
                <tr key={r.trace_id || r.id}>
                  <td>{fmtTime(r.started_at)}</td>
                  <td className="mono" style={{ fontSize: 11 }}>{display(r.trace_id)}</td>
                  <td>{display(r.agent_id)}</td>
                  <td><Chip value={r.status} /></td>
                  <td>{r.latency_ms == null ? <span className="cc-muted">—</span> : `${r.latency_ms} ms`}</td>
                  <td style={{ fontSize: 11, color: 'var(--error)' }}>{display(r.error)}</td>
                </tr>
              ))}</tbody>
            </table></div>
        }
      </SectionCard>

      <SectionCard
        className="cc-top-gap"
        title="Runtime Observability Events"
        subtitle={<><TruthBadge level="RUNTIME" /> Events from observability_events table. Excludes HOOK_* rows (shown in Hook Events tab).</>}
      >
        {!rows.length
          ? <div className="cc-empty">No non-hook observability events recorded yet.</div>
          : <div className="cc-table-scroll"><table className="cc-table">
              <thead><tr><th>Timestamp</th><th>Event Type</th><th>Agent</th><th>Trace ID</th><th>Payload</th></tr></thead>
              <tbody>{rows.map((r, i) => (
                <tr key={r.id || i}>
                  <td>{fmtTime(r.timestamp)}</td>
                  <td><Chip value={r.event_type} /></td>
                  <td>{display(r.agent_id)}</td>
                  <td className="mono" style={{ fontSize: 11 }}>{display(r.trace_id)}</td>
                  <td className="cc-payload" style={{ fontSize: 11, maxWidth: 300 }}>{display(r.payload_json)}</td>
                </tr>
              ))}</tbody>
            </table></div>
        }
      </SectionCard>
    </>
  );
}

// ─── Section B: Hook Events ───────────────────────────────────────────────────
// Raw HOOK_* names are intentionally shown here. This is the technical view.
// The Audit Trail page maps these to business-readable labels.
function HookEvents({ rows }) {
  return (
    <SectionCard
      title="Hook Events"
      subtitle={
        <>
          <TruthBadge level="RUNTIME" />{' '}
          Raw <code>HOOK_*</code> event names emitted by{' '}
          <code>agent_harness/primitives.py HookDispatcher.emit()</code>.{' '}
          These are shown here as emitted — the Audit Trail page maps them to business-readable labels.
        </>
      }
    >
      <div style={{ marginBottom: 12, padding: '8px 12px', borderRadius: 4, background: 'var(--surface-inset)', border: '1px solid var(--border)', fontSize: 12, color: 'var(--text-muted)' }}>
        <strong style={{ color: 'var(--text)' }}>Hook name mapping</strong> (reference only):
        <span style={{ margin: '0 12px' }}><code>HOOK_PRE_INVOKE</code> → <em>HARNESS_PRE_CHECK</em> in Audit Trail</span>
        <span style={{ margin: '0 12px' }}><code>HOOK_POST_INVOKE</code> → <em>HARNESS_POST_CHECK</em></span>
        <span style={{ margin: '0 12px' }}><code>HOOK_ON_COST_RECORD</code> → <em>TELEMETRY_RECORDED</em></span>
      </div>
      {!rows.length
        ? <div className="cc-empty">No hook events recorded yet. Hook events are emitted by the harness on every agent invocation.</div>
        : <div className="cc-table-scroll"><table className="cc-table">
            <thead><tr><th>Timestamp</th><th>Raw Hook Name</th><th>Agent</th><th>Trace ID</th><th>Hook ID / Payload</th></tr></thead>
            <tbody>{rows.map((r, i) => {
              let hookId = '—';
              try { const p = JSON.parse(r.payload_json || '{}'); hookId = p.hook_id || display(p); } catch { hookId = display(r.payload_json); }
              return (
                <tr key={r.id || i}>
                  <td>{fmtTime(r.timestamp)}</td>
                  <td><code style={{ fontSize: 11, color: 'var(--warning)' }}>{display(r.event_type)}</code></td>
                  <td>{display(r.agent_id)}</td>
                  <td className="mono" style={{ fontSize: 11 }}>{display(r.trace_id)}</td>
                  <td style={{ fontSize: 11 }}>{hookId}</td>
                </tr>
              );
            })}</tbody>
          </table></div>
      }
    </SectionCard>
  );
}

// ─── Section C: Latency / Usage ───────────────────────────────────────────────
function LatencyUsage({ runs, usage }) {
  return (
    <>
      <SectionCard
        title="Latency by Run"
        subtitle={<><TruthBadge level="RUNTIME" /> Latency is recorded by the harness runtime for every invocation.</>}
      >
        {!runs.length
          ? <div className="cc-empty">No runs recorded yet.</div>
          : <div className="cc-table-scroll"><table className="cc-table">
              <thead><tr><th>Started</th><th>Agent</th><th>Status</th><th>Latency</th><th>Trace ID</th></tr></thead>
              <tbody>{runs.map(r => (
                <tr key={r.trace_id || r.id}>
                  <td>{fmtTime(r.started_at)}</td>
                  <td>{display(r.agent_id)}</td>
                  <td><Chip value={r.status} /></td>
                  <td style={{ fontWeight: r.latency_ms != null ? 600 : 400 }}>
                    {r.latency_ms == null ? <span className="cc-muted">—</span> : `${r.latency_ms} ms`}
                  </td>
                  <td className="mono" style={{ fontSize: 11 }}>{display(r.trace_id)}</td>
                </tr>
              ))}</tbody>
            </table></div>
        }
      </SectionCard>

      <SectionCard
        className="cc-top-gap"
        title="Usage / Cost Events"
        subtitle="Provider, model, and token data — shown when emitted by the runtime."
      >
        <div style={{ marginBottom: 10, padding: '8px 12px', borderRadius: 4, background: 'var(--surface-inset)', border: '1px solid var(--border)', fontSize: 12, color: 'var(--text-muted)' }}>
          <TruthBadge level="NOT_EMITTED_BY_PLUGIN" />{' '}
          <strong style={{ color: 'var(--text)' }}>Collections plugin:</strong>{' '}
          provider = <code>external</code>, model = <code>unknown</code> — the vendored plugin does not emit token or cost data through the harness usage layer.
          Latency is recorded.
          {' '}<TruthBadge level="RUNTIME" />{' '}
          <strong style={{ color: 'var(--text)' }}>Groq-backed agents</strong> (Policy Assistant, Loan Assessment):{' '}
          emit real model + usage when GROQ_API_KEY is configured.
        </div>
        {!usage.length
          ? <div className="cc-empty">No usage events recorded yet.</div>
          : <div className="cc-table-scroll"><table className="cc-table">
              <thead><tr><th>Timestamp</th><th>Agent</th><th>Provider</th><th>Model</th><th>Latency</th><th>Status</th><th>Trace ID</th></tr></thead>
              <tbody>{usage.map((r, i) => (
                <tr key={r.usage_id || i}>
                  <td>{fmtTime(r.created_at || r.timestamp)}</td>
                  <td>{display(r.agent_id)}</td>
                  <td>
                    {r.provider === 'external' || r.provider === 'unknown'
                      ? <span className="cc-muted" title="Not emitted by plugin">external / not emitted</span>
                      : display(r.provider)}
                  </td>
                  <td>
                    {r.model === 'unknown' || !r.model
                      ? <span className="cc-muted" title="Not emitted by plugin">unknown</span>
                      : display(r.model)}
                  </td>
                  <td>{r.latency_ms == null ? '—' : `${r.latency_ms} ms`}</td>
                  <td><Chip value={r.status} /></td>
                  <td className="mono" style={{ fontSize: 11 }}>{display(r.trace_id)}</td>
                </tr>
              ))}</tbody>
            </table></div>
        }
      </SectionCard>
    </>
  );
}

// ─── Section D: LangSmith ─────────────────────────────────────────────────────
const INTEGRATION_COLOURS = {
  RUNTIME:                   { bg: 'rgba(6,118,71,0.12)',   border: 'rgba(6,118,71,0.3)',   text: '#067647' },
  CONFIG_PRESENT_NOT_ENABLED:{ bg: 'rgba(220,130,0,0.12)',  border: 'rgba(220,130,0,0.3)',  text: '#B45309' },
  NOT_PRESENT:               { bg: 'rgba(100,100,100,0.10)',border: 'rgba(100,100,100,0.25)',text: 'var(--text-muted)' },
};

function IntegrationBadge({ level }) {
  const c = INTEGRATION_COLOURS[level] || INTEGRATION_COLOURS.NOT_PRESENT;
  return (
    <span style={{ fontSize: 11, fontWeight: 700, fontFamily: 'var(--font-mono)', padding: '2px 8px', borderRadius: 4, background: c.bg, border: `1px solid ${c.border}`, color: c.text }}>
      {level}
    </span>
  );
}

function LangSmithPanel({ ls, loading, error }) {
  if (loading) return <SectionCard title="LangSmith"><div className="cc-empty">Loading integration status…</div></SectionCard>;
  if (error)   return <SectionCard title="LangSmith"><div className="cc-empty" style={{ color: 'var(--error)' }}>Could not fetch observability status: {String(error)}</div></SectionCard>;
  if (!ls)     return <SectionCard title="LangSmith"><div className="cc-empty">No status returned.</div></SectionCard>;

  const level = ls.integration_level || 'NOT_PRESENT';

  return (
    <SectionCard
      title="LangSmith Integration"
      subtitle={<><TruthBadge level="CONFIG_STATUS" /> Status is read from env / SDK at startup. No API keys are returned.</>}
    >
      {/* Integration level banner */}
      <div style={{ padding: '12px 16px', borderRadius: 6, background: 'var(--surface-inset)', border: '1px solid var(--border)', marginBottom: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
          <IntegrationBadge level={level} />
          <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)' }}>Integration Level</span>
        </div>
        <p style={{ fontSize: 13, color: 'var(--text-muted)', margin: 0, lineHeight: 1.6 }}>{ls.status_label}</p>
      </div>

      {/* Status fields */}
      <dl className="cc-detail-grid">
        <dt>SDK Installed</dt>
        <dd>{ls.sdk_available
          ? <span style={{ color: 'var(--success)', fontWeight: 600 }}>Yes — langsmith package available</span>
          : <span style={{ color: 'var(--text-muted)' }}>No — install with <code>pip install langsmith</code></span>}
        </dd>

        <dt>Tracing Active</dt>
        <dd>{ls.tracing_enabled
          ? <span style={{ color: 'var(--success)', fontWeight: 600 }}>Yes — spans sent to LangSmith on every control-plane invocation</span>
          : <span style={{ color: 'var(--text-muted)' }}>No — set <code>LANGSMITH_TRACING=true</code> and <code>LANGSMITH_API_KEY</code> to activate</span>}
        </dd>

        <dt>Project</dt>
        <dd>{ls.project ? <code>{ls.project}</code> : <span className="cc-muted">Not configured</span>}</dd>

        <dt>Endpoint</dt>
        <dd>{ls.endpoint ? <code>{ls.endpoint}</code> : <span className="cc-muted">Default (api.smith.langchain.com)</span>}</dd>

        <dt>Trace URL Persisted</dt>
        <dd>
          <span style={{ color: 'var(--text-muted)' }}>
            {ls.trace_url_persisted
              ? 'Yes — LangSmith run URLs are stored in the local DB.'
              : 'No — LangSmith run URLs are not persisted in observability_events. '
              + 'The trace_id column holds the local UUID used to correlate events within this DB. '
              + 'To view LangSmith traces, open the LangSmith project dashboard directly.'}
          </span>
        </dd>

        <dt>Local Store</dt>
        <dd>
          <span style={{ color: 'var(--success)', fontWeight: 600 }}>Always active</span>
          {' — '}<span style={{ color: 'var(--text-muted)', fontSize: 12 }}>{ls.local_store_note}</span>
        </dd>
      </dl>

      {/* Architecture note */}
      <div style={{ marginTop: 16, padding: '10px 14px', borderRadius: 6, background: 'var(--surface-inset)', border: '1px solid var(--border)', fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.7 }}>
        <strong style={{ color: 'var(--text)', display: 'block', marginBottom: 4 }}>How it works</strong>
        LangSmith tracing is wired in <code>agent_harness/tracing.py</code> (<code>TraceManager</code>) and called by
        the control-plane runtime at the start of every invocation. When enabled, structured spans
        (load_agent_contract → check_agent_status → pre_policy_check → adapter_invoke →
        post_guardrail_check → audit_persist) are sent to LangSmith in parallel with
        local SQLite writes. LangSmith is additive — local observability is always the source of truth
        for this dashboard. Individual run URLs are not currently stored in the DB; use the LangSmith
        project dashboard to browse traces when tracing is active.
      </div>
    </SectionCard>
  );
}
