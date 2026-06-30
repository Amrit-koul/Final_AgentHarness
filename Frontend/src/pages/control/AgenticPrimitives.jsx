import React, { useCallback, useMemo, useState } from 'react';
import PageHeader from '../../components/control/PageHeader';
import { Chip, DecisionChip, RiskChip, StatusChip } from '../../components/control/Chips';
import { LoadingState, SectionCard, asArray, display, fmtTime } from '../../components/control/Common';
import { useControlData } from '../../hooks/useControlData';
import { controlPlaneApi } from '../../services/controlPlaneApi';
import { EnforcementBadge, LLMJudgeBadge, SourceBadge, renderMissingField } from '../../utils/evidenceLabels';

const list = (item) => Array.isArray(item) ? item.join(', ') : display(item);
const tabs = [['skills', 'Skills Catalog'], ['tools', 'Tools Registry'], ['toolAuth', 'Tool & Action Authorization Evidence'], ['memory', 'Memory Contracts'], ['hooks', 'Hooks Contract'], ['prompts', 'Prompt Registry'], ['evaluators', 'Evaluation Registry'], ['validation', 'Primitive Validation']];
const endpoints = { skills: controlPlaneApi.listSkills, tools: controlPlaneApi.listTools, toolAuth: controlPlaneApi.listToolAuthorizationEvents, memory: controlPlaneApi.listMemoryContracts, memoryEvents: controlPlaneApi.listMemoryEvents, hooks: controlPlaneApi.listHooks, hookEvents: controlPlaneApi.listHookEvents, prompts: controlPlaneApi.listPrompts, evaluators: controlPlaneApi.listEvaluators, validation: controlPlaneApi.getPrimitiveValidation };

export default function AgenticPrimitives() {
  const [tab, setTab] = useState('skills');
  const [excludeTest, setExcludeTest] = useState(true);

  const fetchData = useCallback(async () => {
    const results = await Promise.all(Object.entries(endpoints).map(async ([key, fn]) => { try { return [key, await fn(), null]; } catch (error) { return [key, null, error]; } }));
    return results.reduce((data, [key, payload, error]) => ({ ...data, [key]: payload, errors: error ? [...data.errors, `${key}: ${error.message}`] : data.errors }), { errors: [] });
  }, []);
  const state = useControlData(fetchData, [], 10000);
  const data = state.data || { errors: [] };

  const filteredToolAuth = useMemo(() => {
    let arr = asArray(data.toolAuth, 'events');
    if (excludeTest) {
      arr = arr.filter(item => !['admin_validation', 'manual_validation', 'simulation', 'demo_endpoint'].includes(String(item.source || '').toLowerCase()));
    }
    return arr;
  }, [data.toolAuth, excludeTest]);

  const body = useMemo(() => ({ skills: <Skills rows={asArray(data.skills, 'skills')} />, tools: <Tools rows={asArray(data.tools, 'tools')} events={filteredToolAuth} />, toolAuth: <ToolAuth rows={filteredToolAuth} />, memory: <Memory rows={asArray(data.memory, 'contracts')} events={asArray(data.memoryEvents, 'events')} />, hooks: <Hooks rows={asArray(data.hooks, 'hooks')} events={asArray(data.hookEvents, 'events')} />, prompts: <Prompts rows={asArray(data.prompts, 'prompts')} />, evaluators: <Evaluators rows={asArray(data.evaluators, 'evaluators')} />, validation: <Validation result={data.validation} /> })[tab], [data, tab, filteredToolAuth]);
  
  return <>
    <PageHeader 
      title="Agentic System Primitives" 
      subtitle="Reusable platform capabilities used to register, govern, observe, evaluate, and control agents." 
      right={
        <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
          <label className="cc-switch"><input type="checkbox" checked={!excludeTest} onChange={(e) => setExcludeTest(!e.target.checked)} /> Include admin/test evidence</label>
          <button className="cc-button" onClick={state.reload}>Refresh</button>
        </div>
      } 
    />
    <div className="cc-tabs">{tabs.map(([id, label]) => <button key={id} className={`cc-tab${tab === id ? ' active' : ''}`} onClick={() => setTab(id)}>{label}</button>)}</div>
    <LoadingState loading={state.loading} error={state.error} />
    {!state.loading && !state.error && <>{data.errors.length > 0 && <div className="cc-notice info">Some primitive registries are unavailable. The remaining registries are shown below.</div>}{body}</>}
  </>;
}

