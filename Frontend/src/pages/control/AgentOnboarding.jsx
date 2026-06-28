import React, { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import PageHeader from '../../components/control/PageHeader';
import { JsonBlock, SectionCard } from '../../components/control/Common';
import { controlPlaneApi } from '../../services/controlPlaneApi';

const STEPS = [
  ['1', 'Define YAML manifest', 'Declare agent identity, ownership, business function, and lifecycle status.'],
  ['2', 'Select adapter type', 'Choose python_function, langgraph, rest_api, or external_webhook.'],
  ['3', 'Provide entrypoint or endpoint', 'Point the contract at the implementation without changing the core registry.'],
  ['4', 'Define schemas', 'Declare input, output, state, and memory contracts.'],
  ['5', 'Attach skills and tools', 'List only the capabilities used by this agent.'],
  ['6', 'Attach guardrails', 'Apply business and security controls appropriate to the agent.'],
  ['7', 'Register into control plane', 'Add the manifest to config/agents and restart the backend.'],
];

const PATTERNS = [
  { name: 'REST Vendor Agent', adapter: 'rest_api', fields: 'agent_id, endpoint, input/output schemas, permissions, guardrails, observability', shape: 'POST endpoint accepting query + trace_id', governance: 'Status check, policy, guardrails, trace, audit, usage/cost, and kill switch run before the HTTP call.', caveat: 'This local validation endpoint is unauthenticated; production vendors need authenticated transport and secret rotation.' },
  { name: 'GitHub Wrapped Agent', adapter: 'python_function', fields: 'agent_id, entrypoint, schemas, permissions, guardrails, observability', shape: 'package.module.wrapper.invoke(payload, trace_id)', governance: 'The wrapper is invoked through the same runtime and policy boundary.', caveat: 'This proves a reviewed wrapper pattern, not safe execution of arbitrary GitHub code.' },
  { name: 'LangGraph Agent', adapter: 'langgraph', fields: 'agent_id, entrypoint, schemas, tools, guardrails, observability', shape: 'graph or callable entrypoint', governance: 'The graph stays behind the shared lifecycle, audit, and guardrail path.', caveat: 'Graph tool permissions still need to be explicitly declared in the manifest.' },
  { name: 'External Heartbeat Agent', adapter: 'external_webhook', fields: 'agent_id, endpoint, health_check metadata, schemas, observability', shape: 'Webhook endpoint plus /heartbeat events', governance: 'Heartbeats and status remain visible to the control plane.', caveat: 'The control plane cannot physically stop an external process that ignores it.' },
];

export default function AgentOnboarding() {
  const [form, setForm] = useState({ agent_id: '', name: '', owner: '', business_function: '', adapter_type: 'python_function', entrypoint: '' });
  const [showPreview, setShowPreview] = useState(false);
  const [vendorRun, setVendorRun] = useState({ loading: false, result: null, error: '' });
  const preview = useMemo(() => ({
    ...form,
    agent_type: form.adapter_type === 'rest_api' || form.adapter_type === 'external_webhook' ? 'external' : 'internal',
    execution_mode: form.adapter_type === 'external_webhook' ? 'decoupled' : 'workflow',
    input_schema: { type: 'object', required: [], properties: {} },
    output_schema: { type: 'object', properties: {} },
    state_schema: { type: 'object', properties: {} },
    memory_schema: { type: 'object', properties: {} },
    skills: [], tools: [], guardrails: [], status: 'active',
  }), [form]);
  const update = (key) => (event) => { setForm((value) => ({ ...value, [key]: event.target.value })); setShowPreview(false); };
  const invokeVendor = async () => {
    setVendorRun({ loading: true, result: null, error: '' });
    try { setVendorRun({ loading: false, result: await controlPlaneApi.invokeAgent('demo_vendor_rest_agent', { query: 'Summarize this customer request' }), error: '' }); }
    catch (error) { setVendorRun({ loading: false, result: null, error: error.message || 'Vendor invocation failed.' }); }
  };
  return (
    <>
      <PageHeader title="Agent Onboarding Guide" subtitle="Prepare a YAML contract for registration. This UI does not register or mutate backend agents." />
      <div className="cc-grid-2">
        <SectionCard title="Onboarding Flow" subtitle="The framework registry remains unchanged when a new manifest is added.">
          <ol className="cc-step-list">{STEPS.map(([number, title, text]) => <li key={number}><span>{number}</span><div><strong>{title}</strong><p>{text}</p></div></li>)}</ol>
        </SectionCard>
        <SectionCard title="Manifest Preview" subtitle="Generate a local preview; no data is sent to the backend.">
          <div className="cc-form-grid">
            <label>Agent ID<input className="cc-input" value={form.agent_id} onChange={update('agent_id')} placeholder="xyz_agent" /></label>
            <label>Agent Name<input className="cc-input" value={form.name} onChange={update('name')} placeholder="XYZ Agent" /></label>
            <label>Owner<input className="cc-input" value={form.owner} onChange={update('owner')} placeholder="Owning team" /></label>
            <label>Business Function<input className="cc-input" value={form.business_function} onChange={update('business_function')} placeholder="Business function" /></label>
            <label>Adapter Type<select className="cc-input" value={form.adapter_type} onChange={update('adapter_type')}>{['python_function', 'langgraph', 'rest_api', 'external_webhook'].map((item) => <option key={item}>{item}</option>)}</select></label>
            <label>{form.adapter_type.includes('api') || form.adapter_type.includes('webhook') ? 'API Endpoint' : 'Python Entrypoint'}<input className="cc-input" value={form.entrypoint} onChange={update('entrypoint')} placeholder={form.adapter_type.includes('api') ? 'https://…' : 'package.module.function'} /></label>
          </div>
          <button className="cc-button cc-top-gap" onClick={() => setShowPreview(true)}>Generate Manifest Preview</button>
          {showPreview && <div className="cc-top-gap"><JsonBlock value={preview} /></div>}
          <div className="cc-notice info cc-top-gap"><strong>Registration endpoint not available yet.</strong> Save the reviewed YAML under <span className="mono">banking_agents/config/agents</span> and restart the backend.</div>
        </SectionCard>
      </div>
      <SectionCard title="Supported Onboarding Patterns" subtitle="All patterns remain manifest-driven; this page only guides and proves onboarding.">
        <div className="cc-table-scroll"><table className="cc-table"><thead><tr><th>Pattern</th><th>Adapter</th><th>Required YAML</th><th>Endpoint / Entrypoint</th><th>Automatic Governance</th><th>Operational Caveat</th></tr></thead><tbody>{PATTERNS.map((pattern) => <tr key={pattern.name}><td><strong>{pattern.name}</strong></td><td className="mono">{pattern.adapter}</td><td>{pattern.fields}</td><td>{pattern.shape}</td><td>{pattern.governance}</td><td>{pattern.caveat}</td></tr>)}</tbody></table></div>
      </SectionCard>
      <SectionCard title="REST Vendor Agent — Live Proof" subtitle="Runs through ControlPlaneRuntime; it does not call the vendor service directly from the browser.">
        <p className="cc-muted">Start the local REST vendor validation service before invoking this check.</p>
        <p className="cc-muted">Manifest source: registered REST vendor control-plane contract.</p>
        <button className="cc-button" onClick={invokeVendor} disabled={vendorRun.loading}>{vendorRun.loading ? 'Invoking vendor…' : 'Invoke vendor test'}</button>{' '}
        <Link className="cc-link-button" to="/control/agents">Open Agent Registry contract</Link>
        {vendorRun.error && <div className="cc-notice warning cc-top-gap"><strong>Invocation failed:</strong> {vendorRun.error}</div>}
        {vendorRun.result && <div className="cc-top-gap"><JsonBlock value={vendorRun.result} /></div>}
      </SectionCard>
    </>
  );
}
