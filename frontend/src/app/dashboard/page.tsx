'use client';

import React, { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { ArrowUpRight, Compass, FlaskConical, Play } from 'lucide-react';
import { createRun, getActivity, startDemo, getDashboardSummary, getRunState, getRuns, getTopology } from '@/lib/api';
import type { DashboardSummary, RunOut, RunState, Segment, SegmentStateName } from '@/lib/types';
import { COLORS, TRUST_STYLE, formatDateTime, formatTick, percent } from '@/lib/detection';
import { StatusBadge } from '@/components/ui/StatusBadge';
import { CountUp } from '@/components/ui/CountUp';
import { Segmented } from '@/components/ui/Segmented';
import { ErrorState, LoadingState } from '@/components/ui/States';
import { useAuth } from '@/contexts/AuthContext';
import { useToast } from '@/components/ui/Toast';
import { usePolling } from '@/hooks/usePolling';
import { ClassificationMark } from '@/components/investigation/ClassificationMark';
import { CATEGORY_STYLE, CLASSIFICATION_ORDER } from '@/lib/investigation';
import { writeDemoState } from '@/components/DemoGuide';
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
  run_paused: 'Run paused',
  run_resumed: 'Run resumed',
  run_reset: 'Run reset',
  model_trained: 'Model trained',
  model_activated: 'Model activated',
  password_changed: 'Password changed',
  user_created: 'User added',
  user_updated: 'User updated',
};

const NUMBER_WORDS = ['No', 'One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight'];

