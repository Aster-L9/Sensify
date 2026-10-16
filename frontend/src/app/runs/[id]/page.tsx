'use client';

import React, { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { getRun, getTelemetry } from '@/lib/api';
import { StatusBadge } from '@/components/ui/StatusBadge';
import { LoadingState, ErrorState } from '@/components/ui/States';
import {
  Activity,
  Gauge,
  Wind,
  Thermometer,
  Clock,
  ArrowLeft,
  RefreshCw,
  Layers
} from 'lucide-react';
import Link from 'next/link';
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts';

export default function RunDetailPage() {
  const params = useParams();
  const runId = Number(params?.id);

  const [run, setRun] = useState<any>(null);
  const [telemetry, setTelemetry] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  const fetchRunData = async () => {
    if (!runId) return;
    try {
      setLoading(true);
      const [runData, telemData] = await Promise.all([
        getRun(runId),
        getTelemetry(runId, undefined, 50)
      ]);
      setRun(runData);
      setTelemetry(telemData || []);
    } catch (e: any) {
      setErr(e.message || 'Failed to load run details');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRunData();
  }, [runId]);

  if (loading && !run) {
    return <LoadingState message={`Fetching Telemetry Data for Run #${runId}...`} />;
  }

  if (err || !run) {
    return <ErrorState message={err || 'Run not found'} />;
  }

  // Format telemetry for chart display
  const chartData = telemetry.slice().reverse().map((t) => ({
    time: new Date(t.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
    pressure: t.pressure_bar,
    flow: t.flow_m3h,
    temp: t.temp_c,
    segmentId: t.segment_id
  }));

  return (
    <div className="space-y-6">
      {/* Top Navigation & Actions */}
      <div className="flex items-center justify-between">
        <Link href="/runs" className="text-xs font-semibold text-gray-500 hover:text-gray-900 flex items-center gap-1.5">
          <ArrowLeft className="w-4 h-4" /> Back to Runs
        </Link>
        <button
          onClick={fetchRunData}
          className="btn-secondary py-1.5 px-3 text-xs flex items-center gap-1.5"
        >
          <RefreshCw className="w-3.5 h-3.5" /> Refresh Telemetry
        </button>
      </div>

      {/* Run Overview Header */}
      <div className="glass-card p-6 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-mono font-bold text-brand-400">RUN #{run.id}</span>
            <StatusBadge status={run.status} size="sm" />
          </div>
          <h1 className="text-2xl font-bold text-gray-900">{run.name}</h1>
          {run.description && <p className="text-xs text-gray-500 mt-1">{run.description}</p>}
        </div>

        <div className="flex items-center gap-6 text-xs text-gray-500 border-t md:border-t-0 md:border-l border-gray-200 pt-3 md:pt-0 md:pl-6 font-mono">
          <div>
            <span className="text-[10px] uppercase text-gray-500 block">Start Time</span>
            <span className="text-gray-800">{new Date(run.start_time).toLocaleString()}</span>
          </div>
          <div>
            <span className="text-[10px] uppercase text-gray-500 block">Total Data Points</span>
            <span className="text-gray-800">{telemetry.length} Records</span>
          </div>
        </div>
      </div>

      {/* Live Telemetry Line Chart */}
      <div className="glass-card p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-semibold text-gray-900 flex items-center gap-2">
            <Activity className="w-4 h-4 text-brand-400" /> Real-time Pressure & Flow Telemetry Stream
          </h2>
          <span className="text-xs text-gray-500 font-mono">50 latest readings</span>
        </div>

        <div className="h-72 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f293d" vertical={false} />
              <XAxis dataKey="time" stroke="#64748b" fontSize={11} tickLine={false} />
              <YAxis yAxisId="left" stroke="#64748b" fontSize={11} tickLine={false} />
              <YAxis yAxisId="right" orientation="right" stroke="#64748b" fontSize={11} tickLine={false} />
              <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '12px', fontSize: '12px' }} />
              <Line yAxisId="left" type="monotone" dataKey="pressure" stroke="#7169d5" strokeWidth={2} dot={false} name="Pressure (Bar)" />
              <Line yAxisId="right" type="monotone" dataKey="flow" stroke="#b09fe8" strokeWidth={2} dot={false} name="Flow Rate (m³/h)" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Raw Telemetry Data Log Table */}
      <div className="glass-card p-6">
        <h2 className="text-base font-semibold text-gray-900 mb-4 flex items-center gap-2">
          <Layers className="w-4 h-4 text-brand-400" /> Sensor Stream Records
        </h2>

        <div className="overflow-x-auto">
          <table className="data-table">
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>Segment ID</th>
                <th>Pressure (Bar)</th>
                <th>Flow Rate (m³/h)</th>
                <th>Temperature (°C)</th>
              </tr>
            </thead>
            <tbody>
              {telemetry.map((t) => (
                <tr key={t.id}>
                  <td className="font-mono text-xs text-gray-500">{new Date(t.timestamp).toLocaleString()}</td>
                  <td className="font-mono text-xs font-semibold text-brand-400">Segment #{t.segment_id}</td>
                  <td className="font-mono text-xs font-bold text-emerald-400">{t.pressure_bar?.toFixed(2)} Bar</td>
                  <td className="font-mono text-xs text-blue-400">{t.flow_m3h?.toFixed(0)} m³/h</td>
                  <td className="font-mono text-xs text-amber-400">{t.temp_c?.toFixed(1)} °C</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
