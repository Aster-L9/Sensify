'use client';

import React, { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { RUNS_PAGE_LIMIT, getRuns } from '@/lib/api';
import type { RunOut } from '@/lib/types';
import { StatusBadge } from '@/components/ui/StatusBadge';
import { LoadingState, ErrorState, EmptyState } from '@/components/ui/States';
import { useAuth } from '@/contexts/AuthContext';
import { usePolling } from '@/hooks/usePolling';
import { SCENARIO_LABELS, formatDateTime, formatDuration } from '@/lib/detection';
import { Activity, ArrowUpRight, FlaskConical, Search } from 'lucide-react';

const STATUS_FILTERS = [
  { id: 'all', label: 'All runs' },
  { id: 'active', label: 'Playing' },
  { id: 'completed', label: 'Completed' },
];

export default function RunsPage() {
  const { isAdmin } = useAuth();
  const [runs, setRuns] = useState<RunOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');

  const fetchRuns = useCallback(async () => {
    try {
      setRuns(await getRuns());
      setErr(null);
    } catch (e: any) {
      setErr(e.message || 'Could not load runs');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchRuns();
  }, [fetchRuns]);

  usePolling(fetchRuns, 3000, runs.some((r) => r.status === 'active'));

  if (loading && runs.length === 0) return <LoadingState message="Loading runs..." />;
  if (err && runs.length === 0) return <ErrorState message={err} onRetry={fetchRuns} />;

  const query = search.trim().toLowerCase();
  const filtered = runs.filter((r) => {
    const matchesSearch = !query || r.name.toLowerCase().includes(query) || String(r.id).includes(query);
    return matchesSearch && (statusFilter === 'all' || r.status === statusFilter);
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Activity className="w-6 h-6 text-brand-500" aria-hidden /> Simulation runs
          </h1>
          <p className="text-sm text-gray-500 mt-1 max-w-2xl">
            Each run is simulated at launch and plays back at its chosen speed, so everyone watches it unfold together.
          </p>
        </div>
        {isAdmin && (
          <Link href="/scenarios" className="btn-primary flex items-center gap-2 text-sm shrink-0 w-fit">
            <FlaskConical className="w-4 h-4" aria-hidden /> Launch a scenario
          </Link>
        )}
      </div>

      <div className="glass-card p-4 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <label className="relative w-full md:w-80">
          <span className="sr-only">Search runs</span>
          <Search className="w-4 h-4 text-gray-400 absolute left-3.5 top-3" aria-hidden />
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by name or number"
            className="input-field pl-10 py-2 text-sm"
          />
        </label>
        <div className="flex items-center gap-1.5" role="group" aria-label="Filter by status">
          {STATUS_FILTERS.map((f) => (
            <button
              key={f.id}
              onClick={() => setStatusFilter(f.id)}
              aria-pressed={statusFilter === f.id}
              className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${
                statusFilter === f.id ? 'bg-brand-500 text-white font-semibold' : 'text-gray-600 hover:bg-gray-100'
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {filtered.length === 0 ? (
        <EmptyState
          title={runs.length ? 'No runs match' : 'No runs yet'}
          message={runs.length ? 'Try a different search or status.' : 'Launch a scenario to create the first run.'}
        />
      ) : (
        <div className="glass-card overflow-x-auto">
          <table className="data-table">
            <thead>
              <tr>
                <th>Run</th>
                {isAdmin && <th>Scenario</th>}
                <th>Status</th>
                <th>Started</th>
                <th>Length</th>
                <th>Model</th>
                <th><span className="sr-only">Open</span></th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((run) => (
                <tr key={run.id}>
                  <td>
                    <p className="font-semibold text-gray-900">{run.name}</p>
                    {run.description && <p className="text-xs text-gray-500 max-w-xs truncate">{run.description}</p>}
                  </td>
                  {isAdmin && (
                    <td>
                      <p className="text-gray-800">{SCENARIO_LABELS[run.scenario_type ?? 'normal'] ?? run.scenario_type}</p>
                      {run.target_segment && (
                        <p className="text-xs text-gray-500">{run.method?.replace('_', ' ')} at {run.target_segment}</p>
                      )}
                    </td>
                  )}
                  <td>
                    {run.status === 'active' ? (
                      <div className="min-w-[8rem]">
                        <StatusBadge status="active" label={`Playing ${Math.round(run.progress * 100)} %`} size="sm" />
                        <div className="mt-1.5 h-1 rounded-full bg-gray-100 overflow-hidden" aria-hidden>
                          <div className="h-full bg-brand-500 transition-all" style={{ width: `${run.progress * 100}%` }} />
                        </div>
                      </div>
                    ) : (
                      <StatusBadge status="completed" size="sm" />
                    )}
                  </td>
                  <td className="text-sm text-gray-600 whitespace-nowrap">{formatDateTime(run.started_at)}</td>
                  <td className="text-sm text-gray-600 whitespace-nowrap">
                    {formatDuration(run.duration_ticks, run.tick_seconds)}
                    <span className="text-gray-400"> at {run.playback_speed}×</span>
                  </td>
                  <td className="text-sm text-gray-600">{run.model_version ? `v${run.model_version}` : 'Unscored'}</td>
                  <td>
                    <Link href={`/runs/${run.id}`} className="btn-ghost py-1 px-3 text-sm flex items-center gap-1 w-fit">
                      Open <ArrowUpRight className="w-3.5 h-3.5" aria-hidden />
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {runs.length >= RUNS_PAGE_LIMIT && (
            <p className="px-4 py-3 text-xs text-gray-500 border-t border-gray-100">
              Showing the {RUNS_PAGE_LIMIT} most recent runs.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
