'use client';

import React from 'react';
import Link from 'next/link';
import { ArrowUpRight, X } from 'lucide-react';
import { STATE_STYLE, formatTick } from '@/lib/detection';
import type { AlertItem, RunEvent, Segment, SegmentState, TelemetryPoint } from '@/lib/types';
import { seriesFor } from '@/hooks/useRunData';
import { TrustIndicator } from '@/components/detection/TrustIndicator';
import { AnomalyBandChart, type FlagWindow } from '@/components/detection/AnomalyBandChart';
import { EventStrip } from '@/components/detection/EventStrip';

interface SegmentDetailProps {
  runId: number;
  segment: Segment;
  state: SegmentState | null;
  tick: number;
  durationTicks: number;
  telemetry: TelemetryPoint[];
  scores: number[];
  threshold: number;
  alerts: AlertItem[];
  events: RunEvent[];
  onPickTick: (tick: number) => void;
  onSelectEvent: (event: RunEvent) => void;
  onClose: () => void;
}

const TYPE_LABEL: Record<string, string> = {
  terminal: 'Terminal',
  pipeline: 'Pipeline',
  pump_station: 'Pump station',
  valve_station: 'Valve station',
};

/** One segment at the cursor time: state, readings, trust and its own charts. */
export function SegmentDetail({
  runId, segment, state, tick, durationTicks, telemetry, scores, threshold, alerts, events, onPickTick, onSelectEvent, onClose,
}: SegmentDetailProps) {
  const series = seriesFor(telemetry, segment.id);
  const windows: FlagWindow[] = alerts.filter((a) => a.segment_id === segment.id).map((a) => ({
    start: a.start_tick, end: a.end_tick, kind: a.kinds.includes('low_trust') ? 'low_trust' : 'anomaly',
  }));
  const segEvents = events.filter((e) => e.segment_id === segment.id || e.segment_id === null);
  const style = STATE_STYLE[state?.state ?? 'normal'];
  const Icon = style.icon;

  return (
    <section className="glass-card p-5 space-y-5" aria-label={`${segment.code} details`}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm text-gray-500">{TYPE_LABEL[segment.segment_type] ?? segment.segment_type}, {segment.length_km} km</p>
          <h2 className="text-lg font-bold text-gray-900">{segment.code} {segment.name}</h2>
          <p className="mt-1 inline-flex items-center gap-1.5 text-sm font-semibold" style={{ color: style.textColor }}>
            <Icon className="w-4 h-4" aria-hidden /> {style.label} at <span className="font-mono tabular">{formatTick(tick)}</span>
          </p>
        </div>
        <button onClick={onClose} className="p-2 rounded-lg text-gray-500 hover:bg-gray-100 hover:text-gray-900" aria-label="Close segment details">
          <X className="w-4 h-4" />
        </button>
      </div>

      <dl className="grid grid-cols-3 gap-3 text-sm">
        <Reading label="Pressure" value={state?.pressure_bar} unit="bar" digits={2} />
        <Reading label="Flow" value={state?.flow_m3h} unit="m³/h" digits={0} />
        <Reading label="Temperature" value={state?.temperature_c} unit="°C" digits={1} />
        <Reading label="Anomaly score" value={state?.anomaly_score} unit="" digits={2} />
        {state?.valve_open_pct !== null && state?.valve_open_pct !== undefined && <Reading label="Valve" value={state.valve_open_pct} unit="% open" digits={0} />}
        {state?.pump_speed_pct !== null && state?.pump_speed_pct !== undefined && <Reading label="Pump" value={state.pump_speed_pct} unit="% speed" digits={0} />}
      </dl>

      <div>
        <h3 className="text-sm font-semibold text-gray-800 mb-2">Can these readings be trusted?</h3>
        <TrustIndicator score={state?.trust_score ?? null} status={state?.trust_status ?? null} factors={state?.factors ?? []} compact />
      </div>

      <div className="space-y-2">
        <AnomalyBandChart label="Pressure" unit="bar" ticks={series.ticks} values={series.pressure} windows={windows}
          durationTicks={durationTicks} cursorTick={tick} onPickTick={onPickTick} syncId={`seg-${segment.id}`}
          showScoreBand={false} height={96} />
        <AnomalyBandChart label="Flow and anomaly score" unit="m³/h" ticks={series.ticks} values={series.flow} scores={scores}
          threshold={threshold} windows={windows} durationTicks={durationTicks} cursorTick={tick} onPickTick={onPickTick}
          syncId={`seg-${segment.id}`} height={96} />
        <EventStrip events={segEvents} durationTicks={durationTicks} onSelect={onSelectEvent} syncId={`seg-${segment.id}`} cursorTick={tick} />
      </div>

      <Link href={`/runs/${runId}?t=${tick}&seg=${segment.code}`} className="btn-secondary w-full py-2 text-sm flex items-center justify-center gap-1.5">
        Open in the run view <ArrowUpRight className="w-4 h-4" aria-hidden />
      </Link>
    </section>
  );
}

function Reading({ label, value, unit, digits }: { label: string; value: number | null | undefined; unit: string; digits: number }) {
  return (
    <div className="rounded-xl bg-gray-50 px-3 py-2">
      <dt className="text-xs text-gray-500">{label}</dt>
      <dd className="font-mono tabular text-gray-900">
        {value === null || value === undefined ? '—' : value.toFixed(digits)}
        {unit && <span className="text-xs text-gray-500 font-sans"> {unit}</span>}
      </dd>
    </div>
  );
}
