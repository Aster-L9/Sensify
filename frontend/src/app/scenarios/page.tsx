'use client';

import React, { useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  Activity, AlertCircle, Check, Droplets, EyeOff, FlaskConical, Gauge, Loader2, Radio, Rocket, Shield,
  ShieldAlert, SlidersHorizontal,
} from 'lucide-react';
import { getScenarios, launchScenario } from '@/lib/api';
import type { ScenarioCatalog, ScenarioLaunch, ScenarioType } from '@/lib/types';
import { COLORS, STATE_STYLE } from '@/lib/detection';
import {
  LIMITS, MAX_SEED, RECOVERY_MIN, envelopeAt, formatMinutes, magnitudeReadout, minutesNeeded, phases, type LimitKey, type Timing,
} from '@/lib/scenarios';
import { useAuth } from '@/contexts/AuthContext';
import { LoadingState, ErrorState } from '@/components/ui/States';
import { PipelineSchematic } from '@/components/detection/PipelineSchematic';

const TYPE_ICONS: Record<string, typeof Activity> = {
  normal: Activity,
  physical_anomaly: Droplets,
  sensor_fault: Gauge,
  telemetry_manipulation: Radio,
  unauthorized_control: SlidersHorizontal,
  concealed_physical_incident: EyeOff,
};

const EQUIPMENT_LABELS: Record<string, string> = {
  inlet_control: 'Inlet control',
  pump: 'Pump P-3',
  valve: 'Valve V-12',
  delivery_control: 'Delivery control',
};

interface Form extends Record<'onset' | 'ramp' | 'active' | 'duration', number | null> {
  type: string;
  method: string | null;
  target: string | null;
  magnitude: number;
  variable: 'pressure' | 'flow';
  recovery: boolean;
  speed: number;
  seed: string;
  name: string;
  description: string;
}

function num(value: unknown, fallback: number): number {
  return typeof value === 'number' ? value : fallback;
}

/** Keep the target when the new method allows it; pick it for the user when only one segment can host it. */
function fitTarget(type: ScenarioType | undefined, method: string | null, current: string | null): string | null {
  const allowed = type?.methods.find((m) => m.id === method)?.allowed_targets ?? [];
  if (current && allowed.includes(current)) return current;
  return allowed.length === 1 ? allowed[0] : null;
}

export default function ScenarioBuilderPage() {
  const { isAdmin } = useAuth();
  if (!isAdmin) {
    return (
      <div className="glass-card p-12 text-center border-red-500/30">
        <Shield className="w-12 h-12 text-red-400 mx-auto mb-3" aria-hidden />
        <h2 className="text-xl font-bold text-gray-900">Access Restricted</h2>
        <p className="text-sm text-gray-500 mt-1">Only administrators can design and launch scenarios.</p>
      </div>
    );
  }
  return <Builder />;
}

