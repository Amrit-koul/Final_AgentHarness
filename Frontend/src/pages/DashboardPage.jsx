import React, { useState, useCallback, useEffect } from 'react';
import { api } from '../api';
import { useBackendHealth } from '../hooks/useBackendHealth';
import { usePoll } from '../hooks/usePoll';
import {
  AppNav, StatusPill, Panel, PanelHeader, Divider,
  Toggle, EmptyState, Spinner, IntentBadge, Toast,
  fmtMs, fmtTs, fmtDate, truncate, latencyColor,
} from '../components/Primitives';
import AuditTrail from '../components/AuditTrail';

// ── Helpers ───────────────────────────────────────────────────────
function HBadge({ children, type = 'neutral' }) {
  const styles = {
    neutral: { color: '#7A96B4', bg: 'rgba(122,150,180,0.12)', border: 'rgba(122,150,180,0.2)' },
    green:   { color: '#34C97A', bg: 'rgba(52,201,122,0.10)', border: 'rgba(52,201,122,0.2)' },
    red:     { color: '#E05C5C', bg: 'rgba(224,92,92,0.10)',  border: 'rgba(224,92,92,0.2)' },
    amber:   { color: '#D89040', bg: 'rgba(216,144,64,0.10)', border: 'rgba(216,144,64,0.2)' },
    blue:    { color: '#4A9EE8', bg: 'rgba(74,158,232,0.10)', border: 'rgba(74,158,232,0.2)' },
    teal:    { color: '#4ABFD8', bg: 'rgba(74,191,216,0.10)', border: 'rgba(74,191,216,0.2)' },
  };
  const s = styles[type] || styles.neutral;
  return (
    <span style={{
      fontSize: 10, fontFamily: 'var(--font-mono)',
      color: s.color, background: s.bg, border: `1px solid ${s.border}`,
      borderRadius: 3, padding: '1px 6px', whiteSpace: 'nowrap',
    }}>{children}</span>
  );
}

function Dot({ active }) {
  return (
    <span style={{
      width: 7, height: 7, borderRadius: '50%', flexShrink: 0,
      background: active ? '#34C97A' : '#E05C5C',
      display: 'inline-block',
      animation: active ? 'pulse 2s infinite' : 'none',
    }} />
  );
}

// ── Summary strip ─────────────────────────────────────────────────
function SummaryStrip({ metrics, agents }) {
  const enabledCount = agents ? agents.filter(a => a.enabled).length : null;
  const total = agents ? agents.length : null;
  const metricAgents = metrics?.agents || [];
  const totalCallsValue = metricAgents.reduce((sum, agent) => sum + (agent.calls || 0), 0);
  const totalErrors = metricAgents.reduce((sum, agent) => sum + (agent.errors || 0), 0);
  const weightedLatency = metricAgents.reduce(
    (sum, agent) => sum + ((agent.avg_latency_ms || 0) * (agent.calls || 0)),
    0,
  );
  const errorRateValue = totalCallsValue > 0 ? totalErrors / totalCallsValue : 0;
  const avgLatencyValue = totalCallsValue > 0 ? weightedLatency / totalCallsValue : 0;
  const totalCalls = metrics ? totalCallsValue : '—';
  const errorRate = metrics ? `${(errorRateValue * 100).toFixed(1)}%` : '—';
  const avgLatency = metrics ? fmtMs(Math.round(avgLatencyValue)) : '—';
  const completed = metrics?.sessions?.total_sessions ?? '—';

  const cells = [
    { label: 'Agents Enabled', val: enabledCount != null ? `${enabledCount}/${total}` : '—', alert: enabledCount != null && enabledCount < total },
    { label: 'Total Calls', val: totalCalls },
    { label: 'Error Rate', val: errorRate, alert: errorRateValue > 0.05 },
    { label: 'Avg Latency', val: avgLatency, alert: avgLatencyValue > 1500 },
    { label: 'Completed Sessions', val: completed },
  ];

  return (
    <div style={{
      display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)',
      borderBottom: '1px solid var(--harness-border)',
    }}>
      {cells.map((c, i) => (
        <div key={c.label} style={{
          padding: '14px 20px',
          borderRight: i < cells.length - 1 ? '1px solid var(--harness-border)' : 'none',
        }}>
          <div style={{
            fontSize: 10, fontFamily: 'var(--font-mono)', textTransform: 'uppercase',
            letterSpacing: '0.06em', color: c.alert ? '#D89040' : '#4A6080', marginBottom: 5,
          }}>{c.label}</div>
          <div style={{
            fontFamily: 'var(--font-mono)', fontSize: 22, fontWeight: 600,
            color: c.alert ? '#D89040' : '#E2EBF7', letterSpacing: '-0.03em',
          }}>{c.val}</div>
        </div>
      ))}
    </div>
  );
}

