'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { getRuns, createRun } from '@/lib/api';
import { StatusBadge } from '@/components/ui/StatusBadge';
import { LoadingState, ErrorState } from '@/components/ui/States';
import { useAuth } from '@/contexts/AuthContext';
import { useToast } from '@/components/ui/Toast';
import {
  Activity,
  Play,
  Plus,
  Clock,
  ArrowUpRight,
  Search,
  Filter,
  Database
} from 'lucide-react';

export default function RunsPage() {
  const { isAdmin } = useAuth();
  const { success, error: toastError } = useToast();
  const [runs, setRuns] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [runName, setRunName] = useState('');
  const [runDesc, setRunDesc] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const fetchRuns = async () => {
    try {
      setLoading(true);
      const data = await getRuns();
      setRuns(data || []);
    } catch (e: any) {
      setErr(e.message || 'Failed to fetch simulation runs');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRuns();
  }, []);

  const handleCreateRun = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isAdmin) return;
    setSubmitting(true);
    try {
      const created = await createRun({
        name: runName || `Simulation Run ${Date.now().toString().slice(-4)}`,
        description: runDesc,
      });
      success('Run Created', `Simulation run #${created.id} initialized.`);
      setShowCreateModal(false);
      setRunName('');
      setRunDesc('');
      fetchRuns();
    } catch (e: any) {
      toastError('Failed to create run', e.message);
    } finally {
      setSubmitting(false);
    }
  };

  if (loading && runs.length === 0) {
    return <LoadingState message="Fetching simulation runs history..." />;
  }

  if (err && runs.length === 0) {
    return <ErrorState message={err} onRetry={fetchRuns} />;
  }

  const filteredRuns = runs.filter((r) => {
    const matchesSearch = r.name.toLowerCase().includes(search.toLowerCase()) ||
                          String(r.id).includes(search);
    const matchesStatus = statusFilter === 'all' || r.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 glass-card p-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Activity className="w-6 h-6 text-brand-400" /> Simulation Runs Directory
          </h1>
          <p className="text-xs text-gray-500 mt-1">
            Manage transient flow simulation scenarios, model telemetry passes & historical benchmarks.
          </p>
        </div>

        {isAdmin && (
          <button
            onClick={() => setShowCreateModal(true)}
            className="btn-primary flex items-center gap-2 text-sm font-semibold shrink-0"
          >
            <Plus className="w-4 h-4" /> Launch New Simulation Run
          </button>
        )}
      </div>

      {/* Filter and Search Bar */}
      <div className="glass-card p-4 flex flex-col md:flex-row items-center justify-between gap-4">
        <div className="relative w-full md:w-80">
          <Search className="w-4 h-4 text-gray-500 absolute left-3.5 top-3" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by run name or ID..."
            className="input-field pl-10 py-2 text-xs"
          />
        </div>

        <div className="flex items-center gap-2 text-xs font-medium w-full md:w-auto">
          <Filter className="w-4 h-4 text-gray-500" />
          <span className="text-gray-500">Status:</span>
          {['all', 'active', 'completed', 'failed'].map((st) => (
            <button
              key={st}
              onClick={() => setStatusFilter(st)}
              className={`px-3 py-1.5 rounded-xl capitalize transition-all ${
                statusFilter === st
                  ? 'bg-brand-500 text-dark-950 font-bold'
                  : 'bg-gray-50 text-gray-600 hover:bg-gray-50'
              }`}
            >
              {st}
            </button>
          ))}
        </div>
      </div>

      {/* Runs Table */}
      <div className="glass-card p-6">
        <div className="overflow-x-auto">
          <table className="data-table">
            <thead>
              <tr>
                <th>Run ID</th>
                <th>Scenario Name</th>
                <th>Status</th>
                <th>Start Time</th>
                <th>End Time</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {filteredRuns.map((run) => (
                <tr key={run.id}>
                  <td className="font-mono text-xs font-bold text-brand-400">#{run.id}</td>
                  <td>
                    <div>
                      <p className="font-semibold text-gray-800">{run.name}</p>
                      {run.description && <p className="text-[11px] text-gray-500">{run.description}</p>}
                    </div>
                  </td>
                  <td><StatusBadge status={run.status} size="sm" /></td>
                  <td className="font-mono text-xs text-gray-500">
                    {new Date(run.start_time).toLocaleString()}
                  </td>
                  <td className="font-mono text-xs text-gray-500">
                    {run.end_time ? new Date(run.end_time).toLocaleString() : 'In Progress'}
                  </td>
                  <td>
                    <Link
                      href={`/runs/${run.id}`}
                      className="btn-ghost py-1 px-3 text-xs flex items-center gap-1 w-fit"
                    >
                      Inspect <ArrowUpRight className="w-3.5 h-3.5" />
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Create Run Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-gray-50 backdrop-blur-md animate-fade-in">
          <div className="glass-card p-6 w-full max-w-md border-gray-200 shadow-2xl space-y-4">
            <h2 className="text-lg font-bold text-gray-900 flex items-center gap-2">
              <Play className="w-5 h-5 text-brand-400" /> Launch New Simulation Run
            </h2>
            <form onSubmit={handleCreateRun} className="space-y-4">
              <div>
                <label className="input-label">Run Name</label>
                <input
                  type="text"
                  required
                  value={runName}
                  onChange={(e) => setRunName(e.target.value)}
                  placeholder="e.g., Winter Demand Peak Scenario"
                  className="input-field"
                />
              </div>

              <div>
                <label className="input-label">Description (Optional)</label>
                <textarea
                  value={runDesc}
                  onChange={(e) => setRunDesc(e.target.value)}
                  placeholder="Notes on simulation physics parameters..."
                  className="input-field h-24 resize-none"
                />
              </div>

              <div className="flex items-center justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="btn-secondary text-xs"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="btn-primary text-xs flex items-center gap-2"
                >
                  {submitting ? 'Initializing...' : 'Start Run'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
