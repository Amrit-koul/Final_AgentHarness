import React from 'react';

export function KpiStrip({ items }) {
  return (
    <div className="cc-kpi-grid">
      {items.map((item) => (
        <div key={item.label} className="cc-kpi-card" style={{ '--accent': `var(--${item.accent || 'corporate-blue'})` }}>
          <div className="cc-kpi-label">{item.label}</div>
          <div className="cc-kpi-value">{item.value}</div>
          {item.sublabel && <div className="cc-muted cc-small">{item.sublabel}</div>}
        </div>
      ))}
    </div>
  );
}
