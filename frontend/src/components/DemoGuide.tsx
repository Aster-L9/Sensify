'use client';

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { ChevronDown, Compass, Loader2, X } from 'lucide-react';
import { getRunIncidents } from '@/lib/api';
import type { IncidentSummary } from '@/lib/types';
import { usePolling } from '@/hooks/usePolling';

export const DEMO_KEY = 'sensify-demo';
export const DEMO_EVENT = 'sensify-demo-change';

export interface DemoGuideState {
  runId: number;
  step: number;
  open: boolean;
}

export function readDemoState(): DemoGuideState | null {
  try {
    const raw = window.localStorage.getItem(DEMO_KEY);
    if (!raw) return null;
    const v = JSON.parse(raw);
    if (typeof v?.runId !== 'number') return null;
    return { runId: v.runId, step: Number.isInteger(v.step) ? v.step : 0, open: v.open !== false };
  } catch {
    return null;
  }
}

/** Save the guide state and tell the mounted guide to pick it up. Pass null to dismiss it. */
export function writeDemoState(state: DemoGuideState | null) {
  try {
    if (state) window.localStorage.setItem(DEMO_KEY, JSON.stringify(state));
    else window.localStorage.removeItem(DEMO_KEY);
  } catch {
    /* storage unavailable: the guide still works for this page view */
  }
  window.dispatchEvent(new CustomEvent(DEMO_EVENT, { detail: state }));
}

interface Stop {
  title: string;
  href: string | null; // null while waiting for data
  text: string;
}

const WAITING = 'Waiting for Sensify to flag something…';

function plural(n: number, one: string, many: string) {
  return `${n} ${n === 1 ? one : many}`;
}

function buildStops(runId: number, incidents: IncidentSummary[]): Stop[] {
  const sorted = [...incidents].sort((a, b) => a.detected_tick - b.detected_tick);
  const first = sorted[0];
  const where = first?.segment_code ? ` on segment ${first.segment_code}` : '';
  return [
    {
      title: 'Dashboard',
      href: '/dashboard',
      text: 'The dashboard shows the line as it plays, with incidents grouped by outcome and the latest evaluation.',
    },
    {
      title: 'Map',
      href: `/map?run=${runId}`,
      text: 'The map shows each segment of the line, coloured and labelled by its current state as the demo run plays.',
    },
    {
      title: 'Incidents',
      href: first ? `/incidents?run_id=${runId}` : null,
      text: first
        ? `Sensify has flagged ${plural(incidents.length, 'incident', 'incidents')} in this run. The first is ${first.classification_label.toLowerCase()}${where}.`
        : WAITING,
    },
    {
      title: 'Investigation',
      href: first ? `/incidents/${encodeURIComponent(first.key)}` : null,
      text: first
        ? `The investigation page lays out how the first incident developed${where}, with its confidence (${first.confidence_label.toLowerCase()}) and the checks suggested for an operator.`
        : WAITING,
    },
    {
      title: 'Evidence',
      href: first ? `/incidents/${encodeURIComponent(first.key)}#evidence` : null,
      text: first
        ? `${plural(first.evidence_count, 'piece', 'pieces')} of evidence back this outcome, each linked to the readings and events behind it.`
        : WAITING,
    },
    {
      title: 'Comparative results',
      href: '/evaluation',
      text: 'The evaluation compares threshold alarms, the anomaly model and the full investigation, with development and held-out results kept apart.',
    },
  ];
}

