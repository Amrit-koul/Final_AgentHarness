import React from 'react';

export const display = (value, fallback = '—') => value == null || value === '' ? fallback : String(value);
export const fmtTime = (value) => value ? new Date(value).toLocaleString('en-IN') : '—';
export const asArray = (payload, key) => Array.isArray(payload) ? payload : payload?.[key] || [];

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
