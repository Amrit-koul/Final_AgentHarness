import { useCallback, useEffect, useState } from 'react';

export function useControlData(fetcher, deps = [], pollMs = 0) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [version, setVersion] = useState(0);
  const reload = useCallback(() => setVersion((value) => value + 1), []);

  useEffect(() => {
    let cancelled = false;
    const load = (showLoading = false) => {
      if (showLoading) setLoading(true);
      return fetcher()
        .then((result) => { if (!cancelled) { setData(result); setError(null); } })
        .catch((reason) => { if (!cancelled) setError(reason); })
        .finally(() => { if (!cancelled && showLoading) setLoading(false); });
    };
    setError(null);
    load(true);
    const timer = pollMs > 0 ? setInterval(() => load(false), pollMs) : null;
    return () => { cancelled = true; if (timer) clearInterval(timer); };
  }, [...deps, version, pollMs]); // eslint-disable-line react-hooks/exhaustive-deps

  return { data, loading, error, reload };
}
