'use client';

import React, { Suspense, useCallback, useEffect, useMemo, useState } from 'react';
import dynamic from 'next/dynamic';
import { useRouter, useSearchParams } from 'next/navigation';
import { AlertCircle, Eye, MapPin } from 'lucide-react';
import { getAlerts, getRunState, getRuns, getTopology } from '@/lib/api';
import type { AlertItem, RunEvent, RunOut, RunState, Segment, SegmentStateName } from '@/lib/types';
import { STATE_STYLE, formatDateTime } from '@/lib/detection';
import { useRunData } from '@/hooks/useRunData';
import { usePolling } from '@/hooks/usePolling';
import { LoadingState, ErrorState, EmptyState } from '@/components/ui/States';
import { SegmentDetail } from '@/components/SegmentDetail';
import { RunPlayback } from '@/components/detection/RunPlayback';
import { StateLegend } from '@/components/detection/StateLegend';
import { EventDrawer } from '@/components/detection/EventDrawer';

// Leaflet touches `window`, so the map pieces load on the client only.
const MapContainer = dynamic(() => import('react-leaflet').then((m) => m.MapContainer), { ssr: false });
const TileLayer = dynamic(() => import('react-leaflet').then((m) => m.TileLayer), { ssr: false });
const Polyline = dynamic(() => import('react-leaflet').then((m) => m.Polyline), { ssr: false });
const CircleMarker = dynamic(() => import('react-leaflet').then((m) => m.CircleMarker), { ssr: false });
const Tooltip = dynamic(() => import('react-leaflet').then((m) => m.Tooltip), { ssr: false });

export default function MapPage() {
  return (
    <Suspense fallback={<LoadingState message="Loading the pipeline map..." />}>
      <MapView />
    </Suspense>
  );
}

function runLabel(r: RunOut): string {
  return r.status === 'active'
    ? `${r.name}, playing (${Math.round(r.progress * 100)} %)`
    : `${r.name}, ${formatDateTime(r.started_at)}`;
}

