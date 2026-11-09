import React from 'react';
import { formatTick } from '@/lib/detection';
import type { TimelineEntry } from '@/lib/types';

/** What was observed (regular weight) with the associated reading of it (grey). */
export function TimelineList({ timeline }: { timeline: TimelineEntry[] }) {
  if (!timeline || timeline.length === 0) {
    return <p className="text-sm text-gray-500">No timeline entries.</p>;
  }
  return (
    <ol className="space-y-3">
      {timeline.map((t, i) => (
        <li key={`${t.evidence_id}-${i}`} className="flex gap-3">
          <span className="tabular text-xs text-gray-500 w-16 shrink-0 pt-0.5">{formatTick(t.tick)}</span>
          <div className="min-w-0">
            <p className="text-sm text-gray-900">
              {t.observation}
              {t.segment && <span className="text-gray-500"> ({t.segment})</span>}
            </p>
            {t.interpretation && <p className="text-sm text-gray-500">{t.interpretation}</p>}
          </div>
        </li>
      ))}
    </ol>
  );
}
