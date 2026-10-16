// Scenario builder rules and wording. The limits mirror validate_config in
// backend/app/sim/scenarios.py and the effect sizes mirror backend/app/sim/engine.py;
// the backend stays the authority and its 400 messages are shown as they come.

export const RECOVERY_MIN = 2;
export const MAX_SEED = 2 ** 31 - 1;

export const LIMITS = {
  magnitude: { min: 0.1, max: 1 },
  onset_min: { min: 1, max: 28 },
  ramp_min: { min: 0.5, max: 5 },
  active_min: { min: 1, max: 25 },
  duration_min: { min: 10, max: 30 },
} as const;

export type LimitKey = keyof typeof LIMITS;

export interface MagnitudeReadout {
  text: string;
  /** False when the method ignores strength (a trip or a frozen reading). */
  applies: boolean;
}

const pct = (x: number) => `${Math.round(x * 100)} %`;  // no wrap between number and unit

/** What the magnitude slider means for this scenario, in plant terms. */
export function magnitudeReadout(
  type: string,
  method: string | null,
  equipment: string | null | undefined,
  variable: 'pressure' | 'flow',
  m: number,
): MagnitudeReadout {
  const sensor = (pressureBar: number, flowM3h: number, sign: string) =>
    variable === 'pressure' ? `${sign}${(pressureBar * m).toFixed(1)} bar` : `${sign}${Math.round(flowM3h * m)} m³/h`;

  switch (`${type}:${method}`) {
    case 'physical_anomaly:leak':
    case 'concealed_physical_incident:leak':
      return { text: `Leak of about ${Math.round(25 * m)} % of the line flow`, applies: true };
    case 'physical_anomaly:blockage':
      return { text: `Segment resistance rises ×${(1 + 4 * m).toFixed(1)}`, applies: true };
    case 'sensor_fault:erratic':
      return { text: `Spikes of up to ${sensor(12, 120, '±')} on the ${variable} reading`, applies: true };
    case 'sensor_fault:drift':
      return { text: `The ${variable} reading drifts ${sensor(10, 100, '+')} by the end of the active phase`, applies: true };
    case 'sensor_fault:stuck':
      return { text: `The ${variable} reading freezes at its last value; strength has no effect`, applies: false };
    case 'telemetry_manipulation:bias':
      return { text: `False offset of ±${(8 * m).toFixed(1)} bar on the reported pressure`, applies: true };
    case 'telemetry_manipulation:replay':
      if (equipment === 'inlet_control') return { text: `Inlet pressure is covertly cut by ${(6 * m).toFixed(1)} bar`, applies: true };
      if (equipment === 'pump') return { text: `Pump P-3 is covertly slowed to ${pct(1 - 0.35 * m)} speed`, applies: true };
      if (equipment === 'valve') return { text: `Valve V-12 is covertly closed to ${pct(1 - 0.7 * m)} open`, applies: true };
      if (equipment === 'delivery_control') return { text: `Delivery back-pressure is covertly raised by ${(5 * m).toFixed(1)} bar`, applies: true };
      return { text: 'Pick a target to see the hidden process change', applies: true };
    case 'unauthorized_control:valve_close':
      return { text: `Valve V-12 is driven to ${pct(1 - 0.75 * m)} open`, applies: true };
    case 'unauthorized_control:pump_slowdown':
      return { text: `Pump P-3 is driven to ${pct(1 - 0.4 * m)} speed`, applies: true };
    case 'unauthorized_control:pump_stop':
      return { text: 'Pump P-3 is tripped; strength has no effect', applies: false };
    default:
      return { text: '', applies: false };
  }
}

export interface Timing {
  onset: number;
  ramp: number;
  active: number;
  recovery: boolean;
  duration: number;
}

/** Minutes the event needs inside the run, including the final minute the backend keeps clear. */
export function minutesNeeded(t: Timing): number {
  return t.onset + t.ramp + t.active + (t.recovery ? RECOVERY_MIN : 0) + 1;
}

export interface Phase {
  id: 'baseline' | 'ramp' | 'active' | 'recovery' | 'after';
  label: string;
  from: number;
  to: number;
}

/** Baseline, ramp, active, recovery and after phases in minutes, clipped to the run. */
export function phases(t: Timing): Phase[] {
  const end = t.duration;
  const clip = (x: number) => Math.min(Math.max(x, 0), end);
  const rampEnd = t.onset + t.ramp;
  const activeEnd = t.recovery ? rampEnd + t.active : end;
  const recoveryEnd = t.recovery ? activeEnd + RECOVERY_MIN : end;
  const list: Phase[] = [
    { id: 'baseline', label: 'Baseline', from: 0, to: clip(t.onset) },
    { id: 'ramp', label: 'Ramp', from: clip(t.onset), to: clip(rampEnd) },
    { id: 'active', label: t.recovery ? 'Active' : 'Active to the end', from: clip(rampEnd), to: clip(activeEnd) },
  ];
  if (t.recovery) {
    list.push({ id: 'recovery', label: 'Recovery', from: clip(activeEnd), to: clip(recoveryEnd) });
    list.push({ id: 'after', label: 'Back to normal', from: clip(recoveryEnd), to: end });
  }
  return list.filter((p) => p.to > p.from);
}

/** Effect strength 0..1 at minute x, the same shape as envelope() in the simulator. */
export function envelopeAt(t: Timing, x: number): number {
  const rampEnd = t.onset + t.ramp;
  const activeEnd = rampEnd + t.active;
  if (x < t.onset) return 0;
  if (x < rampEnd) return (x - t.onset) / Math.max(t.ramp, 1e-6);
  if (!t.recovery || x < activeEnd) return 1;
  if (x < activeEnd + RECOVERY_MIN) return 1 - (x - activeEnd) / RECOVERY_MIN;
  return 0;
}

export function formatMinutes(min: number): string {
  const total = Math.round(min * 60);
  const m = Math.floor(total / 60);
  const s = total % 60;
  if (m === 0) return `${s} s`;
  return s ? `${m} min ${s} s` : `${m} min`;
}
