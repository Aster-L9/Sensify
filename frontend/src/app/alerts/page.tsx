'use client';

import React, { Suspense, useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { ArrowUpRight, BellRing, FilterX, MapPin } from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import { getAlerts, getRuns, getTopology } from '@/lib/api';
import type { AlertItem, AlertKind, RunOut, Segment, Severity, TrustStatus } from '@/lib/types';
import { SCENARIO_LABELS, SEVERITY_STYLE, TRUST_STYLE, formatDateTime, formatDuration, formatTick } from '@/lib/detection';
import { usePolling } from '@/hooks/usePolling';
import { LoadingState, ErrorState, EmptyState } from '@/components/ui/States';
import { KindIcons, SeverityChip } from '@/components/detection/SeverityChip';

const SEVERITIES: Severity[] = ['critical', 'high', 'medium'];
const KINDS: { id: AlertKind; label: string }[] = [
  { id: 'anomaly', label: 'Anomaly' },
  { id: 'low_trust', label: 'Low trust' },
];

function trustStatus(score: number): TrustStatus {
  return score >= 0.7 ? 'Supported' : score >= 0.4 ? 'Review' : 'Contradicted';
}

export default function AlertsPage() {
  return (
    <Suspense fallback={<LoadingState message="Loading alerts..." />}>
      <AlertsView />
    </Suspense>
  );
}

function AlertsView() {
  const router = useRouter();
  const { isAdmin } = useAuth();
  const pathname = usePathname();
  const search = useSearchParams();
  const runFilter = search.get('run');
  const segFilter = search.get('seg');
  const severityFilter = search.get('severity') as Severity | null;
  const kindFilter = search.get('kind') as AlertKind | null;

  const [alerts, setAlerts] = useState<AlertItem[] | null>(null);
  const [runs, setRuns] = useState<RunOut[]>([]);
  const [segments, setSegments] = useState<Segment[]>([]);
  const [err, setErr] = useState<string | null>(null);

  const setFilter = useCallback((key: string, value: string | null) => {
    const next = new URLSearchParams(search.toString());
    if (value) next.set(key, value);
    else next.delete(key);
    const query = next.toString();
    router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false });
  }, [search, router, pathname]);

  const segmentId = segFilter ? segments.find((s) => s.code === segFilter)?.id : undefined;

  const fetchAlerts = useCallback(async () => {
    try {
      const [items, runList] = await Promise.all([
        getAlerts({ runId: runFilter ? Number(runFilter) : undefined, segmentId, kind: kindFilter ?? undefined, limit: 500 }),
        getRuns(),
      ]);
      setAlerts(items);
      setRuns(runList);
      setErr(null);
    } catch (e: any) {
      setErr(e.message || 'Could not load alerts');
    }
  }, [runFilter, segmentId, kindFilter]);

  useEffect(() => {
    getTopology().then((t) => setSegments(t.segments)).catch(() => undefined);
  }, []);

  // A segment filter is a code in the URL; wait for the topology to turn it into an id.
  const ready = !segFilter || segments.length > 0;
  useEffect(() => {
    if (ready) fetchAlerts();
  }, [fetchAlerts, ready]);

  const anyActive = runs.some((r) => r.status === 'active');
  usePolling(fetchAlerts, 3000, anyActive);

  const counts = useMemo(() => {
    const out: Record<Severity, number> = { critical: 0, high: 0, medium: 0 };
    (alerts ?? []).forEach((a) => { out[a.severity] += 1; });
    return out;
  }, [alerts]);

  const shown = useMemo(
    () => (alerts ?? []).filter((a) => !severityFilter || a.severity === severityFilter),
    [alerts, severityFilter],
  );
  const runsById = useMemo(() => new Map(runs.map((r) => [r.id, r])), [runs]);
  // Windows arrive newest first; keep that order and group them under their run.
  const groups = useMemo(() => {
    const out: { runId: number; runName: string; items: AlertItem[] }[] = [];
    shown.forEach((a) => {
      const last = out.find((g) => g.runId === a.run_id);
      if (last) last.items.push(a);
      else out.push({ runId: a.run_id, runName: a.run_name, items: [a] });
    });
    return out;
  }, [shown]);
  const filtered = Boolean(runFilter || segFilter || severityFilter || kindFilter);
  const ongoing = (alerts ?? []).filter((a) => a.ongoing).length;

  if (alerts === null && !err) return <LoadingState message="Loading alerts..." />;
  if (err && alerts === null) return <ErrorState message={err} onRetry={fetchAlerts} />;

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <BellRing className="w-6 h-6 text-brand-500" aria-hidden /> Alerts
          </h1>
          <p className="text-sm text-gray-500 mt-1 max-w-2xl">
            Every stretch of time in which Sensify flagged a segment, either because its readings looked anomalous
            or because they could not be trusted. Playing runs add windows as they unfold.
          </p>
        </div>
        {ongoing > 0 && (
          <p className="inline-flex items-center gap-2 rounded-full bg-red-50 px-3 py-1.5 text-sm font-semibold text-red-700 w-fit" role="status">
            <span className="relative flex h-2 w-2" aria-hidden>
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-red-500 opacity-60" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-red-600" />
            </span>
            {ongoing} ongoing now
          </p>
        )}
      </div>

      <div className="glass-card p-4 space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <label className="text-sm">
            <span className="block text-xs font-semibold text-gray-600 mb-1">Run</span>
            <select value={runFilter ?? ''} onChange={(e) => setFilter('run', e.target.value || null)} className="input-field py-2 text-sm">
              <option value="">All runs</option>
              {runs.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.name}{r.status === 'active' ? ' (playing)' : ''}
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm">
            <span className="block text-xs font-semibold text-gray-600 mb-1">Segment</span>
            <select value={segFilter ?? ''} onChange={(e) => setFilter('seg', e.target.value || null)} className="input-field py-2 text-sm">
              <option value="">All segments</option>
              {segments.map((s) => (
                <option key={s.id} value={s.code}>{s.code}, {s.name}</option>
              ))}
            </select>
          </label>
          <div className="text-sm">
            <span className="block text-xs font-semibold text-gray-600 mb-1" id="kind-label">Reason</span>
            <div className="flex items-center gap-1.5" role="group" aria-labelledby="kind-label">
              <FilterButton active={!kindFilter} onClick={() => setFilter('kind', null)}>Either</FilterButton>
              {KINDS.map((k) => (
                <FilterButton key={k.id} active={kindFilter === k.id} onClick={() => setFilter('kind', k.id)}>
                  {k.label}
                </FilterButton>
              ))}
            </div>
          </div>
        </div>

        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-3 border-t border-gray-100">
          <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label="Filter by severity">
            <FilterButton active={!severityFilter} onClick={() => setFilter('severity', null)}>
              All severities <span className="tabular opacity-70">{alerts?.length ?? 0}</span>
            </FilterButton>
            {SEVERITIES.map((s) => (
              <FilterButton key={s} active={severityFilter === s} onClick={() => setFilter('severity', s)} accent={SEVERITY_STYLE[s].color}>
                {SEVERITY_STYLE[s].label} <span className="tabular opacity-70">{counts[s]}</span>
              </FilterButton>
            ))}
          </div>
          {filtered && (
            <button onClick={() => router.replace(pathname, { scroll: false })} className="btn-ghost py-1.5 px-3 text-sm flex items-center gap-1.5 w-fit">
              <FilterX className="w-4 h-4" aria-hidden /> Clear filters
            </button>
          )}
        </div>
      </div>

      {shown.length === 0 ? (
        <EmptyState
          title={filtered ? 'No windows match these filters' : 'No flagged windows yet'}
          message={filtered
            ? 'Try another run, segment or severity.'
            : 'When Sensify flags a segment during a run, the window appears here for everyone to review.'}
        />
      ) : (
        <div className="glass-card overflow-x-auto">
          <table className="data-table">
            <caption className="sr-only">Flagged windows, newest first</caption>
            <thead>
              <tr>
                <th>Severity</th>
                <th>Segment</th>
                <th>Window</th>
                <th>Peak score</th>
                <th>Lowest trust</th>
                <th>What Sensify saw</th>
                <th><span className="sr-only">Open</span></th>
              </tr>
            </thead>
            {groups.map((g) => (
              <RunGroup key={g.runId} runId={g.runId} runName={g.runName} items={g.items}
                run={runsById.get(g.runId)} showScenario={isAdmin} />
            ))}
          </table>
          {alerts && alerts.length >= 500 && (
            <p className="px-4 py-3 text-xs text-gray-500 border-t border-gray-100">
              Showing the 500 most recent windows. Pick a run or segment to narrow the list.
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function FilterButton({ active, onClick, accent, children }: {
  active: boolean;
  onClick: () => void;
  accent?: string;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      aria-pressed={active}
      className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm transition-colors ${
        active ? `text-white font-semibold ${accent ? '' : 'bg-brand-500'}` : 'text-gray-600 hover:bg-gray-100'
      }`}
      style={active && accent ? { background: accent } : undefined}
    >
      {children}
    </button>
  );
}

function RunGroup({ runId, runName, items, run, showScenario }: {
  runId: number;
  runName: string;
  items: AlertItem[];
  run?: RunOut;
  showScenario: boolean;
}) {
  const segmentsHit = new Set(items.map((a) => a.segment_code)).size;
  return (
    <tbody>
      <tr className="bg-gray-50/80 hover:!bg-gray-50/80">
        <th colSpan={7} scope="rowgroup" className="!py-2.5 text-left !font-normal !normal-case !tracking-normal">
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5">
            <Link href={`/runs/${runId}`} className="text-sm font-semibold text-gray-900 hover:text-brand-600 hover:underline">
              {runName}
            </Link>
            {showScenario && run?.scenario_type && (
              <span className="text-xs text-gray-600">
                {SCENARIO_LABELS[run.scenario_type] ?? run.scenario_type}
                {run.target_segment ? ` at ${run.target_segment}` : ''}
              </span>
            )}
            <span className="text-xs text-gray-500">
              {items.length} {items.length === 1 ? 'window' : 'windows'} across {segmentsHit} {segmentsHit === 1 ? 'segment' : 'segments'}
            </span>
            <span className="text-xs text-gray-500">
              {run?.status === 'active' ? `Playing, ${Math.round(run.progress * 100)} % revealed` : `Started ${formatDateTime(run?.started_at)}`}
            </span>
          </div>
        </th>
      </tr>
      {items.map((a) => (
        <AlertRow key={a.id} alert={a} run={run} />
      ))}
    </tbody>
  );
}

function AlertRow({ alert: a, run }: { alert: AlertItem; run?: RunOut }) {
  const tickSeconds = run?.tick_seconds;
  const status = trustStatus(a.min_trust);
  const tone = TRUST_STYLE[status];
  const length = a.end_tick - a.start_tick + 1;
  const sev = SEVERITY_STYLE[a.severity];

  return (
    <tr>
      <td className="whitespace-nowrap">
        <SeverityChip severity={a.severity} />
        {a.ongoing && (
          <p className="mt-1.5 inline-flex items-center gap-1.5 text-xs font-semibold text-red-700">
            <span className="h-1.5 w-1.5 rounded-full bg-red-600 animate-pulse" aria-hidden /> Ongoing
          </p>
        )}
      </td>
      <td className="whitespace-nowrap">
        <p className="font-semibold text-gray-900">{a.segment_code}</p>
        <p className="text-xs text-gray-500">{a.segment_name}</p>
      </td>
      <td className="whitespace-nowrap">
        <p className="font-mono tabular text-sm text-gray-800">
          {formatTick(a.start_tick, tickSeconds)}
          <span className="text-gray-400">{' – '}</span>
          {a.ongoing ? 'now' : formatTick(a.end_tick, tickSeconds)}
        </p>
        <p className="text-xs text-gray-500">{formatDuration(length, tickSeconds)}{a.ongoing ? ' so far' : ''}</p>
      </td>
      <td className="whitespace-nowrap">
        {a.peak_score === null ? (
          <span className="text-xs text-gray-500">Not scored</span>
        ) : (
          <span className="flex items-center gap-2">
            <span className="block h-1.5 w-16 rounded-full bg-gray-100 overflow-hidden" aria-hidden>
              <span className="block h-full rounded-full" style={{ width: `${Math.min(a.peak_score, 1) * 100}%`, background: sev.color }} />
            </span>
            <span className="font-mono tabular text-sm text-gray-700">{a.peak_score.toFixed(2)}</span>
          </span>
        )}
      </td>
      <td className="whitespace-nowrap">
        <span className="inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-semibold" style={{ background: tone.soft, color: tone.color }}>
          {tone.label}
        </span>
        <span className="ml-2 font-mono tabular text-sm text-gray-600">{a.min_trust.toFixed(2)}</span>
      </td>
      <td className="min-w-[16rem] max-w-md">
        <KindIcons kinds={a.kinds} />
        <p className="text-sm text-gray-700 leading-snug mt-1">{a.summary}</p>
      </td>
      <td>
        <div className="flex flex-col gap-1">
          <Link href={`/runs/${a.run_id}?t=${a.start_tick}&seg=${a.segment_code}`}
            className="btn-ghost py-1 px-3 text-sm flex items-center gap-1 w-fit whitespace-nowrap">
            Run view <ArrowUpRight className="w-3.5 h-3.5" aria-hidden />
          </Link>
          <Link href={`/map?run=${a.run_id}&t=${a.start_tick}&seg=${a.segment_code}`}
            className="btn-ghost py-1 px-3 text-sm flex items-center gap-1 w-fit whitespace-nowrap">
            <MapPin className="w-3.5 h-3.5" aria-hidden /> Map
          </Link>
        </div>
      </td>
    </tr>
  );
}
