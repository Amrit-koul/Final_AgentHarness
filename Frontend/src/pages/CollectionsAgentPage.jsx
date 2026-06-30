import React, { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { AppNav, Btn, Card, CardBody, CardHeader, FieldGroup, Select, Textarea, formatINR } from '../components/Primitives';
import { controlPlaneApi } from '../services/controlPlaneApi';
import { SourceBadge } from '../utils/evidenceLabels';
import { StatusChip } from '../components/control/Chips';

const SCORE_KEYS = ['ability_to_pay', 'intent_to_pay', 'trust', 'contactability', 'self_cure'];
const SCORE_LABELS = { ability_to_pay: 'Ability to Pay', intent_to_pay: 'Intent to Pay', trust: 'Trust', contactability: 'Contactability', self_cure: 'Self Cure' };

const present = (value) => value !== undefined && value !== null && value !== '';
const title = (value) => String(value).replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());

function Value({ value }) {
  if (!present(value)) return <span className="collections-muted">Not returned</span>;
  if (typeof value === 'boolean') return <span className={`collections-pill ${value ? 'green' : 'grey'}`}>{value ? 'Yes' : 'No'}</span>;
  if (typeof value === 'object') return <pre className="collections-inline-json">{JSON.stringify(value, null, 2)}</pre>;
  return <>{String(value)}</>;
}

function Details({ data, keys, showMissing = false }) {
  const rows = (keys || Object.keys(data || {})).filter((key) => showMissing || present(data?.[key]));
  if (!rows.length) return <div className="collections-empty">No details to show</div>;
  return <dl className="collections-details">{rows.map((key) => <React.Fragment key={key}><dt>{title(key)}</dt><dd><Value value={data[key]} /></dd></React.Fragment>)}</dl>;
}

function EventTable({ events, emptyText }) {
  if (!events || !events.length) return <div className="collections-empty">{emptyText}</div>;
  return <div className="collections-table-wrap"><table className="collections-table"><thead><tr><th>Time</th><th>Event</th><th>Status / Decision</th><th>Details</th></tr></thead><tbody>{events.map((event, index) => <tr key={event.id || event.event_id || index}><td>{event.timestamp ? new Date(event.timestamp).toLocaleString('en-IN') : '—'}</td><td>{event.event_type || event.guardrail_id || event.action || event.step || 'Event'}</td><td>{event.status || event.decision || event.severity || '—'}</td><td><Value value={event.details || event.reason || event.payload} /></td></tr>)}</tbody></table></div>;
}

