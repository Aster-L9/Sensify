'use client';

import React, { useCallback, useEffect, useState } from 'react';
import {
  AlertCircle, BrainCircuit, CheckCircle2, CircleDot, Loader2, Play, Shield, XCircle,
} from 'lucide-react';
import { activateModel, getModel, getModels, trainModel } from '@/lib/api';
import type { DetectionMetrics, ModelDetail, ModelVersion } from '@/lib/types';
import { COLORS, SCENARIO_LABELS, formatDateTime } from '@/lib/detection';
import { useAuth } from '@/contexts/AuthContext';
import { usePolling } from '@/hooks/usePolling';
import { LoadingState, ErrorState, EmptyState } from '@/components/ui/States';
import { MetricTarget } from '@/components/detection/MetricTarget';

const TRAIN_LIMITS = {
  n_estimators: { min: 50, max: 400, step: 10, fallback: 150 },
  max_samples: { min: 64, max: 1024, step: 32, fallback: 256 },
  alpha_pct: { min: 0.1, max: 5, step: 0.1, fallback: 0.4 }, // the API takes alpha as a fraction (0.001 to 0.05)
};

/** Percentages that stay readable when tiny (a 0.005 % false-low rate should not print as 0.00 %). */
function pct(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined) return '—';
  const p = value * 100;
  const shown = p !== 0 && Math.abs(p) < 0.01 ? 3 : p !== 0 && Math.abs(p) < 0.1 ? Math.max(digits, 2) : digits;
  return `${p.toFixed(shown)} %`;
}

const seconds = (v: number | null | undefined) => (v === null || v === undefined ? '—' : `${Math.round(v)} s`);
const perRun = (v: number | null | undefined) => (v === null || v === undefined ? '—' : v.toFixed(2));

const TARGET_FORMAT: Record<string, (v: number) => string> = {
  median_time_to_detect: seconds,
  false_windows_per_run: perRun,
};

function lowestType(ml?: DetectionMetrics): string | null {
  if (!ml) return null;
  const entries = Object.entries(ml.per_type).filter(([, v]) => v.rate !== null);
  if (!entries.length) return null;
  const [type] = entries.reduce((a, b) => ((b[1].rate ?? 1) < (a[1].rate ?? 1) ? b : a));
  return SCENARIO_LABELS[type] ?? type;
}

export default function ModelsPage() {
  const { isAdmin } = useAuth();
  if (!isAdmin) {
    return (
      <div className="glass-card p-12 text-center border-red-500/30">
        <Shield className="w-12 h-12 text-red-400 mx-auto mb-3" aria-hidden />
        <h2 className="text-xl font-bold text-gray-900">Access Restricted</h2>
        <p className="text-sm text-gray-500 mt-1">Only administrators can train and activate models.</p>
      </div>
    );
  }
  return <Models />;
}

