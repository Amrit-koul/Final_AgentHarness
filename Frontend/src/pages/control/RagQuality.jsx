import React, { useCallback, useState } from 'react';
import PageHeader from '../../components/control/PageHeader';
import { Chip } from '../../components/control/Chips';
import { LoadingState, SectionCard, asArray, display, fmtTime } from '../../components/control/Common';
import { useControlData } from '../../hooks/useControlData';
import { controlPlaneApi } from '../../services/controlPlaneApi';

function gate(row) {
  const values = [row.groundedness_score, row.semantic_similarity_score, row.answer_relevance_score, row.retrieved_evidence_coverage].filter((value) => value != null);
  if (!values.length) return 'REVIEW';
  return values.some((value) => Number(value) < .4) ? 'BLOCK' : values.some((value) => Number(value) < .6) ? 'REVIEW' : 'PASS';
}
const score = (value) => value == null ? <span className="cc-muted">Not configured</span> : `${Math.round(Number(value) * 100)}%`;

export default function RagQuality() {
  const [excludeTest, setExcludeTest] = useState(true);
  const [timeFilter, setTimeFilter] = useState('today');

  const fetchData = useCallback(async () => asArray(await controlPlaneApi.listEvaluations(), 'evaluations'), []);
  const state = useControlData(fetchData, [], 5000);
  const rawRows = state.data || [];

  // Strict allowlist: only confirmed retrieval/RAG agents.
  // Do NOT add collections_workflow_agent, loan_assessment_agent, demo_vendor_rest_agent,
  // sample_external_agent, sample_external_rest_agent, sample_github_wrapped_agent,
  // or any workflow / voice / vendor / decision agent here.
  const RAG_AGENT_IDS = new Set([
    'policy_assistant_agent',
    // 'document_checker_agent',  // add when onboarded
    // 'knowledge_base_agent',    // add when onboarded
  ]);

  const todayStr = new Date().toDateString();
  const rows = rawRows.filter(r => {
    // Include only explicit rag capability OR confirmed RAG agent IDs — nothing else.
    const isRagCapability = r.agent_capability === 'rag';
    const isRagAgent = RAG_AGENT_IDS.has(r.agent_id);
    if (!isRagCapability && !isRagAgent) return false;
    // Exclude simulated/admin sources when toggle is off
    if (excludeTest) {
      const src = String(r.source || '').toLowerCase();
      if (['admin_validation', 'manual_validation', 'simulation'].includes(src) || r.is_simulated) return false;
    }
    // Time filter
    if (timeFilter === 'today') {
      const dt = new Date(r.created_at || r.timestamp || 0);
      if (dt.toDateString() !== todayStr) return false;
    }
    return true;
  });

  return <>
    <PageHeader 
      title="RAG Quality" 
      subtitle="Retrieval quality signals and quality-gate outcomes recorded across governed agent runs." 
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
      <div style={{ margin: '0 0 16px 0', padding: '10px 14px', borderRadius: 6, background: 'var(--surface-inset)', border: '1px solid var(--border)', fontSize: 13, color: 'var(--text-muted)' }}>
        ℹ️ Only retrieval-based agents appear here. Workflow, voice, and vendor agents are monitored through execution traces, policy decisions, and lifecycle controls.
      </div>
      <SectionCard title="Retrieval Quality Signals" subtitle="Quality gates support review workflows; they do not guarantee factual correctness.">
      {!rows.length ? (
        <div className="cc-empty">No runtime RAG quality evidence recorded today. Run the Policy Assistant agent to populate this view.</div>
      ) : (
        <div className="cc-table-scroll">
          <table className="cc-table">
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>Agent</th>
                <th>Trace ID</th>
                <th>lexical_groundedness</th>
                <th>embedding_similarity</th>
                <th>lexical_answer_relevance</th>
                <th>retrieved_evidence_coverage</th>
                <th>llm_judge</th>
                <th>Method</th>
                <th>RAG Quality Gate</th>
                <th>Reason</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.evaluation_id}>
                  <td>{fmtTime(row.created_at || row.timestamp)}</td>
                  <td>{display(row.agent_id)}</td>
                  <td className="mono">{display(row.trace_id)}</td>
                  <td>{score(row.groundedness_score)}</td>
                  <td>{score(row.semantic_similarity_score)}</td>
                  <td>{score(row.answer_relevance_score)}</td>
                  <td>{score(row.retrieved_evidence_coverage)}</td>
                  <td>{row.llm_judge_score == null ? <span className="cc-muted">Not run</span> : score(row.llm_judge_score)}</td>
                  <td>{display(row.evaluator_method)}</td>
                  <td><Chip value={row.quality_gate || gate(row)} /></td>
                  <td>{display(row.reason)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </SectionCard>
    </>}
  </>;
}
