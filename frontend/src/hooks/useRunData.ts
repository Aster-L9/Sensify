'use client';

import { useCallback, useEffect, useState } from 'react';
import { getAnomalies, getRun, getRunEvents, getTelemetry, getTrust } from '@/lib/api';
import type { AnomalySeries, RunEvent, RunOut, TelemetryPoint, TrustSeries } from '@/lib/types';
import { usePolling } from './usePolling';

export interface RunData {
  run: RunOut | null;
  telemetry: TelemetryPoint[];
  anomalies: AnomalySeries | null;
  trust: TrustSeries | null;
  events: RunEvent[];
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
}

/** Everything a run view needs, refreshed every 2 s while the run is still playing. */
export function useRunData(runId: number | null): RunData {
  const [run, setRun] = useState<RunOut | null>(null);
  const [telemetry, setTelemetry] = useState<TelemetryPoint[]>([]);
  const [anomalies, setAnomalies] = useState<AnomalySeries | null>(null);
  const [trust, setTrust] = useState<TrustSeries | null>(null);
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (runId === null) return;
    try {
      const [r, tel, an, tr, ev] = await Promise.all([
        getRun(runId), getTelemetry(runId, { limit: 5000 }), getAnomalies(runId), getTrust(runId), getRunEvents(runId),
      ]);
      setRun(r);
      setTelemetry(tel);
      setAnomalies(an);
      setTrust(tr);
      setEvents(ev);
      setError(null);
    } catch (e: any) {
      setError(e.message || 'Could not load this run');
    } finally {
      setLoading(false);
    }
  }, [runId]);

  useEffect(() => {
    setLoading(true);
    setRun(null);
    void refresh();
  }, [refresh]);

  usePolling(refresh, 2000, run?.status === 'active');

  return { run, telemetry, anomalies, trust, events, loading, error, refresh };
}

/** Per-segment arrays from the flat telemetry list. */
export function seriesFor(telemetry: TelemetryPoint[], segmentId: number) {
  const rows = telemetry.filter((t) => t.segment_id === segmentId);
  return {
    ticks: rows.map((r) => r.tick),
    pressure: rows.map((r) => r.pressure_bar),
    flow: rows.map((r) => r.flow_m3h),
    temperature: rows.map((r) => r.temperature_c),
  };
}
