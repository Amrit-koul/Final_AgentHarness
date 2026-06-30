import React from 'react';

export function SourceBadge({ source }) {
  const map = {
    'runtime': { label: 'Runtime', className: 'cc-badge success' },
    'admin_validation': { label: 'Admin Validation', className: 'cc-badge warning' },
    'manual_validation': { label: 'Manual Validation', className: 'cc-badge warning' },
    'manual_admin': { label: 'Manual Validation', className: 'cc-badge warning' },
    'config': { label: 'Config', className: 'cc-badge neutral' },
    'derived': { label: 'Calculated', className: 'cc-badge neutral' },
    'estimated': { label: 'Estimated', className: 'cc-badge neutral' },
    'persisted': { label: 'Current DB History', className: 'cc-badge info' },
    'seeded_portfolio': { label: 'Seeded Portfolio Data', className: 'cc-badge neutral' },
    'keyword_fallback': { label: 'Keyword Fallback', className: 'cc-badge warning' },
    'llm_extraction': { label: 'LLM Extraction', className: 'cc-badge success' },
    'not_returned': { label: 'Not Returned', className: 'cc-badge error' }
  };
  const normalizedSource = source || 'not_returned';
  const display = map[normalizedSource] || { label: String(source), className: 'cc-badge neutral' };
  
  return <span className={display.className}>{display.label}</span>;
}

export function EnforcementBadge({ status }) {
  const map = {
    'runtime_enforced': { label: 'Runtime Enforced', className: 'cc-badge success' },
    'available_not_wired': { label: 'Available, Not Wired', className: 'cc-badge warning' },
    'config_only': { label: 'Config Only', className: 'cc-badge neutral' },
    'not_returned': { label: 'Not Returned', className: 'cc-badge error' }
  };
  const normalizedStatus = status || 'not_returned';
  const display = map[normalizedStatus] || { label: String(status), className: 'cc-badge neutral' };
  
  return <span className={display.className}>{display.label}</span>;
}

export function LLMJudgeBadge({ status }) {
  if (!status) return <span className="cc-badge error">No Judge Evidence Returned</span>;

  const map = {
    'success': { label: 'Ran', className: 'cc-badge success' },
    'not_configured': { label: 'Not Configured', className: 'cc-badge neutral' },
    'not_run': { label: 'Not Run', className: 'cc-badge neutral' },
    'timeout': { label: 'Timeout', className: 'cc-badge error' },
    'error': { label: 'Error', className: 'cc-badge error' },
    'invalid_response': { label: 'Invalid Response', className: 'cc-badge warning' }
  };
  
  const display = map[status] || { label: String(status), className: 'cc-badge neutral' };
  return <span className={display.className}>{display.label}</span>;
}

export function renderMissingField(field) {
  if (field === null || field === undefined || field === '') {
    return <span className="cc-muted">Not returned</span>;
  }
  return field;
}
