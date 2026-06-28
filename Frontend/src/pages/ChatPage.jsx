import React, { useState, useRef, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api';
import { useBackendHealth } from '../hooks/useBackendHealth';
import {
  AppNav, StatusPill, Badge, IntentBadge,
  Spinner, Alert, fmtMs, truncate,
} from '../components/Primitives';
import AuditTrail from '../components/AuditTrail';
import RagQualityGate from '../components/RagQualityGate';

const SUGGESTED = [
  { label: 'KYC & Onboarding',     text: 'What are the KYC requirements for opening a new savings account?' },
  { label: 'Dormant Accounts',      text: 'What is the bank policy on dormant and inoperative accounts?' },
  { label: 'Account Closure',       text: 'Explain the account closure process and required notice period.' },
  { label: 'UPI & NEFT Limits',     text: 'What are the daily transaction limits for UPI and NEFT transfers?' },
  { label: 'Payments Policy',       text: 'What is the policy on failed payment reversals and timelines?' },
  { label: 'Nominee Registration',  text: 'How can a customer register or update a nominee on their account?' },
];

const MAX_Q = 2000;
const MIN_Q = 5;

function UserBubble({ text }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 16 }}>
      <div style={{
        background: 'var(--navy)',
        color: 'white',
        borderRadius: '12px 12px 3px 12px',
        padding: '10px 15px',
        maxWidth: '70%',
        fontSize: 13,
        lineHeight: 1.65,
        wordBreak: 'break-word',
        boxShadow: 'var(--shadow-sm)',
      }}>
        {text}
      </div>
    </div>
  );
}

function AiBubble({ msg, loading }) {
  const [trailOpen, setTrailOpen] = useState(false);
  const trail = msg?.auditTrail || [];
  const hasTrail = trail.length > 0;
  const isLoan = msg?.intent === 'LOAN_ELIGIBILITY';

  return (
    <div style={{ display: 'flex', gap: 10, marginBottom: 16, animation: 'fadeIn 0.2s ease-out' }}>
      {/* Avatar */}
      <div style={{
        width: 28, height: 28, borderRadius: 6, flexShrink: 0, marginTop: 2,
        background: 'var(--corporate-blue)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 10, fontWeight: 700, color: 'white',
      }}>PA</div>

      <div style={{ flex: 1, minWidth: 0 }}>
        {/* Label row */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
          <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--text)' }}>Policy Assistant</span>
          {msg?.intent && <IntentBadge intent={msg.intent} />}
          <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', background: 'var(--surface-inset)', border: '1px solid var(--border)', borderRadius: 3, padding: '1px 5px' }}>AI-generated</span>
        </div>

        {!loading && <RagQualityGate evaluation={msg?.ragEvaluation} citations={msg?.citations} />}

        {/* Bubble */}
        <div style={{
          background: 'var(--surface)',
          border: '1px solid var(--border)',
          borderRadius: '3px 12px 12px 12px',
          padding: '12px 16px',
          fontSize: 13, lineHeight: 1.7,
          color: 'var(--text)',
          wordBreak: 'break-word',
          whiteSpace: 'pre-wrap',
          boxShadow: 'var(--shadow-sm)',
        }}>
          {loading ? (
            <span style={{ display: 'flex', gap: 6, alignItems: 'center', color: 'var(--text-muted)' }}>
              <Spinner size={13} /> Processing query…
            </span>
          ) : msg?.text}
        </div>

        {/* Loan redirect notice */}
        {!loading && isLoan && (
          <div style={{
            marginTop: 10,
            background: 'var(--warning-bg)',
            border: '1px solid #F5D5B3',
            borderRadius: 6,
            padding: '10px 14px',
            fontSize: 12,
            color: 'var(--text)',
            lineHeight: 1.6,
          }}>
            <span style={{ fontWeight: 600, color: 'var(--warning)' }}>For a complete assessment</span> — use the dedicated{' '}
            <Link
              to="/loan-assessment"
              style={{ color: 'var(--corporate-blue)', fontWeight: 600, textDecoration: 'underline' }}
            >
              Loan Eligibility Assessment
            </Link>{' '}
            page, which collects your full profile and returns a structured indicative assessment.
          </div>
        )}

        {/* Audit trail */}
        {!loading && hasTrail && (
          <div style={{ marginTop: 8 }}>
            <button
              onClick={() => setTrailOpen(v => !v)}
              aria-expanded={trailOpen}
              style={{
                fontSize: 11, fontFamily: 'var(--font-mono)',
                color: 'var(--text-muted)',
                border: '1px solid var(--border)',
                background: 'var(--surface)',
                borderRadius: 4, padding: '3px 10px',
                cursor: 'pointer',
              }}
            >
              {trailOpen ? '▲' : '▼'} Execution trail ({trail.length} steps)
            </button>

            {trailOpen && (
              <div style={{
                marginTop: 6,
                background: '#0F1E35',
                border: '1px solid rgba(255,255,255,0.08)',
                borderRadius: 8,
                padding: '12px 14px',
                animation: 'fadeIn 0.2s ease-out',
              }}>
                <AuditTrail
                  trail={trail}
                  sessionId={msg.sessionId}
                  intent={msg.intent}
                  stepCount={trail.length}
                />
              </div>
            )}
          </div>
        )}

        {/* Session ID */}
        {!loading && msg?.sessionId && (
          <div style={{ marginTop: 5, fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--text-muted)' }}>
            session {msg.sessionId.slice(0, 12)}…
          </div>
        )}
      </div>
    </div>
  );
}

function ErrorBubble({ text }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <Alert type="error">{text}</Alert>
    </div>
  );
}

