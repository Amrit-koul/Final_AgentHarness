import React, { useCallback } from 'react';
import PageHeader from '../../components/control/PageHeader';
import { KpiStrip } from '../../components/control/Kpi';
import { Chip, StatusChip } from '../../components/control/Chips';
import { LoadingState, SectionCard, asArray, display, fmtTime } from '../../components/control/Common';
import { useControlData } from '../../hooks/useControlData';
import { controlPlaneApi } from '../../services/controlPlaneApi';
const number = (value) => new Intl.NumberFormat('en-IN').format(Number(value || 0));
const money = (value, currency = 'USD') => value == null ? 'Not available' : `${currency === 'USD' ? '$' : `${currency} `}${Number(value).toFixed(4)}`;
const isLlm = (event) => ['provider_reported', 'estimated'].includes(event.usage_source);

export default function UsageCost() {
  const fetchData = useCallback(async () => { const [summary, events] = await Promise.all([controlPlaneApi.getUsageSummary(), controlPlaneApi.listUsageEvents()]); return { summary, events: asArray(events, 'events') }; }, []);
  const state = useControlData(fetchData, [], 10000); const summary = state.data?.summary; const events = state.data?.events || [];
  const llm = events.filter(isLlm); const nonLlm = events.filter((event) => !isLlm(event)); const latency = Object.values(summary?.average_latency_by_agent || {}); const avg = latency.length ? Math.round(latency.reduce((a, b) => a + Number(b || 0), 0) / latency.length) : 0;
  return <><PageHeader title="Usage & Cost" subtitle="Estimated usage telemetry for governance visibility." right={<button className="cc-button" onClick={state.reload}>Refresh</button>} /><LoadingState loading={state.loading} error={state.error} />
    {!state.loading && !state.error && <><KpiStrip items={[{ label: 'LLM Runs', value: number(llm.length), accent: 'blue' }, { label: 'Non-LLM Runs', value: number(nonLlm.length), accent: 'grey' }, { label: 'Token Usage', value: number(summary?.total_tokens), accent: 'teal' }, { label: 'Estimated Cost', value: llm.length ? money(summary?.estimated_total_cost, summary?.currency) : 'Not available', accent: 'purple' }, { label: 'Average Latency', value: `${avg} ms`, accent: 'blue' }]} />
    {!llm.length && <div className="cc-notice info cc-top-gap">No LLM token usage recorded yet. Run Policy Assistant or Loan Assessment to populate token and estimated cost telemetry.</div>}
    <div className="cc-grid-2 cc-top-gap"><Metric title="Token Usage by Agent" values={summary?.tokens_by_agent} render={number} /><Metric title="Estimated Cost by Agent" values={llm.length ? summary?.cost_by_agent : {}} render={(v) => money(v, summary?.currency)} /></div>
    <UsageTable title="Latest LLM Usage Events" events={llm} empty="No LLM token usage recorded yet." /><UsageTable title="Non-LLM / Latency-only" events={nonLlm} empty="No non-LLM usage events recorded." />
    </>}
  </>;
}
function Metric({ title, values, render }) { const rows = Object.entries(values || {}); return <SectionCard title={title}>{!rows.length ? <div className="cc-empty">No model usage recorded.</div> : <div className="cc-metric-list">{rows.map(([name, value]) => <div className="cc-metric-row" key={name}><span>{name}</span><strong>{render(value)}</strong></div>)}</div>}</SectionCard>; }
function UsageTable({ title, events, empty }) { return <SectionCard className="cc-top-gap" title={title}>{!events.length ? <div className="cc-empty">{empty}</div> : <div className="cc-table-scroll"><table className="cc-table"><thead><tr><th>Time</th><th>Agent</th><th>Run Type</th><th>Model / Provider</th><th>Tokens</th><th>Estimated Cost</th><th>Latency</th><th>Usage Source</th><th>Status</th></tr></thead><tbody>{events.map((e) => <tr key={e.usage_id}><td>{fmtTime(e.created_at)}</td><td>{display(e.agent_name || e.agent_id)}</td><td>{isLlm(e) ? 'LLM' : e.provider === 'external' ? 'External' : 'Non-LLM'}</td><td>{e.model && e.model !== 'unknown' ? `${e.provider} / ${e.model}` : e.provider === 'external' ? 'External service' : 'Not available'}</td><td>{e.total_tokens == null ? 'Latency only' : number(e.total_tokens)}</td><td>{money(e.estimated_total_cost, e.currency)}</td><td>{e.latency_ms == null ? 'Not available' : `${e.latency_ms} ms`}</td><td><Chip value={e.usage_source} label={String(e.usage_source || 'unknown').replaceAll('_', ' ')} /></td><td><StatusChip status={e.status} /></td></tr>)}</tbody></table></div>}</SectionCard>; }
