import React from 'react';

const colors = {
  active: 'green', healthy: 'green', low: 'green', ALLOW: 'green', completed: 'green',
  review: 'amber', degraded: 'amber', medium: 'amber', REVIEW: 'amber', running: 'blue',
  disabled: 'grey', quarantined: 'red', critical: 'red', high: 'red', BLOCK: 'red', failed: 'red',
  workflow: 'blue', decoupled: 'purple', event_driven: 'teal', 'event-driven': 'teal',
};

export function Chip({ value, label }) {
  const normalized = value == null ? '' : String(value);
  const tone = colors[normalized] || colors[normalized.toLowerCase()] || 'grey';
  return <span className={`cc-chip cc-chip-${tone}`}><span className="cc-chip-dot" />{label || normalized || '—'}</span>;
}

export const StatusChip = ({ status }) => <Chip value={status} />;
export const HealthChip = ({ health }) => <Chip value={health} />;
export const RiskChip = ({ level }) => <Chip value={level} />;
export const ExecModeChip = ({ mode }) => <Chip value={mode} />;
export const DecisionChip = ({ decision }) => <Chip value={decision} />;
export const SeverityChip = ({ severity }) => <Chip value={severity} />;
