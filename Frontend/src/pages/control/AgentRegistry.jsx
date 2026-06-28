import React, { useCallback, useMemo, useState } from 'react';
import PageHeader from '../../components/control/PageHeader';
import Drawer from '../../components/control/Drawer';
import { ExecModeChip, HealthChip, StatusChip, DecisionChip } from '../../components/control/Chips';
import { JsonBlock, LoadingState, SectionCard, asArray, display, fmtTime } from '../../components/control/Common';
import { useControlData } from '../../hooks/useControlData';
import { controlPlaneApi } from '../../services/controlPlaneApi';
import { renderMissingField, EnforcementBadge, LLMJudgeBadge } from '../../utils/evidenceLabels';

function ContractDrawer({ agentId, onClose }) {
  const fetchDetails = useCallback(async () => {
    const [contract, health, toolAuth, policy, guardrails] = await Promise.all([
      controlPlaneApi.getContract(agentId), 
      controlPlaneApi.getHealth(agentId), 
      controlPlaneApi.listToolAuthorizationEvents(),
      controlPlaneApi.listPolicyDecisions(),
      controlPlaneApi.listGuardrailEvents()
    ]);
    return { 
      contract, 
      health, 
      toolAuth: asArray(toolAuth, 'events').filter(e => e.agent_id === agentId),
      policy: asArray(policy, 'decisions').filter(e => e.agent_id === agentId),
      guardrails: asArray(guardrails, 'events').filter(e => e.agent_id === agentId)
    };
  }, [agentId]);
  
  const state = useControlData(fetchDetails, [agentId]);
  const contract = state.data?.contract;
  const toolAuth = state.data?.toolAuth || [];
  const policy = state.data?.policy || [];
  const guardrails = state.data?.guardrails || [];
  const primitives = contract?.primitives || {};
  
  const latestAuth = toolAuth[0];
  const latestPolicy = policy[0];
  const latestGuardrail = guardrails[0];

  const getRuntimeStatusText = (status) => {
    if (status === 'config_only') return 'Declared in manifest; runtime interception is not yet wired for this flow.';
    if (status === 'available_not_wired') return 'Authorization boundary exists, but this flow has not been routed through it yet.';
    if (status === 'runtime_enforced') return 'Authorization enforced by control plane.';
    return 'Not returned by backend.';
  };

  const arraySections = ['prompts'];
  const objectSections = ['input_schema', 'output_schema', 'state_schema', 'memory_schema', 'model_preferences', 'observability_hooks', 'metrics'];
  
  return (
    <Drawer title={contract?.name || agentId} subtitle="Agent Contract" onClose={onClose}>
      <LoadingState loading={state.loading} error={state.error} />
      {contract && <>
        <dl className="cc-detail-grid">
          {['agent_id', 'owner', 'business_function', 'agent_type', 'execution_mode', 'adapter_type', 'entrypoint', 'endpoint', 'version'].filter((key) => contract[key] != null && contract[key] !== '').map((key) => <React.Fragment key={key}><dt>{key.replaceAll('_', ' ')}</dt><dd>{display(contract[key])}</dd></React.Fragment>)}
          <dt>Status</dt><dd><StatusChip status={contract.status} /></dd>
          <dt>Health</dt><dd><HealthChip health={state.data.health?.status} /></dd>
          {contract.latest_kill_switch_event && <><dt>Latest lifecycle reason</dt><dd>{display(contract.latest_kill_switch_event.reason)} ({display(contract.latest_kill_switch_event.trigger)})</dd><dt>Lifecycle timestamp</dt><dd>{display(contract.latest_kill_switch_event.timestamp)}</dd></>}
        </dl>

        <div className="cc-drawer-section"><h3>Capabilities & Security</h3>
          <dl className="cc-detail-grid">
            <dt>Declared Tools</dt>
            <dd>{contract.tools?.length ? contract.tools.join(', ') : <span className="cc-muted">None declared</span>}</dd>
            
            <dt>Allowed Actions</dt>
            <dd>{contract.policy_permissions?.allowed_actions?.length ? contract.policy_permissions.allowed_actions.join(', ') : renderMissingField()}</dd>
            
            <dt>Allowed Data Scopes</dt>
            <dd>{contract.policy_permissions?.allowed_data_scopes?.length ? contract.policy_permissions.allowed_data_scopes.join(', ') : renderMissingField()}</dd>
            
            <dt>Human Approval Reqs</dt>
            <dd>{contract.guardrails?.some(g => g.requires_human_approval) ? 'Required for certain actions' : 'Not required'}</dd>
            
            <dt>Runtime Auth Status</dt>
            <dd>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <EnforcementBadge status={contract.enforcement_status || (latestAuth ? 'runtime_enforced' : 'config_only')} />
                <span className="cc-muted cc-small">{getRuntimeStatusText(contract.enforcement_status || (latestAuth ? 'runtime_enforced' : 'config_only'))}</span>
              </div>
            </dd>

            <dt>LLM Judge Usage</dt>
            <dd>
              {contract.llm_judge ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  <LLMJudgeBadge status={contract.llm_judge.status} />
                  {contract.llm_judge.score && <span className="cc-small">Score: {contract.llm_judge.score}</span>}
                </div>
              ) : renderMissingField()}
            </dd>
          </dl>
        </div>

        <div className="cc-drawer-section"><h3>Latest Execution Evidence</h3>
          <dl className="cc-detail-grid">
            <dt>Latest Tool Auth</dt>
            <dd>{latestAuth ? <><DecisionChip decision={latestAuth.decision} /> <span className="cc-muted cc-small">({fmtTime(latestAuth.timestamp)})</span></> : <span className="cc-muted">No evidence</span>}</dd>
            
            <dt>Latest Policy Decision</dt>
            <dd>{latestPolicy ? <><DecisionChip decision={latestPolicy.decision} /> <span className="cc-muted cc-small">({fmtTime(latestPolicy.timestamp)})</span></> : <span className="cc-muted">No evidence</span>}</dd>
            
            <dt>Latest Guardrail Event</dt>
            <dd>{latestGuardrail ? <><DecisionChip decision={latestGuardrail.decision} /> <span className="cc-muted cc-small">({fmtTime(latestGuardrail.timestamp)})</span></> : <span className="cc-muted">No evidence</span>}</dd>
          </dl>
        </div>

        {arraySections.map((key) => contract[key]?.length ? <div className="cc-drawer-section" key={key}><h3>{key.replaceAll('_', ' ')}</h3><div className="cc-token-list">{contract[key].map((item) => <span key={String(item)}>{String(item)}</span>)}</div></div> : null)}
        {objectSections.map((key) => contract[key] != null ? <div className="cc-drawer-section" key={key}><h3>{key.replaceAll('_', ' ')}</h3><JsonBlock value={contract[key]} /></div> : null)}
        
        <div className="cc-drawer-section"><h3>Agentic Primitives</h3>
          {['skills', 'memory_contracts', 'hooks', 'evaluators'].map((key) => primitives[key]?.length ? <div className="cc-primitive-detail" key={key}><strong>{key.replaceAll('_', ' ')}</strong><div className="cc-token-list">{primitives[key].map((item, index) => <span key={item.skill_id || item.tool_id || item.memory_scope || item.hook_id || item.prompt_id || item.evaluator_id || index}>{item.name || item.skill_id || item.tool_id || item.memory_scope || item.hook_id || item.prompt_id || item.evaluator_id}</span>)}</div></div> : null)}
          {primitives.validation_warnings?.length ? <div className="cc-primitive-detail"><strong>Validation Warnings</strong><div className="cc-token-list">{primitives.validation_warnings.map((item, index) => <span key={index}>{item.code}: {item.reference}</span>)}</div></div> : <p className="cc-muted cc-small">No primitive validation warnings returned.</p>}
        </div>
      </>}
    </Drawer>
  );
}

