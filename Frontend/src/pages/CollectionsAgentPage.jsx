import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { AppNav, Btn, Card, CardBody, CardHeader, FieldGroup, Select, Textarea, formatINR } from '../components/Primitives';
import { controlPlaneApi } from '../services/controlPlaneApi';
import { SourceBadge } from '../utils/evidenceLabels';
import { DecisionChip, StatusChip } from '../components/control/Chips';

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
  const [voiceStatus, setVoiceStatus] = useState(null);
  const [voiceLoading, setVoiceLoading] = useState(false);
  const [voiceMessage, setVoiceMessage] = useState('');
  const [voiceConversation, setVoiceConversation] = useState([]);
  const [voiceFinalResult, setVoiceFinalResult] = useState(null);
  const [recording, setRecording] = useState(false);
  const voiceConversationRef = useRef([]);
  const recorderRef = useRef(null);
  const streamRef = useRef(null);
  const audioChunksRef = useRef([]);

  const [error, setError] = useState('');
  const selectedAcc = useMemo(() => accounts.find(a => a.id === selectedAccId), [accounts, selectedAccId]);

  // Load initial data
  useEffect(() => {
    controlPlaneApi.listCollectionsAccounts().then(res => setAccounts(res?.accounts || []));
    controlPlaneApi.getCollectionsTranscripts().then(res => setTranscripts(res?.transcripts || []));
    refreshAgentStatus();
    refreshVoiceStatus();
  }, []);

  // When account changes, reset state and run pre-call automatically
  useEffect(() => {
    if (!selectedAccId) return;
    setPreCallResult(null);
    setPostCallResult(null);
    setVoiceFinalResult(null);
    setVoiceConversation([]);
    voiceConversationRef.current = [];
    setVoiceMessage('');
    setHistoryData(null);
    setActiveTab('workflow');
    
    runPreCall(selectedAccId);
    loadHistory(selectedAccId);
    refreshAgentStatus();
    refreshVoiceStatus();
  }, [selectedAccId]);

  async function refreshAgentStatus() {
    try {
      const res = await controlPlaneApi.getStatus('collections_workflow_agent');
      setAgentStatus(res?.status || null);
    } catch {
      setAgentStatus(null);
    }
  }

  async function refreshVoiceStatus() {
    try {
      const res = await controlPlaneApi.getCollectionsVoiceStatus();
      setVoiceStatus(res);
    } catch (err) {
      setVoiceStatus({ ready: false, blocker: err.message || 'Voice status unavailable' });
    }
  }

  function blobToBase64(blob) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onloadend = () => resolve(String(reader.result || '').split(',')[1] || '');
      reader.onerror = reject;
      reader.readAsDataURL(blob);
    });
  }

  function playVoiceAudio(audioB64) {
    if (!audioB64) return;
    const audio = new Audio(`data:audio/mpeg;base64,${audioB64}`);
    audio.play().catch(() => {});
  }

  function greetingFromStartResult(res) {
    const payload = res?.greeting?.result || res?.greeting || {};
    return payload?.greeting || payload;
  }

  async function startLiveVoice() {
    if (!selectedAccId || !voiceStatus?.ready) return;
    setVoiceLoading(true); setError(''); setVoiceMessage('Preparing live voice session...');
    try {
      if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
        throw new Error('This browser does not support MediaRecorder microphone capture');
      }
      const start = await controlPlaneApi.startCollectionsVoice(selectedAccId);
      const greeting = greetingFromStartResult(start);
      const greetingText = greeting?.aria_text || '';
      if (greetingText) {
        const greetingTurns = [{ role: 'assistant', content: greetingText }];
        voiceConversationRef.current = greetingTurns;
        setVoiceConversation(greetingTurns);
      }
      playVoiceAudio(greeting?.audio_b64);

      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus') ? 'audio/webm;codecs=opus' : 'audio/webm';
      const recorder = new MediaRecorder(stream, { mimeType });
      audioChunksRef.current = [];
      recorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) audioChunksRef.current.push(event.data);
      };
      recorder.onstop = () => handleRecordingStopped();
      recorderRef.current = recorder;
      streamRef.current = stream;
      recorder.start();
      setRecording(true);
      setVoiceMessage('Recording live browser audio...');
    } catch (err) {
      setError(err.message);
      setVoiceMessage('');
      stopMediaStream();
    } finally {
      setVoiceLoading(false);
    }
  }

  function stopMediaStream() {
    streamRef.current?.getTracks?.().forEach((track) => track.stop());
    streamRef.current = null;
  }

  function stopLiveVoice() {
    if (recorderRef.current && recorderRef.current.state !== 'inactive') {
      setVoiceMessage('Stopping recording and sending audio to governed STT...');
      recorderRef.current.stop();
    }
  }

  async function handleRecordingStopped() {
    setRecording(false);
    stopMediaStream();
    setVoiceLoading(true); setError('');
    try {
      const blob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
      if (!blob.size) throw new Error('No microphone audio was captured');
      const audio_b64 = await blobToBase64(blob);
      const turn = await controlPlaneApi.runCollectionsVoiceTurn({
        account_id: selectedAccId,
        audio_b64,
        conversation: voiceConversationRef.current,
      });
      const nextConversation = [
        ...voiceConversationRef.current,
        { role: 'user', content: turn.transcript || '' },
        { role: 'assistant', content: turn.aria_text || '' },
      ].filter((turnItem) => turnItem.content);
      voiceConversationRef.current = nextConversation;
      setVoiceConversation(nextConversation);
      playVoiceAudio(turn.audio_b64);
      setVoiceMessage('Transcript received. Running governed post-call finalization...');
      const finalResult = await controlPlaneApi.finalizeCollectionsVoice({
        account_id: selectedAccId,
        conversation: nextConversation,
      });
      setVoiceFinalResult(finalResult);
      setPostCallResult(finalResult);
      loadHistory(selectedAccId);
      refreshAgentStatus();
      refreshVoiceStatus();
      setVoiceMessage('Live voice finalized through post-call governance.');
    } catch (err) {
      setError(err.message);
      setVoiceMessage('');
    } finally {
      setVoiceLoading(false);
      audioChunksRef.current = [];
      recorderRef.current = null;
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
        <h3>A. Case Portfolio <small className="collections-muted" style={{ fontWeight: 'normal', fontSize: 13 }}>(source: seeded_portfolio)</small></h3>
        <Card><CardBody>
          <div className="collections-account-strip">
            {accounts.map(acc => (
              <button key={acc.id} className={`collections-account-card ${selectedAccId === acc.id ? 'selected' : ''}`} onClick={() => setSelectedAccId(acc.id)}>
                <strong>{acc.name}</strong><small>{acc.id}</small>
                <div className="collections-account-metrics"><span><b>{acc.dpd}</b> DPD</span></div>
                <span className="collections-muted" style={{ fontSize: 11 }}>source: seeded_portfolio</span>
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
              <h3>B. Pre-Call Intelligence</h3>
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
              <h3>C. Voice / Transcript Stage</h3>
              <Card><CardHeader title="Live Collections Voice" subtitle={voiceStatus?.provider ? `Provider: ${voiceStatus.provider}` : 'Checking backend voice readiness'} /><CardBody>
                {voiceStatus?.ready ? (
                  <>
                    <div className="collections-muted" style={{ marginBottom: 12 }}>
                      Browser microphone audio is sent to the governed backend as MediaRecorder audio/webm, transcribed by STT, and finalized through post-call governance.
                    </div>
                    <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
                      <Btn onClick={startLiveVoice} loading={voiceLoading && !recording} disabled={recording || voiceLoading || reviewBlocked}>Start Recording</Btn>
                      <Btn onClick={stopLiveVoice} disabled={!recording}>Stop Recording</Btn>
                      <StatusChip status={recording ? 'active' : 'ready'} />
                    </div>
                    {voiceMessage && <div className="cc-notice" style={{ marginTop: 12 }}>{voiceMessage}</div>}
                    {voiceConversation.length > 0 && (
                      <div style={{ marginTop: 14 }}>
                        <strong>Live Transcript</strong>
                        <div className="collections-inline-json" style={{ marginTop: 8 }}>
                          {voiceConversation.map((turn, index) => `${turn.role === 'user' ? 'Customer' : 'ARIA'}: ${turn.content}`).join('\n')}
                        </div>
                      </div>
                    )}
                    {voiceFinalResult && <div className="cc-notice success" style={{ marginTop: 12 }}>Live voice post-call output is shown in sections D-F below.</div>}
                  </>
                ) : (
                  <div className="cc-notice warning">
                    Live voice is disabled until the backend can process browser audio. {voiceStatus?.blocker || 'Voice backend status is unavailable.'}
                  </div>
                )}
              </CardBody></Card>
              <div style={{ height: 16 }} />
              <Card><CardHeader title="Transcript Selection" /><CardBody>
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
                        value={selectedTransId ? 'Captured transcript selected. The backend resolves the stored transcript by ID and extracts evidence server-side.' : customText}
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
                    Run Post-Call Analysis
                  </Btn>
                </div>
              </CardBody></Card>
            </section>

            {postCallResult && (
              <>
                <section>
                  <div className="collections-two-col">
                    <div>
                      <h3>D. Post-Call Analysis</h3>
                      <Card><CardHeader title="LLM Transcript Extraction" subtitle={`Source: ${postCallEvidence?.extraction_method || 'llm_extraction'}`} /><CardBody>
                        <div style={{ marginBottom: 12 }}><SourceBadge source={postCallEvidence?.evidence_source || transcriptAnalysis?.evidence_source || 'not_returned'} /></div>
                        <Details data={transcriptAnalysis} keys={['intent', 'sentiment', 'stress_score', 'life_event_detected', 'life_event_type', 'ptp_signal', 'ptp_date', 'ptp_amount', 'negotiation_signal', 'hostile_signal']} />
                        <div style={{ marginTop: 15, padding: 10, background: '#F1F5F9', color: '#334155', borderRadius: 6, fontSize: 13, border: '1px solid #CBD5E1' }}>
                          <strong>Call Outcome / Agent Guidance:</strong> {transcriptAnalysis?.agent_guidance || 'No guidance generated'}
                        </div>
                      </CardBody></Card>
                    </div>
                    <div>
                      <h3>E. Updates</h3>
                      <Card><CardHeader title="Post-Call Pipeline Updates" subtitle="Scores, Persona, Trust Gate" /><CardBody>
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
