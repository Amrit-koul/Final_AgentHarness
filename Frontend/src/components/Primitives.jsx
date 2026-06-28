import React from 'react';
import { NavLink } from 'react-router-dom';

// ── Format helpers ────────────────────────────────────────────────
export function fmtMs(ms) {
  if (ms == null) return '—';
  return ms > 999 ? `${(ms / 1000).toFixed(2)}s` : `${Math.round(ms)}ms`;
}

export function fmtTs(ts) {
  if (!ts) return '—';
  try {
    const d = new Date(ts);
    return d.toLocaleTimeString('en-IN', { hour12: false });
  } catch { return ts; }
}

export function fmtDate(ts) {
  if (!ts) return '—';
  try {
    const d = new Date(ts);
    return d.toLocaleString('en-IN', { hour12: false, dateStyle: 'medium', timeStyle: 'short' });
  } catch { return ts; }
}

export function truncate(str, n) {
  if (!str) return '—';
  return str.length > n ? str.slice(0, n) + '…' : str;
}

export function latencyColor(ms) {
  if (ms == null) return 'var(--text-muted)';
  if (ms < 500)  return 'var(--success)';
  if (ms < 1200) return 'var(--warning)';
  return 'var(--error)';
}

export function formatINR(n) {
  if (n == null || n === '') return '—';
  return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(n);
}

// ── Status pill ───────────────────────────────────────────────────
export function StatusPill({ status }) {
  const map = {
    online:   { color: 'var(--success)', bg: 'var(--success-bg)', label: 'API Online' },
    offline:  { color: 'var(--error)',   bg: 'var(--error-bg)',   label: 'API Offline' },
    checking: { color: 'var(--warning)', bg: 'var(--warning-bg)', label: 'Connecting' },
  };
  const c = map[status] || map.checking;
  return (
    <span style={{
      fontSize: 11, fontFamily: 'var(--font-mono)',
      color: c.color, background: c.bg,
      border: `1px solid ${c.color}40`,
      borderRadius: 20, padding: '2px 10px',
      display: 'inline-flex', alignItems: 'center', gap: 5, whiteSpace: 'nowrap',
    }}>
      <span style={{
        width: 6, height: 6, borderRadius: '50%', background: c.color, flexShrink: 0,
        animation: status === 'online' ? 'pulse 2s infinite' : 'none',
      }} />
      {c.label}
    </span>
  );
}

// ── Badge ─────────────────────────────────────────────────────────
export function Badge({ children, variant = 'neutral', color, bg }) {
  const variants = {
    neutral: { color: 'var(--text-muted)',   bg: '#F0F2F5' },
    blue:    { color: 'var(--corporate-blue)', bg: '#EBF2FF' },
    green:   { color: 'var(--success)',      bg: 'var(--success-bg)' },
    amber:   { color: 'var(--warning)',      bg: 'var(--warning-bg)' },
    red:     { color: 'var(--error)',        bg: 'var(--error-bg)' },
    teal:    { color: 'var(--info)',         bg: 'var(--info-bg)' },
  };
  const c = variants[variant] || variants.neutral;
  return (
    <span style={{
      fontSize: 11, fontFamily: 'var(--font-mono)',
      color: color || c.color,
      background: bg || c.bg,
      border: `1px solid ${(color || c.color)}30`,
      borderRadius: var_radius_sm,
      padding: '1px 6px',
      whiteSpace: 'nowrap',
      display: 'inline-block',
    }}>
      {children}
    </span>
  );
}
const var_radius_sm = '4px';

// ── Intent badge ──────────────────────────────────────────────────
export function IntentBadge({ intent }) {
  if (intent === 'LOAN_ELIGIBILITY') return <Badge variant="amber">{intent}</Badge>;
  if (intent === 'POLICY')           return <Badge variant="teal">{intent}</Badge>;
  return <Badge variant="neutral">{intent || 'UNKNOWN'}</Badge>;
}

// ── Card / Panel ──────────────────────────────────────────────────
export function Card({ children, style }) {
  return (
    <div style={{
      background: 'var(--surface)',
      border: '1px solid var(--border)',
      borderRadius: 'var(--radius-lg)',
      boxShadow: 'var(--shadow-sm)',
      ...style,
    }}>
      {children}
    </div>
  );
}

export function CardHeader({ title, subtitle, right, border = true }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      padding: '14px 20px',
      borderBottom: border ? '1px solid var(--border)' : 'none',
      gap: 12,
    }}>
      <div>
        <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)' }}>{title}</div>
        {subtitle && <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>{subtitle}</div>}
      </div>
      {right && <div style={{ flexShrink: 0 }}>{right}</div>}
    </div>
  );
}

export function CardBody({ children, style }) {
  return (
    <div style={{ padding: '16px 20px', ...style }}>
      {children}
    </div>
  );
}

