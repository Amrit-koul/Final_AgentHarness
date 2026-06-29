import React, { useCallback, useMemo, useState } from 'react';
import PageHeader from '../../components/control/PageHeader';
import { KpiStrip } from '../../components/control/Kpi';
import { Chip, StatusChip, DecisionChip } from '../../components/control/Chips';
import { ActionButton, LoadingState, SectionCard, asArray, display, fmtTime } from '../../components/control/Common';
import { useControlData } from '../../hooks/useControlData';
import { controlPlaneApi } from '../../services/controlPlaneApi';
import { SourceBadge } from '../../utils/evidenceLabels';

// ─── RAG agent classification ────────────────────────────────────────────────
// Strict allowlist — same rule as RagQuality.jsx (Feature 1).
// Only confirmed retrieval/RAG agents belong here.
// Do NOT add collections_workflow_agent, loan_assessment_agent,
// demo_vendor_rest_agent, sample_external_agent, or any
// workflow / voice / vendor / decision agent.
const RAG_AGENT_IDS = new Set([
  'policy_assistant_agent',
  // 'document_checker_agent',  // add when onboarded
  // 'knowledge_base_agent',    // add when onboarded
]);

/**
 * Returns true only for agents that produce retrieval/groundedness metrics.
 * Checks both the manifest-level agent_capability field (future-proof) and
 * the explicit allowlist (current state of the repo).
 */
function isRagAgent(agent) {
  if (!agent) return false;
  if (agent.agent_capability === 'rag') return true;
  return RAG_AGENT_IDS.has(agent.agent_id);
}

/**
 * Per-agent lifecycle signal for the board table.
 * RAG agents  → groundedness / evidence quality from evaluations.
 * All others  → governance signal: last_decision / last_risk_signal from
 *               policy decisions, with a typed fallback per agent_type so
 *               the component works for any non-RAG agent, not just Collections.
 */
function getLifecycleSignal(agent, evaluation, policyDecisions) {
  if (isRagAgent(agent)) {
    if (!evaluation) return { kind: 'rag', groundedness: null, controlPoint: 'Observability', actionRequired: 'Review if below threshold' };
    const g = Math.round(Number(evaluation.groundedness_score || 0) * 100);
    const below = Number(evaluation.groundedness_score || 0) < 0.6;
    return {
      kind: 'rag',
      groundedness: g,
      controlPoint: 'Observability',
      actionRequired: below ? 'Auto-review triggered — groundedness below threshold' : 'No action',
    };
  }

  // Non-RAG: workflow / external plugin / voice / vendor agents.
  // Pull the most recent policy decision for this agent if available.
  const latestPolicy = policyDecisions
    .filter(p => p.agent_id === agent.agent_id)
    .sort((a, b) => String(b.timestamp).localeCompare(String(a.timestamp)))[0];

  if (latestPolicy) {
    return {
      kind: 'governance',
      lastDecision: latestPolicy.decision,
      lastRiskSignal: latestPolicy.reason || latestPolicy.rule_id || '—',
      controlPoint: 'Policy Engine',
      actionRequired: latestPolicy.decision === 'REVIEW'
        ? 'Case routed to review'
        : latestPolicy.decision === 'BLOCK'
          ? 'Execution blocked — awaiting override'
          : 'No action',
    };
  }

  // Typed fallback — different defaults per agent_type so future agents get
  // a sensible placeholder rather than Collections-specific copy.
  const type = agent.agent_type || '';
  const isExternal = ['external_plugin', 'vendor', 'github_wrapped_workflow'].includes(type) ||
    agent.agent_id === 'collections_workflow_agent';

  return {
    kind: 'governance',
    lastDecision: isExternal ? 'REVIEW' : '—',
    lastRiskSignal: isExternal ? 'Hardship claim requires verification' : 'No decisions recorded',
    controlPoint: 'Policy Engine',
    actionRequired: isExternal ? 'Case routed to review' : 'No action',
  };
}

// ─── Control point legend data ────────────────────────────────────────────────
const CONTROL_POINTS = [
  { name: 'Policy Engine',  desc: 'Pre-execution authorization — rules evaluated before any agent action is taken.' },
  { name: 'Observability',  desc: 'Behaviour / KPI degradation monitoring — continuous quality and drift signals.' },
  { name: 'Agent Hooks',    desc: 'Runtime intervention / kill switch — harness hooks that pause or terminate execution.' },
];