export default function CollectionsAgentPage() {
  const [accounts, setAccounts] = useState([]);
  const [transcripts, setTranscripts] = useState([]);
  const [selectedAccId, setSelectedAccId] = useState('');
  const [activeTab, setActiveTab] = useState('workflow');
  
  // State for pre_call
  const [preCallLoading, setPreCallLoading] = useState(false);
  const [preCallResult, setPreCallResult] = useState(null);
  
  // State for transcript
  const [selectedTransId, setSelectedTransId] = useState('');
  const [customText, setCustomText] = useState('');
  
  // State for post_call
  const [postCallLoading, setPostCallLoading] = useState(false);
  const [postCallResult, setPostCallResult] = useState(null);
  
  // State for history
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyData, setHistoryData] = useState(null);
  const [agentStatus, setAgentStatus] = useState(null);

  const [error, setError] = useState('');
  const selectedAcc = useMemo(() => accounts.find(a => a.id === selectedAccId), [accounts, selectedAccId]);

  // Load initial data
  useEffect(() => {
    controlPlaneApi.listCollectionsAccounts().then(res => setAccounts(res?.accounts || []));
    controlPlaneApi.getCollectionsTranscripts().then(res => setTranscripts(res?.transcripts || []));
    refreshAgentStatus();
  }, []);

  // When account changes, reset state and run pre-call automatically
  useEffect(() => {
    if (!selectedAccId) return;
    setPreCallResult(null);
    setPostCallResult(null);
    setHistoryData(null);
    setActiveTab('workflow');
    
    runPreCall(selectedAccId);
    loadHistory(selectedAccId);
    refreshAgentStatus();
  }, [selectedAccId]);

  async function refreshAgentStatus() {
    try {
      const res = await controlPlaneApi.getStatus('collections_workflow_agent');
      setAgentStatus(res?.status || null);
    } catch {
      setAgentStatus(null);
    }
  }

  async function runPreCall(accId) {
    setPreCallLoading(true); setError('');
    try {
      const res = await controlPlaneApi.runCollectionsPreCall(accId);
      setPreCallResult(res);
      refreshAgentStatus();
    } catch (err) { setError(err.message); }
    finally { setPreCallLoading(false); }
  }

  async function runPostCall() {
    if (!selectedAccId) return;
    setPostCallLoading(true); setError('');
    try {
      const res = await controlPlaneApi.runCollectionsPostCall(selectedAccId, customText, selectedTransId);
      setPostCallResult(res);
      // Refresh history
      loadHistory(selectedAccId);
      refreshAgentStatus();
    } catch (err) { setError(err.message); }
    finally { setPostCallLoading(false); }
  }

  async function loadHistory(accId) {
    setHistoryLoading(true);
    try {
      const res = await controlPlaneApi.getCollectionsHistory(accId);
      setHistoryData(res);
    } catch (err) { /* ignore 404s for new accounts */ }
    finally { setHistoryLoading(false); }
  }

  // Derived variables for UI
  const preCallPayload = preCallResult?.result || preCallResult || {};
  const postCallPayload = postCallResult?.result || postCallResult || {};
  const preCallData = preCallPayload?.pre_call || {};
  const preCallCtx = preCallData.pre_call_context || {};
  const scores = preCallData.scoring?.flat || preCallData.scores || {};
  const persona = preCallData.persona_result || preCallData.persona || {};
  const preCallEvidence = preCallPayload?.control_evidence;

  const postCallData = postCallPayload?.post_call || {};
  const transcriptAnalysis = postCallPayload?.transcript_analysis || {};
  const updates = postCallPayload?.updates || {};
  const postCallEvidence = postCallPayload?.control_evidence;
  const blockedEvidence = (preCallPayload?.adapter_invoked === false && preCallPayload) || (postCallPayload?.adapter_invoked === false && postCallPayload) || null;
  const reviewBlocked = agentStatus === 'review' || blockedEvidence?.status === 'review';

  return <div className="collections-page">
    <AppNav active="/collections" />
    <main className="collections-main">
      <header className="collections-page-header">
        <div>
          <h1>Collections Intelligence</h1>
          <p>Governed multi-stage Collections workflow managed by the Agent Harness.</p>
        </div>
        <SourceBadge source="seeded_portfolio" />
      </header>
      
      {error && <div className="collections-error">{error}</div>}

      <div style={{ marginBottom: 24 }}>
          <h3>A. Case Portfolio</h3>
        <Card><CardBody>
          <div className="collections-account-strip">
            {accounts.map(acc => (
              <button key={acc.id} className={`collections-account-card ${selectedAccId === acc.id ? 'selected' : ''}`} onClick={() => setSelectedAccId(acc.id)}>
                <strong>{acc.name}</strong><small>{acc.id}</small>
                <div className="collections-account-metrics"><span><b>{acc.dpd}</b> DPD</span></div>
                <span className="collections-muted" style={{ fontSize: 11 }}>Prepared case data</span>
              </button>
            ))}
          </div>
        </CardBody></Card>
      </div>

      {selectedAcc && <div className="collections-workspace">
        {reviewBlocked && <div className="cc-notice warning" style={{ marginBottom: 16 }}>
          Agent is in review. Reactivation or human override is required.{' '}
          <Link className="cc-link-button" to="/control/kill-switch">Open lifecycle controls</Link>
          {blockedEvidence?.trace_id && <> Trace ID: <span className="mono">{blockedEvidence.trace_id}</span></>}
        </div>}
        {blockedEvidence && !reviewBlocked && <div className="cc-notice warning" style={{ marginBottom: 16 }}>
          Control plane blocked adapter execution: {blockedEvidence.reason || 'policy decision requires review'}. Trace ID: <span className="mono">{blockedEvidence.trace_id}</span>
        </div>}
        <div className="collections-tabs">
          <button className={activeTab === 'workflow' ? 'active' : ''} onClick={() => setActiveTab('workflow')}>Governed Workflow</button>
          <button className={activeTab === 'history' ? 'active' : ''} onClick={() => setActiveTab('history')}>G. Audit History</button>
        </div>

        {activeTab === 'workflow' && (
          <div className="collections-tab-content" style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
            
            <section>
              <h3>B. Account Intelligence</h3>
              {preCallLoading ? <div className="collections-empty">Running pre-call rules...</div> : (
                <div className="collections-two-col">
                  <Card><CardHeader title="Five-Score Engine" subtitle={preCallEvidence?.scoring_method} /><CardBody>
                    <div className="collections-score-grid">
                      {SCORE_KEYS.map((key) => (
                        <div className="collections-score" key={key}><span>{SCORE_LABELS[key]}</span><strong>{present(scores[key]) ? scores[key] : '—'}</strong></div>
                      ))}
                    </div>
                  </CardBody></Card>
                  <Card><CardHeader title="Context & Risk Flags" /><CardBody>
                    <Details data={persona} keys={['current_persona', 'recommended_persona', 'confidence']} />
                    <div className="collections-alert-box">
                      <strong>Risk Flags:</strong>
                      <ul>{(preCallCtx.risk_flags || []).map((f, i) => <li key={i}>{f}</li>)}</ul>
                    </div>
                    <div style={{ marginTop: 10 }}><strong>Recommended NBA:</strong> {(preCallData.next_best_action || preCallData.nba)?.action || 'Follow up'}</div>
                  </CardBody></Card>
                </div>
              )}
            </section>

            <section>
              <h3>C. Transcript Analysis</h3>
              <Card><CardHeader title="Transcript Selection" subtitle="Choose a prepared transcript or paste text for post-interaction analysis." /><CardBody>
                <div className="collections-two-col">
                  <div>
                    <FieldGroup label="Select Captured Transcript">
                      <Select value={selectedTransId} onChange={(e) => setSelectedTransId(e.target.value)}>
                        <option value="">-- Custom Text Entry --</option>
                        {transcripts.map(t => <option key={t.id} value={t.id}>{t.title} ({t.persona_context})</option>)}
                      </Select>
                    </FieldGroup>
                    {selectedTransId && <div className="collections-muted" style={{ marginTop: 10, fontSize: 13 }}>
                      {transcripts.find(t => t.id === selectedTransId)?.description}
                    </div>}
                  </div>
                  <div>
                    <FieldGroup label="Transcript Text">
                      <Textarea 
                        value={selectedTransId ? 'Prepared transcript selected. The analysis service resolves the stored transcript and extracts evidence.' : customText}
                        onChange={(e) => setCustomText(e.target.value)}
                        disabled={!!selectedTransId}
                        placeholder="Paste raw conversation text here..."
                        style={{ minHeight: 120 }}
                      />
                    </FieldGroup>
                  </div>
                </div>
                <div style={{ marginTop: 20, textAlign: 'right' }}>
                  <Btn onClick={runPostCall} loading={postCallLoading} disabled={!selectedTransId && !customText.trim()}>
                    Run Transcript Analysis
                  </Btn>
                </div>
              </CardBody></Card>
            </section>

            {postCallResult && (
              <>
                <section>
                  <div className="collections-analysis-grid">
                    <div>
                      <h3>D. Transcript Analysis</h3>
                      <Card><CardHeader title="LLM Transcript Extraction" subtitle={`Source: ${postCallEvidence?.extraction_method || 'llm_extraction'}`} /><CardBody>
                        <div style={{ marginBottom: 12 }}><SourceBadge source={postCallEvidence?.evidence_source || transcriptAnalysis?.evidence_source || 'not_returned'} /></div>
                        <Details data={transcriptAnalysis} keys={['intent', 'sentiment', 'stress_score', 'life_event_detected', 'life_event_type', 'ptp_signal', 'ptp_date', 'ptp_amount', 'negotiation_signal', 'hostile_signal']} />
                        <div className="collections-guidance-box">
                          <strong>Outcome / Agent Guidance:</strong> {transcriptAnalysis?.agent_guidance || 'No guidance generated'}
                        </div>
                      </CardBody></Card>
                    </div>
                    <div>
                      <h3>E. Updates</h3>
                      <Card><CardHeader title="Analysis Pipeline Updates" subtitle="Scores, Persona, Trust Gate" /><CardBody>
                        <Details data={updates} keys={['persona_before_label', 'persona_applied', 'recommended_action', 'review_required', 'business_assessment']} />
                        {updates?.review_triggers?.length > 0 && (
                          <div className="collections-alert-box" style={{ marginTop: 10 }}>
                            <strong>Review Triggers:</strong>
                            <ul>{updates.review_triggers.map((t, i) => <li key={i}>{t}</li>)}</ul>
                          </div>
                        )}
                      </CardBody></Card>
                    </div>
                  </div>
                </section>

                <section>
                  <h3>F. Control Plane Evidence</h3>
                  <Card><CardHeader title="Agent Lifecycle & Governance" /><CardBody>
                    <div className="cc-grid-2">
                      <Details data={postCallEvidence} keys={['lifecycle_status', 'adapter_invoked', 'trace_id', 'usage_mode']} />
                      <div>
                        <strong>Policy Decision:</strong> {postCallEvidence?.policy_decision ? <StatusChip status={String(postCallEvidence.policy_decision).toLowerCase()} /> : <span className="cc-muted">Not evaluated</span>}
                        <br/><br/>
                        <strong>Guardrails Evaluated:</strong> {postCallEvidence?.guardrails_evaluated?.length ? postCallEvidence.guardrails_evaluated.join(', ') : <span className="cc-muted">None</span>}
                      </div>
                    </div>
                  </CardBody></Card>
                </section>
              </>
            )}
          </div>
        )}

        {activeTab === 'history' && (
          <div className="collections-tab-content">
            {historyLoading ? <div className="collections-empty">Loading history...</div> : (!historyData || (!historyData.calls?.length && !historyData.review_cases?.length)) ? <div className="collections-empty">No history available for this account.</div> : (
              <>
                <Card><CardHeader title="Call History" /><CardBody>
                  <EventTable events={historyData.calls.map(c => ({
                    timestamp: c.timestamp,
                    event_type: 'Voice Call',
                    status: c.sentiment,
                    details: `${c.summary || ''} [PTP: ${c.ptp_detected ? c.ptp_date : 'No'}]`
                  }))} />
                </CardBody></Card>
                
                <Card style={{ marginTop: 20 }}><CardHeader title="Review Cases" /><CardBody>
                  <EventTable events={historyData.review_cases.map(c => ({
                    timestamp: c.created_at,
                    event_type: c.case_type,
                    status: c.status,
                    details: c.review_reason
                  }))} />
                </CardBody></Card>
              </>
            )}
          </div>
        )}
        
      </div>}
    </main>
  </div>;
}