// Harness-variant panel (dark)
export function HarnessPanel({ children, style }) {
  return (
    <div style={{
      background: 'var(--harness-panel)',
      border: '1px solid var(--harness-border)',
      borderRadius: 'var(--radius-lg)',
      ...style,
    }}>
      {children}
    </div>
  );
}

export function HarnessPanelHeader({ title, subtitle, right }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      padding: '12px 18px',
      borderBottom: '1px solid var(--harness-border)',
      gap: 12,
    }}>
      <div>
        <div style={{ fontSize: 12, fontWeight: 600, color: '#E2EBF7', fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{title}</div>
        {subtitle && <div style={{ fontSize: 11, color: '#667A96', marginTop: 2 }}>{subtitle}</div>}
      </div>
      {right && <div style={{ flexShrink: 0 }}>{right}</div>}
    </div>
  );
}

// ── Divider ───────────────────────────────────────────────────────
export function Divider({ style }) {
  return <div style={{ height: 1, background: 'var(--border)', ...style }} />;
}

// ── Empty state ───────────────────────────────────────────────────
export function EmptyState({ children, dark }) {
  return (
    <div style={{
      textAlign: 'center', padding: '24px 16px',
      fontSize: 12, color: dark ? '#4A6080' : 'var(--text-muted)',
      fontFamily: 'var(--font-mono)',
    }}>
      {children}
    </div>
  );
}

// ── Spinner ───────────────────────────────────────────────────────
export function Spinner({ size = 16, dark }) {
  return (
    <span style={{
      display: 'inline-block', width: size, height: size,
      border: `2px solid ${dark ? 'rgba(255,255,255,0.1)' : 'var(--border)'}`,
      borderTopColor: dark ? '#4A9EE8' : 'var(--corporate-blue)',
      borderRadius: '50%',
      animation: 'spin 0.7s linear infinite',
      flexShrink: 0,
    }} />
  );
}

// ── Toggle ────────────────────────────────────────────────────────
export function Toggle({ checked, onChange, disabled, id }) {
  return (
    <label
      htmlFor={id}
      style={{ position: 'relative', width: 40, height: 22, flexShrink: 0, display: 'inline-block', cursor: disabled ? 'not-allowed' : 'pointer' }}
    >
      <input
        id={id}
        type="checkbox"
        checked={checked}
        onChange={onChange}
        disabled={disabled}
        style={{ opacity: 0, width: 0, height: 0, position: 'absolute' }}
      />
      <span style={{
        position: 'absolute', inset: 0,
        background: checked ? 'var(--success)' : '#94A3B8',
        borderRadius: 11,
        opacity: disabled ? 0.45 : 1,
        transition: 'background 0.2s',
      }}>
        <span style={{
          position: 'absolute',
          width: 16, height: 16, left: 3, top: 3,
          background: 'white',
          borderRadius: '50%',
          boxShadow: '0 1px 3px rgba(0,0,0,0.2)',
          transition: 'transform 0.2s',
          transform: checked ? 'translateX(18px)' : 'translateX(0)',
        }} />
      </span>
    </label>
  );
}

// ── App shell nav ─────────────────────────────────────────────────
export function AppNav({ active }) {
  const navLinks = [
    { to: '/chat',           label: 'Policy Assistant' },
    { to: '/loan-assessment', label: 'Loan Assessment' },
    { to: '/collections',     label: 'Collections Agent' },
    { to: '/control/tower',   label: 'Control Panel', internal: true },
  ];

  return (
    <nav style={{
      background: 'var(--navy)',
      borderBottom: '1px solid rgba(255,255,255,0.08)',
      height: 52,
      display: 'flex',
      alignItems: 'stretch',
      padding: '0 20px',
      position: 'sticky',
      top: 0,
      zIndex: 200,
      gap: 0,
    }}>
      {/* Brand */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 10,
        paddingRight: 24, marginRight: 8,
        borderRight: '1px solid rgba(255,255,255,0.1)',
      }}>
        <div style={{
          width: 28, height: 28,
          background: 'var(--corporate-blue)',
          borderRadius: 4,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 11, fontWeight: 700, color: 'white', letterSpacing: '-0.02em',
        }}>BB</div>
        <div>
          <div style={{ fontSize: 12, fontWeight: 700, color: 'white', letterSpacing: '0.01em' }}>Bandhan Bank</div>
          <div style={{ fontSize: 9, color: 'rgba(255,255,255,0.4)', fontFamily: 'var(--font-mono)', letterSpacing: '0.06em', textTransform: 'uppercase' }}>Agentic AI Platform</div>
        </div>
      </div>

      {/* Links */}
      <div style={{ display: 'flex', alignItems: 'stretch', flex: 1 }}>
        {navLinks.map(link => {
          const isActive = active === link.to;
          return (
            <NavLink
              key={link.to}
              to={link.to}
              style={{
                display: 'flex', alignItems: 'center', gap: 6,
                padding: '0 16px',
                fontSize: 12, fontWeight: isActive ? 600 : 400,
                color: isActive ? 'white' : 'rgba(255,255,255,0.5)',
                borderBottom: isActive ? '2px solid var(--secondary-blue)' : '2px solid transparent',
                textDecoration: 'none',
                transition: 'color 0.15s, border-color 0.15s',
                whiteSpace: 'nowrap',
              }}
              onMouseEnter={e => { if (!isActive) e.currentTarget.style.color = 'rgba(255,255,255,0.8)'; }}
              onMouseLeave={e => { if (!isActive) e.currentTarget.style.color = 'rgba(255,255,255,0.5)'; }}
            >
              {link.internal && (
                <span style={{
                  fontSize: 9, fontFamily: 'var(--font-mono)',
                  color: '#4A9EE8', background: 'rgba(74,158,232,0.12)',
                  border: '1px solid rgba(74,158,232,0.25)',
                  borderRadius: 3, padding: '0 4px',
                  textTransform: 'uppercase', letterSpacing: '0.05em',
                }}>INT</span>
              )}
              {link.label}
            </NavLink>
          );
        })}
      </div>
    </nav>
  );
}