function Models() {
  const [models, setModels] = useState<ModelVersion[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<ModelDetail | null>(null);
  const [activeDetail, setActiveDetail] = useState<ModelDetail | null>(null);
  const [actionErr, setActionErr] = useState<string | null>(null);
  const [activating, setActivating] = useState<number | null>(null);

  const refresh = useCallback(async () => {
    try {
      setModels(await getModels());
      setErr(null);
    } catch (e: any) {
      setErr(e.message || 'Could not load models');
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const training = models?.find((m) => m.status === 'training') ?? null;
  const active = models?.find((m) => m.is_active) ?? null;
  usePolling(refresh, 2000, !!training);

  useEffect(() => {
    if (active && active.status === 'ready') getModel(active.id).then(setActiveDetail).catch(() => undefined);
    else setActiveDetail(null);
  }, [active?.id, active?.status]); // eslint-disable-line react-hooks/exhaustive-deps

  const shownId = selectedId ?? active?.id ?? null;
  const shownStatus = models?.find((m) => m.id === shownId)?.status;
  useEffect(() => {
    if (shownId === null || shownStatus !== 'ready') {
      setDetail(null);
      return;
    }
    getModel(shownId).then(setDetail).catch(() => setDetail(null));
  }, [shownId, shownStatus]);

  const activate = async (id: number) => {
    setActivating(id);
    setActionErr(null);
    try {
      await activateModel(id);
      await refresh();
    } catch (e: any) {
      setActionErr(e.message || 'Could not activate the model');
    } finally {
      setActivating(null);
    }
  };

  if (err && !models) return <ErrorState message={err} onRetry={refresh} />;
  if (!models) return <LoadingState message="Loading models..." />;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
          <BrainCircuit className="w-6 h-6 text-brand-500" aria-hidden /> Models
        </h1>
        <p className="text-sm text-gray-500 mt-1 max-w-3xl">
          Each version learns normal behaviour from normal runs only, then is graded once on held-out test runs it
          never saw. New runs are scored with the active version; earlier runs keep the version that scored them.
        </p>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_320px] gap-6 items-start">
        <ActiveModelCard model={active} detail={activeDetail} />
        <TrainPanel training={training} onStarted={refresh} lastFailed={models.find((m) => m.status === 'failed') ?? null} />
      </div>

      <section className="glass-card overflow-hidden" aria-labelledby="versions-heading">
        <div className="flex flex-wrap items-baseline justify-between gap-2 px-5 pt-5 pb-3">
          <h2 id="versions-heading" className="text-base font-semibold text-gray-900">Versions</h2>
          <p className="text-xs text-gray-500">Figures are from each version&apos;s held-out test runs</p>
        </div>
        {actionErr && (
          <p className="mx-5 mb-3 flex gap-2 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800" role="alert">
            <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" aria-hidden /> {actionErr}
          </p>
        )}
        {models.length === 0 ? (
          <div className="p-5"><EmptyState title="No models yet" message="Train a version to start scoring runs." /></div>
        ) : (
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Version</th>
                  <th>Status</th>
                  <th>Trained</th>
                  <th>Detection</th>
                  <th>False windows per run</th>
                  <th>Precision</th>
                  <th>Median time to detect</th>
                  <th>Targets met</th>
                  <th><span className="sr-only">Actions</span></th>
                </tr>
              </thead>
              <tbody>
                {models.map((m) => (
                  <tr key={m.id} className={m.id === shownId ? 'bg-brand-50/50' : ''}>
                    <td>
                      <p className="font-semibold text-gray-900">v{m.version}</p>
                      {m.is_active && (
                        <span className="inline-flex items-center gap-1 rounded-full bg-brand-500 px-2 py-0.5 text-[11px] font-semibold text-white mt-0.5">
                          <CircleDot className="w-3 h-3" aria-hidden /> Active
                        </span>
                      )}
                    </td>
                    <td><StatusPill status={m.status} /></td>
                    <td className="text-sm text-gray-600 whitespace-nowrap">
                      {formatDateTime(m.created_at)}
                      <p className="text-xs text-gray-400">{m.created_by ? `by ${m.created_by}` : 'Shipped with Sensify'}</p>
                    </td>
                    <td className="font-mono tabular text-sm">{pct(m.headline.detection_rate)}</td>
                    <td className="font-mono tabular text-sm">{perRun(m.headline.false_windows_per_run)}</td>
                    <td className="font-mono tabular text-sm">{pct(m.headline.window_precision)}</td>
                    <td className="font-mono tabular text-sm">{seconds(m.headline.median_time_to_detect_s)}</td>
                    <td className="font-mono tabular text-sm whitespace-nowrap">
                      {m.status === 'ready' ? `${m.targets_passed} of ${m.targets_total}` : '—'}
                    </td>
                    <td>
                      <div className="flex items-center gap-1.5 justify-end">
                        {m.status === 'ready' && (
                          <button type="button" onClick={() => setSelectedId(m.id)} aria-pressed={m.id === shownId}
                            className="btn-ghost py-1 px-3 text-sm whitespace-nowrap">
                            {m.id === shownId ? 'Showing' : 'Details'}
                          </button>
                        )}
                        {m.status === 'ready' && !m.is_active && (
                          <button type="button" onClick={() => activate(m.id)} disabled={activating !== null}
                            className="btn-secondary py-1 px-3 text-sm whitespace-nowrap flex items-center gap-1.5 disabled:opacity-50">
                            {activating === m.id && <Loader2 className="w-3.5 h-3.5 animate-spin" aria-hidden />} Set active
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {detail && <VersionDetail model={detail} />}
    </div>
  );
}

function StatusPill({ status }: { status: ModelVersion['status'] }) {
  if (status === 'training') {
    return (
      <span className="inline-flex items-center gap-1.5 text-sm text-brand-700">
        <Loader2 className="w-3.5 h-3.5 animate-spin" aria-hidden /> Training
      </span>
    );
  }
  if (status === 'failed') {
    return (
      <span className="inline-flex items-center gap-1.5 text-sm text-red-700">
        <XCircle className="w-3.5 h-3.5" aria-hidden /> Failed
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 text-sm text-gray-700">
      <CheckCircle2 className="w-3.5 h-3.5 text-brand-600" aria-hidden /> Ready
    </span>
  );
}

function ActiveModelCard({ model, detail }: { model: ModelVersion | null; detail: ModelDetail | null }) {
  if (!model) {
    return (
      <section className="glass-card p-5">
        <h2 className="text-base font-semibold text-gray-900">No active model</h2>
        <p className="text-sm text-gray-600 mt-1">
          Runs are not scored until a version is active. Train one, or set an existing version active below.
        </p>
      </section>
    );
  }
  const checks = detail ? Object.entries(detail.targets_check) : [];
  const lowest = lowestType(detail?.metrics.ml);

  return (
    <section className="glass-card p-5 space-y-4" aria-labelledby="active-heading">
      <div className="flex flex-col gap-3">
        <div>
          <h2 id="active-heading" className="text-base font-semibold text-gray-900">
            Active model: v{model.version}
          </h2>
          <p className="text-sm text-gray-600 mt-0.5">
            Isolation Forest per segment, {model.params.n_estimators ?? '—'} trees of {model.params.max_samples ?? '—'} samples,
            calibrated to a {pct(model.params.alpha, 1)} false-alarm rate. Trained {formatDateTime(model.created_at)}
            {model.trained_seconds ? ` in ${Math.round(model.trained_seconds)} s` : ''}.
          </p>
        </div>
        {detail && (
          <TargetsMeter passed={detail.targets_passed} total={detail.targets_total} />
        )}
      </div>
      {!detail ? (
        <p className="text-sm text-gray-500">Loading the test results...</p>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {checks.map(([key, c]) => (
            <MetricTarget
              key={key}
              label={targetLabel(detail, key, lowest)}
              value={c.value}
              target={c.target}
              op={c.op}
              passed={c.passed}
              format={TARGET_FORMAT[key] ?? ((v: number) => pct(v))}
            />
          ))}
        </div>
      )}
    </section>
  );
}

function targetLabel(detail: ModelDetail, key: string, lowest: string | null): string {
  const label = detail.targets[key]?.label ?? key.replace(/_/g, ' ');
  if (key === 'detection_rate_per_type' && lowest) return `${label.replace(' (lowest)', '')}, lowest: ${lowest.toLowerCase()}`;
  return label.replace(' (s)', '');
}

function TargetsMeter({ passed, total }: { passed: number; total: number }) {
  return (
    <div>
      <p className="text-sm font-semibold text-gray-900">{passed} of {total} targets met</p>
      <div className="mt-1.5 flex gap-1" aria-hidden>
        {Array.from({ length: total }, (_, i) => (
          <span key={i} className={`h-2 w-4 rounded-sm ${i < passed ? 'bg-brand-500' : 'bg-amber-300'}`} />
        ))}
      </div>
    </div>
  );
}

function TrainPanel({ training, onStarted, lastFailed }: {
  training: ModelVersion | null;
  onStarted: () => void;
  lastFailed: ModelVersion | null;
}) {
  const [trees, setTrees] = useState(String(TRAIN_LIMITS.n_estimators.fallback));
  const [samples, setSamples] = useState(String(TRAIN_LIMITS.max_samples.fallback));
  const [alpha, setAlpha] = useState(String(TRAIN_LIMITS.alpha_pct.fallback));
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [now, setNow] = useState(Date.now());

  useEffect(() => {
    if (!training) return;
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, [training]);

  const fields = [
    { key: 'n_estimators', label: 'Trees per segment', value: trees, set: setTrees, unit: '' },
    { key: 'max_samples', label: 'Samples per tree', value: samples, set: setSamples, unit: '' },
    { key: 'alpha_pct', label: 'Target false-alarm rate', value: alpha, set: setAlpha, unit: '%' },
  ] as const;

  const problems = fields.flatMap((f) => {
    const lim = TRAIN_LIMITS[f.key];
    const n = Number(f.value);
    if (f.value.trim() === '' || !Number.isFinite(n)) return [`Enter the ${f.label.toLowerCase()}.`];
    if (n < lim.min || n > lim.max) return [`${f.label} must be between ${lim.min} and ${lim.max}${f.unit ? ' %' : ''}.`];
    if (f.key !== 'alpha_pct' && !Number.isInteger(n)) return [`${f.label} must be a whole number.`];
    return [];
  });

  const submit = async () => {
    if (problems.length || training || submitting) return;
    setSubmitting(true);
    setErr(null);
    try {
      await trainModel({ n_estimators: Number(trees), max_samples: Number(samples), alpha: Number(alpha) / 100 });
      onStarted();
    } catch (e: any) {
      setErr(typeof e?.message === 'string' ? e.message : 'Training could not start');
    } finally {
      setSubmitting(false);
    }
  };

  const startedAt = training ? Date.parse(/Z|[+-]\d\d:\d\d$/.test(training.created_at) ? training.created_at : `${training.created_at}Z`) : NaN;
  const elapsed = Number.isFinite(startedAt) ? Math.max(0, Math.round((now - startedAt) / 1000)) : null;
  const showFailure = !training && lastFailed && lastFailed.error;

  return (
    <section className="glass-card p-5 space-y-4" aria-labelledby="train-heading">
      <div>
        <h2 id="train-heading" className="text-base font-semibold text-gray-900">Train a new version</h2>
        <p className="text-xs text-gray-500 mt-1">
          Uses the bundled mock dataset (normal runs for training, held-out runs for grading). Takes about half a
          minute; the new version is not activated automatically.
        </p>
      </div>
      <div className="space-y-3">
        {fields.map((f) => {
          const lim = TRAIN_LIMITS[f.key];
          return (
            <label key={f.key} className="block text-sm">
              <span className="flex items-baseline justify-between text-xs font-semibold text-gray-600 mb-1">
                {f.label}
                <span className="font-normal text-gray-400">{lim.min} to {lim.max}{f.unit ? ' %' : ''}</span>
              </span>
              <span className="relative block">
                <input type="number" inputMode="decimal" min={lim.min} max={lim.max} step={lim.step} value={f.value}
                  disabled={!!training} onChange={(e) => f.set(e.target.value)}
                  className="input-field py-2 text-sm font-mono tabular pr-8 disabled:opacity-60" />
                {f.unit && <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-xs text-gray-400">%</span>}
              </span>
            </label>
          );
        })}
      </div>

      {problems.length > 0 && (
        <ul className="space-y-1 text-sm text-red-700" aria-live="polite">
          {problems.map((p) => <li key={p}>{p}</li>)}
        </ul>
      )}

      {training ? (
        <div className="rounded-lg bg-brand-50 px-3 py-3 text-sm text-brand-800" role="status">
          <p className="flex items-center gap-2 font-semibold">
            <Loader2 className="w-4 h-4 animate-spin" aria-hidden /> Training v{training.version}
            {elapsed !== null && <span className="font-normal tabular text-brand-700">{elapsed} s</span>}
          </p>
          <p className="text-xs text-brand-700 mt-1">Fitting six forests, calibrating, then grading on the test runs.</p>
        </div>
      ) : (
        <button type="button" onClick={submit} disabled={problems.length > 0 || submitting}
          className="btn-primary w-full flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed">
          {submitting ? <Loader2 className="w-4 h-4 animate-spin" aria-hidden /> : <Play className="w-4 h-4" aria-hidden />}
          Start training
        </button>
      )}

      {err && (
        <p className="flex gap-2 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800" role="alert">
          <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" aria-hidden /> {err}
        </p>
      )}
      {showFailure && (
        <p className="flex gap-2 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800">
          <XCircle className="w-4 h-4 mt-0.5 shrink-0" aria-hidden />
          <span>v{lastFailed!.version} failed: {lastFailed!.error}</span>
        </p>
      )}
    </section>
  );
}

function VersionDetail({ model }: { model: ModelDetail }) {
  const ml = model.metrics.ml;
  const base = model.metrics.baseline;
  const trust = model.metrics.trust;
  if (!ml || !base) return null;
  const types = Object.keys(ml.per_type);

  const rows: { label: string; ml: string; base: string; better?: 'ml' | 'base' | null }[] = [
    { label: 'Overall detection rate', ml: pct(ml.overall.rate), base: pct(base.overall.rate),
      better: cmp(ml.overall.rate, base.overall.rate, 'high') },
    { label: 'Median time to detect', ml: seconds(ml.time_to_detect_s.median), base: seconds(base.time_to_detect_s.median),
      better: cmp(ml.time_to_detect_s.median, base.time_to_detect_s.median, 'low') },
    { label: 'Slowest 10 % detected within', ml: seconds(ml.time_to_detect_s.p90), base: seconds(base.time_to_detect_s.p90),
      better: cmp(ml.time_to_detect_s.p90, base.time_to_detect_s.p90, 'low') },
    { label: 'Tick false-alarm rate on normal runs', ml: pct(ml.false_alarm.tick_rate, 2), base: pct(base.false_alarm.tick_rate, 2),
      better: cmp(ml.false_alarm.tick_rate, base.false_alarm.tick_rate, 'low') },
    { label: 'False alert windows per normal run', ml: perRun(ml.false_alarm.windows_per_run), base: perRun(base.false_alarm.windows_per_run),
      better: cmp(ml.false_alarm.windows_per_run, base.false_alarm.windows_per_run, 'low') },
    { label: 'Window precision', ml: pct(ml.window_precision), base: pct(base.window_precision),
      better: cmp(ml.window_precision, base.window_precision, 'high') },
    { label: 'Flags the right segment (localization)', ml: pct(ml.localization_hit_rate), base: pct(base.localization_hit_rate),
      better: cmp(ml.localization_hit_rate, base.localization_hit_rate, 'high') },
    { label: 'ROC-AUC per segment and tick', ml: ml.roc_auc === null ? '—' : ml.roc_auc.toFixed(3), base: 'n/a', better: null },
  ];

  return (
    <section className="space-y-6" aria-labelledby="detail-heading">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="detail-heading" className="text-lg font-bold text-gray-900">Version v{model.version} in detail</h2>
        <p className="text-xs text-gray-500">Held-out test split, used once for grading and never for tuning</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="glass-card p-5">
          <h3 className="text-sm font-semibold text-gray-900">Detection by scenario type</h3>
          <p className="text-xs text-gray-500 mt-0.5 mb-4">Share of scenario runs flagged during the event</p>
          <div className="flex flex-wrap gap-4 text-xs text-gray-600 mb-4" aria-hidden>
            <span className="inline-flex items-center gap-1.5"><span className="h-2.5 w-5 rounded-sm" style={{ background: COLORS.normal }} /> Sensify model</span>
            <span className="inline-flex items-center gap-1.5"><span className="h-2.5 w-5 rounded-sm bg-gray-300" /> Threshold baseline</span>
          </div>
          <ul className="space-y-4">
            {types.map((t) => (
              <li key={t}>
                <p className="text-sm font-semibold text-gray-800 mb-1.5">{SCENARIO_LABELS[t] ?? t}</p>
                <Bar label="Sensify model" detected={ml.per_type[t].detected} total={ml.per_type[t].total} rate={ml.per_type[t].rate} color={COLORS.normal} />
                <Bar label="Threshold baseline" detected={base.per_type[t]?.detected ?? 0} total={base.per_type[t]?.total ?? 0} rate={base.per_type[t]?.rate ?? null} color="#D1D5DB" />
              </li>
            ))}
          </ul>
        </div>

        <div className="space-y-6">
          <div className="glass-card overflow-x-auto">
            <table className="data-table">
              <caption className="px-5 pt-5 pb-1 text-left text-sm font-semibold text-gray-900">Sensify model against the threshold baseline</caption>
              <thead>
                <tr>
                  <th>Measure</th>
                  <th className="!text-right">Model</th>
                  <th className="!text-right">Baseline</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.label}>
                    <td className="text-sm">{r.label}</td>
                    <td className={`text-right font-mono tabular text-sm ${r.better === 'ml' ? 'font-bold text-gray-900' : ''}`}>{r.ml}</td>
                    <td className={`text-right font-mono tabular text-sm ${r.better === 'base' ? 'font-bold text-gray-900' : ''}`}>{r.base}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="px-5 py-3 text-xs text-gray-500">The better value in each row is in bold.</p>
          </div>

          {trust && (
            <div className="glass-card p-5">
              <h3 className="text-sm font-semibold text-gray-900 mb-3">Telemetry trust</h3>
              <dl className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <dt className="text-xs text-gray-500">Tampered or faulty reporting caught</dt>
                  <dd className="text-xl font-bold font-mono tabular text-gray-900 mt-1">{pct(trust.compromise_detection_rate)}</dd>
                  <dd className="text-xs text-gray-500">of {trust.compromised_runs} runs with compromised readings</dd>
                </div>
                <div>
                  <dt className="text-xs text-gray-500">Honest readings wrongly doubted</dt>
                  <dd className="text-xl font-bold font-mono tabular text-gray-900 mt-1">{pct(trust.low_trust_rate_honest, 2)}</dd>
                  <dd className="text-xs text-gray-500">of segment ticks on honest runs</dd>
                </div>
              </dl>
            </div>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="glass-card p-5">
          <h3 className="text-sm font-semibold text-gray-900 mb-3">Training configuration</h3>
          <dl className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-4 gap-y-2 text-sm">
            <dt className="text-gray-500">Trees per segment</dt><dd className="font-mono tabular text-right">{model.params.n_estimators ?? '—'}</dd>
            <dt className="text-gray-500">Samples per tree</dt><dd className="font-mono tabular text-right">{model.params.max_samples ?? '—'}</dd>
            <dt className="text-gray-500">Target false-alarm rate</dt><dd className="font-mono tabular text-right">{pct(model.params.alpha, 1)}</dd>
            <dt className="text-gray-500">Random state</dt><dd className="font-mono tabular text-right">{model.params.random_state ?? '—'}</dd>
            <dt className="text-gray-500">Feature set</dt><dd className="font-mono tabular text-right">{model.feature_spec ?? '—'}</dd>
            <dt className="text-gray-500">Training time</dt><dd className="font-mono tabular text-right">{seconds(model.trained_seconds)}</dd>
          </dl>
        </div>
        <div className="glass-card p-5">
          <h3 className="text-sm font-semibold text-gray-900 mb-1">Dataset</h3>
          <p className="text-xs text-gray-500 mb-3">
            {model.dataset.runs ?? '—'} simulated runs{model.dataset.path ? ` from ${model.dataset.path}` : ''}
          </p>
          {model.dataset.splits && <SplitTable splits={model.dataset.splits} />}
        </div>
      </div>
    </section>
  );
}

function cmp(a: number | null, b: number | null, goal: 'high' | 'low'): 'ml' | 'base' | null {
  if (a === null || b === null || a === b) return null;
  return (goal === 'high' ? a > b : a < b) ? 'ml' : 'base';
}

function Bar({ label, detected, total, rate, color }: {
  label: string;
  detected: number;
  total: number;
  rate: number | null;
  color: string;
}) {
  const width = rate === null ? 0 : rate * 100;
  return (
    <div className="grid grid-cols-[7.5rem_minmax(0,1fr)_5.5rem] items-center gap-3 text-xs">
      <span className="text-gray-500">{label}</span>
      <span className="block h-2.5 rounded-full bg-gray-100 overflow-hidden" aria-hidden>
        <span className="block h-full rounded-full" style={{ width: `${width}%`, background: color }} />
      </span>
      <span className="text-right font-mono tabular text-gray-700">
        {detected}/{total} <span className="text-gray-400">{rate === null ? '' : `${Math.round(rate * 100)} %`}</span>
      </span>
    </div>
  );
}

function SplitTable({ splits }: { splits: Record<string, Record<string, number>> }) {
  const names = Object.keys(splits);
  const types = Array.from(new Set(names.flatMap((s) => Object.keys(splits[s]))));
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-xs text-gray-500">
            <th className="text-left font-semibold py-1.5 pr-3">Scenario type</th>
            {names.map((n) => <th key={n} className="text-right font-semibold py-1.5 px-2">{n.charAt(0).toUpperCase() + n.slice(1)}</th>)}
          </tr>
        </thead>
        <tbody>
          {types.map((t) => (
            <tr key={t} className="border-t border-gray-100">
              <td className="py-1.5 pr-3 text-gray-700">{SCENARIO_LABELS[t] ?? t}</td>
              {names.map((n) => <td key={n} className="py-1.5 px-2 text-right font-mono tabular text-gray-700">{splits[n][t] ?? 0}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
