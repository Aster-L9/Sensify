'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import {
  getDashboardSummary,
  getActivity,
  getRuns,
  createRun
} from '@/lib/api';
import { KPITile } from '@/components/ui/KPITile';
import { StatusBadge } from '@/components/ui/StatusBadge';
import { LoadingState, ErrorState } from '@/components/ui/States';
import { useAuth } from '@/contexts/AuthContext';
import { useToast } from '@/components/ui/Toast';
import {
  Activity,
  AlertTriangle,
  ShieldCheck,
  Gauge,
  Wind,
  Thermometer,
  Play,
  ArrowUpRight,
  Zap,
  History,
  MapPin,
  Clock,
  Layers
} from 'lucide-react';
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts';

export default function DashboardPage() {
  const { isAdmin } = useAuth();
  const { success, error: toastError } = useToast();
  const [summary, setSummary] = useState<any>(null);
  const [activities, setActivities] = useState<any[]>([]);
  const [recentRuns, setRecentRuns] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [creatingRun, setCreatingRun] = useState(false);

  const fetchData = async () => {
    try {
      setLoading(true);
      setErr(null);
      const [sumData, actData, runsData] = await Promise.all([
        getDashboardSummary(),
        getActivity(10),
        getRuns()
      ]);
      setSummary(sumData);
      setActivities(actData);
      setRecentRuns(runsData);
    } catch (e: any) {
      setErr(e.message || 'Failed to fetch dashboard telemetry');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 10000);
    return () => clearInterval(interval);
  }, []);

  const handleLaunchRun = async () => {
    if (!isAdmin) return;
    setCreatingRun(true);
    try {
      const newRun = await createRun({
        name: `Simulation Run ${Date.now().toString().slice(-4)}`,
        description: 'Manual live trigger from dashboard',
      });
      success('Run Started', `Simulation Run #${newRun.id} is now active.`);
      fetchData();
    } catch (e: any) {
      toastError('Failed to start run', e.message);
    } finally {
      setCreatingRun(false);
    }
  };

  if (loading && !summary) {
    return <LoadingState message="Connecting to Master Gas System live telemetry..." />;
  }

  if (err && !summary) {
    return <ErrorState message={err} onRetry={fetchData} />;
  }

  // Generate chart sparkline data from active run or mock trends
  const telemetryTrends = [
    { time: '00:00', pressure: 72.1, flow: 1450, temp: 42.0 },
    { time: '04:00', pressure: 74.5, flow: 1520, temp: 43.5 },
    { time: '08:00', pressure: 71.8, flow: 1390, temp: 45.1 },
    { time: '12:00', pressure: 76.2, flow: 1610, temp: 48.2 },
    { time: '16:00', pressure: 75.0, flow: 1580, temp: 46.8 },
    { time: '20:00', pressure: 73.4, flow: 1490, temp: 44.1 },
  ];

  return (
    <div className="space-y-6">
      {/* Page Header Banner */}
      <div className="glass-card p-0 overflow-hidden border-brand-200/40">
        <img
          src="/Banner.png"
          alt="Master Gas System Pipeline Network"
          className="w-full h-auto max-h-[300px] object-cover"
        />
      </div>

      {/* Launch Simulation Run Button - moved to top actions */}
      {isAdmin && (
        <div className="flex justify-end">
          <button
            onClick={handleLaunchRun}
            disabled={creatingRun}
            className="btn-primary flex items-center gap-2 text-sm font-semibold"
          >
            <Play className="w-4 h-4 fill-white" />
            {creatingRun ? 'Launching Run...' : 'Launch Simulation Run'}
          </button>
        </div>
      )}

      {/* Primary KPI Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <KPITile
          title="Total Pipelines"
          value={summary?.total_segments || 0}
          unit="Segments"
          subtitle="Operational status"
          icon={Layers}
          accentColor="#7169d5"
          status="operational"
        />

        <KPITile
          title="Avg System Pressure"
          value={summary?.avg_pressure_bar?.toFixed(1) || '0.0'}
          unit="Bar"
          change={+1.4}
          changePeriod="nominal range 60-80"
          icon={Gauge}
          accentColor="#b09fe8"
          status="operational"
        />

        <KPITile
          title="Total Gas Flow Rate"
          value={summary?.total_flow_m3h?.toLocaleString() || '0'}
          unit="m³/h"
          change={+2.8}
          icon={Wind}
          accentColor="#10b981"
          status="operational"
        />

        <KPITile
          title="Active System Incidents"
          value={summary?.active_incidents || 0}
          unit="Alerts"
          subtitle={summary?.active_incidents > 0 ? 'Requires attention' : 'All systems nominal'}
          icon={AlertTriangle}
          accentColor={summary?.active_incidents > 0 ? '#ef4444' : '#10b981'}
          status={summary?.active_incidents > 0 ? 'critical' : 'operational'}
        />
      </div>

      {/* Main Content Grid: Telemetry Trends & Network Health */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Real-time Telemetry Trend Graph */}
        <div className="lg:col-span-2 glass-card p-6 flex flex-col justify-between">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-base font-semibold text-gray-900 flex items-center gap-2">
                <Activity className="w-4 h-4 text-brand-400" /> Network Telemetry Overview
              </h2>
              <p className="text-xs text-gray-500">Average pressure (Bar) vs Gas Flow Rate (m³/h) trend</p>
            </div>
            <div className="flex items-center gap-2 text-xs font-mono">
              <span className="flex items-center gap-1 text-brand-400">
                <span className="w-2 h-2 rounded-full bg-brand-400" /> Pressure
              </span>
              <span className="flex items-center gap-1 text-blue-400">
                <span className="w-2 h-2 rounded-full bg-blue-400" /> Flow Rate
              </span>
            </div>
          </div>

          <div className="h-64 w-full mt-2">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={telemetryTrends} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="colorPressure" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#7169d5" stopOpacity={0.4}/>
                    <stop offset="95%" stopColor="#7169d5" stopOpacity={0}/>
                  </linearGradient>
                  <linearGradient id="colorFlow" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#b09fe8" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="#b09fe8" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" vertical={false} />
                <XAxis dataKey="time" stroke="#9ca3af" fontSize={11} tickLine={false} />
                <YAxis yAxisId="left" stroke="#9ca3af" fontSize={11} tickLine={false} domain={[60, 90]} />
                <YAxis yAxisId="right" orientation="right" stroke="#9ca3af" fontSize={11} tickLine={false} />
                <Tooltip contentStyle={{ backgroundColor: '#ffffff', borderColor: '#e5e7eb', borderRadius: '12px', fontSize: '12px', color: '#374151' }} />
                <Area yAxisId="left" type="monotone" dataKey="pressure" stroke="#7169d5" strokeWidth={2} fillOpacity={1} fill="url(#colorPressure)" name="Pressure (Bar)" />
                <Area yAxisId="right" type="monotone" dataKey="flow" stroke="#b09fe8" strokeWidth={2} fillOpacity={1} fill="url(#colorFlow)" name="Flow Rate (m³/h)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Status Distribution Summary Card */}
        <div className="glass-card p-6 flex flex-col justify-between">
          <div>
            <h2 className="text-base font-semibold text-gray-900 mb-1 flex items-center gap-2">
              <Zap className="w-4 h-4 text-brand-400" /> Pipeline Segment Status
            </h2>
            <p className="text-xs text-gray-500 mb-4">Breakdown of network assets health</p>

            <div className="space-y-3">
              <div className="flex items-center justify-between p-3 rounded-xl bg-gray-50 border border-brand-500/20">
                <span className="text-xs font-medium text-brand-500 flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-brand-500 shadow-[0_0_8px_rgba(113,105,213,0.6)]" /> Operational
                </span>
                <span className="text-sm font-bold font-mono text-gray-900">
                  {summary?.segment_status_counts?.operational || 0}
                </span>
              </div>

              <div className="flex items-center justify-between p-3 rounded-xl bg-gray-50 border border-accent-peach/20">
                <span className="text-xs font-medium text-accent-peach flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-accent-peach" /> Warning Threshold
                </span>
                <span className="text-sm font-bold font-mono text-gray-900">
                  {summary?.segment_status_counts?.warning || 0}
                </span>
              </div>

              <div className="flex items-center justify-between p-3 rounded-xl bg-gray-50 border border-red-500/20">
                <span className="text-xs font-medium text-red-400 flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-red-400 animate-pulse" /> Critical Incident
                </span>
                <span className="text-sm font-bold font-mono text-gray-900">
                  {summary?.segment_status_counts?.critical || 0}
                </span>
              </div>
            </div>
          </div>

          <Link
            href="/map"
            className="btn-secondary w-full text-xs font-semibold py-2.5 text-center mt-6 flex items-center justify-center gap-2"
          >
            <MapPin className="w-4 h-4 text-brand-400" /> Explore GIS Pipeline Map
          </Link>
        </div>
      </div>

      {/* Bottom Section: Active Simulation Runs & System Audit Log */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Active Runs Panel */}
        <div className="glass-card p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-base font-semibold text-gray-900 flex items-center gap-2">
              <Activity className="w-4 h-4 text-brand-400" /> Simulation Runs
            </h2>
            <Link href="/runs" className="text-xs text-brand-400 hover:underline flex items-center gap-1 font-medium">
              View All Runs <ArrowUpRight className="w-3.5 h-3.5" />
            </Link>
          </div>

          <div className="space-y-2">
            {recentRuns.slice(0, 4).map((run) => (
              <div
                key={run.id}
                className="flex items-center justify-between p-3 rounded-xl bg-gray-50 border border-gray-200 hover:border-gray-200 transition-colors"
              >
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg bg-gray-50 flex items-center justify-center font-mono font-bold text-xs text-brand-400">
                    #{run.id}
                  </div>
                  <div>
                    <h3 className="text-xs font-semibold text-gray-800">{run.name}</h3>
                    <p className="text-[10px] text-gray-500 font-mono">
                      Started: {new Date(run.start_time).toLocaleString()}
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  <StatusBadge status={run.status} size="sm" />
                  <Link
                    href={`/runs/${run.id}`}
                    className="p-1.5 rounded-lg bg-gray-50 hover:bg-gray-50 text-gray-600 transition-colors"
                  >
                    <ArrowUpRight className="w-4 h-4" />
                  </Link>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Audit Log / Activity Panel */}
        <div className="glass-card p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-base font-semibold text-gray-900 flex items-center gap-2">
              <History className="w-4 h-4 text-brand-400" /> Recent System Activity
            </h2>
            <span className="text-xs text-gray-500 font-mono">Real-time log</span>
          </div>

          <div className="space-y-3 max-h-[220px] overflow-y-auto pr-1">
            {activities.map((act) => (
              <div key={act.id} className="flex items-start gap-3 text-xs border-b border-gray-200 pb-2.5 last:border-0">
                <div className="w-2 h-2 rounded-full bg-brand-400 mt-1 shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-gray-600 font-medium">{act.action}</p>
                  {act.details && <p className="text-[11px] text-gray-500 truncate mt-0.5">{act.details}</p>}
                </div>
                <span className="text-[10px] text-gray-500 font-mono whitespace-nowrap">
                  {new Date(act.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