function MapView() {
  const router = useRouter();
  const search = useSearchParams();
  const [segments, setSegments] = useState<Segment[]>([]);
  const [runs, setRuns] = useState<RunOut[]>([]);
  // Hand-edited URLs: anything that is not a number falls back to the defaults.
  const wholeNumber = (v: string | null) => (v !== null && /^\d+$/.test(v) ? Number(v) : null);
  const requestedRun = wholeNumber(search.get('run'));
  // The run loads only once the run list has confirmed it exists.
  const [runId, setRunId] = useState<number | null>(null);
  const [missingRun, setMissingRun] = useState<number | null>(null);
  const [seg, setSeg] = useState<string | null>(search.get('seg'));
  const urlTick = wholeNumber(search.get('t'));
  const [live, setLive] = useState(urlTick === null);
  const [cursor, setCursor] = useState(urlTick ?? 0);
  const [state, setState] = useState<RunState | null>(null);
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [selectedEvent, setSelectedEvent] = useState<RunEvent | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([getTopology(), getRuns()])
      .then(([topo, list]) => {
        setSegments(topo.segments);
        setRuns(list);
        if (seg && !topo.segments.some((s) => s.code === seg)) setSeg(null);
        if (requestedRun !== null && list.some((r) => r.id === requestedRun)) {
          setRunId(requestedRun);
        } else if (list.length) {
          const fallback = (list.find((r) => r.status === 'active') ?? list[0]).id;
          setRunId(fallback);
          if (requestedRun !== null) {
            // The requested run does not exist: say so and show the default run, live.
            setMissingRun(requestedRun);
            setLive(true);
            router.replace(`/map?run=${fallback}`, { scroll: false });
          }
        }
      })
      .catch((e) => setErr(e.message || 'Could not load the pipeline'));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Keep the run list's progress labels current and pick up runs launched meanwhile.
  const refreshRuns = useCallback(() => getRuns().then(setRuns).catch(() => undefined), []);
  usePolling(refreshRuns, 5000, runs.some((r) => r.status === 'active'));

  const { run, telemetry, anomalies, trust, events } = useRunData(runId);
  const latest = run ? run.revealed_ticks - 1 : 0;
  const tick = live ? latest : Math.max(0, Math.min(cursor, latest));

  useEffect(() => {
    if (!run) return;
    const id = window.setTimeout(() => getRunState(run.id, tick).then(setState).catch(() => undefined), 120);
    return () => window.clearTimeout(id);
  }, [run, tick]);

  useEffect(() => {
    if (run) getAlerts({ runId: run.id, limit: 500 }).then(setAlerts).catch(() => undefined);
  }, [run?.id, run?.revealed_ticks]); // eslint-disable-line react-hooks/exhaustive-deps

  const states = useMemo(() => {
    const out: Record<string, SegmentStateName> = {};
    if (!anomalies || !trust) return out;
    anomalies.segments.forEach((s, i) => {
      const status = trust.segments[i]?.status[tick];
      out[s.code] = status && status !== 'Supported' ? 'low_trust' : s.flags[tick] ? 'anomalous' : 'normal';
    });
    return out;
  }, [anomalies, trust, tick]);

  const writeUrl = useCallback((next: { run?: number | null; t?: number | null; seg?: string | null }) => {
    const q = new URLSearchParams();
    const r = next.run !== undefined ? next.run : runId;
    const t = next.t !== undefined ? next.t : (live ? null : tick);
    const s = next.seg !== undefined ? next.seg : seg;
    if (r !== null) q.set('run', String(r));
    if (t !== null) q.set('t', String(t));
    if (s) q.set('seg', s);
    router.replace(`/map?${q}`, { scroll: false });
  }, [router, runId, live, tick, seg]);

  const pickTick = useCallback((t: number) => { setLive(false); setCursor(t); writeUrl({ t }); }, [writeUrl]);
  const goLive = useCallback(() => { setLive(true); writeUrl({ t: null }); }, [writeUrl]);
  const pickSegment = (code: string | null) => { setSeg(code); writeUrl({ seg: code }); };
  const pickRun = (id: number) => { setRunId(id); setLive(true); setState(null); writeUrl({ run: id, t: null }); };

  if (err) return <ErrorState message={err} />;
  if (!segments.length) return <LoadingState message="Loading the pipeline map..." />;
  if (!runs.length) return <EmptyState title="No runs yet" message="Launch a scenario to see the pipeline come alive here." />;

  const selected = segments.find((s) => s.code === seg) ?? null;
  const selectedIndex = selected ? segments.indexOf(selected) : -1;
  const bounds: [[number, number], [number, number]] = [
    [Math.min(...segments.map((s) => Math.min(s.lat_start, s.lat_end))), Math.min(...segments.map((s) => Math.min(s.lon_start, s.lon_end)))],
    [Math.max(...segments.map((s) => Math.max(s.lat_start, s.lat_end))), Math.max(...segments.map((s) => Math.max(s.lon_start, s.lon_end)))],
  ];
  const counts = Object.values(states).reduce<Record<string, number>>((acc, s) => ({ ...acc, [s]: (acc[s] ?? 0) + 1 }), {});

  return (
    <div className="space-y-6">
      <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <MapPin className="w-6 h-6 text-brand-500" aria-hidden /> Pipeline map
          </h1>
          <p className="text-sm text-gray-500 mt-1">The Dhahran to Jubail line, coloured by what each segment is doing at the chosen moment of a run.</p>
        </div>
        <label className="flex flex-col gap-1 text-sm text-gray-600 w-full lg:w-96">
          Run
          <select value={runId ?? ''} onChange={(e) => pickRun(Number(e.target.value))} className="input-field py-2 text-sm">
            {runs.map((r) => <option key={r.id} value={r.id}>{runLabel(r)}</option>)}
          </select>
        </label>
      </div>

      {missingRun !== null && (
        <p className="flex items-center gap-2 rounded-lg bg-amber-50 px-4 py-2.5 text-sm text-amber-900" role="status">
          <AlertCircle className="w-4 h-4 shrink-0" aria-hidden />
          Run {missingRun} was not found, so the map shows {run ? run.name : 'the latest run'} instead.
        </p>
      )}

      {run && (
        <div className="glass-card p-4 space-y-3">
          <RunPlayback status={run.status} revealedTicks={run.revealed_ticks} durationTicks={run.duration_ticks}
            playbackSpeed={run.playback_speed} tick={tick} live={live} onTick={pickTick} onLive={goLive} />
          <StateLegend counts={counts} />
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6 items-start">
        <div className={`${selected ? 'lg:col-span-3' : 'lg:col-span-5'} glass-card overflow-hidden h-[460px] lg:h-[620px]`}>
          <MapContainer bounds={bounds} boundsOptions={{ padding: [40, 40] }} style={{ width: '100%', height: '100%' }} scrollWheelZoom>
            <TileLayer
              attribution='&copy; <a href="https://www.esri.com">Esri</a>'
              url="https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}"
            />
            {segments.map((s) => {
              const st = STATE_STYLE[states[s.code] ?? 'normal'];
              const isSel = s.code === seg;
              return (
                <React.Fragment key={s.code}>
                  {isSel && (
                    <Polyline positions={[[s.lat_start, s.lon_start], [s.lat_end, s.lon_end]]}
                      pathOptions={{ color: '#232838', weight: st.weight + 8, opacity: 0.18 }} />
                  )}
                  <Polyline
                    positions={[[s.lat_start, s.lon_start], [s.lat_end, s.lon_end]]}
                    pathOptions={{ color: st.color, weight: st.weight + 1, opacity: 0.95, dashArray: st.dash, lineCap: st.dash ? 'butt' : 'round' }}
                    eventHandlers={{ click: () => pickSegment(s.code) }}
                  >
                    <Tooltip sticky>{s.code} {s.name}: {st.label.toLowerCase()}</Tooltip>
                  </Polyline>
                </React.Fragment>
              );
            })}
            {segments.map((s, i) => (
              <CircleMarker key={`node-${s.code}`} center={[s.lat_start, s.lon_start]} radius={i === 0 ? 7 : 5}
                pathOptions={{ color: '#6B7280', weight: 2, fillColor: '#fff', fillOpacity: 1 }} />
            ))}
            {/* Short segments are hard to see at this zoom, so abnormal ones also get a marker at their midpoint. */}
            {segments.filter((s) => (states[s.code] ?? 'normal') !== 'normal').map((s) => {
              const st = STATE_STYLE[states[s.code]];
              return (
                <CircleMarker key={`state-${s.code}-${states[s.code]}`} center={[(s.lat_start + s.lat_end) / 2, (s.lon_start + s.lon_end) / 2]}
                  radius={12} pathOptions={{ color: st.color, weight: 3, dashArray: st.dash ? '4 3' : undefined, fillColor: st.color, fillOpacity: 0.18 }}
                  eventHandlers={{ click: () => pickSegment(s.code) }}>
                  <Tooltip direction="top" offset={[0, -10]}>{s.code} {s.name}: {st.label.toLowerCase()}</Tooltip>
                </CircleMarker>
              );
            })}
            {segments.length > 0 && (
              <CircleMarker center={[segments[segments.length - 1].lat_end, segments[segments.length - 1].lon_end]} radius={7}
                pathOptions={{ color: '#6B7280', weight: 2, fillColor: '#fff', fillOpacity: 1 }} />
            )}
          </MapContainer>
        </div>

        {selected && run && (
          <div className="lg:col-span-2">
            <SegmentDetail
              runId={run.id} segment={selected} state={state?.segments.find((s) => s.code === selected.code) ?? null}
              tick={tick} durationTicks={run.duration_ticks} telemetry={telemetry}
              scores={anomalies?.segments[selectedIndex]?.scores ?? []} threshold={anomalies?.threshold ?? 0.5}
              alerts={alerts} events={events} onPickTick={pickTick} onSelectEvent={setSelectedEvent}
              onClose={() => pickSegment(null)}
            />
          </div>
        )}
      </div>

      <section className="glass-card overflow-x-auto" aria-label="Pipeline segments">
        <table className="data-table">
          <thead>
            <tr>
              <th>Segment</th>
              <th>Type</th>
              <th>Length</th>
              <th>Diameter</th>
              <th>Design pressure</th>
              <th>Now</th>
              <th><span className="sr-only">Inspect</span></th>
            </tr>
          </thead>
          <tbody>
            {segments.map((s) => {
              const st = STATE_STYLE[states[s.code] ?? 'normal'];
              const Icon = st.icon;
              const reading = state?.segments.find((x) => x.code === s.code);
              return (
                <tr key={s.code} className={s.code === seg ? 'bg-brand-50/50' : ''}>
                  <td><span className="font-semibold text-gray-900">{s.code}</span> <span className="text-gray-600">{s.name}</span></td>
                  <td className="text-gray-600">{s.segment_type.replace('_', ' ')}</td>
                  <td className="tabular">{s.length_km} km</td>
                  <td className="tabular">{s.diameter_mm} mm</td>
                  <td className="tabular">{s.design_pressure_bar} bar</td>
                  <td>
                    <span className="inline-flex items-center gap-1.5 text-sm font-medium" style={{ color: st.textColor }}>
                      <Icon className="w-4 h-4" aria-hidden /> {st.label}
                    </span>
                    {reading?.pressure_bar !== null && reading?.pressure_bar !== undefined && (
                      <span className="block font-mono tabular text-xs text-gray-500">{reading.pressure_bar.toFixed(1)} bar, {reading.flow_m3h?.toFixed(0)} m³/h</span>
                    )}
                  </td>
                  <td>
                    <button onClick={() => pickSegment(s.code)} className="btn-ghost py-1 px-2.5 text-sm flex items-center gap-1">
                      <Eye className="w-4 h-4" aria-hidden /> Inspect
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </section>

      <EventDrawer event={selectedEvent} onClose={() => setSelectedEvent(null)} />
    </div>
  );
}