function Table({ title, subtitle, rows, columns, empty = 'No records returned.' }) { return <SectionCard title={title} subtitle={subtitle}>{rows.length === 0 ? <div className="cc-empty">{empty}</div> : <div className="cc-table-scroll"><table className="cc-table"><thead><tr>{columns.map((column) => <th key={column.label}>{column.label}</th>)}</tr></thead><tbody>{rows.map((row, index) => <tr key={row.id || row.skill_id || row.tool_id || row.memory_scope || row.hook_id || row.prompt_id || row.evaluator_id || index}>{columns.map((column) => <td key={column.label}>{column.render ? column.render(row) : renderMissingField(row[column.key])}</td>)}</tr>)}</tbody></table></div>}</SectionCard>; }
function Skills({ rows }) { return <Table title="Skills Catalog" subtitle="Registered, reusable capabilities referenced by agents." rows={rows} columns={[{ label: 'Skill ID', key: 'skill_id' }, { label: 'Name', key: 'name' }, { label: 'Owner', key: 'owner' }, { label: 'Version', key: 'version' }, { label: 'Business Function', key: 'business_function' }, { label: 'Risk Tier', render: (r) => <RiskChip level={r.risk_tier} /> }, { label: 'Status', render: (r) => <StatusChip status={r.status} /> }, { label: 'Agents using skill', render: (r) => list(r.agents) }]} />; }

function Tools({ rows, events = [] }) { 
  return <Table title="Tools Registry" subtitle="Tools shown here are registered contracts. Runtime enforcement is only shown when a real authorization event or backend enforcement flag exists." rows={rows} columns={[
    { label: 'Tool Name', key: 'name' }, 
    { label: 'Tool ID', key: 'tool_id' }, 
    { label: 'Purpose', key: 'purpose' }, 
    { label: 'Allowed Actions', render: (r) => list(r.allowed_actions) }, 
    { label: 'Data Scopes', render: (r) => list(r.data_scopes) }, 
    { label: 'Risk Level', render: (r) => <RiskChip level={r.risk_tier} /> }, 
    { label: 'Approval Required', render: (r) => <Chip value={r.requires_human_approval ? 'review' : 'active'} label={r.requires_human_approval ? 'Required' : 'No'} /> }, 
    { label: 'Runtime Auth Status', render: (r) => { 
        const ev = events.find(e => e.tool_id === r.tool_id);
        const status = r.enforcement_status || (ev ? 'runtime_enforced' : 'config_only');
        return <EnforcementBadge status={status} />;
    } }, 
    { label: 'Agents Allowed', render: (r) => list(r.allowed_agent_ids || r.agents) }, 
    { label: 'Latest Auth Decision', render: (r) => {
        const ev = events.find(e => e.tool_id === r.tool_id);
        return ev ? <><DecisionChip decision={ev.decision} /> <span className="cc-muted">({fmtTime(ev.timestamp)})</span></> : <span className="cc-muted">No authorization event recorded</span>;
    } }, 
    { label: 'LLM Judge Available', render: (r) => {
        if (!r.llm_judge) return <span className="cc-muted">Not returned</span>;
        return r.llm_judge.status === 'not_configured' ? <span className="cc-badge neutral">Not Configured</span> : <span className="cc-badge success">Configured</span>;
    } }
  ]} />; 
}

function ToolAuth({ rows }) { 
  return <Table title="Tool & Action Authorization Evidence" subtitle="Recent ALLOW / REVIEW / BLOCK decisions from the tool boundary." rows={rows} empty="No tool authorization decisions match this filter. Evidence appears when runtime or admin validation calls pass through the authorization boundary." columns={[
    { label: 'Time', render: (r) => fmtTime(r.timestamp) }, 
    { label: 'Agent', key: 'agent_id' }, 
    { label: 'Tool', key: 'tool_id' }, 
    { label: 'Action', key: 'action' }, 
    { label: 'Decision', render: (r) => <DecisionChip decision={String(r.decision).toLowerCase()} /> }, 
    { label: 'Risk', render: (r) => <RiskChip level={String(r.risk_level).toLowerCase()} /> }, 
    { label: 'Reason', key: 'reason' }, 
    { label: 'Matched Policy', key: 'matched_policy' }, 
    { label: 'Approval Required', render: (r) => r.required_approval ? 'Yes' : 'No' }, 
    { label: 'LLM Judge Status', render: (r) => <LLMJudgeBadge status={r.llm_judge?.status} /> }, 
    { label: 'LLM Judge Score', render: (r) => r.llm_judge ? renderMissingField(r.llm_judge.score) : <span className="cc-muted">Not returned</span> }, 
    { label: 'Source', render: (r) => <SourceBadge source={r.source} /> }, 
    { label: 'Trace ID', key: 'trace_id' }
  ]} />; 
}

