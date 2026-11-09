'use client';

import React, { useEffect, useMemo, useRef, useState } from 'react';
import { CATEGORY_STYLE, COLORS, formatTick } from '@/lib/detection';
import type { ChainStage, EvidenceItem } from '@/lib/types';
import { CHART_MARGIN, Y_AXIS_WIDTH, xTickFormatter, xTicks } from '@/components/detection/chartFrame';

type LaneId = 'control' | 'equipment' | 'process' | 'trust' | 'findings';

const LANES: { id: LaneId; label: string; style: keyof typeof CATEGORY_STYLE }[] = [
  { id: 'control', label: 'Control and security', style: 'control' },
  { id: 'equipment', label: 'Equipment', style: 'device' },
  { id: 'process', label: 'Process', style: 'process' },
  { id: 'trust', label: 'Trust', style: 'security' },
  { id: 'findings', label: 'Sensify findings', style: 'analysis' },
];

const LANE_HEIGHT = 30;
const CHIP_H = 22;
const CHIP_W = 124;
const CHIP_GAP = 6;
const AXIS_H = 24;

function laneFor(e: EvidenceItem): LaneId {
  switch (e.kind) {
    case 'control event':
    case 'security event':
      return 'control';
    case 'equipment state':
    case 'device event':
    case 'setpoint departure':
      return 'equipment';
    case 'telemetry anomaly':
      return 'process';
    case 'trust drop':
    case 'consistency check':
      return 'trust';
    default:
      return 'findings';
  }
}

function Shape({ shape, cx, cy, color, ring }: { shape: string; cx: number; cy: number; color: string; ring: boolean }) {
  const r = 6;
  let node: React.ReactNode;
  if (shape === 'square') node = <rect x={cx - r} y={cy - r} width={2 * r} height={2 * r} rx={1.5} fill={color} />;
  else if (shape === 'triangle') node = <path d={`M${cx} ${cy - r - 1} L${cx + r + 1} ${cy + r} L${cx - r - 1} ${cy + r} Z`} fill={color} />;
  else if (shape === 'diamond') node = <path d={`M${cx} ${cy - r - 1} L${cx + r + 1} ${cy} L${cx} ${cy + r + 1} L${cx - r - 1} ${cy} Z`} fill={color} />;
  else node = <circle cx={cx} cy={cy} r={r - 0.5} fill={color} />;
  return (
    <>
      {ring && <circle cx={cx} cy={cy} r={r + 4} fill="none" stroke={COLORS.critical} strokeWidth={2} />}
      {node}
    </>
  );
}

interface EvidenceRailProps {
  durationTicks: number;
  evidence: EvidenceItem[];
  chain?: ChainStage[];
  onSelect?: (item: EvidenceItem) => void;
  cursorTick?: number | null;
}

/**
 * The signature element: evidence on the run's time axis, one lane per source, with the
 * attack-to-impact chain above it. Shares the chart frame so it lines up with Sprint 2 charts.
 */
const stageKey = (s: ChainStage) => `${s.stage}-${s.tick}`;

