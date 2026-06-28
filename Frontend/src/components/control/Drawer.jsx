import React, { useEffect } from 'react';

export default function Drawer({ title, subtitle, onClose, children }) {
  useEffect(() => {
    const close = (event) => { if (event.key === 'Escape') onClose(); };
    window.addEventListener('keydown', close);
    return () => window.removeEventListener('keydown', close);
  }, [onClose]);
  return (
    <>
      <button className="cc-drawer-overlay" aria-label="Close details" onClick={onClose} />
      <aside className="cc-drawer" role="dialog" aria-modal="true">
        <div className="cc-drawer-header"><div><h2>{title}</h2><p>{subtitle}</p></div><button onClick={onClose} className="cc-icon-button">×</button></div>
        <div className="cc-drawer-body">{children}</div>
      </aside>
    </>
  );
}
