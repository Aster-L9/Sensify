'use client';

import React, { useMemo } from 'react';
import {
  Area, AreaChart, CartesianGrid, ComposedChart, Line, ReferenceArea, ReferenceLine,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import { COLORS, STATE_STYLE, formatTick } from '@/lib/detection';
import { CHART_MARGIN, Y_AXIS_WIDTH, xTickFormatter, xTicks } from './chartFrame';

export interface FlagWindow {
  start: number;
  end: number;
  kind: 'anomaly' | 'low_trust';
}

export interface AlarmWindow {
  start: number;
  end: number;
  label: string;
}

interface AnomalyBandChartProps {
  ticks: number[];
  values: (number | null)[];
  actual?: (number | null)[] | null;
  scores?: (number | null)[] | null;
  threshold?: number;
  windows?: FlagWindow[];
  alarms?: AlarmWindow[];
  durationTicks: number;
  cursorTick?: number | null;
  onPickTick?: (tick: number) => void;
  label: string;
  unit: string;
  syncId?: string;
  height?: number;
  showScoreBand?: boolean;
  showXAxis?: boolean;
}

const windowColor = (w: FlagWindow) => (w.kind === 'low_trust' ? STATE_STYLE.low_trust.color : STATE_STYLE.anomalous.color);

/** A reported telemetry line with flagged windows shaded, over a 0–1 anomaly-score band. */
export function AnomalyBandChart({
  ticks, values, actual, scores, threshold = 0.5, windows = [], alarms = [], durationTicks, cursorTick,
  onPickTick, label, unit, syncId, height = 170, showScoreBand = true, showXAxis = false,
}: AnomalyBandChartProps) {
  const data = useMemo(
    () => ticks.map((t, i) => ({ tick: t, value: values[i], actual: actual?.[i] ?? null, score: scores?.[i] ?? null })),
    [ticks, values, actual, scores],
  );
  const domain: [number, number] = [0, Math.max(durationTicks - 1, 1)];
  const handleClick = (e: any) => {
    if (onPickTick && e && typeof e.activeLabel === 'number') onPickTick(e.activeLabel);
  };
  const hasScores = !!scores && scores.length > 0;

  return (
    <figure className="w-full">
      <figcaption className="flex items-baseline justify-between px-1 mb-1">
        <span className="text-sm font-semibold text-gray-800">{label}</span>
        <span className="text-xs text-gray-500">{unit}{actual ? ', dashed line shows actual values' : ''}</span>
      </figcaption>
      <div style={{ height }}>
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={CHART_MARGIN} syncId={syncId} onClick={handleClick}>
            <CartesianGrid stroke={COLORS.grid} vertical={false} />
            <XAxis type="number" dataKey="tick" domain={domain} ticks={xTicks(durationTicks)} hide={!showXAxis || showScoreBand}
              tickFormatter={xTickFormatter} stroke={COLORS.muted} fontSize={11} />
            <YAxis width={Y_AXIS_WIDTH} domain={['auto', 'auto']} stroke={COLORS.muted} fontSize={11}
              tickFormatter={(v: number) => (Math.abs(v) >= 100 ? v.toFixed(0) : v.toFixed(1))} />
            {windows.map((w) => (
              <ReferenceArea key={`${w.kind}-${w.start}`} x1={w.start} x2={Math.max(w.end, w.start + 1)}
                fill={windowColor(w)} fillOpacity={0.12} stroke={windowColor(w)} strokeOpacity={0.35}
                strokeDasharray={w.kind === 'low_trust' ? '5 4' : undefined} ifOverflow="hidden" />
            ))}
            {alarms.map((a) => (
              <ReferenceArea key={`alarm-${a.start}-${a.label}`} x1={a.start} x2={Math.max(a.end, a.start + 1)}
                fill={COLORS.threshold} fillOpacity={0.18} ifOverflow="hidden" />
            ))}
            <Tooltip
              labelFormatter={(t: number) => formatTick(t)}
              formatter={(v: number, name: string) => [v === null || v === undefined ? '—' : `${v.toFixed(2)} ${unit}`, name === 'actual' ? 'Actual' : 'Reported']}
            />
            {actual && (
              <Line type="monotone" dataKey="actual" stroke={COLORS.muted} strokeWidth={1.5} strokeDasharray="4 3"
                dot={false} isAnimationActive={false} connectNulls />
            )}
            <Line type="monotone" dataKey="value" stroke={COLORS.ink} strokeWidth={1.6} dot={false}
              isAnimationActive={false} connectNulls />
            {cursorTick !== null && cursorTick !== undefined && (
              <ReferenceLine x={cursorTick} stroke={COLORS.normal} strokeWidth={1.5} />
            )}
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {showScoreBand && (
        <div className="mt-1" style={{ height: showXAxis ? 74 : 56 }}>
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={CHART_MARGIN} syncId={syncId} onClick={handleClick}>
              <defs>
                <linearGradient id="score-fill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={COLORS.anomalous} stopOpacity={0.55} />
                  <stop offset="100%" stopColor={COLORS.anomalous} stopOpacity={0.08} />
                </linearGradient>
              </defs>
              <XAxis type="number" dataKey="tick" domain={domain} ticks={xTicks(durationTicks)} hide={!showXAxis}
                tickFormatter={xTickFormatter} stroke={COLORS.muted} fontSize={11} />
              <YAxis width={Y_AXIS_WIDTH} domain={[0, 1]} ticks={[0, threshold, 1]} stroke={COLORS.muted} fontSize={10}
                tickFormatter={(v: number) => (v === threshold ? String(threshold) : v.toFixed(0))} />
              {hasScores ? (
                <Area type="monotone" dataKey="score" stroke={COLORS.anomalous} strokeWidth={1.2} fill="url(#score-fill)"
                  isAnimationActive={false} connectNulls />
              ) : null}
              <ReferenceLine y={threshold} stroke={COLORS.threshold} strokeDasharray="5 4" />
              {cursorTick !== null && cursorTick !== undefined && (
                <ReferenceLine x={cursorTick} stroke={COLORS.normal} strokeWidth={1.5} />
              )}
              <Tooltip labelFormatter={(t: number) => formatTick(t)}
                formatter={(v: number) => [v === null || v === undefined ? '—' : v.toFixed(2), 'Anomaly score']} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
      {showScoreBand && !hasScores && (
        <p className="text-xs text-gray-500 px-1 -mt-8 mb-6 text-center">No anomaly scores: this run has not been scored by a model.</p>
      )}
    </figure>
  );
}
