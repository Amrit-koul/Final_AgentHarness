import React from 'react';

export default function PageHeader({ title, subtitle, right }) {
  return (
    <div className="cc-page-header">
      <div>
        <h1>{title}</h1>
        {subtitle && <p>{subtitle}</p>}
      </div>
      {right}
    </div>
  );
}
