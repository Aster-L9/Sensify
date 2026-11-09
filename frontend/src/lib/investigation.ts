// Investigation visual language (docs/sprint3/design.md §11.1).
//
// Each outcome has its own icon (never reused from the segment-state icons), a word and a
// colour. Uncertain is neutral grey with a dashed outline and is never styled as an error.

import { CircleHelp, Crosshair, Droplets, EyeOff, Gauge, UserCheck, type LucideIcon } from 'lucide-react';
import type { Classification, OtLayer } from './types';

export const CATEGORY_STYLE: Record<Classification, { label: string; color: string; icon: LucideIcon; dashed?: boolean }> = {
  normal_behaviour: { label: 'Normal behaviour', color: '#4B4AA3', icon: UserCheck },
  physical_anomaly: { label: 'Possible physical/process anomaly', color: '#B45309', icon: Droplets },
  sensor_fault: { label: 'Sensor/device fault', color: '#475569', icon: Gauge },
  cyber_manipulation: { label: 'Possible cyber manipulation', color: '#9F1239', icon: Crosshair },
  reporting_inconsistency: {
    label: 'Possible physical/process anomaly with reporting inconsistency',
    color: '#7E22CE',
    icon: EyeOff,
  },
  uncertain: { label: 'Uncertain', color: '#6B7280', icon: CircleHelp, dashed: true },
};

export const CLASSIFICATION_ORDER: Classification[] = [
  'cyber_manipulation',
  'reporting_inconsistency',
  'physical_anomaly',
  'sensor_fault',
  'uncertain',
  'normal_behaviour',
];

export const OT_LAYER_LABELS: Record<OtLayer, string> = {
  physical_process: 'Physical process',
  field_device: 'Field device',
  control: 'Control',
  reporting: 'Reporting and telemetry',
};

/** A short word for a 0..1 confidence value. */
export function confidenceWord(c: number): 'High' | 'Moderate' | 'Low' {
  if (c >= 0.75) return 'High';
  if (c >= 0.5) return 'Moderate';
  return 'Low';
}

export function classificationLabel(c: string): string {
  return CATEGORY_STYLE[c as Classification]?.label ?? c;
}
