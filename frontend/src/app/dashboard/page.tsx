'use client';

import React, { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import {
  Activity, ArrowUpRight, FlaskConical, Gauge, History, Layers, Play, ShieldAlert, Siren, Target, Wind,
} from 'lucide-react';
import { createRun, getActivity, getDashboardSummary, getRunState, getRuns, getTopology } from '@/lib/api';
import type { DashboardSummary, RunOut, RunState, Segment, SegmentStateName } from '@/lib/types';
import { COLORS, TRUST_STYLE, formatDateTime, formatTick, percent } from '@/lib/detection';
import { KPITile } from '@/components/ui/KPITile';
import { StatusBadge } from '@/components/ui/StatusBadge';
import { ErrorState, LoadingState } from '@/components/ui/States';
import { useAuth } from '@/contexts/AuthContext';
import { useToast } from '@/components/ui/Toast';
import { usePolling } from '@/hooks/usePolling';
import { PipelineSchematic } from '@/components/detection/PipelineSchematic';
import { StateLegend } from '@/components/detection/StateLegend';

interface ActivityItem {
  id: number;
  action: string;
  details: string | null;
  timestamp: string;
  username: string | null;
}

const ACTION_LABEL: Record<string, string> = {
  login: 'Signed in',
  register: 'Registered',
  scenario_launched: 'Run launched',
  run_rescored: 'Run re-scored',
  model_trained: 'Model trained',
  model_activated: 'Model activated',
  password_changed: 'Password changed',
};

const STATUS_COPY: Record<DashboardSummary['system_status'], { label: string; tone: string }> = {
  critical: { label: 'Readings in doubt on the line', tone: 'text-pink-800 bg-pink-50 border-pink-200' },
  warning: { label: 'Anomalous behaviour on the line', tone: 'text-amber-800 bg-amber-50 border-amber-200' },
  operational: { label: 'All segments normal', tone: 'text-brand-700 bg-brand-50 border-brand-200' },
  idle: { label: 'No run playing', tone: 'text-gray-600 bg-gray-50 border-gray-200' },
};

export default function DashboardPage() {
  const { isAdmin } = useAuth();
  const { success, error: toastError } = useToast();
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [liveState, setLiveState] = useState<RunState | null>(null);
  const [segments, setSegments] = useState<Segment[]>([]);
  const [runs, setRuns] = useState<RunOut[]>([]);
  const [activities, setActivities] = useState<ActivityItem[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);

  const fetchAll = useCallback(async () => {
    try {
      const [s, list, acts] = await Promise.all([getDashboardSummary(), getRuns(), getActivity(8)]);
      setSummary(s);
      setRuns(list);
      setActivities(acts);
      setLiveState(s.live ? await getRunState(s.live.run_id) : null);
      setErr(null);
    } catch (e: any) {
      setErr(e.message || 'Could not load the dashboard');
    }
  }, []);

  useEffect(() => {
    fetchAll();
    getTopology().then((t) => setSegments(t.segments)).catch(() => undefined);
  }, [fetchAll]);
  usePolling(fetchAll, 5000);

  const startNormalRun = async () => {
    setStarting(true);
    try {
      const run = await createRun({ description: 'Normal operation started from the dashboard' });
      success('Run started', `${run.name} is playing at ${run.playback_speed}×.`);
      fetchAll();
    } catch (e: any) {
      toastError('Could not start a run', e.message);
    } finally {
      setStarting(false);
    }
  };

  if (!summary && err) return <ErrorState message={err} onRetry={fetchAll} />;
  if (!summary) return <LoadingState message="Loading the dashboard..." />;

  const live = summary.live;
  const states: Record<string, SegmentStateName> = Object.fromEntries((liveState?.segments ?? []).map((s) => [s.code, s.state]));
  const captions = Object.fromEntries((liveState?.segments ?? []).map((s) => [s.code, s.pressure_bar !== null ? `${s.pressure_bar.toFixed(1)} bar` : '']));
  const status = STATUS_COPY[summary.system_status];
  const perDay = summary.alerts_per_day.map((d) => ({
    ...d,
    label: new Date(`${d.date}T00:00:00`).toLocaleDateString(undefined, { day: 'numeric', month: 'short' }),
  }));
  const detection = summary.detection;

  return (
    <div className="space-y-6">
      <div className="glass-card p-0 overflow-hidden">
        <img src="/Banner.png" alt="Sensify pipeline network" className="w-full h-auto max-h-[180px] object-cover" />
      </div>

      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-bold text-gray-900">Pipeline overview</h1>
          <span className={`inline-flex items-center rounded-full border px-3 py-1 text-sm font-medium ${status.tone}`}>{status.label}</span>
        </div>
        {isAdmin && (
          <div className="flex flex-wrap gap-2">
            <button onClick={startNormalRun} disabled={starting} className="btn-secondary py-2 px-4 text-sm flex items-center gap-2">
              <Play className="w-4 h-4" aria-hidden /> {starting ? 'Starting...' : 'Start a normal run'}
            </button>
            <Link href="/scenarios" className="btn-primary py-2 px-4 text-sm flex items-center gap-2">
              <FlaskConical className="w-4 h-4" aria-hidden /> Launch a scenario
            </Link>
          </div>
        )}
      </div>

      {live && (
        <section className="glass-card p-5 space-y-3" aria-label="Live line">
          <div className="flex flex-wrap items-baseline justify-between gap-3">
            <h2 className="text-base font-semibold text-gray-900">
              {summary.active_run ? 'Live: ' : 'Latest run: '}{live.run_name}
              <span className="ml-2 font-mono tabular text-sm font-normal text-gray-500">{formatTick(live.tick)}</span>
            </h2>
            <div className="flex gap-4 text-sm">
              <Link href={`/runs/${live.run_id}`} className="text-brand-600 hover:underline inline-flex items-center gap-1">Open run <ArrowUpRight className="w-3.5 h-3.5" aria-hidden /></Link>
              <Link href={`/map?run=${live.run_id}`} className="text-brand-600 hover:underline inline-flex items-center gap-1">Open map <ArrowUpRight className="w-3.5 h-3.5" aria-hidden /></Link>
            </div>
          </div>
          {summary.active_run && (
            <div className="h-1 rounded-full bg-gray-100 overflow-hidden" aria-label={`Playback ${Math.round(summary.active_run.progress * 100)} %`}>
              <div className="h-full bg-brand-500 transition-all" style={{ width: `${summary.active_run.progress * 100}%` }} />
            </div>
          )}
          {segments.length > 0 && <PipelineSchematic segments={segments} states={states} captions={captions} label="Segment states now" />}
          <StateLegend counts={live.segments_by_state} />
        </section>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-5 gap-4">
        <KPITile title="Segments monitored" value={summary.total_segments} unit="segments" icon={Layers}
          subtitle={`${summary.total_runs} runs on record`} />
        <KPITile title="Average pressure" value={live?.avg_pressure_bar?.toFixed(1) ?? '—'} unit="bar" icon={Gauge}
          subtitle={live ? `${live.run_name}, ${formatTick(live.tick)}` : 'No run yet'} />
        <KPITile title="Throughput" value={live?.throughput_m3h?.toFixed(0) ?? '—'} unit="m³/h" icon={Wind}
          subtitle="Received at Dhahran Terminal" />
        <KPITile title="Anomalies, 24 h" value={summary.anomaly_count_24h} unit="alerts" icon={Siren}
          accentColor={summary.anomaly_count_24h ? COLORS.anomalous : '#7169d5'} status={summary.anomaly_count_24h ? 'warning' : 'neutral'}
          subtitle={`${summary.anomaly_count_total} in total`} />
        {detection ? (
          <KPITile title="Detection rate" value={detection.total ? `${detection.detected} of ${detection.total}` : '—'} icon={Target}
            subtitle={detection.total ? `${percent(detection.rate)} of completed scenario runs flagged` : 'No completed scenario runs yet'} />
        ) : (
          <KPITile title="Runs with findings" icon={Target}
            value={summary.runs_flagged.completed ? `${summary.runs_flagged.flagged} of ${summary.runs_flagged.completed}` : '—'}
            subtitle={summary.runs_flagged.completed ? 'Completed runs with at least one flagged window' : 'No completed runs yet'} />
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <section className="lg:col-span-2 glass-card p-5" aria-label="Alerts over time">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h2 className="text-base font-semibold text-gray-900">Alerts over the last 14 days</h2>
            <ul className="flex gap-4 text-xs text-gray-600" aria-label="Legend">
              <li className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-sm" style={{ background: COLORS.anomalous }} /> Anomaly</li>
              <li className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-sm" style={{ background: COLORS.lowTrust }} /> Low trust</li>
            </ul>
          </div>
          <div className="h-56 mt-3">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={perDay} margin={{ top: 4, right: 4, left: -18, bottom: 0 }}>
                <CartesianGrid stroke={COLORS.grid} vertical={false} />
                <XAxis dataKey="label" stroke={COLORS.muted} fontSize={11} tickLine={false} interval="preserveStartEnd" />
                <YAxis allowDecimals={false} stroke={COLORS.muted} fontSize={11} tickLine={false} />
                <Tooltip cursor={{ fill: '#F3F4F6' }} />
                <Bar dataKey="anomaly" name="Anomaly" stackId="a" fill={COLORS.anomalous} isAnimationActive={false} />
                <Bar dataKey="low_trust" name="Low trust" stackId="a" fill={COLORS.lowTrust} radius={[3, 3, 0, 0]} isAnimationActive={false} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>

        <section className="glass-card p-5" aria-label="Telemetry trust alerts">
          <h2 className="text-base font-semibold text-gray-900 flex items-center gap-2">
            <ShieldAlert className="w-4 h-4" style={{ color: COLORS.lowTrust }} aria-hidden /> Readings in doubt
          </h2>
          {summary.trust_alerts.length > 0 ? (
            <ul className="mt-3 space-y-3">
              {summary.trust_alerts.map((t) => (
                <li key={t.segment_id}>
                  <Link href={`/map?run=${t.run_id}&seg=${t.code}`} className="block rounded-xl border border-pink-200 bg-pink-50/40 p-3 hover:border-pink-300">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-semibold text-gray-900">{t.code} {t.name}</span>
                      <span className="text-xs font-semibold" style={{ color: TRUST_STYLE[t.trust_status].color }}>{t.trust_status}</span>
                    </div>
                    {t.top_factor && <p className="mt-1 text-sm text-gray-600 leading-snug">{t.top_factor.detail}</p>}
                  </Link>
                </li>
              ))}
            </ul>
          ) : summary.recent_trust_alerts.length > 0 ? (
            <>
              <p className="mt-1 text-sm text-gray-500">Nothing in doubt right now. The most recent:</p>
              <ul className="mt-3 space-y-2">
                {summary.recent_trust_alerts.map((a) => (
                  <li key={a.id}>
                    <Link href={`/runs/${a.run_id}?t=${a.start_tick}&seg=${a.segment_code}`} className="block rounded-xl border border-gray-200 p-3 hover:border-brand-300">
                      <p className="text-sm font-semibold text-gray-900">{a.segment_code} in {a.run_name}</p>
                      <p className="text-xs text-gray-500 font-mono tabular">{formatTick(a.start_tick)}</p>
                      <p className="mt-1 text-xs text-gray-600 line-clamp-2">{a.summary}</p>
                    </Link>
                  </li>
                ))}
              </ul>
            </>
          ) : (
            <p className="mt-2 text-sm text-gray-500">No segment&apos;s readings have been in doubt.</p>
          )}
        </section>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <section className="glass-card p-5" aria-label="Recent runs">
          <div className="flex items-baseline justify-between">
            <h2 className="text-base font-semibold text-gray-900 flex items-center gap-2"><Activity className="w-4 h-4 text-brand-500" aria-hidden /> Recent runs</h2>
            <Link href="/runs" className="text-sm text-brand-600 hover:underline">All runs</Link>
          </div>
          <ul className="mt-3 divide-y divide-gray-100">
            {runs.slice(0, 5).map((r) => (
              <li key={r.id}>
                <Link href={`/runs/${r.id}`} className="flex items-center justify-between gap-3 py-2.5 hover:bg-gray-50 rounded-lg px-2 -mx-2">
                  <div>
                    <p className="font-medium text-gray-900">{r.name}</p>
                    <p className="text-xs text-gray-500">{formatDateTime(r.started_at)}</p>
                  </div>
                  {r.status === 'active'
                    ? <StatusBadge status="active" label={`Playing ${Math.round(r.progress * 100)} %`} size="sm" />
                    : <StatusBadge status="completed" size="sm" />}
                </Link>
              </li>
            ))}
            {runs.length === 0 && <li className="py-3 text-sm text-gray-500">No runs yet.</li>}
          </ul>
        </section>

        <section className="glass-card p-5" aria-label="Recent activity">
          <h2 className="text-base font-semibold text-gray-900 flex items-center gap-2"><History className="w-4 h-4 text-brand-500" aria-hidden /> Recent activity</h2>
          <ul className="mt-3 space-y-3">
            {activities.map((a) => (
              <li key={a.id} className="flex items-start justify-between gap-3 text-sm">
                <div>
                  <p className="font-medium text-gray-900">{ACTION_LABEL[a.action] ?? a.action.replace('_', ' ')}{a.username ? ` by ${a.username}` : ''}</p>
                  {a.details && <p className="text-xs text-gray-500">{a.details}</p>}
                </div>
                <span className="text-xs text-gray-400 whitespace-nowrap">{formatDateTime(a.timestamp)}</span>
              </li>
            ))}
            {activities.length === 0 && <li className="text-sm text-gray-500">Nothing yet.</li>}
          </ul>
        </section>
      </div>
    </div>
  );
}