function Builder() {
  const router = useRouter();
  const [catalog, setCatalog] = useState<ScenarioCatalog | null>(null);
  const [loadErr, setLoadErr] = useState<string | null>(null);
  const [form, setForm] = useState<Form | null>(null);
  const [launching, setLaunching] = useState(false);
  const [serverErr, setServerErr] = useState<string | null>(null);

  const load = () => {
    setLoadErr(null);
    getScenarios()
      .then((c) => {
        setCatalog(c);
        const d = c.defaults;
        setForm({
          type: 'physical_anomaly', method: 'leak', target: null,
          magnitude: num(d.magnitude, 0.6), variable: 'pressure',
          onset: num(d.onset_min, 6), ramp: num(d.ramp_min, 1), active: num(d.active_min, 6),
          recovery: d.recovery !== false, duration: num(d.duration_min, 20),
          speed: num(d.playback_speed, 10), seed: '', name: '', description: '',
        });
      })
      .catch((e) => setLoadErr(e.message || 'Could not load the scenario catalog'));
  };
  useEffect(load, []);

  const type = catalog?.types.find((t) => t.id === form?.type);
  const method = type?.methods.find((m) => m.id === form?.method) ?? null;
  const hasEvent = !!type && type.methods.length > 0;
  const targetSegment = catalog?.segments.find((s) => s.code === form?.target);

  const issues = useMemo(() => {
    if (!form || !type) return [];
    const out: string[] = [];
    const range = (key: LimitKey, value: number | null, label: string) => {
      const { min, max } = LIMITS[key];
      if (value === null) out.push(`Enter the ${label}.`);
      else if (value < min || value > max) out.push(`The ${label} must be between ${min} and ${max} min.`);
    };
    if (hasEvent) {
      if (!form.target) out.push('Pick a target segment on the line.');
      range('onset_min', form.onset, 'onset');
      range('ramp_min', form.ramp, 'ramp');
      range('active_min', form.active, 'active time');
    }
    range('duration_min', form.duration, 'run length');
    if (hasEvent && out.length === 0) {
      const need = minutesNeeded({
        onset: form.onset ?? 0, ramp: form.ramp ?? 0, active: form.active ?? 0, recovery: form.recovery, duration: form.duration ?? 0,
      });
      if (need > (form.duration ?? 0)) {
        out.push(`The event needs ${formatMinutes(need)} including the last clear minute, but the run is ${formatMinutes(form.duration ?? 0)}. Shorten the timing or lengthen the run.`);
      }
    }
    const seed = form.seed.trim();
    if (seed && (!/^\d+$/.test(seed) || Number(seed) > MAX_SEED)) out.push(`The seed must be a whole number from 0 to ${MAX_SEED}.`);
    return out;
  }, [form, type, hasEvent]);

  if (loadErr) return <ErrorState message={loadErr} onRetry={load} />;
  if (!catalog || !form || !type) return <LoadingState message="Loading the scenario catalog..." />;

  const update = (patch: Partial<Form>) => {
    setServerErr(null);
    setForm((f) => (f ? { ...f, ...patch } : f));
  };

  const pickType = (t: ScenarioType) => {
    const nextMethod = t.methods[0]?.id ?? null;
    update({ type: t.id, method: nextMethod, target: fitTarget(t, nextMethod, form.target) });
  };

  const pickMethod = (id: string) => update({ method: id, target: fitTarget(type, id, form.target) });

  const timing: Timing = {
    onset: form.onset ?? 0, ramp: form.ramp ?? 0, active: form.active ?? 0,
    recovery: form.recovery, duration: form.duration ?? LIMITS.duration_min.min,
  };
  const readout = hasEvent
    ? magnitudeReadout(type.id, form.method, targetSegment?.equipment, form.variable, form.magnitude)
    : null;

  const launch = async () => {
    if (issues.length || launching) return;
    setLaunching(true);
    setServerErr(null);
    const body: ScenarioLaunch = {
      scenario_type: type.id,
      duration_min: form.duration ?? undefined,
      playback_speed: form.speed,
      name: form.name.trim() || undefined,
      description: form.description.trim() || undefined,
      seed: form.seed.trim() ? Number(form.seed.trim()) : undefined,
    };
    if (hasEvent) {
      Object.assign(body, {
        method: form.method, target_segment: form.target, magnitude: form.magnitude,
        onset_min: form.onset, ramp_min: form.ramp, active_min: form.active, recovery: form.recovery,
        variable: type.id === 'sensor_fault' ? form.variable : undefined,
      });
    }
    try {
      const run = await launchScenario(body);
      router.push(`/runs/${run.id}`);
    } catch (e: any) {
      setServerErr(typeof e?.message === 'string' ? e.message : 'The launch failed. Check the settings and try again.');
      setLaunching(false);
    }
  };

  const playSeconds = ((form.duration ?? 0) * 60) / form.speed;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
          <FlaskConical className="w-6 h-6 text-brand-500" aria-hidden /> Scenario builder
        </h1>
        <p className="text-sm text-gray-500 mt-1 max-w-2xl">
          Design an incident on the line and launch it. Everyone signed in watches the run unfold at the speed you
          choose; analysts see what Sensify finds, never the scenario itself.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_340px] gap-6 items-start">
        <div className="space-y-6 min-w-0">
          <Step n={1} title="What happens">
            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3" role="radiogroup" aria-label="Scenario type">
              {catalog.types.map((t) => (
                <TypeCard key={t.id} type={t} selected={t.id === type.id} onSelect={() => pickType(t)} />
              ))}
            </div>
          </Step>

          {hasEvent && (
            <Step n={2} title="Where and how">
              <div className="space-y-4">
                {type.methods.length > 1 && (
                  <div className="flex flex-wrap gap-1.5" role="radiogroup" aria-label="Method">
                    {type.methods.map((m) => (
                      <Choice key={m.id} active={m.id === form.method} onClick={() => pickMethod(m.id)} role="radio">
                        {m.label}
                      </Choice>
                    ))}
                  </div>
                )}
                {method && <p className="text-sm text-gray-600">{method.description}</p>}
                {type.id === 'sensor_fault' && (
                  <div className="flex items-center gap-3">
                    <span className="text-sm text-gray-600" id="variable-label">Faulty sensor</span>
                    <div className="flex gap-1.5" role="radiogroup" aria-labelledby="variable-label">
                      {(['pressure', 'flow'] as const).map((v) => (
                        <Choice key={v} active={form.variable === v} onClick={() => update({ variable: v })} role="radio">
                          {v === 'pressure' ? 'Pressure' : 'Flow'}
                        </Choice>
                      ))}
                    </div>
                  </div>
                )}
                <div className="rounded-xl border border-gray-100 bg-gray-50/60 px-2 pt-1">
                  <PipelineSchematic
                    segments={catalog.segments}
                    selected={form.target}
                    allowed={method?.allowed_targets ?? []}
                    onSelect={(code) => update({ target: code })}
                    captions={Object.fromEntries(catalog.segments
                      .filter((s) => s.equipment && method?.allowed_targets.includes(s.code))
                      .map((s) => [s.code, EQUIPMENT_LABELS[s.equipment as string] ?? s.equipment as string]))}
                    label="Pick the target segment"
                  />
                </div>
                <p className="text-sm text-gray-600" aria-live="polite">
                  {targetSegment
                    ? <>Target: <span className="font-semibold text-gray-900">{targetSegment.code}, {targetSegment.name}</span></>
                    : method && method.allowed_targets.length < catalog.segments.length
                      ? `${method.label} can only target ${method.allowed_targets.join(', ')}; the other segments are dimmed.`
                      : 'Select a segment on the line.'}
                </p>
              </div>
            </Step>
          )}

          {hasEvent && readout && (
            <Step n={3} title="How strong">
              <div className="space-y-3">
                <p className="text-lg font-semibold" style={{ color: readout.applies ? STATE_STYLE.anomalous.textColor : COLORS.muted }}>
                  {readout.text}
                </p>
                <MagnitudeSlider value={form.magnitude} disabled={!readout.applies}
                  label={type.magnitude_label ?? 'Strength'} onChange={(v) => update({ magnitude: v })} />
              </div>
            </Step>
          )}

          <Step n={hasEvent ? 4 : 2} title="When">
            <div className="space-y-5">
              <div className={`grid grid-cols-2 ${hasEvent ? 'sm:grid-cols-4' : 'sm:grid-cols-2'} gap-3`}>
                {hasEvent && (
                  <>
                    <MinutesField label="Onset" hint="after the run starts" limit="onset_min" value={form.onset} onChange={(v) => update({ onset: v })} />
                    <MinutesField label="Ramp" hint="to full strength" limit="ramp_min" value={form.ramp} onChange={(v) => update({ ramp: v })} step={0.5} />
                    <MinutesField label="Active" hint="at full strength" limit="active_min" value={form.active} onChange={(v) => update({ active: v })} />
                  </>
                )}
                <MinutesField label="Run length" hint="10 to 30 min" limit="duration_min" value={form.duration} onChange={(v) => update({ duration: v })} />
              </div>
              {hasEvent && (
                <label className="flex items-center gap-3 text-sm text-gray-700 w-fit cursor-pointer">
                  <input type="checkbox" checked={form.recovery} onChange={(e) => update({ recovery: e.target.checked })}
                    className="h-4 w-4 rounded border-gray-300 accent-brand-500" />
                  Recover over {RECOVERY_MIN} min after the active phase
                  <span className="text-gray-500">(otherwise it holds to the end)</span>
                </label>
              )}
              <TimelinePreview timing={timing} hasEvent={hasEvent} />
            </div>
          </Step>

          <Step n={hasEvent ? 5 : 3} title="Playback and labels">
            <div className="space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center gap-3">
                <span className="text-sm text-gray-600" id="speed-label">Playback speed</span>
                <div className="flex gap-1.5" role="radiogroup" aria-labelledby="speed-label">
                  {catalog.playback_speeds.map((s) => (
                    <Choice key={s} active={form.speed === s} onClick={() => update({ speed: s })} role="radio">
                      <span className="tabular">{s}×</span>
                    </Choice>
                  ))}
                </div>
                <span className="text-sm text-gray-500">
                  plays in {formatMinutes(playSeconds / 60)}
                </span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-[minmax(0,1fr)_10rem] gap-3">
                <label className="text-sm">
                  <span className="block text-xs font-semibold text-gray-600 mb-1">Run name <span className="font-normal text-gray-400">(optional)</span></span>
                  <input value={form.name} maxLength={100} onChange={(e) => update({ name: e.target.value })}
                    placeholder="Numbered automatically" className="input-field py-2 text-sm" />
                </label>
                <label className="text-sm">
                  <span className="block text-xs font-semibold text-gray-600 mb-1">Seed <span className="font-normal text-gray-400">(optional)</span></span>
                  <input value={form.seed} inputMode="numeric" onChange={(e) => update({ seed: e.target.value })}
                    placeholder="Random" className="input-field py-2 text-sm font-mono" />
                </label>
              </div>
              <label className="text-sm block">
                <span className="block text-xs font-semibold text-gray-600 mb-1">Note for the run list <span className="font-normal text-gray-400">(optional, visible to everyone)</span></span>
                <input value={form.description} maxLength={500} onChange={(e) => update({ description: e.target.value })}
                  placeholder="For example: drill for the night shift" className="input-field py-2 text-sm" />
              </label>
              <p className="text-xs text-gray-500">The same seed and settings always produce the same run.</p>
            </div>
          </Step>
        </div>

        <aside className="lg:sticky lg:top-6">
          <LaunchSummary
            type={type}
            methodLabel={method?.label ?? null}
            target={targetSegment ? `${targetSegment.code}, ${targetSegment.name}` : null}
            readout={readout?.applies ? readout.text : null}
            timing={timing}
            hasEvent={hasEvent}
            speed={form.speed}
            playSeconds={playSeconds}
            issues={issues}
            serverErr={serverErr}
            launching={launching}
            onLaunch={launch}
          />
        </aside>
      </div>
    </div>
  );
}