// ── Agent table ───────────────────────────────────────────────────
function AgentRow({ agent, onToggle, pending }) {
  const killable = agent.killable === true;
  const enabled = agent.enabled;
  const errorRate = agent.calls > 0
    ? ((agent.errors / agent.calls) * 100).toFixed(1) + '%' : '0.0%';
  const id = `toggle-${agent.tool_name}`;

  return (
    <tr style={{ borderBottom: '1px solid var(--harness-border)' }}>
      <td style={{ padding: '10px 16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Dot active={enabled} />
          <span style={{ fontSize: 12, fontWeight: 500, color: '#E2EBF7' }}>{agent.display_name}</span>
        </div>
      </td>
      <td style={{ padding: '10px 16px' }}>
        {agent.type && <HBadge type="blue">{agent.type}</HBadge>}
      </td>
      <td style={{ padding: '10px 16px', fontFamily: 'var(--font-mono)', fontSize: 11, color: '#4A9EE8' }}>
        {agent.model || '—'}
      </td>
      <td style={{ padding: '10px 16px' }}>
        <HBadge type={enabled ? 'green' : 'red'}>{enabled ? 'Enabled' : 'Disabled'}</HBadge>
      </td>
      <td style={{ padding: '10px 16px', fontFamily: 'var(--font-mono)', fontSize: 11, color: '#7A96B4' }}>
        {agent.calls ?? '—'}
      </td>
      <td style={{ padding: '10px 16px', fontFamily: 'var(--font-mono)', fontSize: 11 }}>
        <span style={{ color: agent.errors > 0 ? '#D89040' : '#7A96B4' }}>
          {agent.errors ?? '—'} ({errorRate})
        </span>
      </td>
      <td style={{ padding: '10px 16px', fontFamily: 'var(--font-mono)', fontSize: 11 }}>
        {agent.avg_latency_ms != null ? (
          <span style={{ color: latencyColor(agent.avg_latency_ms).replace('var(--', '#').replace(')', '') }}>
            {fmtMs(agent.avg_latency_ms)}
          </span>
        ) : '—'}
      </td>
      <td style={{ padding: '10px 16px', fontFamily: 'var(--font-mono)', fontSize: 11, color: '#4A6080' }}>
        {fmtTs(agent.last_called)}
      </td>
      <td style={{ padding: '10px 16px' }}>
        {killable ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Toggle
              id={id}
              checked={enabled}
              onChange={() => onToggle(agent)}
              disabled={pending}
            />
            {pending && <Spinner size={12} dark />}
          </div>
        ) : (
          <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: '#4A6080' }}>Protected</span>
        )}
      </td>
    </tr>
  );
}