export default function AgentRegistry() {
  const [selected, setSelected] = useState(null);
  const [query, setQuery] = useState('');
  const fetchAgents = useCallback(() => controlPlaneApi.listAgents(), []);
  const state = useControlData(fetchAgents, [], 10000);
  const agents = asArray(state.data, 'agents');
  const filtered = useMemo(() => agents.filter((agent) => `${agent.name} ${agent.agent_id} ${agent.business_function}`.toLowerCase().includes(query.toLowerCase())), [agents, query]);
  return (
    <>
      <PageHeader title="Agent Registry" subtitle="YAML-registered agents returned by the control plane. Select an agent to inspect its contract." right={<button className="cc-button" onClick={state.reload}>Refresh</button>} />
      <SectionCard title="Registered Agents" right={<input className="cc-input" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Filter agents" aria-label="Filter agents" />}>
        <LoadingState loading={state.loading} error={state.error} empty={!state.loading && filtered.length === 0}>No registered agents match this filter.</LoadingState>
        {filtered.length > 0 && <div className="cc-table-scroll"><table className="cc-table"><thead><tr><th>Agent Name</th><th>Agent ID</th><th>Business Function</th><th>Owner</th><th>Agent Type</th><th>Execution Mode</th><th>Status</th><th>Health</th><th>Last Run</th><th>Actions</th></tr></thead><tbody>{filtered.map((agent) => <tr key={agent.agent_id} className="clickable" onClick={() => setSelected(agent.agent_id)}><td><strong>{display(agent.name)}</strong></td><td className="mono">{display(agent.agent_id)}</td><td>{display(agent.business_function)}</td><td>{display(agent.owner)}</td><td>{display(agent.agent_type)}</td><td><ExecModeChip mode={agent.execution_mode} /></td><td><StatusChip status={agent.status} /></td><td>{agent.health ? <HealthChip health={agent.health} /> : '—'}</td><td>{display(agent.last_run)}</td><td><button className="cc-link-button">View contract</button></td></tr>)}</tbody></table></div>}
      </SectionCard>
      {selected && <ContractDrawer agentId={selected} onClose={() => setSelected(null)} />}
    </>
  );
}
