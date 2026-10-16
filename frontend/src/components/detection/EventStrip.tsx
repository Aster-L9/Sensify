'use client';

import React, { useMemo } from 'react';
import { ReferenceLine, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis } from 'recharts';
import { CATEGORY_STYLE, COLORS, formatTick } from '@/lib/detection';
import type { EventCategory, RunEvent } from '@/lib/types';
import { CHART_MARGIN, Y_AXIS_WIDTH, xTickFormatter, xTicks } from './chartFrame';

const LANE_ORDER: EventCategory[] = ['control', 'security', 'device', 'process', 'analysis'];
const LANE_HEIGHT = 26;

interface EventStripProps {
  events: RunEvent[];
  durationTicks: number;
  onSelect?: (event: RunEvent) => void;
  syncId?: string;
  showXAxis?: boolean;
  cursorTick?: number | null;
}

function Marker(props: any) {
  const { cx, cy, payload } = props;
  if (cx === undefined || cy === undefined) return null;
  const event: RunEvent = payload.event;
  const style = CATEGORY_STYLE[event.category] ?? CATEGORY_STYLE.analysis;
  const r = 6;
  const unauthorized = event.authorized === 'no';
  let shape: React.ReactNode;
  if (style.shape === 'square') {
    shape = <rect x={cx - r} y={cy - r} width={2 * r} height={2 * r} rx={1.5} fill={style.color} />;
  } else if (style.shape === 'triangle') {
    shape = <path d={`M${cx} ${cy - r - 1} L${cx + r + 1} ${cy + r} L${cx - r - 1} ${cy + r} Z`} fill={style.color} />;
  } else if (style.shape === 'diamond') {
    shape = <path d={`M${cx} ${cy - r - 1} L${cx + r + 1} ${cy} L${cx} ${cy + r + 1} L${cx - r - 1} ${cy} Z`} fill={style.color} />;
  } else {
    shape = <circle cx={cx} cy={cy} r={r - 0.5} fill={style.color} />;
  }
  return (
    <g style={{ cursor: 'pointer' }}>
      {unauthorized && <circle cx={cx} cy={cy} r={r + 4} fill="none" stroke={COLORS.critical} strokeWidth={2} />}
      {shape}
    </g>
  );
}

/** Control, security, device and analysis events on the run's time axis, one lane per category. */
export function EventStrip({ events, durationTicks, onSelect, syncId, showXAxis = true, cursorTick }: EventStripProps) {
  const lanes = useMemo(() => LANE_ORDER.filter((c) => events.some((e) => e.category === c)), [events]);
  const points = useMemo(
    () => events.map((e) => ({ tick: e.tick, lane: lanes.indexOf(e.category), event: e })),
    [events, lanes],
  );
  const height = Math.max(lanes.length, 1) * LANE_HEIGHT + (showXAxis ? 26 : 8);

  return (
    <figure className="w-full">
      <figcaption className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5 px-1 mb-1">
        <span className="text-sm font-semibold text-gray-800">Events</span>
        <span className="text-xs text-gray-500">
          {events.length ? 'Select a marker for details; a red ring marks an unauthorized action' : 'No events yet'}
        </span>
      </figcaption>
      <div style={{ height }}>
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart margin={CHART_MARGIN} syncId={syncId}>
            <XAxis type="number" dataKey="tick" domain={[0, Math.max(durationTicks - 1, 1)]} ticks={xTicks(durationTicks)}
              hide={!showXAxis} tickFormatter={xTickFormatter} stroke={COLORS.muted} fontSize={11} />
            <YAxis type="number" dataKey="lane" width={Y_AXIS_WIDTH} domain={[-0.6, Math.max(lanes.length - 0.4, 0.4)]}
              ticks={lanes.map((_, i) => i)} reversed tickLine={false} axisLine={false} interval={0}
              tickFormatter={(i: number) => (lanes[i] ? CATEGORY_STYLE[lanes[i]].label.replace('Sensify analysis', 'Analysis') : '')}
              stroke={COLORS.muted} fontSize={11} />
            {cursorTick !== null && cursorTick !== undefined && (
              <ReferenceLine x={cursorTick} stroke={COLORS.normal} strokeWidth={1.5} />
            )}
            <Tooltip
              cursor={false}
              content={({ payload }: any) => {
                const e: RunEvent | undefined = payload?.[0]?.payload?.event;
                if (!e) return null;
                return (
                  <div className="bg-white/95 border border-gray-200 rounded-xl shadow-lg px-3 py-2 text-xs max-w-xs">
                    <p className="font-semibold text-gray-900">{e.event_type}</p>
                    <p className="text-gray-500">{formatTick(e.tick)} at {e.segment_code ?? 'pipeline'}</p>
                  </div>
                );
              }}
            />
            <Scatter data={points} shape={<Marker />} isAnimationActive={false}
              onClick={(p: any) => p?.event && onSelect?.(p.event)} />
          </ScatterChart>
        </ResponsiveContainer>
      </div>
      {onSelect && events.length > 0 && (
        <ul className="sr-only" aria-label="Run events">
          {events.map((e) => (
            <li key={e.id}>
              <button onClick={() => onSelect(e)}>
                {formatTick(e.tick)}: {e.event_type}{e.authorized === 'no' ? ' (unauthorized)' : ''}
              </button>
            </li>
          ))}
        </ul>
      )}
    </figure>
  );
}
