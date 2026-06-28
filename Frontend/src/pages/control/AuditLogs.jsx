import React, { useCallback, useMemo, useState } from 'react';
import PageHeader from '../../components/control/PageHeader';
import { DecisionChip, SeverityChip } from '../../components/control/Chips';
import { LoadingState, SectionCard, asArray, display, fmtTime } from '../../components/control/Common';
import { useControlData } from '../../hooks/useControlData';
import { controlPlaneApi } from '../../services/controlPlaneApi';

export default function AuditLogs() {
  const [source, setSource] = useState('all');
  const fetchAudit = useCallback(async () => {
    const [events, policy, guardrails, kill, degradation] = await Promise.all([
      controlPlaneApi.listEvents(), controlPlaneApi.listPolicyDecisions(), controlPlaneApi.listGuardrailEvents(), controlPlaneApi.listKillSwitchEvents(), controlPlaneApi.listDegradationEvents(),
    ]);
    return [
      ...asArray(events, 'events').map((item) => ({ ...item, source: 'Event', event_type: item.event_type })),
      ...asArray(policy, 'decisions').map((item) => ({ ...item, source: 'Policy', event_type: item.action || 'Policy Decision' })),
      ...asArray(guardrails, 'events').map((item) => ({ ...item, source: 'Guardrail', event_type: item.guardrail_id || 'Guardrail Event' })),
      ...asArray(kill, 'events').map((item) => ({ ...item, source: 'Kill Switch', event_type: item.new_status || 'Status Change' })),
      ...asArray(degradation, 'events').map((item) => ({ ...item, source: 'Degradation', event_type: 'Degradation Event' })),
    ].sort((a, b) => new Date(b.timestamp || 0) - new Date(a.timestamp || 0));
  }, []);
  const state = useControlData(fetchAudit, [], 5000);
  const rows = useMemo(() => (state.data || []).filter((item) => source === 'all' || item.source === source), [state.data, source]);
  return (
    <>
      <PageHeader title="Audit Logs" subtitle="Unified audit view assembled only from control-plane event and decision endpoints." right={<button className="cc-button" onClick={state.reload}>Refresh</button>} />
      <SectionCard title="Control-Plane Audit" right={<select className="cc-input" value={source} onChange={(event) => setSource(event.target.value)}><option value="all">All sources</option>{['Event', 'Policy', 'Guardrail', 'Kill Switch', 'Degradation'].map((item) => <option key={item}>{item}</option>)}</select>}>
        <LoadingState loading={state.loading} error={state.error} empty={!state.loading && rows.length === 0}>No audit events recorded.</LoadingState>
        {rows.length > 0 && <div className="cc-table-scroll"><table className="cc-table"><thead><tr><th>Timestamp</th><th>Source</th><th>Agent ID</th><th>Event Type</th><th>Decision</th><th>Severity</th><th>Reason</th><th>Trace ID</th></tr></thead><tbody>{rows.map((item, index) => <tr key={`${item.source}-${item.id || index}`}><td>{fmtTime(item.timestamp)}</td><td>{item.source}</td><td className="mono">{display(item.agent_id)}</td><td>{display(item.event_type)}</td><td>{item.decision ? <DecisionChip decision={item.decision} /> : '—'}</td><td>{item.severity ? <SeverityChip severity={String(item.severity).toLowerCase()} /> : '—'}</td><td>{display(item.reason)}</td><td className="mono">{display(item.trace_id)}</td></tr>)}</tbody></table></div>}
      </SectionCard>
    </>
  );
}