// ── Form field wrapper ────────────────────────────────────────────
export function FieldGroup({ label, htmlFor, required, hint, error, children }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      <label
        htmlFor={htmlFor}
        style={{
          fontSize: 12, fontWeight: 500, color: 'var(--text)',
          display: 'flex', gap: 4, alignItems: 'center',
        }}
      >
        {label}
        {required && <span style={{ color: 'var(--error)', fontSize: 12 }}>*</span>}
      </label>
      {children}
      {hint && !error && (
        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{hint}</span>
      )}
      {error && (
        <span style={{ fontSize: 11, color: 'var(--error)', display: 'flex', gap: 4, alignItems: 'center' }}>
          {error}
        </span>
      )}
    </div>
  );
}

const inputBase = {
  width: '100%',
  background: 'var(--surface)',
  border: '1px solid var(--border)',
  borderRadius: 'var(--radius)',
  padding: '7px 10px',
  fontSize: 13,
  color: 'var(--text)',
  outline: 'none',
  transition: 'border-color 0.15s, box-shadow 0.15s',
};

export function Input({ hasError, style, ...props }) {
  return (
    <input
      {...props}
      style={{
        ...inputBase,
        borderColor: hasError ? 'var(--error)' : 'var(--border)',
        ...style,
      }}
      onFocus={e => {
        e.target.style.borderColor = hasError ? 'var(--error)' : 'var(--corporate-blue)';
        e.target.style.boxShadow = hasError
          ? '0 0 0 3px rgba(180,35,24,0.10)'
          : '0 0 0 3px rgba(23,92,211,0.10)';
      }}
      onBlur={e => {
        e.target.style.borderColor = hasError ? 'var(--error)' : 'var(--border)';
        e.target.style.boxShadow = 'none';
      }}
    />
  );
}

export function Select({ hasError, style, children, ...props }) {
  return (
    <select
      {...props}
      style={{
        ...inputBase,
        appearance: 'none',
        backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath fill='%23667085' d='M6 8L1 3h10z'/%3E%3C/svg%3E")`,
        backgroundRepeat: 'no-repeat',
        backgroundPosition: 'right 10px center',
        paddingRight: 30,
        cursor: 'pointer',
        borderColor: hasError ? 'var(--error)' : 'var(--border)',
        ...style,
      }}
      onFocus={e => {
        e.target.style.borderColor = hasError ? 'var(--error)' : 'var(--corporate-blue)';
        e.target.style.boxShadow = '0 0 0 3px rgba(23,92,211,0.10)';
      }}
      onBlur={e => {
        e.target.style.borderColor = hasError ? 'var(--error)' : 'var(--border)';
        e.target.style.boxShadow = 'none';
      }}
    >
      {children}
    </select>
  );
}

export function Textarea({ hasError, style, ...props }) {
  return (
    <textarea
      {...props}
      style={{
        ...inputBase,
        resize: 'vertical',
        minHeight: 72,
        lineHeight: 1.6,
        borderColor: hasError ? 'var(--error)' : 'var(--border)',
        ...style,
      }}
      onFocus={e => {
        e.target.style.borderColor = hasError ? 'var(--error)' : 'var(--corporate-blue)';
        e.target.style.boxShadow = '0 0 0 3px rgba(23,92,211,0.10)';
      }}
      onBlur={e => {
        e.target.style.borderColor = hasError ? 'var(--error)' : 'var(--border)';
        e.target.style.boxShadow = 'none';
      }}
    />
  );
}