function Step({ n, title, children }: { n: number; title: string; children: React.ReactNode }) {
  return (
    <section className="glass-card p-5" aria-labelledby={`step-${n}`}>
      <h2 id={`step-${n}`} className="flex items-center gap-2.5 text-base font-semibold text-gray-900 mb-4">
        <span className="flex h-6 w-6 items-center justify-center rounded-full bg-brand-50 text-xs font-bold text-brand-700 tabular" aria-hidden>
          {n}
        </span>
        {title}
      </h2>
      {children}
    </section>
  );
}

function Choice({ active, onClick, role, children }: {
  active: boolean;
  onClick: () => void;
  role?: 'radio';
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      role={role}
      aria-checked={role ? active : undefined}
      aria-pressed={role ? undefined : active}
      onClick={onClick}
      className={`px-3 py-1.5 rounded-lg text-sm border transition-colors ${
        active ? 'bg-brand-500 border-brand-500 text-white font-semibold' : 'border-gray-200 text-gray-700 hover:bg-gray-50'
      }`}
    >
      {children}
    </button>
  );
}

function TypeCard({ type, selected, onSelect }: { type: ScenarioType; selected: boolean; onSelect: () => void }) {
  const Icon = TYPE_ICONS[type.id] ?? Activity;
  return (
    <button
      type="button"
      role="radio"
      aria-checked={selected}
      onClick={onSelect}
      className={`relative text-left rounded-xl border p-4 transition-colors ${
        selected ? 'border-brand-500 bg-brand-50/60 ring-1 ring-brand-500' : 'border-gray-200 hover:border-brand-300 hover:bg-gray-50'
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <span className={`flex h-9 w-9 items-center justify-center rounded-lg ${selected ? 'bg-brand-500 text-white' : 'bg-gray-100 text-gray-600'}`}>
          <Icon className="w-5 h-5" aria-hidden />
        </span>
        {type.cyber && (
          <span className="inline-flex items-center gap-1 rounded-full bg-pink-50 px-2 py-0.5 text-[11px] font-semibold text-pink-700">
            <ShieldAlert className="w-3 h-3" aria-hidden /> Cyber
          </span>
        )}
      </div>
      <p className="mt-3 text-sm font-semibold text-gray-900 flex items-center gap-1.5">
        {sentenceCase(type.label)}
        {selected && <Check className="w-4 h-4 text-brand-600" aria-hidden />}
      </p>
      <p className="mt-1 text-xs leading-snug text-gray-600">{type.description}</p>
    </button>
  );
}

function sentenceCase(label: string): string {
  return label.charAt(0) + label.slice(1).toLowerCase();
}

function MagnitudeSlider({ value, disabled, label, onChange }: {
  value: number;
  disabled: boolean;
  label: string;
  onChange: (v: number) => void;
}) {
  const { min, max } = LIMITS.magnitude;
  const fill = ((value - min) / (max - min)) * 100;
  return (
    <div className={disabled ? 'opacity-50' : ''}>
      <div className="flex items-center justify-between text-xs text-gray-500 mb-1">
        <label htmlFor="magnitude">{sentenceCase(label)}</label>
        <span className="font-mono tabular text-gray-700">{value.toFixed(2)}</span>
      </div>
      <div className="relative h-6">
        <div className="absolute inset-x-0 top-1/2 -translate-y-1/2 h-1.5 rounded-full bg-gray-100" aria-hidden />
        <div className="absolute left-0 top-1/2 -translate-y-1/2 h-1.5 rounded-full"
          style={{ width: `calc(${fill}% + ${8 - fill * 0.16}px)`, background: STATE_STYLE.anomalous.color }} aria-hidden />
        <input id="magnitude" type="range" min={min} max={max} step={0.05} value={value} disabled={disabled}
          onChange={(e) => onChange(Number(e.target.value))}
          className="playback-range absolute inset-0 w-full disabled:cursor-not-allowed" />
      </div>
      <div className="flex justify-between text-[11px] text-gray-400 mt-0.5" aria-hidden>
        <span>Subtle</span>
        <span>Severe</span>
      </div>
    </div>
  );
}

function MinutesField({ label, hint, limit, value, onChange, step = 1 }: {
  label: string;
  hint: string;
  limit: LimitKey;
  value: number | null;
  onChange: (v: number | null) => void;
  step?: number;
}) {
  const { min, max } = LIMITS[limit];
  const [text, setText] = useState(value === null ? '' : String(value));
  useEffect(() => {
    if (value !== null && Number(text) !== value) setText(String(value));
  }, [value]); // eslint-disable-line react-hooks/exhaustive-deps
  const invalid = value === null || value < min || value > max;
  const id = `field-${limit}`;
  return (
    <label className="text-sm" htmlFor={id}>
      <span className="block text-xs font-semibold text-gray-600 mb-1">{label}</span>
      <span className="relative block">
        <input
          id={id}
          type="number"
          inputMode="decimal"
          min={min}
          max={max}
          step={step}
          value={text}
          aria-invalid={invalid}
          aria-describedby={`${id}-hint`}
          onChange={(e) => {
            setText(e.target.value);
            const n = e.target.value.trim() === '' ? NaN : Number(e.target.value);
            onChange(Number.isFinite(n) ? n : null);
          }}
          className={`input-field py-2 pr-12 text-sm font-mono tabular ${invalid ? '!border-red-400' : ''}`}
        />
        <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-xs text-gray-400">min</span>
      </span>
      <span id={`${id}-hint`} className="block text-[11px] text-gray-500 mt-1">{hint}</span>
    </label>
  );
}

const PHASE_FILL: Record<string, string> = {
  baseline: '#F3F4F6',
  ramp: '#FDE7C2',
  active: '#FBD38D',
  recovery: '#FEF3C7',
  after: '#F3F4F6',
};

function TimelinePreview({ timing, hasEvent }: { timing: Timing; hasEvent: boolean }) {
  const W = 640;
  const H = 96;
  const top = 10;
  const base = 62;
  const x = (min: number) => (Math.min(Math.max(min, 0), timing.duration) / timing.duration) * W;
  const list = hasEvent ? phases(timing) : [{ id: 'baseline' as const, label: 'Normal operation', from: 0, to: timing.duration }];

  const samples = 160;
  const pts = Array.from({ length: samples + 1 }, (_, i) => {
    const m = (i / samples) * timing.duration;
    const e = hasEvent ? envelopeAt(timing, m) : 0;
    return `${x(m).toFixed(1)},${(base - e * (base - top)).toFixed(1)}`;
  });
  const area = `M0,${base} L${pts.join(' L')} L${W},${base} Z`;
  const ticks = Array.from({ length: Math.floor(timing.duration / 5) + 1 }, (_, i) => i * 5);
  const overflow = hasEvent && minutesNeeded(timing) > timing.duration;

  return (
    <figure>
      <figcaption className="flex flex-wrap items-baseline justify-between gap-2 mb-2">
        <span className="text-sm font-semibold text-gray-800">Timeline preview</span>
        <span className="text-xs text-gray-500">Effect strength across the {formatMinutes(timing.duration)} run</span>
      </figcaption>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" role="img"
        aria-label={list.map((p) => `${p.label} from minute ${p.from} to ${p.to}`).join('; ')}>
        {list.map((p) => (
          <rect key={p.id} x={x(p.from)} y={top - 6} width={Math.max(x(p.to) - x(p.from), 0)} height={base - top + 6} fill={PHASE_FILL[p.id]} />
        ))}
        {hasEvent && (
          <>
            <path d={area} fill={STATE_STYLE.anomalous.color} fillOpacity={0.18} />
            <polyline points={pts.join(' ')} fill="none" stroke={STATE_STYLE.anomalous.color} strokeWidth={2} strokeLinejoin="round" />
            <line x1={x(timing.onset)} x2={x(timing.onset)} y1={top - 6} y2={base} stroke={COLORS.ink} strokeWidth={1} strokeDasharray="3 3" />
          </>
        )}
        {!hasEvent && <line x1={0} x2={W} y1={base} y2={base} stroke={COLORS.normal} strokeWidth={2} />}
        <line x1={0} x2={W} y1={base} y2={base} stroke={COLORS.grid} strokeWidth={1} />
        {ticks.map((t) => (
          <g key={t}>
            <line x1={x(t)} x2={x(t)} y1={base} y2={base + 4} stroke={COLORS.muted} />
            <text x={x(t)} y={base + 16} fontSize={11} fill={COLORS.muted}
              textAnchor={t === 0 ? 'start' : x(t) > W - 24 ? 'end' : 'middle'}>
              {t} min
            </text>
          </g>
        ))}
      </svg>
      <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1.5 text-xs text-gray-600">
        {list.map((p) => (
          <li key={p.id} className="inline-flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-sm border border-black/5" style={{ background: PHASE_FILL[p.id] }} aria-hidden />
            {p.label} <span className="tabular text-gray-400">{formatMinutes(p.to - p.from)}</span>
          </li>
        ))}
      </ul>
      {overflow && (
        <p className="mt-2 text-xs font-semibold text-red-700">The event runs past the end of the run.</p>
      )}
    </figure>
  );
}

function LaunchSummary({ type, methodLabel, target, readout, timing, hasEvent, speed, playSeconds, issues, serverErr, launching, onLaunch }: {
  type: ScenarioType;
  methodLabel: string | null;
  target: string | null;
  readout: string | null;
  timing: Timing;
  hasEvent: boolean;
  speed: number;
  playSeconds: number;
  issues: string[];
  serverErr: string | null;
  launching: boolean;
  onLaunch: () => void;
}) {
  const Icon = TYPE_ICONS[type.id] ?? Activity;
  const ready = issues.length === 0;
  const rows: [string, string][] = [
    ['Scenario', hasEvent && methodLabel && type.methods.length > 1 ? `${sentenceCase(type.label)}, ${methodLabel.toLowerCase()}` : sentenceCase(type.label)],
  ];
  if (hasEvent) {
    rows.push(['Target', target ?? 'Not chosen yet']);
    if (readout) rows.push(['Strength', readout]);
    rows.push(['Starts', `${formatMinutes(timing.onset)} into the run`]);
    rows.push(['Lasts', timing.recovery
      ? `${formatMinutes(timing.ramp)} ramp, ${formatMinutes(timing.active)} active, ${RECOVERY_MIN} min recovery`
      : `${formatMinutes(timing.ramp)} ramp, then holds to the end`]);
  }
  rows.push(['Run', `${formatMinutes(timing.duration)} at ${speed}×, plays in ${formatMinutes(playSeconds / 60)}`]);

  return (
    <div className="glass-card p-5 space-y-4">
      <div className="flex items-center gap-3">
        <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-500 text-white">
          <Icon className="w-5 h-5" aria-hidden />
        </span>
        <div>
          <h2 className="text-base font-semibold text-gray-900">Launch summary</h2>
          {type.cyber && (
            <p className="inline-flex items-center gap-1 text-xs font-semibold text-pink-700">
              <ShieldAlert className="w-3 h-3" aria-hidden /> Cyber scenario
            </p>
          )}
        </div>
      </div>

      <dl className="space-y-2.5 text-sm">
        {rows.map(([k, v]) => (
          <div key={k} className="grid grid-cols-[5rem_minmax(0,1fr)] gap-2">
            <dt className="text-gray-500">{k}</dt>
            <dd className={`text-gray-900 ${v === 'Not chosen yet' ? 'text-red-700 font-semibold' : ''}`}>{v}</dd>
          </div>
        ))}
      </dl>

      {issues.length > 0 && (
        <ul className="space-y-1.5 rounded-lg bg-red-50 px-3 py-2.5 text-sm text-red-800" aria-live="polite">
          {issues.map((i) => (
            <li key={i} className="flex gap-2">
              <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" aria-hidden /> {i}
            </li>
          ))}
        </ul>
      )}
      {serverErr && (
        <p className="flex gap-2 rounded-lg bg-red-50 px-3 py-2.5 text-sm text-red-800" role="alert">
          <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" aria-hidden /> {serverErr}
        </p>
      )}

      <button type="button" onClick={onLaunch} disabled={!ready || launching}
        className="btn-primary w-full flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed">
        {launching ? <Loader2 className="w-4 h-4 animate-spin" aria-hidden /> : <Rocket className="w-4 h-4" aria-hidden />}
        {launching ? 'Launching...' : 'Launch and watch'}
      </button>
      <p className="text-xs text-gray-500">
        The run is simulated and scored at launch, then revealed at {speed}× in the live run view.
      </p>
    </div>
  );
}
