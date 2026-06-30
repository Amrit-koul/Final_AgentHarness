import React, { useCallback } from 'react';
import PageHeader from '../../components/control/PageHeader';
import { KpiStrip } from '../../components/control/Kpi';
import { Chip } from '../../components/control/Chips';
import { LoadingState, SectionCard, asArray, display, fmtTime } from '../../components/control/Common';
import { useControlData } from '../../hooks/useControlData';
import { controlPlaneApi } from '../../services/controlPlaneApi';
import { SourceBadge } from '../../utils/evidenceLabels';

const statusOf = (agent) => String(agent.status || '').toLowerCase();
const riskOf = (agent) => ['disabled', 'quarantined'].includes(statusOf(agent)) ? 'high' : statusOf(agent) === 'review' ? 'medium' : 'low';

export default function ControlTower() {
  const [excludeTest, setExcludeTest] = React.useState(true);
  const [timeFilter, setTimeFilter] = React.useState('today');

  const fetchDashboard = useCallback(async () => {
    const [agents, policy, guardrails, kill, degradation, toolAuth] = await Promise.all([
      controlPlaneApi.listAgents(), controlPlaneApi.listPolicyDecisions(), controlPlaneApi.listGuardrailEvents(), controlPlaneApi.listKillSwitchEvents(), controlPlaneApi.listDegradationEvents(), controlPlaneApi.listToolAuthorizationEvents(),
    ]);
    return {
      agents: asArray(agents, 'agents'), policy: asArray(policy, 'decisions'), guardrails: asArray(guardrails, 'events'),
      kill: asArray(kill, 'events'), degradation: asArray(degradation, 'events'), toolAuth: asArray(toolAuth, 'events'),
    };
  }, []);
  const state = useControlData(fetchDashboard, [], 5000);
  if (state.loading || state.error) return <><PageHeader title="Control Tower" subtitle="Estate health from the Agent Control Plane." /><LoadingState loading={state.loading} error={state.error} /></>;

  const { agents, policy: rawPolicy, guardrails: rawGuardrails, kill: rawKill, degradation: rawDegradation, toolAuth: rawToolAuth } = state.data;
  
  const todayStr = new Date().toDateString();
  const filterEvents = (arr) => {
    let res = arr;
    if (excludeTest) res = res.filter(e => e.source === 'runtime');
    if (timeFilter === 'today') res = res.filter(e => new Date(e.timestamp || e.started_at || 0).toDateString() === todayStr);
    return res;
  };
  
  const policy = filterEvents(rawPolicy);
  const toolAuth = filterEvents(rawToolAuth);
  const guardrails = filterEvents(rawGuardrails);
  const kill = filterEvents(rawKill);
  const degradation = filterEvents(rawDegradation);

  const active = agents.filter((agent) => statusOf(agent) === 'active').length;
  const review = agents.filter((agent) => statusOf(agent) === 'review').length;
  const stopped = agents.filter((agent) => ['disabled', 'quarantined'].includes(statusOf(agent))).length;
  const toolBlocks = toolAuth.filter((item) => String(item.decision).toUpperCase() === 'BLOCK').length;
  const degradedIds = new Set(degradation.map((item) => item.agent_id).filter(Boolean));
  
  const functions = Object.values(agents.reduce((result, agent) => {
    const name = agent.business_function || 'Unassigned';
    result[name] ||= { name, total: 0, active: 0, review: 0, critical: 0 };
    result[name].total += 1;
    const status = statusOf(agent);
    if (status === 'active') result[name].active += 1;
    else if (status === 'review') result[name].review += 1;
    else result[name].critical += 1;
    return result;
  }, {}));
  const risks = agents.reduce((result, agent) => ({ ...result, [riskOf(agent)]: (result[riskOf(agent)] || 0) + 1 }), {});
  
  const criticalEvents = [
    ...kill.map((event) => ({ ...event, source_label: 'Kill Switch', event_label: event.new_status || 'Status change' })),
    ...degradation.map((event) => ({ ...event, source_label: 'Degradation', event_label: 'Degradation detected' })),
    ...guardrails.filter((event) => String(event.decision).toUpperCase() === 'BLOCK').map((event) => ({ ...event, source_label: 'Guardrail', event_label: event.guardrail_id })),
    ...toolAuth.filter((event) => String(event.decision).toUpperCase() === 'BLOCK').map((event) => ({ ...event, source_label: 'Tool Auth', event_label: event.action })),
  ].sort((a, b) => new Date(b.timestamp || 0) - new Date(a.timestamp || 0)).slice(0, 10);

  return (
    <>
      <PageHeader title="Control Tower" subtitle="Agent inventory, governance activity, and critical lifecycle events from control-plane APIs." right={
        <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
          <select className="cc-input" value={timeFilter} onChange={(e) => setTimeFilter(e.target.value)}>
            <option value="today">Today only</option>
            <option value="all">All current database history</option>
          </select>
          <label className="cc-switch"><input type="checkbox" checked={!excludeTest} onChange={(e) => setExcludeTest(!e.target.checked)} /> Include admin/manual validation</label>
          <button className="cc-button" onClick={state.reload}>Refresh</button>
        </div>
      } />
      <KpiStrip items={[
        { label: 'Total Agents', value: agents.length }, 
        { label: 'Active Agents', value: active, accent: 'green' },
        { label: 'Agents in Review', value: review, accent: 'amber' }, 
        { label: 'Disabled / Quarantined', value: stopped, accent: 'red' },
        { label: 'Tool Auth Blocks', value: toolBlocks, accent: 'red' }, 
        { label: 'Guardrail Events', value: guardrails.length, accent: 'amber' },
        { label: 'Lifecycle Events', value: kill.length, accent: 'red' }, 
        { label: 'Quality Alerts', value: degradedIds.size, accent: 'amber' },
      ]} />
      <div className="cc-grid-2 cc-top-gap">
        <SectionCard title="AI Estate Health by Business Function" subtitle="This card uses config metadata only.">
          {functions.length === 0 ? <div className="cc-empty">No agents registered.</div> : functions.map((item) => (
            <div className="cc-health-row" key={item.name}><strong>{item.name}</strong><span>{item.total} agents</span><div><i className="green" style={{ width: `${item.total ? item.active / item.total * 100 : 0}%` }} /><i className="amber" style={{ width: `${item.total ? item.review / item.total * 100 : 0}%` }} /><i className="red" style={{ width: `${item.total ? item.critical / item.total * 100 : 0}%` }} /></div></div>
          ))}
        </SectionCard>
        <SectionCard title="Agent Risk Distribution" subtitle="This card uses config metadata only.">
          <div className="cc-risk-grid">{['low', 'medium', 'high'].map((level) => <div key={level}><Chip value={level} /><strong>{risks[level] || 0}</strong><span>agents</span></div>)}</div>
        </SectionCard>
      </div>
      <SectionCard title="Recent Critical Events" subtitle="Filtered runtime evidence for policy blocks, guardrail blocks, kill-switch actions, and degradation events." className="cc-top-gap">
        {criticalEvents.length === 0 ? <div className="cc-empty">No runtime events recorded today. Run Policy Assistant, Loan Assessment, Collections, or a tool authorization check to populate evidence.</div> : (
          <div className="cc-table-scroll"><table className="cc-table"><thead><tr><th>Time</th><th>Source</th><th>System</th><th>Agent</th><th>Event</th><th>Reason</th><th>Trace</th></tr></thead><tbody>{criticalEvents.map((event, index) => <tr key={`${event.source_label}-${event.id || index}`}><td>{fmtTime(event.timestamp)}</td><td><SourceBadge source={event.source} /></td><td><span className="cc-badge neutral">{event.source_label}</span></td><td className="mono">{display(event.agent_id)}</td><td>{display(event.event_label)}</td><td>{display(event.reason)}</td><td className="mono">{display(event.trace_id)}</td></tr>)}</tbody></table></div>
        )}
      </SectionCard>
    </>
  );
}