export default function KillSwitchDegradation() {
  const [excludeTest, setExcludeTest] = useState(true);
  const [busy, setBusy] = useState('');
  const [notice, setNotice] = useState(null);
  const [agentId, setAgentId] = useState('collections_workflow_agent');
  const [open, setOpen] = useState(false);
  const [override, setOverride] = useState({ status: 'active', reason: 'manual_review_completed_after_quality_check', approved_by: 'demo_admin', override_type: 'reactivate_after_review' });

  const fetchData = useCallback(async () => {
    const [agents, kill, degradation, policy, guardrails, evaluations] = await Promise.all([
      controlPlaneApi.listAgents(),
      controlPlaneApi.listKillSwitchEvents(),
      controlPlaneApi.listDegradationEvents(),
      controlPlaneApi.listPolicyDecisions(),
      controlPlaneApi.listGuardrailEvents(),
      controlPlaneApi.listEvaluations(),
    ]);
    return {
      agents: asArray(agents, 'agents'),
      kill: asArray(kill, 'events'),
      degradation: asArray(degradation, 'events'),
      policy: asArray(policy, 'decisions'),
      guardrails: asArray(guardrails, 'events'),
      evaluations: asArray(evaluations, 'evaluations'),
    };
  }, []);

  const state = useControlData(fetchData, [], 5000);
  const data = state.data || { agents: [], kill: [], degradation: [], policy: [], guardrails: [], evaluations: [] };

  const filterEvents = (arr) => {
    if (!excludeTest) return arr;
    return arr.filter(e => {
      const src = String(e.source || '').toLowerCase();
      if (['admin_validation', 'manual_validation', 'simulation', 'demo_endpoint'].includes(src)) return false;
      // Drop any stray RAG-looking rows for non-RAG agents regardless of source
      if (e.agent_id && !isRagAgent({ agent_id: e.agent_id }) && e.groundedness_score != null) return false;
      return true;
    });
  };

  const kill = filterEvents(data.kill);
  const degradation = filterEvents(data.degradation);
  const guardrails = filterEvents(data.guardrails);
  const policy = filterEvents(data.policy);
  // Evaluations shown in Quality section: RAG-only — same strict rule as RagQuality.jsx
  const ragEvaluations = data.evaluations.filter(e => isRagAgent({ agent_id: e.agent_id, agent_capability: e.agent_capability }));

  const counts = useMemo(() => ['active', 'review', 'quarantined', 'disabled'].reduce(
    (out, s) => ({ ...out, [s]: data.agents.filter((a) => a.status === s).length }), {}
  ), [data.agents]);

  const timeline = useMemo(() => {
    // ── Label mapping rules ──────────────────────────────────────────────────
    // kill_switch_events where new_status is 'disabled' or 'quarantined'
    //   → "Kill Switch Triggered"  (actual hard stop)
    // kill_switch_events where new_status is 'review'
    //   → "Automatic Review Triggered"  (soft intervention, not a kill switch)
    // kill_switch_events where new_status is 'active' and source is 'manual_admin'
    //   → "Manual Override — Reactivated"
    // degradation_events
    //   → "Quality Degradation Detected"
    // guardrail_events
    //   → "Guardrail Block"
    // policy_decisions
    //   → "Policy Decision"
    function killLabel(x) {
      if (x.source === 'manual_admin') return 'Manual Override';
      if (x.new_status === 'disabled' || x.new_status === 'quarantined') return 'Kill Switch Triggered';
      if (x.new_status === 'review') return 'Automatic Review Triggered';
      return 'Lifecycle Status Change';
    }
    return [
      ...kill.map((x) => ({ ...x, type: killLabel(x), time: x.timestamp, trigger: x.reason, next: x.new_status })),
      ...degradation.map((x) => ({ ...x, type: 'Quality Degradation Detected', time: x.created_at || x.timestamp, trigger: x.reason, next: 'review' })),
      ...guardrails.map((x) => ({ ...x, type: 'Guardrail Block', time: x.timestamp, trigger: x.reason, next: x.decision })),
      ...policy.map((x) => ({ ...x, type: 'Policy Decision', time: x.timestamp, trigger: x.reason, next: x.decision })),
    ].sort((a, b) => String(b.time).localeCompare(String(a.time))).slice(0, 30);
  }, [kill, degradation, guardrails, policy]);

  async function applyOverride() {
    setBusy('override');
    try {
      const result = await controlPlaneApi.changeAgentStatus(agentId, { ...override, source: 'manual_admin', triggered_by: 'audited_control_panel' });
      setNotice(`Audited override recorded: ${result.previous_status} -> ${result.new_status}.`);
      state.reload();
    } catch (e) { setNotice(e.message); } finally { setBusy(''); }
  }

  async function test(kind) {
    setBusy(kind);
    try {
      if (kind === 'unsafe') await controlPlaneApi.runUnsafeSql({ agent_id: agentId, sql: 'DROP TABLE customers;' });
      else if (kind === 'quality') await controlPlaneApi.simulateDegradation({ agent_id: agentId, scenario: 'low_groundedness' });
      else await controlPlaneApi.invokeAgent(agentId, { query: 'Governed validation invocation' });
      state.reload();
      setNotice('Internal validation action recorded in the evidence timeline.');
    } catch (e) { setNotice(e.message); } finally { setBusy(''); }
  }

  return <>
    <PageHeader
      title="Agent Lifecycle / Kill Switch"
      subtitle="Lifecycle status, governance signals, and runtime intervention controls for all registered agents."
      right={
        <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
          <label className="cc-switch"><input type="checkbox" checked={!excludeTest} onChange={(e) => setExcludeTest(!e.target.checked)} /> Include admin/test evidence</label>
          <button className="cc-button" onClick={state.reload}>Refresh</button>
        </div>
      }
    />
    {notice && <div className="cc-notice info">{notice}</div>}
    <LoadingState loading={state.loading} error={state.error} />
    {!state.loading && !state.error && <>
      <KpiStrip items={[
        { label: 'Active Agents', value: counts.active },
        { label: 'Agents in Review', value: counts.review, accent: 'amber' },
        { label: 'Quarantined Agents', value: counts.quarantined, accent: 'red' },
        { label: 'Disabled Agents', value: counts.disabled, accent: 'grey' },
        { label: 'Automatic Interventions', value: degradation.filter((x) => x.source === 'automatic').length + kill.filter((x) => x.source === 'automatic').length, accent: 'purple' },
        { label: 'Human Overrides', value: kill.filter((x) => x.source === 'manual_admin').length, accent: 'teal' },
      ]} />

      {/* Lifecycle logic explanation */}
      <div style={{ display: 'flex', gap: 10, margin: '16px 0', flexWrap: 'wrap' }}>
        {[
          { icon: '🟡', label: 'Soft quality issue', desc: 'RAG score below threshold on a valid policy query — agent moved to Review. Still operational with human oversight.' },
          { icon: '🔴', label: 'Repeated / critical issue', desc: 'Multiple RAG failures, guardrail breach, or high error rate — agent Disabled or Quarantined. Manual override required.' },
          { icon: '🔵', label: 'Manual override', desc: 'Operator-approved lifecycle change via this panel. Recorded as an audited human action with reason and approver.' },
        ].map(item => (
          <div key={item.label} style={{ flex: '1 1 200px', padding: '10px 14px', borderRadius: 6, background: 'var(--surface-inset)', border: '1px solid var(--border)', fontSize: 12 }}>
            <div style={{ fontWeight: 700, marginBottom: 4, color: 'var(--text)' }}>{item.icon} {item.label}</div>
            <div style={{ color: 'var(--text-muted)', lineHeight: 1.5 }}>{item.desc}</div>
          </div>
        ))}
      </div>

      {/* Control point legend */}
      <div style={{ display: 'flex', gap: 10, margin: '0 0 16px 0', flexWrap: 'wrap' }}>
        {CONTROL_POINTS.map(cp => (
          <div key={cp.name} style={{ flex: '1 1 200px', padding: '10px 14px', borderRadius: 6, background: 'var(--surface-inset)', border: '1px solid var(--border)', fontSize: 12 }}>
            <div style={{ fontWeight: 700, marginBottom: 4, color: 'var(--text)' }}>{cp.name}</div>
            <div style={{ color: 'var(--text-muted)' }}>{cp.desc}</div>
          </div>
        ))}
      </div>

      <SectionCard className="cc-top-gap" title="Agent Lifecycle Board" subtitle="Current lifecycle status and latest governance signal per agent.">
        <LifecycleBoard agents={data.agents} kill={kill} policy={policy} evaluations={data.evaluations} />
      </SectionCard>

      {/* Human Override placed ABOVE Automatic Interventions — always visible without excessive scrolling */}
      <SectionCard className="cc-top-gap" title="Human Override / Reactivation" subtitle="An audited administrative workflow for approved lifecycle changes.">
        <div className="cc-detail-grid">
          <dt>Agent</dt><dd><select className="cc-input" value={agentId} onChange={(e) => setAgentId(e.target.value)}>{data.agents.map((a) => <option key={a.agent_id} value={a.agent_id}>{a.name || a.agent_id}</option>)}</select></dd>
          <dt>Target status</dt><dd><select className="cc-input" value={override.status} onChange={(e) => setOverride({ ...override, status: e.target.value })}>{['active', 'review', 'quarantined', 'disabled'].map((s) => <option key={s}>{s}</option>)}</select></dd>
          <dt>Reason</dt><dd><input className="cc-input" value={override.reason} onChange={(e) => setOverride({ ...override, reason: e.target.value })} /></dd>
          <dt>Approved by</dt><dd><input className="cc-input" value={override.approved_by} onChange={(e) => setOverride({ ...override, approved_by: e.target.value })} /></dd>
          <dt>Override type</dt><dd><input className="cc-input" value={override.override_type} onChange={(e) => setOverride({ ...override, override_type: e.target.value })} /></dd>
        </div>
        <ActionButton loading={busy === 'override'} onClick={applyOverride}>Apply Audited Override</ActionButton>
      </SectionCard>

      <div className="cc-grid-2 cc-top-gap">
        <SectionCard title="Automatic Interventions" subtitle="Most recent first. RAG quality failures trigger Review, not Kill Switch, unless repeated or critical.">
          <Timeline rows={timeline} />
        </SectionCard>
        <SectionCard title="RAG Quality Degradation Monitor" subtitle="Retrieval quality signals for RAG agents only. Workflow, voice, and vendor agents are not shown here.">
          <Quality rows={ragEvaluations} />
        </SectionCard>
      </div>

      <SectionCard className="cc-top-gap" title="Admin Validation Controls" subtitle="For internal validation only." right={<button className="cc-button" onClick={() => setOpen(!open)}>{open ? 'Hide controls' : 'Show controls'}</button>}>
        {open && <div className="cc-actions">
          <ActionButton danger loading={busy === 'unsafe'} onClick={() => test('unsafe')}>Trigger unsafe SQL</ActionButton>
          <ActionButton loading={busy === 'quality'} onClick={() => test('quality')}>Create Quality Validation Event</ActionButton>
          <ActionButton loading={busy === 'invoke'} onClick={() => test('invoke')}>Try invoke in current state</ActionButton>
        </div>}
      </SectionCard>
    </>}
  </>;
}

