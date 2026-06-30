import React, { useCallback, useMemo, useState } from 'react';
import PageHeader from '../../components/control/PageHeader';
import { Chip } from '../../components/control/Chips';
import { JsonBlock, SectionCard, asArray, display, fmtTime } from '../../components/control/Common';
import { controlPlaneApi } from '../../services/controlPlaneApi';

const DEFAULT_PAYLOAD = {
  mode: 'post_call',
  account_id: 'ACC-DEMO-01',
  transcript: "Customer: I lost my job and cannot pay this month's EMI.",
};

const MODES = ['post_call', 'pre_call', 'full_lifecycle'];

function TruthTag({ label, tone }) {
  // Reuses the existing Chip component's color map purely for visual tone —
  // no new CSS is introduced. tone must be a key Chip already recognizes.
  return <Chip value={tone} label={label} />;
}

function isPolicyBlockedShape(response) {
  return !!response && typeof response === 'object' && !('result' in response) && 'decision' in response;
}

export default function RunConsole() {
  const [mode, setMode] = useState(DEFAULT_PAYLOAD.mode);
  const [accountId, setAccountId] = useState(DEFAULT_PAYLOAD.account_id);
  const [transcript, setTranscript] = useState(DEFAULT_PAYLOAD.transcript);

  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState(null);
  const [response, setResponse] = useState(null);

  const [events, setEvents] = useState(null);
  const [eventsError, setEventsError] = useState(null);
  const [eventsLoading, setEventsLoading] = useState(false);

  const [policyRows, setPolicyRows] = useState(null);
  const [policyError, setPolicyError] = useState(null);
  const [policyLoading, setPolicyLoading] = useState(false);

  const traceId = response?.trace_id || null;
  const blocked = isPolicyBlockedShape(response);
  const result = !blocked ? response?.result : null;

  const fetchRelated = useCallback(async (id) => {
    if (!id) {
      setEvents(null);
      setEventsError('No trace_id was returned — related events cannot be fetched.');
      setPolicyRows(null);
      setPolicyError('No trace_id was returned — related policy decisions cannot be fetched.');
      return;
    }

    setEventsLoading(true);
    setEventsError(null);
    try {
      const eventsResponse = await controlPlaneApi.getTraceEvents(id);
      const list = asArray(eventsResponse, 'events');
      setEvents(list);
      if (list.length === 0) setEventsError('No events found for this trace.');
    } catch (err) {
      setEvents(null);
      setEventsError(err.message || 'Unable to load trace events.');
    } finally {
      setEventsLoading(false);
    }

    setPolicyLoading(true);
    setPolicyError(null);
    try {
      const policyResponse = await controlPlaneApi.listPolicyDecisions();
      const all = asArray(policyResponse, 'decisions');
      const filtered = all.filter((row) => row.trace_id === id);
      setPolicyRows(filtered);
      if (filtered.length === 0) setPolicyError('No policy decisions found for this trace.');
    } catch (err) {
      setPolicyRows(null);
      setPolicyError(err.message || 'Unable to load policy decisions.');
    } finally {
      setPolicyLoading(false);
    }
  }, []);

  const handleRun = useCallback(async () => {
    setRunning(true);
    setRunError(null);
    setResponse(null);
    setEvents(null);
    setEventsError(null);
    setPolicyRows(null);
    setPolicyError(null);

    const payload = { mode, account_id: accountId };
    if (mode === 'post_call' || mode === 'full_lifecycle') payload.transcript = transcript;

    try {
      const result = await controlPlaneApi.runCollections(payload);
      setResponse(result);
      await fetchRelated(result?.trace_id || null);
    } catch (err) {
      setRunError(err.message || 'Run failed.');
    } finally {
      setRunning(false);
    }
  }, [mode, accountId, transcript, fetchRelated]);

  const hardshipReviewRow = useMemo(
    () => (policyRows || []).find((row) => String(row.decision || '').toUpperCase() === 'REVIEW'),
    [policyRows],
  );

  return (
    <>
      <PageHeader
        title="Run Console"
        subtitle="Run Console executes the Collections workflow and then fetches trace-linked evidence from the control plane."
      />

      <SectionCard title="A. Request">
        <p className="cc-small cc-muted">
          Agent: <strong>Collections Workflow Agent</strong> — Vendored external Collections plugin — invoked through harness manifest/adapter boundary.
        </p>
        <div className="cc-form-grid" style={{ marginTop: 12 }}>
          <label>
            Mode
            <select className="cc-input" value={mode} onChange={(e) => setMode(e.target.value)}>
              {MODES.map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
          </label>
          <label>
            Account ID
            <input className="cc-input" value={accountId} onChange={(e) => setAccountId(e.target.value)} />
          </label>
        </div>
        {(mode === 'post_call' || mode === 'full_lifecycle') && (
          <label style={{ display: 'flex', flexDirection: 'column', gap: 5, marginTop: 12, fontSize: 11, fontWeight: 600 }}>
            Transcript
            <textarea
              className="cc-input"
              style={{ minHeight: 70, width: '100%' }}
              value={transcript}
              onChange={(e) => setTranscript(e.target.value)}
            />
          </label>
        )}
        <div style={{ marginTop: 14 }}>
          <button className="cc-button" onClick={handleRun} disabled={running}>
            {running ? 'Running…' : 'Run'}
          </button>
        </div>
        {runError && <div className="cc-empty cc-error" style={{ marginTop: 10 }}>Run error: {runError}</div>}
      </SectionCard>

      <SectionCard title="B. Workflow Response" right={<TruthTag tone="completed" label="RUNTIME" />}>
        {!response && !runError && <div className="cc-empty">No run yet. Click Run to execute the Collections workflow.</div>}
        {response && <JsonBlock value={response} />}
      </SectionCard>

      <SectionCard title="C. Harness Evidence">
        {!response && <div className="cc-empty">No run yet.</div>}
        {response && (
          <div className="cc-table-scroll">
            <table className="cc-table">
              <tbody>
                <tr><td>trace_id</td><td className="mono">{display(response.trace_id, 'Not emitted')}</td></tr>
                <tr><td>agent_id</td><td className="mono">{display(response.agent_id, 'Not emitted')}</td></tr>
                {blocked ? (
                  <>
                    <tr><td>decision</td><td><Chip value={response.decision} /></td></tr>
                    <tr><td>reason</td><td>{display(response.reason, 'Not emitted')}</td></tr>
                    <tr><td>status</td><td>{display(response.status, 'Not emitted')}</td></tr>
                    <tr><td>adapter_invoked</td><td>{String(response.adapter_invoked ?? 'Not emitted')}</td></tr>
                    <tr><td>policy_decision</td><td>{response.policy_decision ? <JsonBlock value={response.policy_decision} /> : 'Not emitted'}</td></tr>
                  </>
                ) : (
                  <>
                    <tr><td>workflow_status</td><td>{display(result?.workflow_status, 'Not emitted')}</td></tr>
                    <tr><td>status</td><td>{display(result?.status, 'Not emitted')}</td></tr>
                    <tr><td>control_evidence</td><td>{result?.control_evidence ? <JsonBlock value={result.control_evidence} /> : 'Not emitted'}</td></tr>
                  </>
                )}
              </tbody>
            </table>
          </div>
        )}
      </SectionCard>

      <SectionCard title="D. Related Audit Events" right={<TruthTag tone="completed" label="RUNTIME" />}>
        {eventsLoading && <div className="cc-empty">Loading events for this trace…</div>}
        {!eventsLoading && eventsError && <div className="cc-empty">{eventsError}</div>}
        {!eventsLoading && events && events.length > 0 && (
          <div className="cc-table-scroll">
            <table className="cc-table">
              <thead><tr><th>Timestamp</th><th>Event Type</th><th>Agent ID</th><th>Trace ID</th><th>Payload</th></tr></thead>
              <tbody>
                {events.map((item, index) => (
                  <tr key={item.id || index}>
                    <td>{fmtTime(item.timestamp)}</td>
                    <td>{display(item.event_type)}</td>
                    <td className="mono">{display(item.agent_id)}</td>
                    <td className="mono">{display(item.trace_id)}</td>
                    <td><JsonBlock value={item.payload ?? item} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {!eventsLoading && !eventsError && (!events || events.length === 0) && <div className="cc-empty">No events found for this trace.</div>}
      </SectionCard>

      <SectionCard title="E. Related Policy Decisions" right={<TruthTag tone="completed" label="RUNTIME" />}>
        {policyLoading && <div className="cc-empty">Loading policy decisions for this trace…</div>}
        {!policyLoading && policyRows && policyRows.length > 0 && (
          <div className="cc-table-scroll">
            <table className="cc-table">
              <thead><tr><th>Timestamp</th><th>Agent ID</th><th>Action</th><th>Decision</th><th>Reason</th></tr></thead>
              <tbody>
                {policyRows.map((row, index) => (
                  <tr key={row.id || index}>
                    <td>{fmtTime(row.timestamp)}</td>
                    <td className="mono">{display(row.agent_id)}</td>
                    <td>{display(row.action)}</td>
                    <td><Chip value={row.decision} /></td>
                    <td>{display(row.reason)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {!policyLoading && (!policyRows || policyRows.length === 0) && (
          <div className="cc-empty">{policyError || 'No policy decisions found for this trace.'}</div>
        )}
        {!policyLoading && policyRows && policyRows.length > 0 && !hardshipReviewRow && (
          <p className="cc-small cc-muted" style={{ marginTop: 10 }}>
            No harness-level hardship REVIEW policy emitted yet. Collections domain may create a review case, but this has not yet been mapped into policy_decisions.
          </p>
        )}
      </SectionCard>

      <SectionCard title="F. Data Truth Panel">
        <div className="cc-table-scroll">
          <table className="cc-table">
            <tbody>
              <tr><td>Workflow response (Section B)</td><td><TruthTag tone="completed" label="RUNTIME" /></td></tr>
              <tr><td>Trace events (Section D)</td><td><TruthTag tone="completed" label="RUNTIME" /></td></tr>
              <tr><td>Policy decisions (Section E)</td><td><TruthTag tone="completed" label="RUNTIME" /></td></tr>
              <tr><td>Missing fields shown as "Not emitted"</td><td><TruthTag tone="review" label="NOT_EMITTED" /></td></tr>
              <tr><td>Section labels, agent description, hardship-review note</td><td><TruthTag tone="event_driven" label="STATIC_EXPLANATION" /></td></tr>
            </tbody>
          </table>
        </div>
      </SectionCard>
    </>
  );
}