function AgentRegistry({ agents, loading, error, onToggle, pendingToggle }) {
  const theadStyle = {
    fontFamily: 'var(--font-mono)', fontSize: 10, textTransform: 'uppercase',
    letterSpacing: '0.06em', color: '#4A6080', padding: '8px 16px',
    textAlign: 'left', fontWeight: 500, whiteSpace: 'nowrap',
    borderBottom: '2px solid var(--harness-border)',
  };

  return (
    <Panel>
      <PanelHeader
        title="Agent Registry"
        right={agents ? `${agents.filter(a => a.enabled).length}/${agents.length} enabled` : '—'}
      />
      <div style={{ overflowX: 'auto' }}>
        {loading && !agents?.length ? (
          <EmptyState dark><Spinner dark size={13} /> Loading agents…</EmptyState>
        ) : error && !agents?.length ? (
          <EmptyState dark>Could not load agents: {error}</EmptyState>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
            <thead>
              <tr>
                {['Agent', 'Type', 'Model', 'Status', 'Calls', 'Errors', 'Avg Latency', 'Last Called', 'Kill Switch'].map(h => (
                  <th key={h} style={theadStyle}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(agents || []).map(agent => (
                <AgentRow
                  key={agent.tool_name}
                  agent={agent}
                  onToggle={onToggle}
                  pending={pendingToggle === agent.tool_name}
                />
              ))}
            </tbody>
          </table>
        )}
      </div>
    </Panel>
  );
}

// ── Session audit ─────────────────────────────────────────────────
function AuditPanel({ auditData, auditLoading, auditError }) {
  const [expanded, setExpanded] = useState(null);
  const [detailData, setDetailData] = useState({});
  const [loadingDetail, setLoadingDetail] = useState(null);

  async function toggleSession(sid) {
    if (expanded === sid) { setExpanded(null); return; }
    setExpanded(sid);
    if (detailData[sid]) return;
    setLoadingDetail(sid);
    try {
      const data = await api.auditSession(sid);
      setDetailData(prev => ({ ...prev, [sid]: data }));
    } catch {
      setDetailData(prev => ({ ...prev, [sid]: { error: true } }));
    } finally {
      setLoadingDetail(null);
    }
  }

  const sessions = auditData?.sessions || [];
  const stats = auditData?.stats || {};
  const theadStyle = {
    fontFamily: 'var(--font-mono)', fontSize: 10, textTransform: 'uppercase',
    letterSpacing: '0.06em', color: '#4A6080', padding: '8px 14px',
    textAlign: 'left', fontWeight: 500, whiteSpace: 'nowrap',
    borderBottom: '2px solid var(--harness-border)',
  };

  return (
    <Panel>
      <PanelHeader
        title="Session Audit"
        right={`${stats.total_sessions ?? sessions.length} sessions`}
      />
      {auditLoading && !sessions.length ? (
        <EmptyState dark><Spinner dark size={13} /> Loading sessions…</EmptyState>
      ) : auditError && !sessions.length ? (
        <EmptyState dark>Could not load audit: {auditError}</EmptyState>
      ) : sessions.length === 0 ? (
        <EmptyState dark>No sessions recorded yet.</EmptyState>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
            <thead>
              <tr>
                {['Time', 'Session ID', 'Query', 'Intent', 'Steps', 'Latency'].map(h => (
                  <th key={h} style={theadStyle}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sessions.map(s => (
                <React.Fragment key={s.session_id}>
                  <tr
                    onClick={() => toggleSession(s.session_id)}
                    style={{ cursor: 'pointer', borderBottom: '1px solid var(--harness-border)' }}
                    onMouseEnter={e => Array.from(e.currentTarget.cells).forEach(c => c.style.background = 'rgba(255,255,255,0.02)')}
                    onMouseLeave={e => Array.from(e.currentTarget.cells).forEach(c => c.style.background = '')}
                  >
                    <td style={{ padding: '9px 14px', fontFamily: 'var(--font-mono)', fontSize: 11, color: '#4A6080', whiteSpace: 'nowrap' }}>
                      {fmtDate(s.timestamp)}
                    </td>
                    <td style={{ padding: '9px 14px', fontFamily: 'var(--font-mono)', fontSize: 11, color: '#4A9EE8' }}>
                      {s.session_id?.slice(0, 8)}…
                    </td>
                    <td style={{ padding: '9px 14px', color: '#7A96B4', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {truncate(s.query, 40)}
                    </td>
                    <td style={{ padding: '9px 14px' }}>
                      <IntentBadge intent={s.intent} />
                    </td>
                    <td style={{ padding: '9px 14px', fontFamily: 'var(--font-mono)', fontSize: 11, color: '#E2EBF7' }}>
                      {s.step_count}
                    </td>
                    <td style={{ padding: '9px 14px', fontFamily: 'var(--font-mono)', fontSize: 11, color: '#7A96B4' }}>
                      {fmtMs(s.total_ms)}
                    </td>
                  </tr>

                  {expanded === s.session_id && (
                    <tr>
                      <td colSpan={6} style={{ padding: '0 14px 14px' }}>
                        <div style={{
                          background: 'rgba(255,255,255,0.02)',
                          border: '1px solid var(--harness-border)',
                          borderRadius: 6, padding: '12px 14px',
                          animation: 'fadeIn 0.2s ease-out',
                        }}>
                          {loadingDetail === s.session_id ? (
                            <div style={{ display: 'flex', gap: 8, alignItems: 'center', color: '#4A6080', fontSize: 12 }}>
                              <Spinner size={13} dark /> Loading session detail…
                            </div>
                          ) : detailData[s.session_id]?.error ? (
                            <EmptyState dark>Failed to load session detail.</EmptyState>
                          ) : (
                            <AuditTrail
                              trail={detailData[s.session_id]?.audit_trail}
                              sessionId={s.session_id}
                              intent={s.intent}
                              stepCount={s.step_count}
                              totalMs={s.total_ms}
                            />
                          )}
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
}

// ── Governance ────────────────────────────────────────────────────
function GovernancePanel({ data, loading, error }) {
  if (loading) return <EmptyState dark><Spinner dark size={13} /> Loading…</EmptyState>;
  if (error) return <EmptyState dark>Could not load governance config: {error}</EmptyState>;
  if (!data) return <EmptyState dark>No governance data.</EmptyState>;

  const allRules = data.rules || [];

  if (!allRules.length) return <EmptyState dark>No governance rules returned by API.</EmptyState>;

  const typeColors = { input: 'teal', loop: 'blue', rag: 'amber', output: 'green' };
  const theadStyle = {
    fontFamily: 'var(--font-mono)', fontSize: 10, textTransform: 'uppercase',
    letterSpacing: '0.05em', color: '#4A6080', padding: '6px 12px',
    textAlign: 'left', fontWeight: 500,
    borderBottom: '2px solid var(--harness-border)',
  };

  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
        <thead>
          <tr>
            {['Category', 'Rule ID', 'Description', 'Value'].map(h => <th key={h} style={theadStyle}>{h}</th>)}
          </tr>
        </thead>
        <tbody>
          {allRules.map((rule, i) => (
            <tr key={i} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
              <td style={{ padding: '8px 12px' }}>
                <HBadge type={typeColors[rule.category] || 'neutral'}>{rule.category}</HBadge>
              </td>
              <td style={{ padding: '8px 12px', fontFamily: 'var(--font-mono)', fontSize: 11, color: '#E2EBF7' }}>
                {rule.id || rule.name || '—'}
              </td>
              <td style={{ padding: '8px 12px', color: '#7A96B4', fontSize: 12 }}>
                {rule.description || '—'}
              </td>
              <td style={{ padding: '8px 12px', fontFamily: 'var(--font-mono)', fontSize: 11, color: '#4ABFD8' }}>
                {rule.value != null ? String(rule.value) : '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function GuardrailEvents({ events }) {
  if (!events || events.length === 0) {
    return (
      <div style={{
        background: 'rgba(255,255,255,0.02)', border: '1px dashed rgba(255,255,255,0.06)',
        borderRadius: 5, padding: '14px 16px',
        fontFamily: 'var(--font-mono)', fontSize: 11, color: '#4A6080', lineHeight: 1.6,
      }}>
        No guardrail events have been recorded yet.
        <div style={{ marginTop: 6, fontSize: 10, opacity: 0.7 }}>
          Trigger an input, retrieval, orchestration, or output guardrail to populate this feed.
        </div>
      </div>
    );
  }
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4, maxHeight: 180, overflowY: 'auto' }}>
      {events.map((ev, i) => (
        <div key={i} style={{
          fontFamily: 'var(--font-mono)', fontSize: 11,
          padding: '5px 10px', borderRadius: 4,
          borderLeft: '3px solid #D89040',
          background: 'rgba(216,144,64,0.06)',
          display: 'flex', gap: 8,
        }}>
          <span style={{ color: '#4A6080', whiteSpace: 'nowrap' }}>{fmtTs(ev.timestamp)}</span>
          <span style={{ color: '#D89040' }}>{ev.event_type || '—'}</span>
          <span style={{ color: '#7A96B4' }}>{ev.detail || ''}</span>
        </div>
      ))}
    </div>
  );
}

// ── Kill switch log ───────────────────────────────────────────────
function KillSwitchLog({ events }) {
  if (!events || events.length === 0) {
    return <EmptyState dark>No kill-switch events recorded.</EmptyState>;
  }
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4, maxHeight: 160, overflowY: 'auto' }}>
      {events.map((ev, i) => (
        <div key={i} style={{
          fontFamily: 'var(--font-mono)', fontSize: 11,
          padding: '6px 10px', borderRadius: 4,
          borderLeft: `3px solid ${ev.action === 'disabled' ? '#E05C5C' : '#34C97A'}`,
          background: ev.action === 'disabled' ? 'rgba(224,92,92,0.05)' : 'rgba(52,201,122,0.05)',
          display: 'flex', gap: 8, alignItems: 'center',
        }}>
          <span style={{ color: '#4A6080', whiteSpace: 'nowrap' }}>{fmtDate(ev.ts)}</span>
          <HBadge type={ev.action === 'disabled' ? 'red' : 'green'}>{ev.action?.toUpperCase() || '—'}</HBadge>
          <span style={{ color: '#7A96B4' }}>{ev.agent || ev.display_name || '—'}</span>
        </div>
      ))}
    </div>
  );
}

// ── Latency bars ──────────────────────────────────────────────────
function LatencyBars({ metrics }) {
  if (!metrics?.agents) return <EmptyState dark>No latency data available.</EmptyState>;
  const entries = metrics.agents.map(agent => [agent.display_name, agent]);
  if (!entries.length) return <EmptyState dark>No agent latency recorded.</EmptyState>;

  const maxMs = Math.min(Math.max(...entries.map(([, v]) => v.avg_latency_ms || 0), 1), 2000);

  function barColor(ms) {
    if (ms < 500) return '#34C97A';
    if (ms < 1200) return '#D89040';
    return '#E05C5C';
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {entries.map(([name, stats]) => {
        const ms = stats.avg_latency_ms || 0;
        const pct = Math.min((ms / maxMs) * 100, 100);
        const col = barColor(ms);
        return (
          <div key={name} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{
              fontFamily: 'var(--font-mono)', fontSize: 11, color: '#7A96B4',
              width: 170, flexShrink: 0,
              overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
            }}>{name}</span>
            <div style={{ flex: 1, height: 6, background: 'rgba(255,255,255,0.06)', borderRadius: 3, overflow: 'hidden' }}>
              <div style={{ width: `${pct}%`, height: '100%', background: col, borderRadius: 3, transition: 'width 0.5s' }} />
            </div>
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: col, width: 60, textAlign: 'right', flexShrink: 0 }}>
              {fmtMs(ms)}
            </span>
          </div>
        );
      })}
    </div>
  );
}

// ── Live log ──────────────────────────────────────────────────────
function LiveLog({ logs }) {
  if (!logs || !logs.length) return <EmptyState dark>No log entries yet.</EmptyState>;

  const eventColors = {
    agent_call: '#4ABFD8', model_call: '#4A9EE8',
    guardrail_trigger: '#D89040', kill_switch_toggle: '#E05C5C',
    session_start: '#7A96B4', session_end: '#7A96B4',
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4, maxHeight: 240, overflowY: 'auto' }}>
      {logs.slice(0, 20).map((entry, i) => {
        const col = eventColors[entry.event] || '#7A96B4';
        const detail = entry.detail || entry.query || entry.agent || '';
        return (
          <div key={i} style={{
            fontFamily: 'var(--font-mono)', fontSize: 11,
            padding: '5px 10px', borderRadius: 4,
            borderLeft: `3px solid ${col}`,
            background: 'rgba(255,255,255,0.02)',
            display: 'flex', gap: 8, alignItems: 'flex-start', lineHeight: 1.4,
          }}>
            <span style={{ color: '#4A6080', whiteSpace: 'nowrap', flexShrink: 0 }}>{fmtTs(entry.ts)}</span>
            <span style={{ fontSize: 9, padding: '1px 5px', borderRadius: 3, background: `${col}22`, color: col, marginTop: 1, flexShrink: 0 }}>
              {entry.event}
            </span>
            <span style={{ color: '#7A96B4', wordBreak: 'break-all' }}>
              {entry.agent ? `[${entry.agent}] ` : ''}{truncate(detail, 80)}
              {entry.latency_ms != null && <span style={{ color: '#4A6080' }}> {fmtMs(entry.latency_ms)}</span>}
            </span>
          </div>
        );
      })}
    </div>
  );
}

// ── Confirm dialog ────────────────────────────────────────────────
function ConfirmDialog({ agent, onConfirm, onCancel }) {
  useEffect(() => {
    function onKey(e) { if (e.key === 'Escape') onCancel(); }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onCancel]);

  return (
    <div
      style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}
      onClick={e => { if (e.target === e.currentTarget) onCancel(); }}
      role="dialog"
      aria-modal="true"
      aria-label={`Confirm ${agent.enabled ? 'disable' : 'enable'} ${agent.display_name}`}
    >
      <div style={{
        background: '#1A2F4A', border: '1px solid rgba(255,255,255,0.12)',
        borderRadius: 8, padding: 28, maxWidth: 400, width: '90%',
        animation: 'fadeIn 0.2s ease-out', boxShadow: '0 20px 48px rgba(0,0,0,0.5)',
      }}>
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: '#D89040', marginBottom: 12, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          Confirm Kill Switch Toggle
        </div>
        <div style={{ fontSize: 14, fontWeight: 600, color: '#E2EBF7', marginBottom: 8 }}>
          {agent.enabled ? 'Disable' : 'Enable'} {agent.display_name}?
        </div>
        <div style={{ fontSize: 12, color: '#7A96B4', lineHeight: 1.6, marginBottom: 22 }}>
          {agent.enabled
            ? `Disabling ${agent.display_name} will immediately stop it from handling new requests.`
            : `Enabling ${agent.display_name} will allow it to handle new requests immediately.`}
        </div>
        <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
          <button
            onClick={onCancel}
            style={{
              padding: '7px 16px', borderRadius: 6,
              border: '1px solid rgba(255,255,255,0.12)',
              background: 'none', color: '#7A96B4', fontSize: 12, cursor: 'pointer',
            }}
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            autoFocus
            style={{
              padding: '7px 16px', borderRadius: 6, border: 'none',
              background: agent.enabled ? '#B42318' : '#067647',
              color: 'white', fontSize: 12, fontWeight: 600, cursor: 'pointer',
            }}
          >
            {agent.enabled ? 'Disable agent' : 'Enable agent'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Sub-section label ─────────────────────────────────────────────
function SubLabel({ children }) {
  return (
    <div style={{
      fontFamily: 'var(--font-mono)', fontSize: 10, textTransform: 'uppercase',
      letterSpacing: '0.06em', color: '#4A6080', padding: '10px 18px',
      borderTop: '1px solid var(--harness-border)',
    }}>{children}</div>
  );
}

// ── Main dashboard ────────────────────────────────────────────────
export default function DashboardPage() {
  const backendStatus = useBackendHealth();
  const [pendingToggle, setPendingToggle] = useState(null);
  const [confirmAgent, setConfirmAgent] = useState(null);
  const [toast, setToast] = useState(null);
  const [agents, setAgents] = useState(null);

  const agentFetcher   = useCallback(() => api.agents(), []);
  const auditFetcher   = useCallback(() => api.audit(20), []);
  const metricsFetcher = useCallback(() => api.metrics(), []);
  const govFetcher     = useCallback(() => api.governance(), []);
  const logsFetcher    = useCallback(() => api.logs(20), []);
  const killFetcher    = useCallback(() => api.killSwitchLog(10), []);

  const agentPoll   = usePoll(agentFetcher, 5000);
  const auditPoll   = usePoll(auditFetcher, 5000);
  const metricsPoll = usePoll(metricsFetcher, 5000);
  const govPoll     = usePoll(govFetcher, 30000);
  const logsPoll    = usePoll(logsFetcher, 5000);
  const killPoll    = usePoll(killFetcher, 5000);

  useEffect(() => {
    if (agentPoll.data?.agents) setAgents(agentPoll.data.agents);
  }, [agentPoll.data]);

  async function doToggle(agent) {
    setPendingToggle(agent.tool_name);
    try {
      const response = await api.toggleAgent(agent.tool_name, !agent.enabled);
      setAgents(prev => prev.map(a => a.tool_name === agent.tool_name ? response.agent : a));
      setToast({ message: `${agent.display_name} ${agent.enabled ? 'disabled' : 'enabled'}.`, type: 'success' });
      agentPoll.refresh();
      killPoll.refresh();
    } catch (e) {
      setToast({ message: `Toggle failed: ${e.message}`, type: 'error' });
    } finally {
      setPendingToggle(null);
    }
  }

  function requestToggle(agent) {
    if (!agent.killable) return;
    setConfirmAgent(agent);
  }

  const allAgents = agents || agentPoll.data?.agents || [];
  const lastRefresh = agentPoll.lastRefresh;

  function refreshAll() {
    agentPoll.refresh();
    auditPoll.refresh();
    metricsPoll.refresh();
    govPoll.refresh();
    logsPoll.refresh();
    killPoll.refresh();
  }

  return (
    <div style={{ minHeight: '100vh', background: 'var(--harness-bg)', color: 'var(--harness-text)' }}>
      <AppNav active="/dashboard" />

      {/* Harness header bar */}
      <div style={{
        background: '#0B1A2E',
        borderBottom: '1px solid var(--harness-border)',
        padding: '10px 20px',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <div>
            <div style={{ fontSize: 14, fontWeight: 700, color: '#E2EBF7' }}>Control Panel</div>
            <div style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: '#4A6080', marginTop: 1, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
              Internal Operations Console
            </div>
          </div>
          <div style={{ width: 1, height: 32, background: 'var(--harness-border)' }} />
          <StatusPill status={backendStatus} />
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          {lastRefresh && (
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: '#4A6080' }}>
              Refreshed {lastRefresh.toLocaleTimeString('en-IN', { hour12: false })}
            </span>
          )}
          <button
            onClick={refreshAll}
            style={{
              fontFamily: 'var(--font-mono)', fontSize: 11, color: '#7A96B4',
              border: '1px solid var(--harness-border)',
              borderRadius: 4, padding: '4px 12px', cursor: 'pointer',
              background: 'transparent',
            }}
          >
            Refresh
          </button>
          <span style={{
            fontSize: 10, fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.05em',
            color: '#D89040', background: 'rgba(216,144,64,0.08)',
            border: '1px solid rgba(216,144,64,0.2)', borderRadius: 3, padding: '2px 8px',
          }}>Internal</span>
        </div>
      </div>

      {/* Summary strip */}
      <SummaryStrip metrics={metricsPoll.data} agents={allAgents} />

      {/* Main content */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '1fr 1fr',
        gap: 16, padding: 16,
        maxWidth: 1600, margin: '0 auto',
      }}>
        {/* ── LEFT ── */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

          {/* Agent Registry */}
          <AgentRegistry
            agents={allAgents}
            loading={agentPoll.loading}
            error={agentPoll.error}
            onToggle={requestToggle}
            pendingToggle={pendingToggle}
          />

          {/* Kill Switch Log */}
          <Panel>
            <PanelHeader title="Kill Switch History" right={`${killPoll.data?.events?.length ?? 0} events`} />
            <div style={{ padding: '12px 18px' }}>
              <KillSwitchLog events={killPoll.data?.events} />
            </div>
          </Panel>

          {/* Governance */}
          <Panel>
            <PanelHeader
              title="Governance — Configured Rules"
              right={govPoll.data ? `${govPoll.data.rule_count || 0} rules` : '—'}
            />
            <div style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: '#4A6080', padding: '10px 18px 0' }}>
              Configuration reference only. Presence here is not proof of regulatory compliance.
            </div>
            <div style={{ padding: '10px 0' }}>
              <GovernancePanel data={govPoll.data} loading={govPoll.loading} error={govPoll.error} />
            </div>
            <SubLabel>Guardrail Events</SubLabel>
            <div style={{ padding: '10px 18px 16px' }}>
              <GuardrailEvents events={govPoll.data?.trigger_log} />
            </div>
          </Panel>
        </div>

        {/* ── RIGHT ── */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

          {/* Observability */}
          <Panel>
            <PanelHeader title="Observability" />

            <div style={{ padding: '12px 18px 4px' }}>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.06em', color: '#4A6080', marginBottom: 10 }}>
                Per-Agent Avg Latency
              </div>
              {metricsPoll.loading && !metricsPoll.data ? (
                <EmptyState dark><Spinner dark size={13} /></EmptyState>
              ) : (
                <LatencyBars metrics={metricsPoll.data} />
              )}
            </div>

            <SubLabel>Structured Log Stream</SubLabel>
            <div style={{ padding: '10px 18px 16px' }}>
              {logsPoll.loading && !logsPoll.data ? (
                <EmptyState dark><Spinner dark size={13} /></EmptyState>
              ) : (
                <LiveLog logs={logsPoll.data?.logs} />
              )}
            </div>
          </Panel>

          {/* Session Audit */}
          <AuditPanel
            auditData={auditPoll.data}
            auditLoading={auditPoll.loading}
            auditError={auditPoll.error}
          />
        </div>
      </div>

      {/* Dialogs & toasts */}
      {confirmAgent && (
        <ConfirmDialog
          agent={confirmAgent}
          onConfirm={() => { const a = confirmAgent; setConfirmAgent(null); doToggle(a); }}
          onCancel={() => setConfirmAgent(null)}
        />
      )}
      {toast && <Toast message={toast.message} type={toast.type} onDone={() => setToast(null)} />}
    </div>
  );
}
