import { useState, useRef, useCallback } from 'react';

const API = '';  // empty = same origin (proxied by Vite in dev)
const CACHE_KEY = 'flood_analysis_cache';

function getCacheKey(district, eventDate, baselineDate) {
  return `${district}::${eventDate}::${baselineDate}`;
}

function getCache(district, eventDate, baselineDate) {
  try {
    const cache = JSON.parse(localStorage.getItem(CACHE_KEY) || '{}');
    return cache[getCacheKey(district, eventDate, baselineDate)] || null;
  } catch {
    return null;
  }
}

function setCache(district, eventDate, baselineDate, data) {
  try {
    const cache = JSON.parse(localStorage.getItem(CACHE_KEY) || '{}');
    cache[getCacheKey(district, eventDate, baselineDate)] = data;
    localStorage.setItem(CACHE_KEY, JSON.stringify(cache));
  } catch (e) {
    console.warn('Failed to cache results:', e);
  }
}

export function useFloodAnalysis() {
  const [statusMsg, setStatusMsg] = useState('Ready. Select a district and run analysis.');
  const [statusType, setStatusType] = useState('');
  const [results, setResults] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const pollRef = useRef(null);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const runAnalysis = useCallback(async ({ district, eventDate, baselineDate }) => {
    stopPolling();
    setIsLoading(true);
    setResults(null);
    setStatusType('');

    // Check cache first
    const cached = getCache(district, eventDate, baselineDate);
    if (cached) {
      setResults(cached);
      setStatusMsg(
        `✓ ${cached.event_date} vs ${cached.baseline_date} · ${cached.subdivisions.length} subdivisions analysed (cached)`,
      );
      setStatusType('success');
      setIsLoading(false);
      return;
    }

    setStatusMsg('Submitting job…');

    try {
      const res = await fetch(`${API}/flood-detection`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          district,
          event_date: eventDate,
          baseline_date: baselineDate,
        }),
      });
      const job = await res.json();
      if (!res.ok) throw new Error(job.detail || 'Request failed');

      setStatusMsg('Fetching SAR imagery from GEE…');
      let dots = 0;

      pollRef.current = setInterval(async () => {
        dots = (dots + 1) % 4;
        try {
          const pollRes = await fetch(`${API}/jobs/${job.job_id}`);
          const data = await pollRes.json();

          if (data.status === 'running') {
            setStatusMsg('Running flood detection' + '.'.repeat(dots + 1));
          } else if (data.status === 'completed') {
            stopPolling();
            setIsLoading(false);
            setStatusMsg(
              `✓ ${data.event_date} vs ${data.baseline_date} · ${data.subdivisions.length} subdivisions analysed`,
            );
            setStatusType('success');
            setCache(district, eventDate, baselineDate, data);
            setResults(data);
          } else if (data.status === 'failed') {
            stopPolling();
            setIsLoading(false);
            setStatusMsg(`Failed: ${data.error}`);
            setStatusType('error');
          }
        } catch (e) {
          stopPolling();
          setIsLoading(false);
          setStatusMsg(`Polling error: ${e.message}`);
          setStatusType('error');
        }
      }, 3000);
    } catch (e) {
      setStatusMsg(`Error: ${e.message}`);
      setStatusType('error');
      setIsLoading(false);
    }
  }, [stopPolling]);

  return { statusMsg, statusType, results, isLoading, runAnalysis };
}