export default function ChatPage() {
  const backendStatus = useBackendHealth();
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const [validErr, setValidErr] = useState('');
  const bottomRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  function validate(q) {
    if (q.length < MIN_Q) return `Query must be at least ${MIN_Q} characters.`;
    if (q.length > MAX_Q) return `Query must not exceed ${MAX_Q} characters.`;
    return '';
  }

  async function send(queryText) {
    const q = (queryText ?? input).trim();
    const err = validate(q);
    if (err) { setValidErr(err); return; }
    setValidErr('');
    setMessages(prev => [...prev, { type: 'user', text: q }]);
    setInput('');
    setLoading(true);

    if (backendStatus === 'offline') {
      setMessages(prev => [...prev, { type: 'error', text: 'Backend unreachable. Start the FastAPI server at localhost:8000 and try again.' }]);
      setLoading(false);
      return;
    }

    try {
      const data = await api.chat(q, sessionId);
      if (data.session_id) setSessionId(data.session_id);
      setMessages(prev => [...prev, {
        type: 'ai', text: data.final,
        auditTrail: data.audit_trail || [],
        sessionId: data.session_id,
        intent: data.intent,
        ragEvaluation: data.rag_evaluation,
        citations: data.citations,
      }]);
    } catch (e) {
      setMessages(prev => [...prev, { type: 'error', text: `Request failed: ${e.message}` }]);
    } finally {
      setLoading(false);
    }
  }

  function onKey(e) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
  }

  const isEmpty = messages.length === 0;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', minHeight: '100vh', background: 'var(--bg)' }}>
      <AppNav active="/chat" />

      {/* Offline bar */}
      {backendStatus === 'offline' && (
        <div style={{
          background: 'var(--error-bg)', borderBottom: '1px solid #F5C4C2',
          padding: '8px 20px', fontSize: 12, color: 'var(--error)',
          fontFamily: 'var(--font-mono)',
        }}>
          Backend unreachable — start the FastAPI server at localhost:8000
        </div>
      )}

      {/* Chat area */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '24px 0' }}>
        <div style={{ maxWidth: 760, margin: '0 auto', padding: '0 20px' }}>

          {isEmpty && (
            <div style={{ paddingTop: 48, paddingBottom: 32 }}>
              {/* Page intro */}
              <div style={{
                background: 'var(--surface)', border: '1px solid var(--border)',
                borderRadius: 8, padding: '20px 24px', marginBottom: 28,
                boxShadow: 'var(--shadow-sm)',
              }}>
                <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--text)', marginBottom: 6 }}>
                  Bank Policy Assistant
                </div>
                <div style={{ fontSize: 13, color: 'var(--text-muted)', lineHeight: 1.65, marginBottom: 14 }}>
                  Ask questions about bank policies, account management, and regulatory guidelines.
                  Responses are AI-generated — verify against official circulars before acting.
                </div>
                <div style={{ fontSize: 12, color: 'var(--text-muted)', display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  <span>Topics covered:</span>
                  {['KYC & Onboarding', 'Dormant accounts', 'Account closure', 'Payments & UPI', 'Nominee management'].map(t => (
                    <span key={t} style={{
                      background: 'var(--surface-inset)', border: '1px solid var(--border)',
                      borderRadius: 4, padding: '1px 8px', fontSize: 11,
                    }}>{t}</span>
                  ))}
                </div>
              </div>

              {/* Suggested prompts */}
              <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 10 }}>
                Suggested queries
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                {SUGGESTED.map(p => (
                  <button
                    key={p.label}
                    onClick={() => send(p.text)}
                    disabled={loading}
                    style={{
                      background: 'var(--surface)',
                      border: '1px solid var(--border)',
                      borderRadius: 6,
                      padding: '10px 14px',
                      cursor: loading ? 'not-allowed' : 'pointer',
                      textAlign: 'left',
                      transition: 'border-color 0.15s, box-shadow 0.15s',
                    }}
                    onMouseEnter={e => {
                      if (!loading) {
                        e.currentTarget.style.borderColor = 'var(--corporate-blue)';
                        e.currentTarget.style.boxShadow = '0 0 0 3px rgba(23,92,211,0.08)';
                      }
                    }}
                    onMouseLeave={e => {
                      e.currentTarget.style.borderColor = 'var(--border)';
                      e.currentTarget.style.boxShadow = 'none';
                    }}
                  >
                    <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--corporate-blue)', marginBottom: 3 }}>{p.label}</div>
                    <div style={{ fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.4 }}>{p.text}</div>
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((m, i) => {
            if (m.type === 'user')  return <UserBubble key={i} text={m.text} />;
            if (m.type === 'ai')    return <AiBubble key={i} msg={m} />;
            if (m.type === 'error') return <ErrorBubble key={i} text={m.text} />;
            return null;
          })}

          {loading && <AiBubble loading />}
          <div ref={bottomRef} />
        </div>
      </div>

      {/* Input area */}
      <div style={{
        background: 'var(--surface)',
        borderTop: '1px solid var(--border)',
        padding: '14px 20px',
        boxShadow: '0 -2px 8px rgba(16,24,40,0.04)',
      }}>
        <div style={{ maxWidth: 760, margin: '0 auto' }}>
          {validErr && (
            <div style={{ fontSize: 11, color: 'var(--error)', fontFamily: 'var(--font-mono)', marginBottom: 6 }}>
              {validErr}
            </div>
          )}
          <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end' }}>
            <textarea
              ref={inputRef}
              value={input}
              onChange={e => { setInput(e.target.value); if (validErr) setValidErr(''); }}
              onKeyDown={onKey}
              disabled={loading}
              rows={1}
              placeholder="Ask about policies, account rules, or procedures…"
              maxLength={MAX_Q}
              aria-label="Policy query"
              style={{
                flex: 1,
                background: 'var(--bg)',
                border: '1px solid var(--border)',
                borderRadius: 6,
                color: 'var(--text)',
                fontSize: 13,
                padding: '8px 12px',
                resize: 'none',
                outline: 'none',
                lineHeight: 1.55,
                minHeight: 40,
                maxHeight: 120,
                overflow: 'auto',
                fontFamily: 'var(--font)',
                transition: 'border-color 0.15s',
              }}
              onFocus={e => { e.target.style.borderColor = 'var(--corporate-blue)'; e.target.style.boxShadow = '0 0 0 3px rgba(23,92,211,0.10)'; }}
              onBlur={e => { e.target.style.borderColor = 'var(--border)'; e.target.style.boxShadow = 'none'; }}
            />
            <button
              onClick={() => send()}
              disabled={loading || !input.trim()}
              style={{
                background: (loading || !input.trim()) ? 'var(--border)' : 'var(--corporate-blue)',
                color: (loading || !input.trim()) ? 'var(--text-muted)' : 'white',
                border: 'none',
                borderRadius: 6,
                padding: '8px 18px',
                fontWeight: 600,
                fontSize: 13,
                cursor: (loading || !input.trim()) ? 'not-allowed' : 'pointer',
                display: 'flex', alignItems: 'center', gap: 6,
                height: 40, whiteSpace: 'nowrap',
                transition: 'background 0.15s',
              }}
            >
              {loading ? <Spinner size={13} /> : 'Send'}
            </button>
          </div>

          <div style={{
            display: 'flex', justifyContent: 'space-between',
            marginTop: 6, fontSize: 10,
            fontFamily: 'var(--font-mono)', color: 'var(--text-muted)',
          }}>
            <span>Shift+Enter for new line · Enter to send</span>
            <span style={{ color: input.length > MAX_Q * 0.9 ? 'var(--warning)' : 'var(--text-muted)' }}>
              {input.length}/{MAX_Q}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