export function EvidenceRail({ durationTicks, evidence, chain = [], onSelect, cursorTick }: EvidenceRailProps) {
  const ref = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(640);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    setWidth(el.clientWidth || 640);
    if (typeof ResizeObserver === 'undefined') return;
    const ro = new ResizeObserver((entries) => setWidth(entries[0].contentRect.width || 640));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const lanes = useMemo(() => LANES.filter((l) => evidence.some((e) => laneFor(e) === l.id)), [evidence]);

  const plotLeft = Y_AXIS_WIDTH + CHART_MARGIN.left;
  const plotRight = Math.max(width - CHART_MARGIN.right, plotLeft + 10);
  const span = Math.max(durationTicks - 1, 1);
  const xOf = (t: number) => plotLeft + (Math.min(Math.max(t, 0), span) / span) * (plotRight - plotLeft);

  // Chain chips: greedy rows so neighbouring chips never overlap.
  const chips = useMemo(() => {
    const rowEnds: number[] = [];
    return chain.map((s) => {
      const tickX = xOf(s.tick);
      const x = Math.min(Math.max(tickX - CHIP_W / 2, plotLeft), Math.max(plotRight - CHIP_W, plotLeft));
      let row = rowEnds.findIndex((end) => x >= end + CHIP_GAP);
      if (row === -1) row = rowEnds.length;
      rowEnds[row] = x + CHIP_W;
      return { stage: s, x, row, tickX };
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chain, width, durationTicks]);

  const chipRows = chips.length ? Math.max(...chips.map((c) => c.row)) + 1 : 0;
  const chainH = chipRows * (CHIP_H + CHIP_GAP) + (chipRows ? 6 : 0);
  const lanesTop = chainH + CHART_MARGIN.top;
  const height = lanesTop + Math.max(lanes.length, 1) * LANE_HEIGHT + AXIS_H;
  const axisY = lanesTop + Math.max(lanes.length, 1) * LANE_HEIGHT;
  const ticks = xTicks(durationTicks);

  const byId = useMemo(() => new Map(evidence.map((e) => [e.id, e])), [evidence]);

  return (
    <figure className="w-full">
      <figcaption className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5 px-1 mb-1">
        <span className="text-sm font-semibold text-gray-800">Evidence rail</span>
        <span className="text-xs text-gray-500">
          {evidence.length ? 'Select a marker for details; a red ring marks an unauthorized action' : 'No evidence yet'}
        </span>
      </figcaption>
      <div ref={ref} className="w-full">
        <svg width={width} height={height} role="img" aria-label="Evidence on the run timeline" className="block">
          {/* time grid */}
          {ticks.map((t) => (
            <line key={t} x1={xOf(t)} x2={xOf(t)} y1={lanesTop} y2={axisY} stroke={COLORS.grid} strokeWidth={1} />
          ))}

          {/* lanes */}
          {lanes.map((l, i) => {
            const y = lanesTop + i * LANE_HEIGHT;
            return (
              <g key={l.id}>
                {i % 2 === 0 && <rect x={plotLeft} y={y} width={plotRight - plotLeft} height={LANE_HEIGHT} fill="#F9FAFB" />}
                <text x={plotLeft - 8} y={y + LANE_HEIGHT / 2} textAnchor="end" dominantBaseline="middle" fontSize={11} fill={COLORS.muted}>
                  {l.label.length > 11 ? l.label.split(' ')[0] : l.label}
                  <title>{l.label}</title>
                </text>
              </g>
            );
          })}

          {/* axis */}
          <line x1={plotLeft} x2={plotRight} y1={axisY} y2={axisY} stroke={COLORS.muted} strokeWidth={1} />
          {ticks.map((t) => (
            <text key={t} x={xOf(t)} y={axisY + 15} textAnchor="middle" fontSize={11} fill={COLORS.muted}>
              {xTickFormatter(t)}
            </text>
          ))}

          {/* chain connectors, then chips */}
          {chips.map((c, i) => (
            <line key={`l-${stageKey(c.stage)}`} x1={c.tickX} x2={c.tickX} y1={6 + c.row * (CHIP_H + CHIP_GAP) + CHIP_H} y2={lanesTop}
              stroke="#A5A4D8" strokeWidth={1} strokeDasharray="3 3" />
          ))}
          {chips.slice(1).map((c, i) => {
            const p = chips[i];
            return (
              <line key={`a-${stageKey(p.stage)}-${stageKey(c.stage)}`} x1={p.x + CHIP_W} y1={6 + p.row * (CHIP_H + CHIP_GAP) + CHIP_H / 2}
                x2={c.x} y2={6 + c.row * (CHIP_H + CHIP_GAP) + CHIP_H / 2} stroke="#7169D5" strokeWidth={1.5} />
            );
          })}
          {chips.map((c, i) => {
            const y = 6 + c.row * (CHIP_H + CHIP_GAP);
            const target = c.stage.evidence_ids.map((id) => byId.get(id)).find(Boolean);
            return (
              <g key={`c-${stageKey(c.stage)}`} style={{ cursor: target && onSelect ? 'pointer' : 'default' }}
                onClick={() => target && onSelect?.(target)}>
                <rect x={c.x} y={y} width={CHIP_W} height={CHIP_H} rx={8} fill="#EEF0FB" stroke="#7169D5" />
                <text x={c.x + CHIP_W / 2} y={y + CHIP_H / 2} textAnchor="middle" dominantBaseline="middle" fontSize={11} fill="#4B4AA3">
                  {i + 1}. {c.stage.label.length > 17 ? `${c.stage.label.slice(0, 16)}…` : c.stage.label}
                  <title>{`${c.stage.label}, ${formatTick(c.stage.tick)}`}</title>
                </text>
              </g>
            );
          })}

          {cursorTick !== null && cursorTick !== undefined && (
            <line x1={xOf(cursorTick)} x2={xOf(cursorTick)} y1={lanesTop} y2={axisY} stroke={COLORS.normal} strokeWidth={1.5} />
          )}

          {/* evidence markers */}
          {evidence.map((e) => {
            const lane = laneFor(e);
            const li = lanes.findIndex((l) => l.id === lane);
            if (li < 0) return null;
            const cy = lanesTop + li * LANE_HEIGHT + LANE_HEIGHT / 2;
            const base = CATEGORY_STYLE[LANES[LANES.findIndex((l) => l.id === lane)].style];
            const unauthorized = e.supports?.cyber_manipulation !== undefined && e.supports.cyber_manipulation >= 0.5 && lane === 'control';
            const shape = lane === 'control' && e.kind === 'security event' ? 'triangle' : base.shape;
            const color = lane === 'control' && e.kind === 'security event' ? CATEGORY_STYLE.security.color : base.color;
            const x1 = xOf(e.tick);
            const x2 = xOf(e.end_tick);
            return (
              <g key={e.id} style={{ cursor: onSelect ? 'pointer' : 'default' }} onClick={() => onSelect?.(e)}>
                {x2 - x1 > 3 && <rect x={x1} y={cy - 2} width={x2 - x1} height={4} rx={2} fill={color} opacity={0.35} />}
                <Shape shape={shape} cx={x1} cy={cy} color={color} ring={unauthorized} />
                <title>{`${formatTick(e.tick)}: ${e.observation}`}</title>
              </g>
            );
          })}
        </svg>
      </div>
      {evidence.length > 0 && (
        <ul className="sr-only" aria-label="Evidence items">
          {chain.map((s, i) => (
            <li key={`chain-${stageKey(s)}`}>Stage {i + 1}: {s.label} at {formatTick(s.tick)}</li>
          ))}
          {evidence.map((e) => (
            <li key={e.id}>
              {onSelect ? (
                <button onClick={() => onSelect(e)}>{formatTick(e.tick)}: {e.observation}</button>
              ) : (
                <span>{formatTick(e.tick)}: {e.observation}</span>
              )}
            </li>
          ))}
        </ul>
      )}
    </figure>
  );
}
