// Detection visual language: colours, labels and icons for segment states.
//
// Colour means abnormal: a normal segment keeps the calm brand indigo, an anomalous
// one turns amber, and one whose readings can't be trusted turns rose with a dashed
// line. Colour is never the only cue: every state also has a pattern, an icon and a word.

import { AlertTriangle, CheckCircle2, ShieldAlert, type LucideIcon } from 'lucide-react';
import type { EventCategory, SegmentStateName, Severity, TrustStatus } from './types';

export const TICK_SECONDS = 5;

export const COLORS = {
  ink: '#232838',
  muted: '#6B7280',
  grid: '#E5E7EB',
  normal: '#7169D5',
  anomalous: '#D97706',
  anomalousText: '#B45309',
  lowTrust: '#BE185D',
  review: '#DB2777',
  threshold: '#9CA3AF',
  medium: '#D97706',
  high: '#EA580C',
  critical: '#DC2626',
  analysis: '#0F766E',
} as const;

export interface StateStyle {
  label: string;
  description: string;
  color: string;
  textColor: string;
  dash?: string;
  weight: number;
  icon: LucideIcon;
}

export const STATE_STYLE: Record<SegmentStateName, StateStyle> = {
  normal: {
    label: 'Normal',
    description: 'Readings match normal behaviour and are trusted',
    color: COLORS.normal,
    textColor: '#4B4AA3',
    weight: 4,
    icon: CheckCircle2,
  },
  anomalous: {
    label: 'Anomalous',
    description: 'The model flags behaviour outside the normal envelope',
    color: COLORS.anomalous,
    textColor: COLORS.anomalousText,
    weight: 7,
    icon: AlertTriangle,
  },
  low_trust: {
    label: 'Low trust',
    description: 'Reported readings disagree with the evidence',
    color: COLORS.lowTrust,
    textColor: COLORS.lowTrust,
    dash: '10 7',
    weight: 7,
    icon: ShieldAlert,
  },
};

export const SEVERITY_STYLE: Record<Severity, { label: string; color: string; soft: string }> = {
  medium: { label: 'Medium', color: '#B45309', soft: '#FEF3C7' },
  high: { label: 'High', color: '#C2410C', soft: '#FFEDD5' },
  critical: { label: 'Critical', color: '#B91C1C', soft: '#FEE2E2' },
};

export const TRUST_STYLE: Record<TrustStatus, { label: string; color: string; soft: string }> = {
  Supported: { label: 'Supported', color: '#4B4AA3', soft: '#EEF0FB' },
  Review: { label: 'Review', color: '#BE185D', soft: '#FCE7F3' },
  Contradicted: { label: 'Contradicted', color: '#9D174D', soft: '#FBCFE8' },
};

export const CATEGORY_STYLE: Record<EventCategory, { label: string; color: string; shape: 'square' | 'triangle' | 'diamond' | 'circle' }> = {
  control: { label: 'Control', color: '#4B4AA3', shape: 'square' },
  security: { label: 'Security', color: '#BE185D', shape: 'triangle' },
  device: { label: 'Device', color: '#6B7280', shape: 'diamond' },
  process: { label: 'Process', color: '#B45309', shape: 'diamond' },
  analysis: { label: 'Sensify analysis', color: COLORS.analysis, shape: 'circle' },
};

export const SCENARIO_LABELS: Record<string, string> = {
  normal: 'Normal operation',
  physical_anomaly: 'Physical anomaly',
  sensor_fault: 'Sensor / device fault',
  telemetry_manipulation: 'Telemetry manipulation',
  unauthorized_control: 'Unauthorized control',
  concealed_physical_incident: 'Concealed physical incident',
};

export const CHECK_LABELS: Record<string, string> = {
  flow_balance: 'Flow balance',
  pressure_gradient: 'Pressure gradient',
  implausible_change: 'Implausible change',
  range: 'Physical range',
  replay: 'Replay signature',
  flatline: 'Flat readings',
};

/** Elapsed run time as T+mm:ss. */
export function formatTick(tick: number, tickSeconds: number = TICK_SECONDS): string {
  const total = Math.max(0, Math.round(tick * tickSeconds));
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `T+${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

export function formatDuration(ticks: number, tickSeconds: number = TICK_SECONDS): string {
  const total = Math.round(ticks * tickSeconds);
  if (total < 60) return `${total} s`;
  const m = Math.floor(total / 60);
  const s = total % 60;
  return s ? `${m} min ${s} s` : `${m} min`;
}

export function trustTone(status: TrustStatus | null | undefined) {
  return TRUST_STYLE[status ?? 'Supported'];
}

export function percent(value: number | null | undefined, digits = 0): string {
  return value === null || value === undefined ? '—' : `${(value * 100).toFixed(digits)} %`;
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return '—';
  const d = new Date(iso.endsWith('Z') || iso.includes('+') ? iso : `${iso}Z`);
  return d.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
}
