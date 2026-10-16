// Shared frame for every time-aligned chart, so the telemetry charts, the score band and
// the event strip line up tick-for-tick when stacked.
import { formatTick } from '@/lib/detection';

export const Y_AXIS_WIDTH = 64;
export const CHART_MARGIN = { top: 6, right: 14, bottom: 0, left: 0 };

export function xTicks(durationTicks: number): number[] {
  const step = durationTicks > 300 ? 48 : 24; // every 2 minutes (4 for long runs)
  const out: number[] = [];
  for (let t = 0; t < durationTicks; t += step) out.push(t);
  return out;
}

export const xTickFormatter = (t: number) => formatTick(t).replace('T+', '');
