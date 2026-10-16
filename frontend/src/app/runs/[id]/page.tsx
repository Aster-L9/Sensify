'use client';

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { ArrowLeft, CheckCircle2, Eye, EyeOff, RefreshCw, XCircle } from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import { useToast } from '@/components/ui/Toast';
import { ErrorState, LoadingState } from '@/components/ui/States';
import { useRunData, seriesFor } from '@/hooks/useRunData';
import {
  getAlerts, getBaselineAlarms, getConsistency, getGroundTruth, getRunState, getTopology, rescoreRun,
} from '@/lib/api';
import type {
  AlertItem, BaselineAlarms, ConsistencySeries, GroundTruth, RunEvent, RunState, Segment, SegmentStateName,
} from '@/lib/types';
import {
  CHECK_LABELS, SCENARIO_LABELS, STATE_STYLE, formatDateTime, formatTick,
} from '@/lib/detection';
import { PipelineSchematic } from '@/components/detection/PipelineSchematic';
import { RunPlayback } from '@/components/detection/RunPlayback';
import { StateLegend } from '@/components/detection/StateLegend';
import { AnomalyBandChart, type AlarmWindow, type FlagWindow } from '@/components/detection/AnomalyBandChart';
import { EventStrip } from '@/components/detection/EventStrip';
import { EventDrawer } from '@/components/detection/EventDrawer';
import { TrustIndicator } from '@/components/detection/TrustIndicator';
import { KindIcons, SeverityChip } from '@/components/detection/SeverityChip';

const SYNC_ID = 'run-detail';

