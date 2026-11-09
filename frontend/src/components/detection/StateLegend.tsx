import React from 'react';
import { STATE_STYLE } from '@/lib/detection';
import type { SegmentStateName } from '@/lib/types';

const ORDER: SegmentStateName[] = ['normal', 'anomalous', 'low_trust', 'insufficient'];

/** Line sample + icon + word for each segment state; colour is never the only cue. */
export function StateLegend({ counts, className = '' }: { counts?: Partial<Record<SegmentStateName, number>>; className?: string }) {
  return (
    <ul className={`flex flex-wrap items-center gap-x-5 gap-y-2 text-sm ${className}`} aria-label="Segment states">
      {ORDER.filter((state) => state !== 'insufficient' || (counts?.insufficient ?? 0) > 0).map((state) => {
        const s = STATE_STYLE[state];
        const Icon = s.icon;
        return (
          <li key={state} className="flex items-center gap-2" title={s.description}>
            <svg width="34" height="10" aria-hidden>
              <line x1="2" y1="5" x2="32" y2="5" stroke={s.color} strokeWidth={state === 'normal' ? 3 : 5}
                strokeDasharray={s.dash ? (state === 'insufficient' ? '1 6' : '6 4') : undefined}
                strokeLinecap={s.dash && state !== 'insufficient' ? 'butt' : 'round'} />
            </svg>
            <Icon className="w-4 h-4" style={{ color: s.color }} aria-hidden />
            <span className="text-gray-700">{s.label}</span>
            {counts && <span className="tabular font-medium text-gray-900">{counts[state] ?? 0}</span>}
          </li>
        );
      })}
    </ul>
  );
}
