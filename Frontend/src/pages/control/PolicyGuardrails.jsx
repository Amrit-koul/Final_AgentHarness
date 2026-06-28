import React, { useCallback, useState } from 'react';
import PageHeader from '../../components/control/PageHeader';
import { KpiStrip } from '../../components/control/Kpi';
import { DecisionChip, SeverityChip } from '../../components/control/Chips';
import { LoadingState, SectionCard, asArray, display, fmtTime } from '../../components/control/Common';
import { useControlData } from '../../hooks/useControlData';
import { controlPlaneApi } from '../../services/controlPlaneApi';
import { SourceBadge } from '../../utils/evidenceLabels';

export default function PolicyGuardrails() {
  const [excludeTest, setExcludeTest] = useState(true);
  const [timeFilter, setTimeFilter] = useState('today');

  const fetchData = useCallback(async () => {
    const [guardrails, events, decisions, toolAuth] = await Promise.all([controlPlaneApi.listGuardrails(), controlPlaneApi.listGuardrailEvents(), controlPlaneApi.listPolicyDecisions(), controlPlaneApi.listToolAuthorizationEvents()]);
    return { guardrails: asArray(guardrails, 'guardrails'), events: asArray(events, 'events'), decisions: asArray(decisions, 'decisions'), toolAuth: asArray(toolAuth, 'events') };
  }, []);
  const state = useControlData(fetchData, [], 5000);
  const data = state.data || { guardrails: [], events: [], decisions: [], toolAuth: [] };
  
  const todayStr = new Date().toDateString();
  const filterEvents = (arr) => {
    let res = arr;
    if (excludeTest) {
      res = res.filter(item => {
        const src = String(item.source || '').toLowerCase();
        return !['admin_validation', 'manual_validation', 'simulation', 'demo_endpoint'].includes(src);
      });
    }
    if (timeFilter === 'today') {
      res = res.filter(item => {
        const dt = new Date(item.timestamp || item.created_at || 0);
        return dt.toDateString() === todayStr;
      });
    }
    return res;
  };

  const filteredToolAuth = filterEvents(data.toolAuth);
  const filteredEvents = filterEvents(data.events);
  const filteredDecisions = filterEvents(data.decisions);

  const blocks = filteredToolAuth.filter((item) => String(item.decision).toUpperCase() === 'BLOCK').length;
  const reviews = filteredToolAuth.filter((item) => String(item.decision).toUpperCase() === 'REVIEW').length;
  
  return (
    <>
      <PageHeader 
        title="Policy & Guardrails" 
        subtitle="Configured banking guardrails, their events, and persisted policy decisions." 
        right={
          <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
            <select className="cc-input" value={timeFilter} onChange={(e) => setTimeFilter(e.target.value)}>
              <option value="today">Today only</option>
              <option value="all">All current database history</option>
            </select>
            <label className="cc-switch"><input type="checkbox" checked={!excludeTest} onChange={(e) => setExcludeTest(!e.target.checked)} /> Include admin/test evidence</label>
            <button className="cc-button" onClick={state.reload}>Refresh</button>
          </div>
        } 
      />
      <LoadingState loading={state.loading} error={state.error} />
      {!state.loading && !state.error && <>
        <KpiStrip items={[
          { label: 'Configured Guardrails', value: data.guardrails.length }, 
          { label: 'Guardrail Events (Filtered)', value: filteredEvents.length, accent: 'amber' }, 
          { label: 'Tool Auth Blocks (Filtered)', value: blocks, accent: 'red' }, 
          { label: 'Tool Auth Reviews (Filtered)', value: reviews, accent: 'amber' }
        ]} />
        <SectionCard title="Banking Policy Matrix" subtitle="Runtime policies and their latest recorded evidence from the authorization boundary." className="cc-top-gap">
          <div className="cc-table-scroll"><table className="cc-table"><thead><tr>
            <th>Policy Area</th>
            <th>Banking Risk</th>
            <th>Example Action</th>
            <th>Deterministic Decision Rule</th>
            <th>Human Approval</th>
            <th>LLM Judge Role</th>
            <th>Runtime Status</th>
            <th>Latest Evidence</th>
          </tr></thead><tbody>
          {[
            { id: "customer_data_access", name: "Customer Data Access", risk: "Data Leakage", action: "read_bureau_summary", rule: "Manifest action/data-scope policy", approval: "Human approval gate", judge: "Not applicable", status: "Lifecycle status enforcement" },
            { id: "payment_and_waiver", name: "Payment / Waiver / Settlement", risk: "Financial Loss", action: "approve_waiver", rule: "Banking business-rule policy", approval: "Required for REVIEW", judge: "Not applicable", status: "Lifecycle status enforcement" },
            { id: "collections_conduct", name: "Collections Conduct", risk: "Regulatory / Reputation", action: "threaten_customer", rule: "Regex-based PII guardrail", approval: "No", judge: "Optional LLM judge for soft-risk language", status: "Lifecycle status enforcement" },
            { id: "policy_and_regulatory_advice", name: "Regulatory Advice Boundary", risk: "Compliance Risk", action: "give_legal_advice", rule: "Banking business-rule policy", approval: "No", judge: "Optional LLM judge for soft-risk language", status: "Lifecycle status enforcement" },
            { id: "external_vendor_calls", name: "External Vendor Call", risk: "Third-party Data Risk", action: "vendor_agent_invoke", rule: "Manifest action/data-scope policy", approval: "Human approval gate", judge: "Not applicable", status: "Lifecycle status enforcement" },
            { id: "sql_database", name: "SQL / Database Action", risk: "Destructive Operation", action: "drop_table", rule: "Pattern-based SQL guardrail", approval: "No", judge: "Not applicable", status: "Lifecycle status enforcement" },
            { id: "prompt_model_ops", name: "Prompt / Model Change", risk: "Configuration Risk", action: "promote_prompt", rule: "Static prompt-injection heuristic", approval: "Human approval gate", judge: "Not applicable", status: "Lifecycle status enforcement" }
          ].map((policy) => { 
            const latest = filteredToolAuth.find((event) => event.matched_policy && event.matched_policy.includes(policy.id) || (event.action && event.action.includes(policy.action.split('_')[0]))); 
            return <tr key={policy.id}>
              <td><strong>{policy.name}</strong></td>
              <td>{policy.risk}</td>
              <td className="mono">{policy.action}</td>
              <td>{policy.rule}</td>
              <td>{policy.approval}</td>
              <td>{policy.judge}</td>
              <td>{policy.status}</td>
              <td>{latest ? <><DecisionChip decision={latest.decision} /> <span className="cc-muted">({fmtTime(latest.timestamp)})</span></> : <span className="cc-muted">No runtime evidence recorded yet</span>}</td>
            </tr>; 
          })}
          </tbody></table></div>
        </SectionCard>
        <div className="cc-grid-2 cc-top-gap">
          <SectionCard title="Recent Guardrail Events">
            {filteredEvents.length === 0 ? <div className="cc-empty">No guardrail events recorded.</div> : <div className="cc-table-scroll"><table className="cc-table"><thead><tr><th>Time</th><th>Source</th><th>Guardrail</th><th>Agent</th><th>Decision</th><th>Severity</th><th>Reason</th></tr></thead><tbody>{filteredEvents.map((event, index) => <tr key={event.id || index}><td>{fmtTime(event.timestamp)}</td><td><SourceBadge source={event.source} /></td><td className="mono">{display(event.guardrail_id)}</td><td className="mono">{display(event.agent_id)}</td><td><DecisionChip decision={event.decision} /></td><td><SeverityChip severity={String(event.severity || '').toLowerCase()} /></td><td>{display(event.reason)}</td></tr>)}</tbody></table></div>}
          </SectionCard>
          <SectionCard title="Recent Policy Decisions">
            {filteredDecisions.length === 0 ? <div className="cc-empty">No policy decisions recorded.</div> : <div className="cc-table-scroll"><table className="cc-table"><thead><tr><th>Time</th><th>Source</th><th>Agent</th><th>Action</th><th>Decision</th><th>Reason</th></tr></thead><tbody>{filteredDecisions.map((item, index) => <tr key={item.id || index}><td>{fmtTime(item.timestamp)}</td><td><SourceBadge source={item.source} /></td><td className="mono">{display(item.agent_id)}</td><td>{display(item.action)}</td><td><DecisionChip decision={item.decision} /></td><td>{display(item.reason)}</td></tr>)}</tbody></table></div>}
          </SectionCard>
        </div>
      </>}
    </>
  );
}