export default function RunDetailPage() {
  const params = useParams();
  const runId = Number(params.id);
  const router = useRouter();
  const search = useSearchParams();
  const { isAdmin } = useAuth();
  const { success, error: toastError } = useToast();
  const { run, telemetry, anomalies, trust, events, loading, error, refresh } = useRunData(runId);

  const [segments, setSegments] = useState<Segment[]>([]);
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [consistency, setConsistency] = useState<ConsistencySeries | null>(null);
  const [state, setState] = useState<RunState | null>(null);
  const [showAlarms, setShowAlarms] = useState(false);
  const [alarms, setAlarms] = useState<BaselineAlarms | null>(null);
  const [showTruth, setShowTruth] = useState(false);
  const [truth, setTruth] = useState<GroundTruth | null>(null);
  const [selectedEvent, setSelectedEvent] = useState<RunEvent | null>(null);
  const [rescoring, setRescoring] = useState(false);

  // A hand-edited ?t= that is not a tick number falls back to the live view.
  const rawTick = search.get('t');
  const urlTick = rawTick !== null && /^\d+$/.test(rawTick) ? Number(rawTick) : null;
  const [live, setLive] = useState(urlTick === null);
  const [cursor, setCursor] = useState(urlTick ?? 0);
  const [seg, setSeg] = useState<string | null>(search.get('seg'));

  const latest = run ? run.revealed_ticks - 1 : 0;
  const tick = live ? latest : Math.max(0, Math.min(cursor, latest));
  const revealed = run?.revealed_ticks ?? 0;

  useEffect(() => {
    getTopology().then((t) => setSegments(t.segments)).catch(() => undefined);
  }, []);

  // Alerts and consistency follow the run as it is revealed.
  useEffect(() => {
    if (!run) return;
    getAlerts({ runId, limit: 500 }).then(setAlerts).catch(() => undefined);
    getConsistency(runId).then(setConsistency).catch(() => undefined);
  }, [runId, revealed, run?.model_version]);

  useEffect(() => {
    if (!run) return;
    const id = window.setTimeout(() => {
      getRunState(runId, tick).then(setState).catch(() => undefined);
    }, 120);
    return () => window.clearTimeout(id);
  }, [runId, tick, run?.model_version, revealed]);

  useEffect(() => {
    if (showAlarms) getBaselineAlarms(runId).then(setAlarms).catch(() => undefined);
  }, [showAlarms, runId, revealed]);

  useEffect(() => {
    if (isAdmin && showTruth) getGroundTruth(runId).then(setTruth).catch(() => undefined);
  }, [isAdmin, showTruth, runId, revealed]);

  // Per-tick state of every segment at the cursor.
  const states = useMemo(() => {
    const out: Record<string, SegmentStateName> = {};
    if (!anomalies || !trust) return out;
    anomalies.segments.forEach((s, i) => {
      const status = trust.segments[i]?.status[tick];
      out[s.code] = status && status !== 'Supported' ? 'low_trust' : s.flags[tick] ? 'anomalous' : 'normal';
    });
    return out;
  }, [anomalies, trust, tick]);

  // Forget a ?seg= that names no segment, so the default selection below takes over.
  useEffect(() => {
    if (seg && segments.length && !segments.some((s) => s.code === seg)) setSeg(null);
  }, [seg, segments]);

  // Default selection: the most serious segment right now.
  useEffect(() => {
    if (seg || !segments.length || !anomalies) return;
    const rank = (c: string) => (states[c] === 'low_trust' ? 2 : states[c] === 'anomalous' ? 1 : 0);
    const best = [...segments].sort((a, b) => rank(b.code) - rank(a.code))[0];
    setSeg(best.code);
  }, [seg, segments, anomalies, states]);

  const setUrl = useCallback((t: number | null, code: string | null) => {
    const q = new URLSearchParams();
    if (t !== null) q.set('t', String(t));
    if (code) q.set('seg', code);
    router.replace(`/runs/${runId}${q.toString() ? `?${q}` : ''}`, { scroll: false });
  }, [router, runId]);

  const pickTick = useCallback((t: number) => {
    setLive(false);
    setCursor(t);
    setUrl(t, seg);
  }, [seg, setUrl]);

  const goLive = useCallback(() => {
    setLive(true);
    setUrl(null, seg);
  }, [seg, setUrl]);

  const pickSegment = (code: string) => {
    setSeg(code);
    setUrl(live ? null : tick, code);
  };

  const handleRescore = async () => {
    setRescoring(true);
    try {
      const r = await rescoreRun(runId);
      success('Run re-scored', `Analysed again with model v${r.model_version}.`);
      await refresh();
    } catch (e: any) {
      toastError('Could not re-score', e.message);
    } finally {
      setRescoring(false);
    }
  };

  if (loading && !run) return <LoadingState message="Loading run..." />;
  if (error && !run) return <ErrorState message={error} onRetry={refresh} />;
  if (!run) return null;

  const segIndex = Math.max(segments.findIndex((s) => s.code === seg), 0);
  const segment = segments[segIndex];
  const series = segment ? seriesFor(telemetry, segment.id) : { ticks: [], pressure: [], flow: [], temperature: [] };
  const scores = anomalies?.segments[segIndex]?.scores ?? [];
  const segAlerts = alerts.filter((a) => a.segment_id === segment?.id);
  const windows: FlagWindow[] = segAlerts.map((a) => ({
    start: a.start_tick, end: a.end_tick, kind: a.kinds.includes('low_trust') ? 'low_trust' : 'anomaly',
  }));
  const alarmsFor = (variable: 'pressure' | 'flow'): AlarmWindow[] =>
    showAlarms && alarms ? alarms.windows
      .filter((w) => w.segment_id === segment?.id && w.variable === variable)
      .map((w) => ({ start: w.start_tick, end: w.end_tick, label: w.kind })) : [];
  const truthSeg = showTruth && truth ? truth.segments[segIndex] : null;
  const segState = state?.segments.find((s) => s.code === seg);
  const captions = Object.fromEntries((state?.segments ?? []).map((s) => [s.code, s.pressure_bar !== null ? `${s.pressure_bar.toFixed(1)} bar` : '']));
  const consistencySeg = consistency?.segments[segIndex];

  return (
    <div className="space-y-6">
      <header className="glass-card p-5 md:p-6 space-y-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <Link href="/runs" className="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-900">
              <ArrowLeft className="w-4 h-4" aria-hidden /> All runs
            </Link>
            <h1 className="text-2xl font-bold text-gray-900 mt-1">{run.name}</h1>
            <p className="text-sm text-gray-500 mt-0.5">
              Started {formatDateTime(run.started_at)}.{' '}
              {run.model_version ? `Analysed by model v${run.model_version}.` : 'Not analysed yet: no model was active at launch.'}
            </p>
          </div>
          {isAdmin && (
            <div className="flex flex-wrap gap-2">
              <button onClick={() => setShowTruth((v) => !v)} className="btn-secondary py-2 px-3 text-sm flex items-center gap-2" aria-pressed={showTruth}>
                {showTruth ? <EyeOff className="w-4 h-4" aria-hidden /> : <Eye className="w-4 h-4" aria-hidden />}
                {showTruth ? 'Hide what was injected' : 'Show what was injected'}
              </button>
              <button onClick={handleRescore} disabled={rescoring} className="btn-secondary py-2 px-3 text-sm flex items-center gap-2">
                <RefreshCw className={`w-4 h-4 ${rescoring ? 'animate-spin' : ''}`} aria-hidden />
                {rescoring ? 'Re-scoring...' : 'Re-score with active model'}
              </button>
            </div>
          )}
        </div>

        <RunPlayback
          status={run.status} revealedTicks={run.revealed_ticks} durationTicks={run.duration_ticks}
          playbackSpeed={run.playback_speed} tick={tick} live={live && run.status === 'active' ? true : live}
          onTick={pickTick} onLive={goLive}
        />

        {segments.length > 0 && (
          <div className="space-y-2">
            <PipelineSchematic segments={segments} states={states} captions={captions} selected={seg}
              onSelect={pickSegment} label="Segments at the cursor time; select one to inspect it" />
            <StateLegend />
          </div>
        )}
      </header>

      {isAdmin && showTruth && truth?.summary && (
        <section className="rounded-2xl border border-dashed border-gray-300 bg-white p-5" aria-label="Ground truth">
          <h2 className="text-base font-semibold text-gray-900">What was injected</h2>
          <p className="text-sm text-gray-500 mt-0.5">Visible to admins only. The analysis never sees this; dashed chart lines show the actual values.</p>
          <dl className="mt-3 grid gap-x-6 gap-y-2 text-sm sm:grid-cols-2 lg:grid-cols-4">
            <div><dt className="text-gray-500">Scenario</dt><dd className="font-medium text-gray-900">{SCENARIO_LABELS[truth.summary.scenario_type] ?? truth.summary.scenario_type}{truth.summary.method ? ` (${truth.summary.method.replace('_', ' ')})` : ''}</dd></div>
            <div><dt className="text-gray-500">Target</dt><dd className="font-medium text-gray-900">{truth.summary.target_segment ?? 'None'}</dd></div>
            <div><dt className="text-gray-500">Effect window</dt><dd className="font-mono tabular text-gray-900">{truth.summary.event_start_tick !== null ? `${formatTick(truth.summary.event_start_tick)} to ${formatTick(truth.summary.event_end_tick ?? 0)}` : 'None'}</dd></div>
            <div><dt className="text-gray-500">Expected root cause</dt><dd className="font-medium text-gray-900">{truth.summary.expected_root_cause}</dd></div>
          </dl>
          {truth.summary.notes && <p className="mt-3 text-sm text-gray-600">{truth.summary.notes}.</p>}
        </section>
      )}

      <div className="grid gap-6 lg:grid-cols-3 items-start">
        <section className="lg:col-span-2 glass-card p-5 space-y-4" aria-label="Telemetry">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-base font-semibold text-gray-900">
              {segment ? `${segment.code} ${segment.name}` : 'Segment'}
            </h2>
            <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer">
              <input type="checkbox" checked={showAlarms} onChange={(e) => setShowAlarms(e.target.checked)}
                className="rounded border-gray-300 text-brand-500 focus:ring-brand-500" />
              Show threshold-baseline alarms
            </label>
          </div>
          <AnomalyBandChart label="Pressure" unit="bar" ticks={series.ticks} values={series.pressure}
            actual={truthSeg ? truthSeg.actual_pressure_bar : null} windows={windows} alarms={alarmsFor('pressure')}
            durationTicks={run.duration_ticks} cursorTick={tick} onPickTick={pickTick} syncId={SYNC_ID} showScoreBand={false} height={150} />
          <AnomalyBandChart label="Flow, with the anomaly score below" unit="m³/h" ticks={series.ticks} values={series.flow}
            actual={truthSeg ? truthSeg.actual_flow_m3h : null} scores={scores} threshold={anomalies?.threshold ?? 0.5}
            windows={windows} alarms={alarmsFor('flow')} durationTicks={run.duration_ticks} cursorTick={tick}
            onPickTick={pickTick} syncId={SYNC_ID} height={150} />
          <EventStrip events={events} durationTicks={run.duration_ticks} onSelect={setSelectedEvent} syncId={SYNC_ID} cursorTick={tick} />
        </section>

        <aside className="space-y-6">
          <section className="glass-card p-5" aria-label="Segment at cursor">
            <h2 className="text-base font-semibold text-gray-900">
              {seg ?? 'Segment'} at <span className="font-mono tabular">{formatTick(tick)}</span>
            </h2>
            {segState ? (
              <>
                <StateBadge state={segState.state} />
                <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
                  <Reading label="Pressure" value={segState.pressure_bar} unit="bar" digits={2} />
                  <Reading label="Flow" value={segState.flow_m3h} unit="m³/h" digits={0} />
                  <Reading label="Temperature" value={segState.temperature_c} unit="°C" digits={1} />
                  <Reading label="Anomaly score" value={segState.anomaly_score} unit="" digits={2} />
                  {segState.valve_open_pct !== null && <Reading label="Valve V-12" value={segState.valve_open_pct} unit="% open" digits={0} />}
                  {segState.pump_speed_pct !== null && <Reading label="Pump P-3" value={segState.pump_speed_pct} unit="% speed" digits={0} />}
                </dl>
              </>
            ) : (
              <p className="text-sm text-gray-500 mt-2">Loading readings...</p>
            )}
          </section>

          <section className="glass-card p-5 space-y-3" aria-label="Telemetry trust">
            <h2 className="text-base font-semibold text-gray-900">Can these readings be trusted?</h2>
            <TrustIndicator score={segState?.trust_score ?? null} status={segState?.trust_status ?? null} factors={segState?.factors ?? []} />
          </section>

          <section className="glass-card p-5" aria-label="Alerts in this run">
            <h2 className="text-base font-semibold text-gray-900">Alerts in this run</h2>
            {alerts.length === 0 ? (
              <p className="text-sm text-gray-500 mt-2">{run.model_version ? 'Nothing flagged so far.' : 'Alerts appear once the run is analysed.'}</p>
            ) : (
              <ul className="mt-3 space-y-2 max-h-80 overflow-y-auto pr-1">
                {alerts.slice().sort((a, b) => a.start_tick - b.start_tick).map((a) => (
                  <li key={a.id}>
                    <button
                      onClick={() => { setSeg(a.segment_code); pickTick(a.start_tick); }}
                      className={`w-full text-left rounded-xl border p-3 transition-colors hover:border-brand-300 hover:bg-brand-50/40 ${a.segment_code === seg ? 'border-brand-200' : 'border-gray-200'}`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <SeverityChip severity={a.severity} />
                        <span className="font-mono tabular text-xs text-gray-500">
                          {formatTick(a.start_tick)}{a.ongoing ? ', ongoing' : ` to ${formatTick(a.end_tick)}`}
                        </span>
                      </div>
                      <p className="mt-1.5 text-sm font-semibold text-gray-900">{a.segment_code} {a.segment_name}</p>
                      <KindIcons kinds={a.kinds} />
                      <p className="mt-1 text-xs text-gray-600 leading-snug line-clamp-3">{a.summary}</p>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="glass-card p-5" aria-label="Consistency checks">
            <h2 className="text-base font-semibold text-gray-900">Consistency checks</h2>
            {consistencySeg && Object.keys(consistencySeg.series).length ? (
              <>
                <p className="text-xs text-gray-500 mt-0.5">{seg} at <span className="font-mono tabular">{formatTick(tick)}</span></p>
                <ul className="mt-3 space-y-1.5 text-sm">
                  {Object.entries(consistencySeg.series).map(([check, levels]) => [check, levels?.[Math.min(tick, (levels?.length ?? 1) - 1)] ?? 0] as const).map(([check, level]) => (
                    <li key={check} className="flex items-center justify-between gap-2">
                      <span className="text-gray-700">{CHECK_LABELS[check] ?? check}</span>
                      {level === 0 ? (
                        <span className="inline-flex items-center gap-1 text-xs text-gray-500"><CheckCircle2 className="w-3.5 h-3.5" aria-hidden /> Consistent</span>
                      ) : (
                        <span className={`inline-flex items-center gap-1 text-xs font-semibold ${level === 2 ? 'text-red-700' : 'text-amber-800'}`}>
                          <XCircle className="w-3.5 h-3.5" aria-hidden /> {level === 2 ? 'Failing' : 'Warning'}
                        </span>
                      )}
                    </li>
                  ))}
                </ul>
                {tick === consistency?.cutoff_tick && consistencySeg.messages.length > 0 && (
                  <ul className="mt-3 space-y-1.5 text-xs text-gray-600 border-t border-gray-100 pt-3">
                    {consistencySeg.messages.map((m, i) => <li key={i}>{m.message}</li>)}
                  </ul>
                )}
              </>
            ) : (
              <p className="text-sm text-gray-500 mt-2">Checks appear once the run is analysed.</p>
            )}
          </section>
        </aside>
      </div>

      <EventDrawer event={selectedEvent} onClose={() => setSelectedEvent(null)} />
    </div>
  );
}

function StateBadge({ state }: { state: SegmentStateName }) {
  const s = STATE_STYLE[state];
  const Icon = s.icon;
  return (
    <div className="mt-2">
      <p className="inline-flex items-center gap-1.5 text-sm font-semibold" style={{ color: s.textColor }}>
        <Icon className="w-4 h-4" aria-hidden /> {s.label}
      </p>
      <p className="text-xs text-gray-500 mt-0.5">{s.description}.</p>
    </div>
  );
}

function Reading({ label, value, unit, digits }: { label: string; value: number | null; unit: string; digits: number }) {
  return (
    <div>
      <dt className="text-gray-500">{label}</dt>
      <dd className="font-mono tabular text-gray-900">
        {value === null || value === undefined ? '—' : value.toFixed(digits)}
        {unit && <span className="text-gray-500 font-sans"> {unit}</span>}
      </dd>
    </div>
  );
}
