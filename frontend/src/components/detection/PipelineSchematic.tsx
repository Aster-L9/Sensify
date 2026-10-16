'use client';

import React from 'react';
import { STATE_STYLE, COLORS } from '@/lib/detection';
import type { SegmentStateName } from '@/lib/types';

export interface SchematicSegment {
  code: string;
  name: string;
  segment_type: string;
  equipment?: string | null;
}

interface PipelineSchematicProps {
  segments: SchematicSegment[];
  states?: Partial<Record<string, SegmentStateName>>;
  captions?: Partial<Record<string, string>>;
  selected?: string | null;
  allowed?: string[] | null; // when set, only these segments can be picked
  onSelect?: (code: string) => void;
  label?: string;
}

const VIEW_W = 960;
const PIPE_Y = 58;
const LEFT = 36;
const RIGHT = 924;

/** The six-segment chain drawn like a process diagram, coloured by state. */
export function PipelineSchematic({
  segments, states = {}, captions = {}, selected, allowed, onSelect, label = 'Pipeline line view',
}: PipelineSchematicProps) {
  const span = (RIGHT - LEFT) / Math.max(segments.length, 1);

  return (
    <div className="w-full overflow-x-auto">
      <svg
        viewBox={`0 0 ${VIEW_W} 150`}
        className="w-full min-w-[620px] h-auto select-none"
        role="group"
        aria-label={label}
      >
        <defs>
          <marker id="flow-arrow" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="5" markerHeight="5" orient="auto">
            <path d="M0,0 L10,5 L0,10 z" fill={COLORS.muted} />
          </marker>
        </defs>

        {/* flow direction */}
        <line x1={LEFT - 30} y1={PIPE_Y} x2={LEFT - 6} y2={PIPE_Y} stroke={COLORS.muted} strokeWidth={1.5} markerEnd="url(#flow-arrow)" />
        <line x1={RIGHT + 6} y1={PIPE_Y} x2={RIGHT + 28} y2={PIPE_Y} stroke={COLORS.muted} strokeWidth={1.5} markerEnd="url(#flow-arrow)" />

        {segments.map((seg, i) => {
          const x1 = LEFT + i * span;
          const x2 = x1 + span;
          const mid = (x1 + x2) / 2;
          const state = states[seg.code] ?? 'normal';
          const style = STATE_STYLE[state];
          const disabled = !!allowed && !allowed.includes(seg.code);
          const isSelected = selected === seg.code;
          const interactive = !!onSelect && !disabled;
          const stateWord = state === 'normal' ? '' : `, ${style.label.toLowerCase()}`;

          return (
            <g
              key={seg.code}
              role={onSelect ? 'button' : undefined}
              tabIndex={interactive ? 0 : undefined}
              aria-label={`${seg.code} ${seg.name}${stateWord}${disabled ? ', not available for this scenario' : ''}`}
              aria-pressed={onSelect ? isSelected : undefined}
              aria-disabled={onSelect ? disabled : undefined}
              onClick={() => interactive && onSelect?.(seg.code)}
              onKeyDown={(e) => {
                if (interactive && (e.key === 'Enter' || e.key === ' ')) {
                  e.preventDefault();
                  onSelect?.(seg.code);
                }
              }}
              className={`schematic-seg ${interactive ? 'cursor-pointer' : ''} ${disabled ? 'opacity-40' : ''}`}
            >
              {/* hit area + selection */}
              <rect
                x={x1 + 3} y={14} width={span - 6} height={128} rx={12}
                fill={isSelected ? '#EEF0FB' : 'transparent'}
                stroke={isSelected ? COLORS.normal : 'transparent'}
                strokeWidth={1.5}
                className="schematic-hit"
              />
              {/* pipe casing */}
              <line x1={x1} y1={PIPE_Y} x2={x2} y2={PIPE_Y} stroke={COLORS.grid} strokeWidth={16} strokeLinecap="butt" />
              {/* state line; low trust is dashed so it never relies on colour alone */}
              {state !== 'normal' && (
                <line
                  key={`${seg.code}-${state}`}
                  x1={x1 + 2} y1={PIPE_Y} x2={x2 - 2} y2={PIPE_Y}
                  stroke={style.color} strokeWidth={16} strokeOpacity={0.35}
                  className="schematic-halo"
                />
              )}
              <line
                x1={x1 + 2} y1={PIPE_Y} x2={x2 - 2} y2={PIPE_Y}
                stroke={style.color}
                strokeWidth={state === 'normal' ? 5 : 8}
                strokeDasharray={style.dash}
                strokeLinecap={style.dash ? 'butt' : 'round'}
              />
              <EquipmentGlyph kind={seg.equipment ?? null} type={seg.segment_type} x={mid} color={state === 'normal' ? COLORS.ink : style.color} />

              {/* abnormal badge */}
              {state !== 'normal' && (
                <g transform={`translate(${mid + (seg.equipment ? 24 : 0) - 9}, ${PIPE_Y - 40})`} aria-hidden>
                  <circle cx={9} cy={9} r={10} fill="#fff" stroke={style.color} strokeWidth={1.5} />
                  {state === 'anomalous' ? (
                    <path d="M9 3.5 L15 14 L3 14 Z M9 7.5 V10.5 M9 12.2 V12.4" fill="none" stroke={style.color} strokeWidth={1.6} strokeLinejoin="round" strokeLinecap="round" />
                  ) : (
                    <path d="M9 3.5 L14.5 5.5 V9.5 C14.5 12.5 12 14.5 9 15.5 C6 14.5 3.5 12.5 3.5 9.5 V5.5 Z M9 7 V10 M9 12 V12.2" fill="none" stroke={style.color} strokeWidth={1.5} strokeLinejoin="round" strokeLinecap="round" />
                  )}
                </g>
              )}

              {/* junction node */}
              {i > 0 && <circle cx={x1} cy={PIPE_Y} r={4} fill="#fff" stroke={COLORS.muted} strokeWidth={1.5} />}

              <text x={mid} y={104} textAnchor="middle" className="fill-gray-900" style={{ font: '600 15px Inter, system-ui, sans-serif' }}>
                {seg.code}
              </text>
              <text x={mid} y={122} textAnchor="middle" className="fill-gray-500" style={{ font: '400 12px Inter, system-ui, sans-serif' }}>
                {shortName(seg.name)}
              </text>
              {captions[seg.code] && (
                <text x={mid} y={139} textAnchor="middle" style={{ font: '500 12px "JetBrains Mono", ui-monospace, monospace', fill: state === 'normal' ? COLORS.muted : style.textColor }}>
                  {captions[seg.code]}
                </text>
              )}
            </g>
          );
        })}
      </svg>
    </div>
  );
}

