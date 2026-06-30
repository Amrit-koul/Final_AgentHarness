import React, { useCallback, useMemo, useState } from 'react';
import PageHeader from './control/PageHeader';
import { DecisionChip, SeverityChip } from './control/Chips';
import { LoadingState, SectionCard, asArray, display, fmtTime } from './control/Common';
import { useControlData } from '../hooks/useControlData';
import { controlPlaneApi } from '../services/controlPlaneApi';

// ─── Event name mapping ───────────────────────────────────────────────────────
// Internal hook names from agent_harness/primitives.py are stored verbatim
// in observability_events as "HOOK_<HOOK_NAME_UPPER>". We map them to
// business-readable labels for the main audit table.
// Raw names are still available in the "Technical Details" expandable row.

const HOOK_LABEL_MAP = {
  HOOK_PRE_INVOKE:      'HARNESS_PRE_CHECK',
  HOOK_POST_INVOKE:     'HARNESS_POST_CHECK',
  HOOK_ON_COST_RECORD:  'TELEMETRY_RECORDED',
  HOOK_ON_ERROR:        'HARNESS_ERROR_CAUGHT',
  HOOK_ON_KILL:         'KILL_SWITCH_TRIGGERED',
  HOOK_ON_GUARDRAIL:    'GUARDRAIL_EVALUATED',
  HOOK_ON_POLICY:       'POLICY_EVALUATED',
};

// Preferred ordering for the harness trace flow. Events matching these labels
// will be sorted to the top within the same trace, in this order.
const PREFERRED_EVENT_ORDER = [
  'RUN_STARTED',
  'AGENT_CATALOG_LOOKUP',
  'HARNESS_PRE_CHECK',
  'PLUGIN_INVOKED',
  'ADAPTER_NORMALIZED_OUTPUT',
  'POLICY_DECISION',
  'POLICY_EVALUATED',
  'GUARDRAIL_EVALUATED',
  'HARNESS_POST_CHECK',
  'TELEMETRY_RECORDED',
  'AUDIT_COMMITTED',
  'RUN_COMPLETED',
];

/**
 * Maps a raw backend event_type to its business-readable label.
 * Unknown HOOK_* names get a generic HARNESS_HOOK label.
 * All other event_type values pass through unchanged.
 */
function toDisplayLabel(rawEventType) {
  if (!rawEventType) return '—';
  const upper = rawEventType.toUpperCase();
  if (HOOK_LABEL_MAP[upper]) return HOOK_LABEL_MAP[upper];
  if (upper.startsWith('HOOK_')) return 'HARNESS_HOOK';   // unknown hook — still safe to show
  return rawEventType;
}

/** Returns true if this is a raw internal hook name that should be hidden from the main column. */
function isInternalHook(rawEventType) {
  if (!rawEventType) return false;
  return rawEventType.toUpperCase().startsWith('HOOK_');
}

/** Human-readable description for known event labels shown in Evidence column. */
function eventDescription(displayLabel, row) {
  switch (displayLabel) {
    case 'RUN_STARTED':              return 'Request received and trace initialised by harness.';
    case 'AGENT_CATALOG_LOOKUP':     return 'Registered agent located in Agent Catalog.';
    case 'HARNESS_PRE_CHECK':        return 'Pre-execution checks run: identity, policy, guardrails.';
    case 'PLUGIN_INVOKED':           return 'External / vendored plugin invoked through harness adapter.';
    case 'ADAPTER_NORMALIZED_OUTPUT': return 'Plugin output converted to harness-standard schema.';
    case 'POLICY_DECISION':          return row.reason || 'Policy Engine evaluated the agent output.';
    case 'POLICY_EVALUATED':         return row.reason || 'Policy Engine evaluated the agent output.';
    case 'GUARDRAIL_EVALUATED':      return row.reason || 'Guardrail check completed.';
    case 'HARNESS_POST_CHECK':       return 'Post-execution checks run: output validation, cost recording.';
    case 'TELEMETRY_RECORDED':       return 'Usage and cost telemetry written to observability store.';
    case 'AUDIT_COMMITTED':          return 'Audit evidence committed to the immutable audit trail.';
    case 'RUN_COMPLETED':            return 'Final governed response returned to caller.';
    case 'KILL_SWITCH_TRIGGERED':    return row.reason || 'Kill switch fired — agent execution halted.';
    case 'HARNESS_ERROR_CAUGHT':     return row.reason || 'Harness caught and contained an execution error.';
    case 'HARNESS_HOOK':             return 'Internal harness hook recorded.';
    default:                         return row.reason || row.detail || '';
  }
}

