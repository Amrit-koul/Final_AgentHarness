import React, { useCallback, useState } from 'react';
import PageHeader from '../../components/control/PageHeader';
import { Chip } from '../../components/control/Chips';
import { LoadingState, SectionCard, asArray, display, fmtTime, parseControlTimestamp } from '../../components/control/Common';
import { useControlData } from '../../hooks/useControlData';
import { controlPlaneApi } from '../../services/controlPlaneApi';

// ── Threshold logic (mirrors backend) ────────────────────────────────────────
function gate(row) {
  const values = [
    row.groundedness_score,
    row.semantic_similarity_score,
    row.answer_relevance_score,
    row.retrieved_evidence_coverage,
  ].filter((v) => v != null);
  if (!values.length) return 'REVIEW';
  return values.some((v) => Number(v) < 0.4)
    ? 'BLOCK'
    : values.some((v) => Number(v) < 0.6)
    ? 'REVIEW'
    : 'PASS';
}

const pct = (value) =>
  value == null
    ? <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>—</span>
    : `${Math.round(Number(value) * 100)}%`;

// ── Summary card ─────────────────────────────────────────────────────────────
function SummaryCard({ rows }) {
  if (!rows.length) return null;
  const latest = rows[0];
  const outcome = latest.quality_gate || gate(latest);
  const outcomeColor =
    outcome === 'PASS' ? 'var(--success)' :
    outcome === 'BLOCK' ? 'var(--error)' : 'var(--warning)';
  const sourcesCount = latest.retrieved_chunk_count ?? latest.cited_chunk_count ?? '—';
  const coverage = latest.retrieved_evidence_coverage != null
    ? `${Math.round(Number(latest.retrieved_evidence_coverage) * 100)}%`
    : '—';
  const method = latest.evaluator_method || '—';

  return (
    <div style={{
      display: 'flex', gap: 12, margin: '0 0 16px 0', flexWrap: 'wrap',
    }}>
      {[
        {
          label: 'Latest Quality Gate',
          value: <span style={{ color: outcomeColor, fontWeight: 700, fontSize: 16 }}>{outcome}</span>,
        },
        { label: 'Evidence Coverage', value: coverage },
        { label: 'Retrieved Sources', value: sourcesCount },
        { label: 'Evaluation Method', value: method },
        { label: 'Timestamp', value: <span style={{ fontSize: 11 }}>{fmtTime(latest.created_at || latest.timestamp)}</span> },
      ].map(card => (
        <div key={card.label} style={{
          flex: '1 1 130px',
          padding: '12px 16px',
          borderRadius: 6,
          background: 'var(--surface)',
          border: '1px solid var(--border)',
          boxShadow: 'var(--shadow-sm)',
        }}>
          <div style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-muted)', marginBottom: 6 }}>
            {card.label}
          </div>
          <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text)' }}>
            {card.value}
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function RagQuality() {
  const [excludeTest, setExcludeTest] = useState(true);
  const [timeFilter, setTimeFilter] = useState('last24h');

  const fetchData = useCallback(async () => asArray(await controlPlaneApi.listEvaluations(), 'evaluations'), []);
  const state = useControlData(fetchData, [], 5000);
  const rawRows = state.data || [];

  // Strict allowlist: only confirmed retrieval/RAG agents.
  // Do NOT add collections_workflow_agent, loan_assessment_agent, or any
  // workflow / voice / vendor / decision agent here.
  const RAG_AGENT_IDS = new Set([
    'policy_assistant_agent',
    // 'document_checker_agent',  // add when onboarded
    // 'knowledge_base_agent',    // add when onboarded
  ]);

  const now = Date.now();
  const todayStr = new Date().toLocaleDateString();

  const rows = rawRows.filter(r => {
    const isRagCapability = r.agent_capability === 'rag';
    const isRagAgent = RAG_AGENT_IDS.has(r.agent_id);
    if (!isRagCapability && !isRagAgent) return false;
    if (excludeTest) {
      const src = String(r.source || '').toLowerCase();
      if (['admin_validation', 'manual_validation', 'simulation'].includes(src) || r.is_simulated) return false;
    }
    if (timeFilter === 'last24h') {
      const dt = parseControlTimestamp(r.created_at || r.timestamp);
      if (!dt || (now - dt.getTime()) > 86400000) return false;
    } else if (timeFilter === 'today_local') {
      const dt = parseControlTimestamp(r.created_at || r.timestamp);
      if (!dt || dt.toLocaleDateString() !== todayStr) return false;
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
            <option value="last24h">Last 24 hours</option>
            <option value="today_local">Today (local time)</option>
            <option value="all">All current database history</option>
          </select>
          <label className="cc-switch">
            <input type="checkbox" checked={!excludeTest} onChange={(e) => setExcludeTest(!e.target.checked)} />
            {' '}Include admin/test evidence
          </label>
          <button className="cc-button" onClick={state.reload}>Refresh</button>
        </div>
      }
    />

    <LoadingState loading={state.loading} error={state.error} />

    {!state.loading && !state.error && <>
      <div style={{
        margin: '0 0 16px 0', padding: '10px 14px', borderRadius: 6,
        background: 'var(--surface-inset)', border: '1px solid var(--border)',
        fontSize: 12, color: 'var(--text-muted)',
      }}>
        ℹ️ Only retrieval-based agents appear here. Workflow, voice, and vendor agents are
        monitored through execution traces, policy decisions, and lifecycle controls.
      </div>

      {/* Summary card — latest run at a glance */}
      <SummaryCard rows={rows} />

      <SectionCard
        title="Retrieval Quality Signals"
        subtitle="Quality gates support review workflows; they do not guarantee factual correctness."
      >
        {!rows.length ? (
          <div className="cc-empty">
            No runtime RAG quality evidence recorded in this time window.
            Run the Policy Assistant agent to populate this view, or widen the time filter.
          </div>
        ) : (
          <div className="cc-table-scroll">
            <table className="cc-table" style={{ fontSize: 12 }}>
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>Agent</th>
                  <th>Trace ID</th>
                  {/* Business-readable column headers */}
                  <th>Groundedness</th>
                  <th>Embedding Similarity</th>
                  <th>Answer Relevance</th>
                  <th>Evidence Coverage</th>
                  <th>LLM Judge</th>
                  <th>Method</th>
                  <th>Quality Gate</th>
                  <th>Reason</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.evaluation_id} style={{ fontSize: 12 }}>
                    <td style={{ whiteSpace: 'nowrap' }}>{fmtTime(row.created_at || row.timestamp)}</td>
                    <td style={{ whiteSpace: 'nowrap' }}>{display(row.agent_id)}</td>
                    <td className="mono" style={{ fontSize: 10, maxWidth: 90, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {display(row.trace_id)}
                    </td>
                    <td style={{ textAlign: 'right' }}>{pct(row.groundedness_score)}</td>
                    <td style={{ textAlign: 'right' }}>{pct(row.semantic_similarity_score)}</td>
                    <td style={{ textAlign: 'right' }}>{pct(row.answer_relevance_score)}</td>
                    <td style={{ textAlign: 'right' }}>{pct(row.retrieved_evidence_coverage)}</td>
                    <td style={{ textAlign: 'right' }}>
                      {row.llm_judge_score == null
                        ? <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>Not run</span>
                        : pct(row.llm_judge_score)}
                    </td>
                    <td style={{ fontSize: 11 }}>{display(row.evaluator_method)}</td>
                    <td><Chip value={row.quality_gate || gate(row)} /></td>
                    <td style={{ fontSize: 11, maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {display(row.reason)}
                    </td>
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