// ── Buttons ───────────────────────────────────────────────────────
export function Btn({ variant = 'primary', size = 'md', disabled, loading, children, style, ...props }) {
  const sizes = {
    sm: { padding: '5px 12px', fontSize: 12 },
    md: { padding: '8px 16px', fontSize: 13 },
    lg: { padding: '10px 20px', fontSize: 14 },
  };
  const variants = {
    primary: {
      background: disabled ? '#B0BBC8' : 'var(--corporate-blue)',
      color: 'white',
      border: 'none',
    },
    secondary: {
      background: 'white',
      color: 'var(--text)',
      border: '1px solid var(--border)',
    },
    ghost: {
      background: 'transparent',
      color: 'var(--text-muted)',
      border: '1px solid var(--border)',
    },
    danger: {
      background: disabled ? '#F4BFBC' : 'var(--error)',
      color: 'white',
      border: 'none',
    },
  };
  const v = variants[variant];
  const s = sizes[size];
  return (
    <button
      {...props}
      disabled={disabled || loading}
      style={{
        ...s, ...v,
        borderRadius: 'var(--radius)',
        fontWeight: 500,
        cursor: (disabled || loading) ? 'not-allowed' : 'pointer',
        display: 'inline-flex', alignItems: 'center', gap: 6,
        transition: 'background 0.15s, opacity 0.15s',
        opacity: (disabled && !loading) ? 0.6 : 1,
        whiteSpace: 'nowrap',
        ...style,
      }}
    >
      {loading && <Spinner size={13} />}
      {children}
    </button>
  );
}

// ── Alert banner ──────────────────────────────────────────────────
export function Alert({ type = 'info', children }) {
  const map = {
    info:    { bg: 'var(--info-bg)',    border: 'var(--info)',    color: 'var(--info)' },
    success: { bg: 'var(--success-bg)', border: 'var(--success)', color: 'var(--success)' },
    warning: { bg: 'var(--warning-bg)', border: 'var(--warning)', color: 'var(--warning)' },
    error:   { bg: 'var(--error-bg)',   border: 'var(--error)',   color: 'var(--error)' },
  };
  const c = map[type];
  return (
    <div style={{
      background: c.bg, borderLeft: `3px solid ${c.border}`,
      borderRadius: 'var(--radius)', padding: '10px 14px',
      fontSize: 12, color: c.color, lineHeight: 1.5,
    }}>
      {children}
    </div>
  );
}

// ── Toast ─────────────────────────────────────────────────────────
export function Toast({ message, type = 'success', onDone }) {
  const map = {
    success: { color: 'var(--success)', border: '#ABE0C5' },
    error:   { color: 'var(--error)',   border: '#F5C4C2' },
    info:    { color: 'var(--info)',    border: '#B3DEE2' },
    warning: { color: 'var(--warning)', border: '#F5D5B3' },
  };
  const c = map[type] || map.info;

  React.useEffect(() => {
    const id = setTimeout(onDone, 3500);
    return () => clearTimeout(id);
  }, [onDone]);

  return (
    <div style={{
      position: 'fixed', top: 64, right: 20, zIndex: 9999,
      background: 'white',
      border: `1px solid ${c.border}`,
      borderLeft: `3px solid ${c.color}`,
      borderRadius: 'var(--radius)',
      padding: '10px 16px',
      fontSize: 12, color: 'var(--text)', lineHeight: 1.5,
      maxWidth: 380, boxShadow: 'var(--shadow-md)',
      animation: 'fadeIn 0.25s ease-out',
    }}>
      {message}
    </div>
  );
}

// ── Section divider with label ────────────────────────────────────
export function SectionLabel({ children }) {
  return (
    <div style={{
      fontSize: 11, fontWeight: 600, color: 'var(--text-muted)',
      textTransform: 'uppercase', letterSpacing: '0.07em',
      display: 'flex', alignItems: 'center', gap: 10,
      marginBottom: 12,
    }}>
      <span style={{ flex: 1, height: 1, background: 'var(--border)' }} />
      {children}
      <span style={{ flex: 1, height: 1, background: 'var(--border)' }} />
    </div>
  );
}

// ── Panel & PanelHeader (legacy compat) ───────────────────────────
export function Panel({ children, style }) {
  return (
    <div style={{
      background: 'var(--harness-panel)',
      border: '1px solid var(--harness-border)',
      borderRadius: 'var(--radius-lg)',
      ...style,
    }}>
      {children}
    </div>
  );
}

export function PanelHeader({ title, right }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      padding: '12px 18px', borderBottom: '1px solid var(--harness-border)',
    }}>
      <span style={{
        fontFamily: 'var(--font-mono)', fontSize: 11, fontWeight: 600,
        color: '#E2EBF7', textTransform: 'uppercase', letterSpacing: '0.05em',
      }}>{title}</span>
      {right && <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: '#4A6080' }}>{right}</span>}
    </div>
  );
}
