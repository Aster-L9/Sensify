import React from 'react';
import type { SegmentState } from '@/lib/types';

/**
 * The recorded valve or pump state at the cursor time, as a word first (Open, Closed, Running,
 * Stopped) with the measured position or speed beside it. Segments without a valve or pump say so
 * instead of showing a meaningless default (handover V-01).
 */
export function EquipmentState({ state, segmentType }: { state: SegmentState | null; segmentType: string }) {
  if (segmentType === 'valve_station') {
    return (
      // The valve word already carries its position (Open, 32 % open, Closed).
      <Row label="Valve V-12" word={state?.valve_state ?? null} detail={null} warn={state?.valve_state === 'Closed'} />
    );
  }
  if (segmentType === 'pump_station') {
    return (
      <Row label="Pump P-3" word={state?.equipment_state ?? null}
        detail={state?.pump_speed_pct != null ? `${state.pump_speed_pct.toFixed(0)} % speed` : null}
        warn={state?.equipment_state === 'Stopped'} />
    );
  }
  return <p className="text-sm text-gray-500">No valve or pump on this segment.</p>;
}

function Row({ label, word, detail, warn }: { label: string; word: string | null; detail: string | null; warn: boolean }) {
  return (
    <div className="flex items-baseline justify-between gap-3 text-sm">
      <span className="text-gray-500">{label}</span>
      <span className="text-right">
        {word ? (
          <span className={`font-semibold ${warn ? 'text-amber-800' : 'text-gray-900'}`}>{word.replace(/(\d+)% Open/, '$1 % open')}</span>
        ) : (
          <span className="text-gray-500">No reading</span>
        )}
        {detail && word && !/\d/.test(word) && <span className="ml-2 text-gray-500 tabular">{detail}</span>}
      </span>
    </div>
  );
}