function Memory({ rows, events }) { return <><Table title="Memory Contracts" subtitle="Contract metadata only; no memory records or customer PII are displayed." rows={rows} columns={[{ label: 'Scope', key: 'memory_scope' }, { label: 'Description', key: 'description' }, { label: 'Allowed Agents', render: (r) => list(r.allowed_agent_ids) }, { label: 'PII Classification', key: 'pii_classification' }, { label: 'Retention Days', key: 'retention_days' }, { label: 'Persistence', key: 'persistence' }, { label: 'Redaction Required', render: (r) => r.redaction_required ? 'Yes' : 'No' }, { label: 'Encryption Required', render: (r) => r.encryption_required ? 'Yes' : 'No' }, { label: 'Status', render: (r) => <StatusChip status={r.status} /> }]} /><Table title="Recent Memory Contract Events" subtitle="Presence and timing only." rows={events} empty="No memory contract events recorded." columns={[{ label: 'Agent', key: 'agent_id' }, { label: 'Record Present', render: (r) => r.record_present ? 'Yes' : 'No' }, { label: 'Updated', render: (r) => fmtTime(r.updated_at) }]} /></>; }
function Hooks({ rows, events }) { return <><Table title="Hooks Contract" subtitle="Safe hook contract points and subscribers; untrusted hooks are not executed." rows={rows} columns={[{ label: 'Hook ID', key: 'hook_id' }, { label: 'Trigger Point', key: 'trigger_point' }, { label: 'Description', key: 'description' }, { label: 'Enabled', render: (r) => <Chip value={r.enabled ? 'active' : 'disabled'} label={r.enabled ? 'Enabled' : 'Disabled'} /> }, { label: 'Subscribers', render: (r) => list(r.subscribers) }, { label: 'Audit Required', render: (r) => r.audit_required ? 'Yes' : 'No' }, { label: 'Risk Tier', render: (r) => <RiskChip level={r.risk_tier} /> }]} /><Table title="Recent Hook Events" subtitle="Events emitted by configured hook points." rows={events} empty="No hook events recorded." columns={[{ label: 'Time', render: (r) => fmtTime(r.timestamp) }, { label: 'Hook Event', key: 'event_type' }, { label: 'Agent', key: 'agent_id' }, { label: 'Trace ID', key: 'trace_id' }]} /></>; }
function Prompts({ rows }) { return <Table title="Prompt Registry" subtitle="Versioned prompt packages and their registered use." rows={rows} columns={[{ label: 'Prompt ID', key: 'prompt_id' }, { label: 'Version', key: 'version' }, { label: 'Source', key: 'source' }, { label: 'Owner', key: 'owner' }, { label: 'Business Function', key: 'business_function' }, { label: 'Agents using it', render: (r) => list(r.agents_using_it) }, { label: 'Hash', render: (r) => r.hash ? <span className="mono">{r.hash.slice(0, 12)}…</span> : '—' }, { label: 'Status', render: (r) => <StatusChip status={r.status} /> }]} />; }
function Evaluators({ rows }) { return <Table title="Evaluation Registry" subtitle="Registered evaluation methods and scope." rows={rows} columns={[{ label: 'Evaluator ID', key: 'evaluator_id' }, { label: 'Method', key: 'method' }, { label: 'Applies To', key: 'applies_to' }, { label: 'Score Range', render: (r) => list(r.score_range) }, { label: 'Prompt Version', key: 'prompt_version' }, { label: 'Owner', key: 'owner' }, { label: 'Status', render: (r) => <StatusChip status={r.status} /> }]} />; }
function Validation({ result }) { const warnings = result?.warnings || []; const errors = result?.errors || []; return <SectionCard title="Primitive Validation" subtitle="Reference validation across registered agents, skills, and tools.">{!result ? <div className="cc-empty">Primitive Validation is unavailable.</div> : <><div className={`cc-notice ${result.valid && warnings.length === 0 ? 'success' : 'info'}`}>{result.valid && warnings.length === 0 ? 'All registered agents have valid primitive mappings.' : `${warnings.length} warning(s) and ${errors.length} error(s) returned by validation.`}</div><div className="cc-grid-2"><ValidationList title="Missing Skill References" rows={result.missing_skill_refs} /><ValidationList title="Missing Tool References" rows={result.missing_tool_refs} /><ValidationList title="High-Risk Tools Without Guardrails" rows={result.high_risk_without_guardrail} /><ValidationMap title="Agent–Skill Map" map={result.agent_skill_map} /><ValidationMap title="Agent–Tool Map" map={result.agent_tool_map} /></div></>}</SectionCard>; }
function ValidationList({ title, rows = [] }) { return <div className="cc-primitive-detail"><strong>{title}</strong>{rows.length ? <div className="cc-inline-list">{rows.map((row, index) => <span key={index}>{row.agent_id}: {row.skill_id || row.tool_id}</span>)}</div> : <span className="cc-muted">None</span>}</div>; }
function ValidationMap({ title, map = {} }) { return <div className="cc-primitive-detail"><strong>{title}</strong>{Object.keys(map).length ? <div className="cc-inline-list">{Object.entries(map).map(([agent, values]) => <span key={agent}>{agent}: {list(values)}</span>)}</div> : <span className="cc-muted">None</span>}</div>; }
