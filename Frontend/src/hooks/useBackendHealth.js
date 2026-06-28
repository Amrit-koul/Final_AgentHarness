import { useState, useEffect } from 'react';
import { api } from '../api';

export function useBackendHealth(intervalMs = 15000) {
  const [status, setStatus] = useState('checking'); // 'online' | 'offline' | 'checking'

  useEffect(() => {
    let cancelled = false;

    async function check() {
      try {
        await api.health();
        if (!cancelled) setStatus('online');
      } catch {
        if (!cancelled) setStatus('offline');
      }
    }

    check();
    const id = setInterval(check, intervalMs);
    return () => { cancelled = true; clearInterval(id); };
  }, [intervalMs]);

  return status;
}