// ─── Agent Lifecycle Board ────────────────────────────────────────────────────
function LifecycleBoard({ agents, kill, policy, evaluations }) {
  if (!agents.length) return <div className="cc-empty">No agents registered.</div>;
  return (
    <div className="cc-table-scroll">
      <table className="cc-table">
        <thead>
          <tr>
            <th>Agent</th>
            <th>Type</th>
            <th>Business Function</th>
            <th>Status</th>
            <th>Last Intervention</th>
            <th>Governance Signal</th>
            <th>Control Point</th>
            <th>Action Required</th>
          </tr>
        </thead>
        <tbody>
          {agents.map((a) => {
            const event = kill.find((x) => x.agent_id === a.agent_id);
            const evaluation = evaluations.find((x) => x.agent_id === a.agent_id);
            const sig = getLifecycleSignal(a, evaluation, policy);
            const agentTypeLabel = isRagAgent(a) ? 'RAG Agent' : agentTypeDisplay(a);

            return (
              <tr key={a.agent_id}>
                <td>{display(a.name || a.agent_id)}</td>
                <td><span style={{ fontSize: 11, fontWeight: 600, padding: '2px 7px', borderRadius: 4, background: 'var(--surface-inset)', border: '1px solid var(--border)' }}>{agentTypeLabel}</span></td>
                <td>{display(a.business_function)}</td>
                <td><StatusChip status={a.status} /></td>
                <td>{fmtTime(event?.timestamp)}</td>
                <td><GovernanceSignal sig={sig} /></td>
                <td style={{ fontSize: 12, color: 'var(--text-muted)' }}>{sig.controlPoint}</td>
                <td style={{ fontSize: 12 }}>{resolveActionRequired(a, sig)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

/** Human-readable agent type label derived from manifest fields. */
function agentTypeDisplay(agent) {
  const execMode = agent.execution_mode || '';
  const agentType = agent.agent_type || '';
  if (['external_plugin', 'github_wrapped_workflow'].includes(agentType)) return 'Workflow / External Plugin';
  if (agentType === 'vendor') return 'Vendor Agent';
  if (execMode === 'voice') return 'Voice Agent';
  if (execMode === 'workflow') return 'Workflow Agent';
  return 'Agent';
}

/**
 * Action required cell: lifecycle status takes priority; governance signal
 * fills in when the agent is active and not under intervention.
 */
function resolveActionRequired(agent, sig) {
  if (agent.status === 'review') return 'Human review required';
  if (agent.status === 'quarantined') return 'Blocked — awaiting override';
  if (agent.status === 'disabled') return 'Disabled';
  return sig.actionRequired || 'No action';
}

/** Renders the right column content depending on agent type. */
function GovernanceSignal({ sig }) {
  if (sig.kind === 'rag') {
    return sig.groundedness == null
      ? <span className="cc-muted" style={{ fontSize: 12 }}>No evaluations recorded</span>
      : <span style={{ fontSize: 12 }}>{sig.groundedness}% groundedness</span>;
  }
  // Governance/policy signal for workflow / vendor / voice agents
  return (
    <div style={{ fontSize: 12, lineHeight: 1.6 }}>
      {sig.lastDecision && sig.lastDecision !== '—' && (
        <div><span style={{ fontWeight: 600 }}>Decision:</span> <DecisionOrChip value={sig.lastDecision} /></div>
      )}
      {sig.lastRiskSignal && sig.lastRiskSignal !== 'No decisions recorded' && (
        <div style={{ color: 'var(--text-muted)' }}>{sig.lastRiskSignal}</div>
      )}
      {(!sig.lastDecision || sig.lastDecision === '—') && (
        <span className="cc-muted">No decisions recorded</span>
      )}
    </div>
  );
}

/** Renders a coloured chip for known decision values, plain text otherwise. */
function DecisionOrChip({ value }) {
  const colour = value === 'REVIEW' ? 'var(--warning)' : value === 'BLOCK' ? 'var(--error)' : value === 'ALLOW' ? 'var(--success)' : 'var(--text-muted)';
  return <span style={{ fontWeight: 700, color: colour }}>{value}</span>;
}

// ─── Sub-components (unchanged logic, RAG-only filter applied upstream) ──────
function Timeline({ rows }) {
  return !rows.length
    ? <div className="cc-empty">No runtime interventions recorded.</div>
    : <div className="cc-table-scroll"><table className="cc-table"><thead><tr><th>Time</th><th>Source</th><th>Agent</th><th>Intervention</th><th>Trigger</th><th>Result</th><th>Trace ID</th></tr></thead><tbody>{rows.map((r, i) => <tr key={r.id || i}><td>{fmtTime(r.time)}</td><td><SourceBadge source={r.source} /></td><td>{display(r.agent_id)}</td><td><Chip value={r.type} /></td><td>{display(r.trigger)}</td><td><StatusChip status={r.next} /></td><td className="mono">{display(r.trace_id)}</td></tr>)}</tbody></table></div>;
}

// ragEvaluations is already pre-filtered to RAG agents only before being passed here.
function Quality({ rows }) {
  return !rows.length
    ? <div className="cc-empty">No runtime RAG quality signals recorded. Run the Policy Assistant agent to populate this view.</div>
    : <div className="cc-table-scroll"><table className="cc-table"><thead><tr><th>Agent</th><th>Groundedness</th><th>Similarity</th><th>Evidence Coverage</th><th>Relevance</th><th>Action</th></tr></thead><tbody>{rows.slice(0, 10).map((r) => <tr key={r.evaluation_id}><td>{display(r.agent_id)}</td><td>{display(r.groundedness_score)}</td><td>{display(r.semantic_similarity_score)}</td><td>{display(r.retrieved_evidence_coverage)}</td><td>{display(r.answer_relevance_score)}</td><td>{Number(r.groundedness_score) < 0.6 ? 'Moved to review when threshold breached' : 'No action'}</td></tr>)}</tbody></table></div>;
}