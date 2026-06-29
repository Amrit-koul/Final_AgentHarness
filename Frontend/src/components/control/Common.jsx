import React from 'react';

export const display = (value, fallback = '—') => value == null || value === '' ? fallback : String(value);
export const asArray = (payload, key) => Array.isArray(payload) ? payload : payload?.[key] || [];

/**
 * parseControlTimestamp — safely converts backend timestamps to a JS Date.
 *
 * SQLite DEFAULT CURRENT_TIMESTAMP stores values like "2026-06-29 03:26:00"
 * which are UTC but have NO timezone suffix. V8/Chrome parses bare
 * "YYYY-MM-DD HH:MM:SS" strings as LOCAL time, while Firefox parses them as
 * UTC — so the same string shows different hours in different browsers.
 *
 * Fix: if the value has no timezone indicator (no Z, no +, no explicit UTC
 * offset), append " UTC" so every browser treats it as UTC before converting
 * to local display time. ISO strings that already carry timezone info
 * (e.g. "2026-06-29T08:56:00+05:30" or "2026-06-29T03:26:00Z") are passed
 * through unchanged.
 */
export function parseControlTimestamp(value) {
  if (!value) return null;
  const s = String(value).trim();
  // Already has timezone info — parse as-is
  if (/Z$/i.test(s) || /[+-]\d{2}:\d{2}$/.test(s) || /[+-]\d{4}$/.test(s)) {
    return new Date(s);
  }
  // Naive string (SQLite CURRENT_TIMESTAMP format or ISO without tz) — treat as UTC
  return new Date(s.replace(' ', 'T') + 'Z');
}

/**
 * formatLocalDateTime — format a timestamp in the browser's local timezone.
 * Always call parseControlTimestamp first so UTC naive strings are handled.
 */
export function formatLocalDateTime(value) {
  const dt = parseControlTimestamp(value);
  if (!dt || isNaN(dt.getTime())) return '—';
  return dt.toLocaleString(undefined, {
    year: 'numeric', month: 'short', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
    hour12: true,
  });
}

/** Drop-in replacement for the old fmtTime — uses local timezone correctly. */
export const fmtTime = (value) => formatLocalDateTime(value);

export function LoadingState({ error, loading, empty, children }) {
  if (loading) return <div className="cc-empty">Loading control-plane data…</div>;
  if (error) return <div className="cc-empty cc-error">Unable to load data: {error.message}</div>;
  if (empty) return <div className="cc-empty">{children || 'No records returned by the backend.'}</div>;
  return null;
}

export function SectionCard({ title, subtitle, right, children, className = '' }) {
  return (
    <section className={`cc-section-card ${className}`}>
      <div className="cc-section-heading">
        <div><h2>{title}</h2>{subtitle && <p>{subtitle}</p>}</div>
        {right}
      </div>
      {children}
    </section>
  );
}

export function JsonBlock({ value }) {
  if (value == null) return <span className="cc-muted">Not configured</span>;
  return <pre className="cc-json">{JSON.stringify(value, null, 2)}</pre>;
}

export function ActionButton({ children, danger, loading, ...props }) {
  return <button className={`cc-button${danger ? ' danger' : ''}`} disabled={loading || props.disabled} {...props}>{loading ? 'Working…' : children}</button>;
}