function shortName(name: string): string {
  return name.replace('Pipeline ', '').replace('Industrial ', '').replace(' Station', '');
}

function EquipmentGlyph({ kind, type, x, color }: { kind: string | null; type: string; x: number; color: string }) {
  const y = PIPE_Y;
  if (kind === 'pump') {
    return (
      <g aria-hidden>
        <circle cx={x} cy={y} r={15} fill="#fff" stroke={color} strokeWidth={2} />
        <path d={`M${x - 6} ${y - 8} L${x + 9} ${y} L${x - 6} ${y + 8} Z`} fill="none" stroke={color} strokeWidth={2} strokeLinejoin="round" />
      </g>
    );
  }
  if (kind === 'valve') {
    return (
      <g aria-hidden>
        <path d={`M${x - 14} ${y - 11} L${x + 14} ${y + 11} L${x + 14} ${y - 11} L${x - 14} ${y + 11} Z`} fill="#fff" stroke={color} strokeWidth={2} strokeLinejoin="round" />
        <line x1={x} y1={y} x2={x} y2={y - 18} stroke={color} strokeWidth={2} />
        <line x1={x - 7} y1={y - 18} x2={x + 7} y2={y - 18} stroke={color} strokeWidth={2} strokeLinecap="round" />
      </g>
    );
  }
  if (type === 'terminal') {
    return (
      <g aria-hidden>
        <rect x={x - 17} y={y - 14} width={34} height={28} rx={5} fill="#fff" stroke={color} strokeWidth={2} />
        <line x1={x - 9} y1={y - 4} x2={x + 9} y2={y - 4} stroke={color} strokeWidth={1.5} />
        <line x1={x - 9} y1={y + 4} x2={x + 9} y2={y + 4} stroke={color} strokeWidth={1.5} />
      </g>
    );
  }
  return null;
}