export default function AuditTrail() {
  const [source, setSource] = useState('all');
  const [expandedRow, setExpandedRow] = useState(null);

  const fetchAudit = useCallback(async () => {
    const [events, policy, guardrails, kill, degradation] = await Promise.all([
      controlPlaneApi.listEvents(),
      controlPlaneApi.listPolicyDecisions(),
      controlPlaneApi.listGuardrailEvents(),
      controlPlaneApi.listKillSwitchEvents(),
      controlPlaneApi.listDegradationEvents(),
    ]);

    return [
      // Observability events — map HOOK_* to readable labels
      ...asArray(events, 'events').map((item) => ({
        ...item,
        _source: 'Event',
        _raw_event_type: item.event_type,
        _display_event: toDisplayLabel(item.event_type),
        _is_internal: isInternalHook(item.event_type),
        _evidence: eventDescription(toDisplayLabel(item.event_type), item),
      })),
      // Policy decisions — always use POLICY_DECISION label
      ...asArray(policy, 'decisions').map((item) => ({
        ...item,
        _source: 'Policy',
        _raw_event_type: item.action || 'POLICY_DECISION',
        _display_event: 'POLICY_DECISION',
        _is_internal: false,
        _evidence: item.reason || item.rule_id || '',
      })),
      // Guardrail events
      ...asArray(guardrails, 'events').map((item) => ({
        ...item,
        _source: 'Guardrail',
        _raw_event_type: item.event_type || item.guardrail_id || 'GUARDRAIL_EVALUATED',
        _display_event: toDisplayLabel(item.event_type || item.guardrail_id || 'GUARDRAIL_EVALUATED'),
        _is_internal: false,
        _evidence: item.reason || item.detail || '',
      })),
      // Kill switch events
      ...asArray(kill, 'events').map((item) => ({
        ...item,
        _source: 'Kill Switch',
        _raw_event_type: item.event_type || 'KILL_SWITCH_TRIGGERED',
        _display_event: 'KILL_SWITCH_TRIGGERED',
        _is_internal: false,
        _evidence: item.reason || '',
      })),
      // Degradation events
      ...asArray(degradation, 'events').map((item) => ({
        ...item,
        _source: 'Degradation',
        _raw_event_type: item.event_type || 'QUALITY_DEGRADATION',
        _display_event: toDisplayLabel(item.event_type || 'QUALITY_DEGRADATION'),
        _is_internal: false,
        _evidence: item.reason || item.detail || '',
      })),
    ].sort((a, b) => new Date(b.timestamp || 0) - new Date(a.timestamp || 0));
  }, []);

  const state = useControlData(fetchAudit, [], 5000);

  const rows = useMemo(() => {
    const all = state.data || [];
    const filtered = source === 'all' ? all : all.filter((item) => item._source === source);
    // Within each timestamp bucket, sort by preferred event order so the harness
    // trace flow reads top-to-bottom in a coherent sequence.
    return filtered.sort((a, b) => {
      const timeDiff = new Date(b.timestamp || 0) - new Date(a.timestamp || 0);
      if (timeDiff !== 0) return timeDiff;
      const ai = PREFERRED_EVENT_ORDER.indexOf(a._display_event);
      const bi = PREFERRED_EVENT_ORDER.indexOf(b._display_event);
      if (ai === -1 && bi === -1) return 0;
      if (ai === -1) return 1;
      if (bi === -1) return -1;
      return ai - bi;
    });
  }, [state.data, source]);

  function toggleExpand(key) {
    setExpandedRow(prev => (prev === key ? null : key));
  }

  return (
    <>
      <PageHeader
        title="Audit Trail"
        subtitle="Business-readable trace of harness activity. All events are sourced directly from control-plane endpoints — no synthetic data."
        right={<button className="cc-button" onClick={state.reload}>Refresh</button>}
      />
      <div style={{ margin: '0 0 16px 0', padding: '10px 14px', borderRadius: 6, background: 'var(--surface-inset)', border: '1px solid var(--border)', fontSize: 13, color: 'var(--text-muted)' }}>
        ℹ️ Internal harness hook names (HOOK_*) are mapped to business-readable labels in this view. Raw event names are visible in the Technical Details row for each event.
      </div>
      <SectionCard
        title="Control-Plane Audit Trail"
        subtitle="Events from the harness runtime, policy engine, guardrails, and lifecycle controls."
        right={
          <select className="cc-input" value={source} onChange={(e) => setSource(e.target.value)}>
            <option value="all">All sources</option>
            {['Event', 'Policy', 'Guardrail', 'Kill Switch', 'Degradation'].map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
        }
      >
        <LoadingState loading={state.loading} error={state.error} empty={!state.loading && rows.length === 0}>
          No audit events recorded. Run Collections to populate this view.
        </LoadingState>
        {rows.length > 0 && (
          <div className="cc-table-scroll">
            <table className="cc-table">
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>Trace ID</th>
                  <th>Agent</th>
                  <th>Event</th>
                  <th>Decision</th>
                  <th>Evidence / Reason</th>
                  <th style={{ width: 40 }}></th>
                </tr>
              </thead>
              <tbody>
                {rows.map((item, index) => {
                  const rowKey = `${item._source}-${item.id || index}`;
                  const isExpanded = expandedRow === rowKey;
                  const hasRawDetail = item._is_internal || item._raw_event_type !== item._display_event;
                  return (
                    <React.Fragment key={rowKey}>
                      <tr style={item._is_internal ? { opacity: 0.75 } : {}}>
                        <td>{fmtTime(item.timestamp)}</td>
                        <td className="mono" style={{ fontSize: 11 }}>{display(item.trace_id)}</td>
                        <td className="mono">{display(item.agent_id)}</td>
                        <td>
                          <EventLabel label={item._display_event} source={item._source} />
                        </td>
                        <td>
                          {item.decision
                            ? <DecisionChip decision={item.decision} />
                            : item.new_status
                              ? <DecisionChip decision={item.new_status} />
                              : '—'}
                        </td>
                        <td style={{ fontSize: 12, color: 'var(--text-muted)', maxWidth: 280 }}>
                          {item._evidence || display(item.reason) || '—'}
                        </td>
                        <td>
                          {hasRawDetail && (
                            <button
                              className="cc-button"
                              style={{ fontSize: 10, padding: '2px 6px' }}
                              onClick={() => toggleExpand(rowKey)}
                              title="Show technical details"
                            >
                              {isExpanded ? '▲' : '▼'}
                            </button>
                          )}
                        </td>
                      </tr>
                      {isExpanded && (
                        <tr style={{ background: 'var(--surface-inset)' }}>
                          <td colSpan={7} style={{ padding: '8px 16px', fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                            <strong style={{ color: 'var(--text)' }}>Technical Details</strong>
                            <div style={{ marginTop: 4 }}>
                              Raw event type: <span style={{ color: 'var(--warning)' }}>{item._raw_event_type}</span>
                            </div>
                            {item.severity && <div>Severity: {String(item.severity)}</div>}
                            {item.source && item._source !== item.source && <div>Source field: {item.source}</div>}
                            {item.payload_json && <div style={{ marginTop: 4, wordBreak: 'break-all' }}>Payload: {item.payload_json}</div>}
                            {item.detail && <div style={{ marginTop: 4 }}>Detail: {item.detail}</div>}
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </SectionCard>
    </>
  );
}

// ─── EventLabel chip ─────────────────────────────────────────────────────────
const EVENT_COLOURS = {
  RUN_STARTED:              { bg: 'rgba(6,118,71,0.12)',  border: 'rgba(6,118,71,0.3)',   text: '#067647' },
  RUN_COMPLETED:            { bg: 'rgba(6,118,71,0.12)',  border: 'rgba(6,118,71,0.3)',   text: '#067647' },
  AUDIT_COMMITTED:          { bg: 'rgba(6,118,71,0.12)',  border: 'rgba(6,118,71,0.3)',   text: '#067647' },
  POLICY_DECISION:          { bg: 'rgba(220,130,0,0.12)', border: 'rgba(220,130,0,0.3)',  text: '#B45309' },
  POLICY_EVALUATED:         { bg: 'rgba(220,130,0,0.12)', border: 'rgba(220,130,0,0.3)',  text: '#B45309' },
  KILL_SWITCH_TRIGGERED:    { bg: 'rgba(180,35,24,0.12)', border: 'rgba(180,35,24,0.3)',  text: '#B42318' },
  HARNESS_ERROR_CAUGHT:     { bg: 'rgba(180,35,24,0.12)', border: 'rgba(180,35,24,0.3)',  text: '#B42318' },
  GUARDRAIL_EVALUATED:      { bg: 'rgba(74,90,200,0.12)', border: 'rgba(74,90,200,0.3)',  text: '#4A5AC8' },
  HARNESS_PRE_CHECK:        { bg: 'rgba(46,111,216,0.10)', border: 'rgba(46,111,216,0.25)', text: '#2E6FD8' },
  HARNESS_POST_CHECK:       { bg: 'rgba(46,111,216,0.10)', border: 'rgba(46,111,216,0.25)', text: '#2E6FD8' },
  TELEMETRY_RECORDED:       { bg: 'rgba(100,100,100,0.10)', border: 'rgba(100,100,100,0.25)', text: 'var(--text-muted)' },
  HARNESS_HOOK:             { bg: 'rgba(100,100,100,0.10)', border: 'rgba(100,100,100,0.25)', text: 'var(--text-muted)' },
  PLUGIN_INVOKED:           { bg: 'rgba(8,126,139,0.12)', border: 'rgba(8,126,139,0.3)',  text: '#087E8B' },
  ADAPTER_NORMALIZED_OUTPUT:{ bg: 'rgba(8,126,139,0.12)', border: 'rgba(8,126,139,0.3)',  text: '#087E8B' },
  AGENT_CATALOG_LOOKUP:     { bg: 'rgba(46,111,216,0.10)', border: 'rgba(46,111,216,0.25)', text: '#2E6FD8' },
};

function EventLabel({ label }) {
  const colours = EVENT_COLOURS[label] || {
    bg: 'rgba(100,100,100,0.08)', border: 'rgba(100,100,100,0.2)', text: 'var(--text-muted)',
  };
  return (
    <span style={{
      fontSize: 11, fontWeight: 700, fontFamily: 'var(--font-mono)',
      padding: '2px 8px', borderRadius: 4,
      background: colours.bg, border: `1px solid ${colours.border}`, color: colours.text,
      whiteSpace: 'nowrap',
    }}>
      {label}
    </span>
  );
}
