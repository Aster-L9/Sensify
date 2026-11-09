'use client';

import React, { Suspense, useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { FileSearch, FilterX } from 'lucide-react';
import { getIncidents, getRuns, getTopology } from '@/lib/api';
import type { Classification, IncidentStatus, IncidentSummary, RunOut, Segment, Severity } from '@/lib/types';
import { CATEGORY_STYLE, CLASSIFICATION_ORDER, confidenceWord } from '@/lib/investigation';
import { SEVERITY_STYLE, formatDuration, formatTick } from '@/lib/detection';
import { usePolling } from '@/hooks/usePolling';
import { EmptyState, ErrorState, LoadingState } from '@/components/ui/States';
import { SeverityChip } from '@/components/detection/SeverityChip';
import { ClassificationMark } from '@/components/investigation/ClassificationMark';
import { STATUS_OPTIONS, StatusBadge, statusLabel } from './StatusBadge';

type SortKey = 'detected' | 'severity' | 'confidence';
const SORTS: { id: SortKey; label: string }[] = [
  { id: 'detected', label: 'Detected' },
  { id: 'severity', label: 'Severity' },
  { id: 'confidence', label: 'Confidence' },
];
const SEVERITIES: Severity[] = ['critical', 'high', 'medium'];
const SEV_RANK: Record<string, number> = { critical: 3, high: 2, medium: 1 };

export default function IncidentsPage() {
  return (
    <Suspense fallback={<LoadingState message="Loading incidents..." />}>
      <IncidentsView />
    </Suspense>
  );
}

function IncidentsView() {
  const router = useRouter();
  const pathname = usePathname();
  const search = useSearchParams();
  const classFilter = (search.get('class') ?? search.get('classification')) as Classification | null;
  const statusFilter = search.get('status') as IncidentStatus | null;
  const severityFilter = search.get('severity') as Severity | null;
  // ?run_id= is the form other pages link with; ?run= is what the filter writes.
  const runFilter = search.get('run') ?? search.get('run_id');
  const segFilter = search.get('seg');
  const rawSort = search.get('sort');
  const sort: SortKey = SORTS.some((s) => s.id === rawSort) ? (rawSort as SortKey) : 'detected';
  const order = search.get('order') === 'asc' ? 'asc' : 'desc';

  const [items, setItems] = useState<IncidentSummary[] | null>(null);
  const [runs, setRuns] = useState<RunOut[]>([]);
  const [segments, setSegments] = useState<Segment[]>([]);
  const [err, setErr] = useState<string | null>(null);

  const setParam = useCallback((key: string, value: string | null) => {
    const next = new URLSearchParams(search.toString());
    if (key === 'run') next.delete('run_id');
    if (value) next.set(key, value);
    else next.delete(key);
    const q = next.toString();
    router.replace(q ? `${pathname}?${q}` : pathname, { scroll: false });
  }, [search, router, pathname]);

  useEffect(() => {
    getTopology().then((t) => setSegments(t.segments)).catch(() => undefined);
  }, []);

  const fetchAll = useCallback(async () => {
    try {
      const [list, runList] = await Promise.all([
        getIncidents({
          runId: runFilter && /^\d+$/.test(runFilter) ? Number(runFilter) : undefined,
          classification: classFilter ?? undefined,
          status: statusFilter ?? undefined,
          severity: severityFilter ?? undefined,
          segment: segFilter ?? undefined,
          sort, order, limit: 200,
        }),
        getRuns(),
      ]);
      setItems(list);
      setRuns(runList);
      setErr(null);
    } catch (e: any) {
      setErr(e.message || 'Could not load incidents');
    }
  }, [runFilter, classFilter, statusFilter, severityFilter, segFilter, sort, order]);

  useEffect(() => { fetchAll(); }, [fetchAll]);
  usePolling(fetchAll, 3000, runs.some((r) => r.status === 'active'));

  const runsById = useMemo(() => new Map(runs.map((r) => [r.id, r])), [runs]);
  const shown = useMemo(() => {
    const dir = order === 'asc' ? 1 : -1;
    return [...(items ?? [])].sort((a, b) => {
      const d = sort === 'severity' ? (SEV_RANK[a.severity] ?? 0) - (SEV_RANK[b.severity] ?? 0)
        : sort === 'confidence' ? a.confidence - b.confidence
        : a.detected_time.localeCompare(b.detected_time) || a.detected_tick - b.detected_tick;
      return d * dir;
    });
  }, [items, sort, order]);
  const filtered = Boolean(classFilter || statusFilter || severityFilter || runFilter || segFilter);

  if (items === null && !err) return <LoadingState message="Loading incidents..." />;
  if (err && items === null) return <ErrorState message={err} onRetry={fetchAll} />;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-[28px] leading-tight text-gray-900">Incidents</h1>
        <p className="text-sm text-gray-500 mt-1 max-w-2xl">
          Flagged windows and events grouped into incidents, each with a classification, a confidence and the
          evidence behind it. Open one to investigate.
        </p>
      </div>

      <div className="glass-card p-4 space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
          <Select label="Classification" value={classFilter ?? ''} onChange={(v) => setParam('class', v || null)} all="All classifications">
            {CLASSIFICATION_ORDER.map((c) => <option key={c} value={c}>{CATEGORY_STYLE[c].label}</option>)}
          </Select>
          <Select label="Status" value={statusFilter ?? ''} onChange={(v) => setParam('status', v || null)} all="All statuses">
            {STATUS_OPTIONS.map((s) => <option key={s} value={s}>{statusLabel(s)}</option>)}
          </Select>
          <Select label="Severity" value={severityFilter ?? ''} onChange={(v) => setParam('severity', v || null)} all="All severities">
            {SEVERITIES.map((s) => <option key={s} value={s}>{SEVERITY_STYLE[s].label}</option>)}
          </Select>
          <Select label="Run" value={runFilter ?? ''} onChange={(v) => setParam('run', v || null)} all="All runs">
            {runs.map((r) => <option key={r.id} value={r.id}>{r.name}{r.status === 'active' ? ' (playing)' : ''}</option>)}
          </Select>
          <Select label="Segment" value={segFilter ?? ''} onChange={(v) => setParam('seg', v || null)} all="All segments">
            {segments.map((s) => <option key={s.id} value={s.code}>{s.code}, {s.name}</option>)}
          </Select>
        </div>
        <div className="flex flex-wrap items-end justify-between gap-3 pt-3 border-t border-gray-100">
          <div className="flex flex-wrap items-end gap-3">
            <Select label="Sort by" value={sort} onChange={(v) => setParam('sort', v === 'detected' ? null : v)}>
              {SORTS.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}
            </Select>
            <Select label="Order" value={order} onChange={(v) => setParam('order', v === 'desc' ? null : v)}>
              <option value="desc">Highest or newest first</option>
              <option value="asc">Lowest or oldest first</option>
            </Select>
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
          title={filtered ? 'No incidents match these filters' : 'No incidents yet'}
          message={filtered
            ? 'Try another classification, status, run or segment.'
            : 'When Sensify groups flagged activity into an incident, it appears here. Runs with nothing flagged have none.'}
        />
      ) : (
        <div className="glass-card overflow-x-auto">
          <table className="data-table">
            <caption className="sr-only">Incidents, sorted by {sort}</caption>
            <thead>
              <tr>
                <th>Classification</th>
                <th>Confidence</th>
                <th>Location</th>
                <th>Run</th>
                <th>Detected</th>
                <th>Duration</th>
                <th>Severity</th>
                <th>Status</th>
                <th>Evidence</th>
              </tr>
            </thead>
            <tbody>
              {shown.map((i) => {
                const tickSeconds = runsById.get(i.run_id)?.tick_seconds;
                return (
                  <tr key={i.key}>
                    <td>
                      <Link href={`/incidents/${encodeURIComponent(i.key)}`} className="hover:underline">
                        <ClassificationMark classification={i.classification} size="sm" />
                      </Link>
                    </td>
                    <td className="whitespace-nowrap text-sm">
                      <span className="tabular">{Math.round(i.confidence * 100)} %</span>{' '}
                      <span className="text-gray-500">{confidenceWord(i.confidence)}</span>
                    </td>
                    <td className="whitespace-nowrap">
                      {i.segment_code ? (
                        <>
                          <p className="font-semibold text-gray-900">{i.segment_code}</p>
                          <p className="text-xs text-gray-500">{i.segment_name}</p>
                        </>
                      ) : (
                        <span className="text-sm text-gray-500">Not localised</span>
                      )}
                    </td>
                    <td className="text-sm">
                      <Link href={`/runs/${i.run_id}`} className="text-gray-900 hover:text-brand-600 hover:underline">{i.run_name}</Link>
                    </td>
                    <td className="whitespace-nowrap">
                      <p className="font-mono tabular text-sm text-gray-800">{formatTick(i.detected_tick, tickSeconds)}</p>
                      <p className="text-xs text-gray-500">{new Date(i.detected_time).toLocaleTimeString()}</p>
                    </td>
                    <td className="whitespace-nowrap text-sm text-gray-700">
                      {formatDuration(i.end_tick - i.start_tick + 1, tickSeconds)}{i.developing ? ' so far' : ''}
                    </td>
                    <td><SeverityChip severity={i.severity} /></td>
                    <td><StatusBadge status={i.developing ? 'developing' : i.status} /></td>
                    <td className="tabular text-sm text-gray-700">{i.evidence_count}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function Select({ label, value, onChange, all, children }: {
  label: string; value: string; onChange: (v: string) => void; all?: string; children: React.ReactNode;
}) {
  return (
    <label className="text-sm">
      <span className="block text-xs font-semibold text-gray-600 mb-1">{label}</span>
      <select value={value} onChange={(e) => onChange(e.target.value)} className="input-field py-2 text-sm">
        {all !== undefined && <option value="">{all}</option>}
        {children}
      </select>
    </label>
  );
}