export function DemoGuide() {
  const router = useRouter();
  const [state, setState] = useState<DemoGuideState | null>(null);
  const [incidents, setIncidents] = useState<IncidentSummary[]>([]);

  useEffect(() => {
    setState(readDemoState());
    const onChange = (e: Event) => setState((e as CustomEvent<DemoGuideState | null>).detail ?? null);
    window.addEventListener(DEMO_EVENT, onChange);
    return () => window.removeEventListener(DEMO_EVENT, onChange);
  }, []);

  const runId = state?.runId ?? null;
  const load = useCallback(async () => {
    if (runId === null) return;
    try {
      setIncidents(await getRunIncidents(runId));
    } catch {
      /* keep what we have; the stop keeps waiting */
    }
  }, [runId]);

  useEffect(() => {
    setIncidents([]);
    load();
  }, [load]);
  usePolling(load, 5000, runId !== null);

  const stops = useMemo(() => (runId === null ? [] : buildStops(runId, incidents)), [runId, incidents]);

  if (!state || stops.length === 0) return null;

  const update = (patch: Partial<DemoGuideState>) => writeDemoState({ ...state, ...patch });
  const step = Math.min(Math.max(state.step, 0), stops.length - 1);
  const stop = stops[step];
  const ready = stop.href !== null;

  if (!state.open) {
    return (
      <button type="button" onClick={() => update({ open: true })} aria-label="Open the demo guide"
        className="fixed bottom-4 right-4 z-40 flex items-center gap-2 rounded-full bg-brand-600 px-4 py-2.5 text-sm font-semibold text-white shadow-lg hover:bg-brand-700">
        <Compass className="w-4 h-4" aria-hidden /> Demo guide
      </button>
    );
  }

  return (
    <aside aria-label="Demo guide" className="fixed bottom-4 right-4 z-40 w-[22rem] max-w-[calc(100vw-2rem)] rounded-2xl border border-gray-200 bg-white shadow-xl">
      <div className="flex items-center justify-between gap-2 border-b border-gray-100 px-4 py-2.5">
        <p className="flex items-center gap-2 text-sm font-semibold text-gray-900">
          <Compass className="w-4 h-4 text-brand-500" aria-hidden /> Demo guide
          <span className="font-normal text-gray-500">Stop {step + 1} of {stops.length}</span>
        </p>
        <div className="flex items-center gap-1">
          <button type="button" onClick={() => update({ open: false })} aria-label="Collapse the demo guide" className="rounded p-1 text-gray-500 hover:bg-gray-100">
            <ChevronDown className="w-4 h-4" aria-hidden />
          </button>
          <button type="button" onClick={() => writeDemoState(null)} aria-label="End the demo guide" className="rounded p-1 text-gray-500 hover:bg-gray-100">
            <X className="w-4 h-4" aria-hidden />
          </button>
        </div>
      </div>
      <div className="px-4 py-3 space-y-3">
        <ol className="flex gap-1" aria-label="Stops">
          {stops.map((s, i) => (
            <li key={s.title} aria-current={i === step ? 'step' : undefined}
              className={`h-1.5 flex-1 rounded-full ${i < step ? 'bg-brand-300' : i === step ? 'bg-brand-600' : 'bg-gray-200'}`} title={s.title} />
          ))}
        </ol>
        <div>
          <h2 className="text-sm font-semibold text-gray-900">{stop.title}</h2>
          <p className="mt-1 text-sm text-gray-600 leading-snug flex items-start gap-2" aria-live="polite">
            {!ready && <Loader2 className="w-4 h-4 mt-0.5 shrink-0 animate-spin text-gray-400" aria-hidden />}
            <span>{stop.text}</span>
          </p>
        </div>
        <div className="flex items-center justify-between gap-2">
          <button type="button" onClick={() => update({ step: step - 1 })} disabled={step === 0}
            className="btn-ghost py-1 px-3 text-sm disabled:opacity-40">Back</button>
          <button type="button" disabled={!ready} onClick={() => stop.href && router.push(stop.href)}
            className="btn-primary py-1.5 px-4 text-sm disabled:opacity-50">Show me</button>
          <button type="button" onClick={() => update({ step: step + 1 })} disabled={step === stops.length - 1}
            className="btn-ghost py-1 px-3 text-sm disabled:opacity-40">Next</button>
        </div>
      </div>
    </aside>
  );
}