/** One sentence for the whole line, naming the segments that need a look. */
function headline(states: { code: string; state: SegmentStateName }[], hasRun: boolean): { text: string; tone: string } {
  if (!hasRun || states.length === 0) return { text: 'No run on the line yet', tone: 'text-gray-500' };
  const named = (s: SegmentStateName) => states.filter((x) => x.state === s).map((x) => x.code);
  const doubt = named('low_trust');
  const anomalous = named('anomalous');
  const missing = named('insufficient');
  const parts: string[] = [];
  if (doubt.length) parts.push(`${doubt.join(', ')} in doubt`);
  if (anomalous.length) parts.push(`${anomalous.join(', ')} anomalous`);
  if (missing.length) parts.push(`${missing.join(', ')} without enough data`);
  if (!parts.length) {
    return { text: `All ${NUMBER_WORDS[states.length]?.toLowerCase() ?? states.length} segments normal`, tone: 'text-gray-900' };
  }
  const tone = doubt.length ? 'text-[#9D174D]' : anomalous.length ? 'text-[#B45309]' : 'text-gray-700';
  return { text: parts.join('; '), tone };
}

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
  const [demoBusy, setDemoBusy] = useState(false);
  const [feed, setFeed] = useState<'runs' | 'activity'>('runs');
  // Bars grow in once on arrival; the 5 s refresh must not replay that every time.
  const [chartIntro, setChartIntro] = useState(true);
  useEffect(() => { const id = window.setTimeout(() => setChartIntro(false), 1500); return () => window.clearTimeout(id); }, []);

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

  const openDemo = (runId: number) => writeDemoState({ runId, step: 0, open: true });
  const startTheDemo = async () => {
    setDemoBusy(true);
    try {
      const d = await startDemo();
      if (d.run_id !== null) openDemo(d.run_id);
      success('Demo started', 'The demo run is playing. Follow the guide at the bottom right.');
      fetchAll();
    } catch (e: any) {
      toastError('Could not start the demo', e.message);
    } finally {
      setDemoBusy(false);
    }
  };

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
  if (!summary) return <LoadingState message="Loading the dashboard" />;

  const live = summary.live;
  const activeRun = summary.active_run;
  const segStates = (liveState?.segments ?? []).map((s) => ({ code: s.code, state: s.state }));
  const states: Record<string, SegmentStateName> = Object.fromEntries(segStates.map((s) => [s.code, s.state]));
  const captions = Object.fromEntries((liveState?.segments ?? []).map((s) => [s.code, s.pressure_bar !== null ? `${s.pressure_bar.toFixed(1)} bar` : 'no reading']));
  const head = headline(segStates, !!live);
  const perDay = summary.alerts_per_day.map((d) => ({
    ...d,
    label: new Date(`${d.date}T00:00:00`).toLocaleDateString(undefined, { day: 'numeric', month: 'short' }),
  }));
  const detection = summary.detection;
  const demoRunId = summary.demo_run_id ?? null;
  const byClass = summary.incidents_by_classification ?? {};
  const incidentTotal = CLASSIFICATION_ORDER.reduce((n, c) => n + (byClass[c] ?? 0), 0);
  const openItems = summary.open_investigations ?? [];

  return (
    <div className="space-y-6">
      <header className="flex flex-col lg:flex-row lg:items-end justify-between gap-4 pt-2">
        <div>
          <h1 className="text-sm font-medium text-gray-500" style={{ fontStretch: '100%', letterSpacing: 0 }}>Pipeline overview</h1>
          <p className={`display mt-1 text-[28px] md:text-[34px] leading-tight font-semibold ${head.tone}`} aria-live="polite">
            {head.text}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {isAdmin && (
            <button type="button" onClick={startTheDemo} disabled={demoBusy} className="btn-ghost" title="A guided walk from the dashboard to an incident and the comparative results">
              <Compass className="w-4 h-4" aria-hidden /> {demoBusy ? 'Starting demo' : 'Start demo'}
            </button>
          )}
          {demoRunId !== null && (
            <button type="button" onClick={() => openDemo(demoRunId)} className="btn-ghost">
              <Compass className="w-4 h-4" aria-hidden /> Follow the demo
            </button>
          )}
          {isAdmin && (
            <>
              <button onClick={startNormalRun} disabled={starting} className="btn-secondary">
                <Play className="w-4 h-4" aria-hidden /> {starting ? 'Starting' : 'Start a normal run'}
              </button>
              <Link href="/scenarios" className="btn-primary">
                <FlaskConical className="w-4 h-4" aria-hidden /> Launch a scenario
              </Link>
            </>
          )}
        </div>
      </header>

      {/* The hero: the line itself, with the few numbers that describe it. */}
      <section className="glass-card overflow-hidden" aria-label="Live line">
        {live ? (
          <div className="px-5 md:px-7 pt-5 pb-4 space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex flex-wrap items-center gap-3">
                <h2 className="sheet-title">{live.run_name}</h2>
                {activeRun?.status === 'paused'
                  ? <StatusBadge status="paused" size="sm" label={`Paused at ${formatTick(live.tick)}`} />
                  : activeRun
                    ? <StatusBadge status="active" size="sm" label={`Playing, ${formatTick(live.tick)}`} />
                    : <StatusBadge status="completed" size="sm" label={`Latest run, ended ${formatTick(live.tick)}`} />}
              </div>
              <div className="flex gap-5">
                <Link href={`/runs/${live.run_id}`} className="muted-link inline-flex items-center gap-1">Open run <ArrowUpRight className="w-3.5 h-3.5" aria-hidden /></Link>
                <Link href={`/map?run=${live.run_id}`} className="muted-link inline-flex items-center gap-1">Open map <ArrowUpRight className="w-3.5 h-3.5" aria-hidden /></Link>
              </div>
            </div>
            {activeRun && (
              <div className="h-1 rounded-full bg-gray-100 overflow-hidden" role="progressbar" aria-valuenow={Math.round(activeRun.progress * 100)}
                aria-valuemin={0} aria-valuemax={100} aria-label="Run progress">
                <div className="h-full bg-brand-500 transition-[width] duration-1000 ease-linear" style={{ width: `${activeRun.progress * 100}%` }} />
              </div>
            )}
            {segments.length > 0 && (
              <PipelineSchematic segments={segments} states={states} captions={captions} label="Segment states now"
                flowing={activeRun?.status === 'active'} intro />
            )}
            <StateLegend counts={live.segments_by_state} />
          </div>
        ) : (
          <div className="px-7 py-10 text-center">
            <p className="text-gray-600">Nothing has run yet. {isAdmin ? 'Start a normal run or launch a scenario to see the line.' : 'An administrator starts runs; they appear here as they play.'}</p>
          </div>
        )}

        <dl className="grid grid-cols-2 lg:grid-cols-5 border-t border-rule divide-x divide-y lg:divide-y-0 divide-rule">
          <Stat label="Segments monitored" detail={`${summary.total_runs} runs on record`}>
            <CountUp value={summary.total_segments} />
          </Stat>
          <Stat label="Average pressure" unit="bar" detail={live ? `At ${formatTick(live.tick)}` : 'No run yet'}>
            {live?.avg_pressure_bar != null ? <CountUp value={live.avg_pressure_bar} digits={1} /> : '—'}
          </Stat>
          <Stat label="Throughput" unit="m³/h" detail="Received at Dhahran Terminal">
            {live?.throughput_m3h != null ? <CountUp value={live.throughput_m3h} /> : '—'}
          </Stat>
          <Stat label="Anomaly alerts, 24 h" detail={`${summary.anomaly_count_total} in total`} tone={summary.anomaly_count_24h ? COLORS.anomalousText : undefined}>
            <CountUp value={summary.anomaly_count_24h} />
          </Stat>
          {detection ? (
            <Stat label="Detection rate" detail={detection.total ? `${percent(detection.rate)} of completed scenario runs flagged` : 'No completed scenario runs yet'}>
              {detection.total ? <><CountUp value={detection.detected} /> <span className="text-gray-400 font-normal text-lg">of {detection.total}</span></> : '—'}
            </Stat>
          ) : (
            <Stat label="Runs with findings" detail={summary.runs_flagged.completed ? 'Completed runs with a flagged window' : 'No completed runs yet'}>
              {summary.runs_flagged.completed
                ? <><CountUp value={summary.runs_flagged.flagged} /> <span className="text-gray-400 font-normal text-lg">of {summary.runs_flagged.completed}</span></>
                : '—'}
            </Stat>
          )}
        </dl>
      </section>

      {/* Two independent stacks: a tall column never leaves a hole beside a short one. */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
        <div className="lg:col-span-2 space-y-6">
          <section className="glass-card p-5 md:p-6" aria-label="Needs attention">
            <div className="flex items-baseline justify-between gap-4">
              <h2 className="sheet-title">Needs attention</h2>
              <Link href="/incidents" className="muted-link">All incidents</Link>
            </div>

            <h3 className="mt-4 text-sm font-medium text-gray-500">Open investigations</h3>
            {openItems.length > 0 ? (
              <ul className="mt-1 divide-y divide-rule">
                {openItems.slice(0, 5).map((i) => (
                  <li key={i.key}>
                    <Link href={`/incidents/${encodeURIComponent(i.key)}`} className="group flex flex-wrap items-center justify-between gap-x-4 gap-y-1 py-3 -mx-2 px-2 rounded-lg hover:bg-gray-50 transition-colors">
                      <ClassificationMark classification={i.classification} size="sm" />
                      <span className="text-sm text-gray-600">
                        {i.segment_code ?? 'Whole line'} in {i.run_name}
                        {i.developing && <span className="ml-2 text-brand-700 font-medium">developing</span>}
                        <ArrowUpRight className="inline w-3.5 h-3.5 ml-1 text-gray-300 group-hover:text-gray-600 transition-colors" aria-hidden />
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-1 py-2 text-sm text-gray-500">No investigations are open.</p>
            )}

            <h3 className="mt-5 text-sm font-medium text-gray-500">Readings in doubt</h3>
            {summary.trust_alerts.length > 0 ? (
              <ul className="mt-1 divide-y divide-rule">
                {summary.trust_alerts.map((t) => {
                  const tone = TRUST_STYLE[t.trust_status];
                  return (
                    <li key={t.segment_id}>
                      <Link href={`/map?run=${t.run_id}&seg=${t.code}`} className="block py-3 -mx-2 px-2 rounded-lg hover:bg-gray-50 transition-colors">
                        <span className="flex items-center justify-between gap-2">
                          <span className="font-medium text-gray-900">{t.code} {t.name}</span>
                          <span className="text-xs font-semibold" style={{ color: tone.color }}>{tone.label}</span>
                        </span>
                        {t.top_factor && <span className="mt-0.5 text-sm text-gray-600 leading-snug line-clamp-2" title={t.top_factor.detail}>{t.top_factor.detail}</span>}
                      </Link>
                    </li>
                  );
                })}
              </ul>
            ) : summary.recent_trust_alerts.length > 0 ? (
              <>
                <p className="mt-1 text-sm text-gray-500">Nothing in doubt right now. The most recent:</p>
                <ul className="mt-1 divide-y divide-rule">
                  {summary.recent_trust_alerts.slice(0, 3).map((a) => (
                    <li key={a.id}>
                      <Link href={`/runs/${a.run_id}?t=${a.start_tick}&seg=${a.segment_code}`} className="block py-3 -mx-2 px-2 rounded-lg hover:bg-gray-50 transition-colors">
                        <span className="text-sm font-medium text-gray-900">{a.segment_code} in {a.run_name}</span>
                        <span className="ml-2 text-xs text-gray-500 tabular">{formatTick(a.start_tick)}</span>
                        <span className="mt-0.5 text-sm text-gray-600 line-clamp-1" title={a.summary}>{a.summary}</span>
                      </Link>
                    </li>
                  ))}
                </ul>
              </>
            ) : (
              <p className="mt-1 py-2 text-sm text-gray-500">No segment&apos;s readings have been in doubt.</p>
            )}
          </section>

          <section className="glass-card p-5 md:p-6" aria-label="Alerts over time">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <h2 className="sheet-title">Alerts over the last 14 days</h2>
              <ul className="flex gap-4 text-xs text-gray-600" aria-label="Legend">
                <li className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-sm" style={{ background: COLORS.anomalous }} /> Anomaly</li>
                <li className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-sm" style={{ background: COLORS.lowTrust }} /> Low trust</li>
              </ul>
            </div>
            <div className="h-56 mt-4">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={perDay} margin={{ top: 4, right: 4, left: -18, bottom: 0 }}>
                  <CartesianGrid stroke={COLORS.grid} vertical={false} />
                  <XAxis dataKey="label" stroke={COLORS.muted} fontSize={11} tickLine={false} axisLine={false} interval="preserveStartEnd" />
                  <YAxis allowDecimals={false} stroke={COLORS.muted} fontSize={11} tickLine={false} axisLine={false} />
                  <Tooltip cursor={{ fill: '#F1F2F6' }} />
                  <Bar dataKey="anomaly" name="Anomaly" stackId="a" fill={COLORS.anomalous} isAnimationActive={chartIntro} animationDuration={700} />
                  <Bar dataKey="low_trust" name="Low trust" stackId="a" fill={COLORS.lowTrust} radius={[3, 3, 0, 0]} isAnimationActive={chartIntro} animationDuration={700} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </section>
        </div>

        <div className="space-y-6">
          <section className="glass-card p-5 md:p-6" aria-label="Incidents by classification">
            <div className="flex items-baseline justify-between gap-4">
              <h2 className="sheet-title">Incidents</h2>
              <span className="text-sm text-gray-500 tabular">{incidentTotal} in total</span>
            </div>
            {/* One bar for the mix, then the counts; each row filters the incident list. */}
            <div className="mt-4 flex h-2.5 rounded-full overflow-hidden bg-gray-100" aria-hidden>
              {CLASSIFICATION_ORDER.map((c) => (byClass[c] ?? 0) > 0 && (
                <span key={c} className="h-full transition-[width] duration-700 ease-out"
                  style={{ width: `${((byClass[c] ?? 0) / Math.max(incidentTotal, 1)) * 100}%`, background: CATEGORY_STYLE[c].color }} />
              ))}
            </div>
            <ul className="mt-3 space-y-0.5">
              {CLASSIFICATION_ORDER.map((c) => {
                const style = CATEGORY_STYLE[c];
                const Icon = style.icon;
                return (
                  <li key={c}>
                    <Link href={`/incidents?class=${c}`} className="flex items-center justify-between gap-3 rounded-lg -mx-2 px-2 py-1.5 hover:bg-gray-50 transition-colors">
                      <span className="flex items-center gap-2 min-w-0 text-sm text-gray-700">
                        <Icon className="w-4 h-4 shrink-0" style={{ color: style.color }} aria-hidden />
                        <span className="truncate">{style.label}</span>
                      </span>
                      <span className="tabular text-sm font-semibold text-gray-900">{byClass[c] ?? 0}</span>
                    </Link>
                  </li>
                );
              })}
            </ul>
          </section>

          <section className="glass-card p-5 md:p-6" aria-label="Latest evaluation">
            <div className="flex items-baseline justify-between gap-4">
              <h2 className="sheet-title">Latest evaluation</h2>
              <Link href="/evaluation" className="muted-link">Open</Link>
            </div>
            {summary.latest_evaluation ? (
              <table className="mt-3 w-full text-sm">
                <thead>
                  <tr className="text-xs text-gray-500">
                    <th className="text-left font-medium pb-1.5">Detection</th>
                    <th className="text-right font-medium pb-1.5">Threshold</th>
                    <th className="text-right font-medium pb-1.5">Sensify</th>
                  </tr>
                </thead>
                <tbody>
                  {(['development', 'heldout'] as const).map((ds) => {
                    const e = summary.latest_evaluation![ds];
                    const pc = (v: number | null | undefined) => (v === null || v === undefined ? '—' : `${Math.round(v * 100)} %`);
                    return (
                      <tr key={ds} className="border-t border-rule">
                        <td className="py-2 text-gray-700">{ds === 'development' ? 'Development' : 'Held-out'}</td>
                        <td className="py-2 text-right tabular text-gray-500">{pc(e?.A?.detection_rate)}</td>
                        <td className="py-2 text-right tabular font-semibold text-gray-900">{pc(e?.C?.detection_rate)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            ) : (
              <p className="mt-2 text-sm text-gray-500">No evaluation has been run yet.</p>
            )}
          </section>

          <section className="glass-card p-5 md:p-6" aria-label="Recent runs and activity">
            <div className="flex items-center justify-between gap-3">
              <Segmented label="Recent" value={feed} onChange={setFeed}
                options={[{ value: 'runs', label: 'Recent runs' }, { value: 'activity', label: 'Activity' }]} />
              {feed === 'runs' && <Link href="/runs" className="muted-link">All runs</Link>}
            </div>
            <div key={feed} className="animate-fade-in" role="tabpanel">
              {feed === 'runs' ? (
                <ul className="mt-3 divide-y divide-rule">
                  {runs.slice(0, 5).map((r) => (
                    <li key={r.id}>
                      <Link href={`/runs/${r.id}`} className="flex items-center justify-between gap-3 py-2.5 -mx-2 px-2 rounded-lg hover:bg-gray-50 transition-colors">
                        <span>
                          <span className="block font-medium text-gray-900">{r.name}</span>
                          <span className="block text-xs text-gray-500">{formatDateTime(r.started_at)}</span>
                        </span>
                        {r.status === 'active'
                          ? <StatusBadge status="active" label={`Playing ${Math.round(r.progress * 100)} %`} size="sm" />
                          : r.status === 'paused'
                            ? <StatusBadge status="paused" label={`Paused ${Math.round(r.progress * 100)} %`} size="sm" />
                            : <StatusBadge status="completed" size="sm" />}
                      </Link>
                    </li>
                  ))}
                  {runs.length === 0 && <li className="py-3 text-sm text-gray-500">No runs yet.</li>}
                </ul>
              ) : (
                <ul className="mt-3 divide-y divide-rule">
                  {activities.map((a) => (
                    <li key={a.id} className="py-2.5 text-sm">
                      <span className="flex items-baseline justify-between gap-3">
                        <span className="font-medium text-gray-900">{ACTION_LABEL[a.action] ?? a.action.replaceAll('_', ' ')}{a.username ? ` by ${a.username}` : ''}</span>
                        <span className="text-xs text-gray-400 whitespace-nowrap">{formatDateTime(a.timestamp)}</span>
                      </span>
                      {a.details && <span className="block text-xs text-gray-500 mt-0.5">{a.details}</span>}
                    </li>
                  ))}
                  {activities.length === 0 && <li className="py-3 text-sm text-gray-500">Nothing yet.</li>}
                </ul>
              )}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}

function Stat({ label, unit, detail, tone, children }: { label: string; unit?: string; detail: string; tone?: string; children: React.ReactNode }) {
  return (
    <div className="px-5 md:px-7 py-4">
      <dt className="text-sm text-gray-500">{label}</dt>
      <dd className="mt-1">
        <span className="display text-[26px] leading-none font-semibold text-gray-900" style={tone ? { color: tone } : undefined}>{children}</span>
        {unit && <span className="ml-1.5 text-sm text-gray-500">{unit}</span>}
        <span className="block mt-1.5 text-xs text-gray-500">{detail}</span>
      </dd>
    </div>
  );
}
