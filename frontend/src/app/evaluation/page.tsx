'use client';

import React, { useCallback, useEffect, useState } from 'react';
import { AlertCircle, CheckCircle2, FileDown, FlaskConical, Info, Loader2, Play, XCircle } from 'lucide-react';
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { downloadReport, getEvaluation, getEvaluations, runEvaluation } from '@/lib/api';
import type {
  EvalDatasetName, EvalSystem, EvaluationDataset, EvaluationDetail, EvaluationRunOut, TargetCheck,
} from '@/lib/types';
import { COLORS, formatDateTime } from '@/lib/detection';
import { CATEGORY_STYLE } from '@/lib/investigation';
import { useAuth } from '@/contexts/AuthContext';
import { usePolling } from '@/hooks/usePolling';
import { EmptyState, ErrorState, LoadingState } from '@/components/ui/States';

const SYSTEMS: EvalSystem[] = ['A', 'B', 'C'];
const SYSTEM_NAME: Record<EvalSystem, string> = { A: 'A: Threshold alarms', B: 'B: Anomaly model', C: 'C: Sensify investigation' };
const DATASET_NAME: Record<EvalDatasetName, string> = { development: 'Development', heldout: 'Held-out' };

type Fmt = 'pct' | 'sec' | 'per_run';
interface Criterion {
  key: string; // target key, when one exists
  label: string;
  fmt: Fmt;
  chart?: boolean;
  classification?: boolean; // not available for A and B
  get: (d: EvaluationDataset, s: EvalSystem) => number | null | undefined;
}

const rate = (r: { rate: number | null } | null | undefined) => r?.rate ?? null;

const CRITERIA: Criterion[] = [
  { key: 'detection_rate', label: 'Event detection rate', fmt: 'pct', chart: true, get: (d, s) => d.systems[s].detection.overall.rate },
  { key: 'detection_rate_per_type', label: 'Detection rate, lowest scenario type', fmt: 'pct', get: (d, s) => d.systems[s].detection.per_type_min_rate },
  { key: 'tick_false_alarm_rate', label: 'Tick false-alarm rate on normal runs', fmt: 'pct', get: (d, s) => d.systems[s].detection.false_alarm.tick_rate },
  { key: 'false_windows_per_run', label: 'False alert windows per normal run', fmt: 'per_run', get: (d, s) => d.systems[s].detection.false_alarm.windows_per_run },
  { key: 'window_precision', label: 'Window precision', fmt: 'pct', chart: true, get: (d, s) => d.systems[s].detection.window_precision },
  { key: 'median_time_to_detect', label: 'Median time to detect', fmt: 'sec', get: (d, s) => d.systems[s].detection.time_to_detect_s.median },
  { key: 'incident_detection', label: 'Incident detection', fmt: 'pct', chart: true, get: (d, s) => rate(d.systems[s].investigation.incident_detection) },
  { key: 'classification_accuracy', label: 'Classification accuracy', fmt: 'pct', chart: true, classification: true, get: (d, s) => rate(d.systems[s].investigation.classification_accuracy) },
  { key: 'decision_coverage', label: 'Decision coverage', fmt: 'pct', classification: true, get: (d, s) => rate(d.systems[s].investigation.decision_coverage) },
  { key: 'ambiguity_handled', label: 'Ambiguous runs with an acceptable outcome', fmt: 'pct', classification: true, get: (d, s) => rate(d.systems[s].investigation.ambiguity_handled) },
  { key: 'segment_localisation', label: 'Segment localisation', fmt: 'pct', chart: true, get: (d, s) => rate(d.systems[s].investigation.segment_localisation) },
  { key: 'ot_layer_accuracy', label: 'OT layer accuracy', fmt: 'pct', chart: true, classification: true, get: (d, s) => rate(d.systems[s].investigation.ot_layer_accuracy) },
  { key: 'unexplained_per_normal_run', label: 'Unexplained incidents per normal run', fmt: 'per_run', get: (d, s) => d.systems[s].investigation.unexplained_per_normal_run },
];

function fmtValue(v: number | null | undefined, fmt: Fmt): string {
  if (v === null || v === undefined) return '—';
  if (fmt === 'sec') return `${Math.round(v)} s`;
  if (fmt === 'per_run') return v.toFixed(2);
  const p = v * 100;
  return `${p.toFixed(Math.abs(p) < 0.1 && p !== 0 ? 2 : 1)} %`;
}

function targetText(c: TargetCheck, fmt: Fmt): string {
  return `${c.op === '>=' ? 'at least' : 'at most'} ${fmtValue(c.target, fmt)}`;
}

function TargetCell({ check, fmt }: { check: TargetCheck | undefined; fmt: Fmt }) {
  if (!check) return <span className="text-gray-400">No target</span>;
  return (
    <span className={`inline-flex items-center gap-1.5 font-semibold ${check.passed ? 'text-brand-700' : 'text-amber-800'}`}>
      {check.passed ? <CheckCircle2 className="w-4 h-4" aria-hidden /> : <XCircle className="w-4 h-4" aria-hidden />}
      {check.passed ? 'Met' : 'Missed'}
      <span className="font-normal text-xs text-gray-500">{targetText(check, fmt)}</span>
    </span>
  );
}

export default function EvaluationPage() {
  const { isAdmin } = useAuth();
  const [runs, setRuns] = useState<EvaluationRunOut[] | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<EvaluationDetail | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [detailErr, setDetailErr] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setRuns(await getEvaluations());
      setErr(null);
    } catch (e: any) {
      setErr(e.message || 'Could not load evaluations');
    }
  }, []);
  useEffect(() => { refresh(); }, [refresh]);

  const running = runs?.some((r) => r.status === 'running') ?? false;
  usePolling(refresh, 2000, running);

  const latestReady = runs?.filter((r) => r.status === 'ready').sort((a, b) => b.version - a.version)[0] ?? null;
  const shownId = selectedId ?? latestReady?.id ?? null;
  const shownStatus = runs?.find((r) => r.id === shownId)?.status;

  useEffect(() => {
    if (shownId === null || shownStatus !== 'ready') { setDetail(null); return; }
    setDetailErr(null);
    getEvaluation(shownId).then(setDetail).catch((e: any) => { setDetail(null); setDetailErr(e.message || 'Could not load this evaluation'); });
  }, [shownId, shownStatus]);

  if (err && !runs) return <ErrorState message={err} onRetry={refresh} />;
  if (!runs) return <LoadingState message="Loading evaluations..." />;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-[28px] leading-tight text-gray-900">Evaluation</h1>
        <p className="text-sm text-gray-500 mt-1 max-w-3xl">
          Three systems are compared on the same runs: threshold alarms (A), the anomaly model (B) and the full Sensify
          investigation (C). Development results were used while building and tuning. Held-out results were looked at once
          and are reported separately.
        </p>
      </div>

      {isAdmin && <RunPanel runs={runs} running={running} onStarted={refresh} />}

      {runs.length === 0 ? (
        <EmptyState title="No evaluations yet" message={isAdmin ? 'Run an evaluation to compare the three systems.' : 'No evaluation has been run yet.'} />
      ) : (
        <>
          <History runs={runs} shownId={shownId} onSelect={setSelectedId} />
          {detailErr && (
            <p className="flex gap-2 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800" role="alert">
              <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" aria-hidden /> {detailErr}
            </p>
          )}
          {shownId !== null && shownStatus === 'ready' && !detail && !detailErr && <LoadingState message="Loading results..." />}
          {detail?.results && <Results detail={detail} />}
        </>
      )}
    </div>
  );
}

function RunPanel({ runs, running, onStarted }: { runs: EvaluationRunOut[]; running: boolean; onStarted: () => void }) {
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const live = runs.find((r) => r.status === 'running');
  const newest = runs.reduce<EvaluationRunOut | null>((m, r) => (!m || r.id > m.id ? r : m), null);
  const failed = newest && newest.status === 'failed' && newest.error ? newest : null;

  const start = async () => {
    setSubmitting(true);
    setErr(null);
    try {
      await runEvaluation();
      onStarted();
    } catch (e: any) {
      setErr(typeof e?.message === 'string' ? e.message : 'The evaluation could not start');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section className="glass-card p-5 space-y-3" aria-labelledby="eval-run-heading">
      <h2 id="eval-run-heading" className="text-base font-semibold text-gray-900">Run an evaluation</h2>
      <p className="text-xs text-gray-500 max-w-3xl">
        Scores the active model and engine on the bundled development and held-out runs. It takes a short while and is
        recorded in the history below.
      </p>
      {running ? (
        <p className="flex items-center gap-2 rounded-lg bg-brand-50 px-3 py-3 text-sm font-semibold text-brand-800" role="status">
          <Loader2 className="w-4 h-4 animate-spin" aria-hidden /> Evaluation {live ? `e${live.version} ` : ''}is running
        </p>
      ) : (
        <button type="button" onClick={start} disabled={submitting} className="btn-primary flex items-center gap-2 disabled:opacity-50">
          {submitting ? <Loader2 className="w-4 h-4 animate-spin" aria-hidden /> : <Play className="w-4 h-4" aria-hidden />} Run evaluation
        </button>
      )}
      {err && (
        <p className="flex gap-2 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800" role="alert">
          <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" aria-hidden /> {err}
        </p>
      )}
      {failed && !running && (
        <p className="flex gap-2 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800">
          <XCircle className="w-4 h-4 mt-0.5 shrink-0" aria-hidden /> e{failed.version} failed: {failed.error}
        </p>
      )}
    </section>
  );
}

function History({ runs, shownId, onSelect }: { runs: EvaluationRunOut[]; shownId: number | null; onSelect: (id: number) => void }) {
  return (
    <section className="glass-card overflow-hidden" aria-labelledby="eval-history-heading">
      <h2 id="eval-history-heading" className="text-base font-semibold text-gray-900 px-5 pt-5 pb-3">History</h2>
      <div className="overflow-x-auto">
        <table className="data-table">
          <thead>
            <tr><th>Evaluation</th><th>Status</th><th>Created</th><th>Model</th><th>Engine</th><th><span className="sr-only">Actions</span></th></tr>
          </thead>
          <tbody>
            {runs.map((r) => (
              <tr key={r.id} className={r.id === shownId ? 'bg-brand-50/50' : ''}>
                <td>
                  <p className="font-semibold text-gray-900">e{r.version}</p>
                  <p className="text-xs text-gray-400">{r.shipped ? 'Shipped with Sensify' : r.created_by ? `by ${r.created_by}` : 'Run in this app'}</p>
                </td>
                <td className="text-sm">
                  {r.status === 'running' && <span className="inline-flex items-center gap-1.5 text-brand-700"><Loader2 className="w-3.5 h-3.5 animate-spin" aria-hidden /> Running</span>}
                  {r.status === 'ready' && <span className="inline-flex items-center gap-1.5 text-gray-700"><CheckCircle2 className="w-3.5 h-3.5 text-brand-600" aria-hidden /> Ready</span>}
                  {r.status === 'failed' && <span className="inline-flex items-center gap-1.5 text-red-700"><XCircle className="w-3.5 h-3.5" aria-hidden /> Failed</span>}
                </td>
                <td className="text-sm text-gray-600 whitespace-nowrap">{formatDateTime(r.created_at)}</td>
                <td className="text-sm font-mono tabular">{r.model_version !== null ? `v${r.model_version}` : '—'}</td>
                <td className="text-sm tabular">{r.engine_version ? `Engine ${r.engine_version}` : '—'}</td>
                <td className="text-right">
                  {r.status === 'ready' && (
                    <button type="button" onClick={() => onSelect(r.id)} aria-pressed={r.id === shownId} className="btn-ghost py-1 px-3 text-sm">
                      {r.id === shownId ? 'Showing' : 'Show'}
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function Results({ detail }: { detail: EvaluationDetail }) {
  const results = detail.results!;
  const [exportErr, setExportErr] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const extra = results as unknown as Record<string, unknown>;
  const disclosure = (extra.disclosure ?? extra.rerun_disclosure ?? null) as string | null;
  const hasRerun = !!disclosure || !!extra.rerun || !!extra.first_look;

  const exportAs = async (format: 'pdf' | 'csv') => {
    setBusy(format);
    setExportErr(null);
    try { await downloadReport('evaluation', detail.id, format); }
    catch (e: any) { setExportErr(e.message || 'Export failed'); }
    finally { setBusy(null); }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-bold text-gray-900">Results of e{detail.version}</h2>
        <div className="flex gap-2">
          {(['pdf', 'csv'] as const).map((f) => (
            <button key={f} type="button" onClick={() => exportAs(f)} disabled={busy !== null}
              className="btn-secondary py-1.5 px-3 text-sm flex items-center gap-1.5 disabled:opacity-50">
              {busy === f ? <Loader2 className="w-4 h-4 animate-spin" aria-hidden /> : <FileDown className="w-4 h-4" aria-hidden />} Export {f.toUpperCase()}
            </button>
          ))}
        </div>
      </div>
      {exportErr && (
        <p className="flex gap-2 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800" role="alert">
          <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" aria-hidden /> {exportErr}
        </p>
      )}
      {hasRerun && (
        <p className="flex gap-2 rounded-lg bg-amber-50 border border-amber-200 px-3 py-2 text-sm text-amber-900" role="note">
          <Info className="w-4 h-4 mt-0.5 shrink-0" aria-hidden />
          {typeof disclosure === 'string' ? disclosure : 'These results include a re-run after the first look. The first look is kept in the history and was not replaced.'}
        </p>
      )}

      {(['development', 'heldout'] as const).map((ds) => (
        <DatasetTable key={ds} name={ds} data={results.datasets[ds]} checks={results.targets_check?.[ds] ?? {}} />
      ))}

      <Charts results={results.datasets} />
      <Confusion data={results.datasets.heldout} title="Held-out" />
      <Confusion data={results.datasets.development} title="Development" />
    </div>
  );
}

function DatasetTable({ name, data, checks }: { name: EvalDatasetName; data: EvaluationDataset; checks: Record<string, TargetCheck> }) {
  const held = name === 'heldout';
  return (
    <section className={`glass-card overflow-hidden ${held ? 'border-2 border-dashed border-brand-300' : ''}`} aria-labelledby={`tbl-${name}`}>
      <div className="px-5 pt-5 pb-3">
        <h3 id={`tbl-${name}`} className="text-base font-semibold text-gray-900">{DATASET_NAME[name]} results</h3>
        <p className="text-xs text-gray-500">
          {data.runs} runs. {held ? 'Looked at once, never used for tuning.' : 'Used while building and tuning, so treat as optimistic.'}
        </p>
      </div>
      <div className="overflow-x-auto">
        <table className="data-table">
          <thead>
            <tr>
              <th>Criterion</th>
              {SYSTEMS.map((s) => <th key={s} className="!text-right">{SYSTEM_NAME[s]}</th>)}
              <th>Target for C</th>
            </tr>
          </thead>
          <tbody>
            {CRITERIA.map((c) => (
              <tr key={c.key}>
                <td className="text-sm">{c.label}</td>
                {SYSTEMS.map((s) => (
                  <td key={s} className="text-right font-mono tabular text-sm">
                    {c.classification && s !== 'C' ? <span className="font-sans text-gray-400">Not available</span> : fmtValue(c.get(data, s), c.fmt)}
                  </td>
                ))}
                <td className="text-sm whitespace-nowrap"><TargetCell check={checks[c.key]} fmt={c.fmt} /></td>
              </tr>
            ))}
            <tr>
              <td className="text-sm">Compromised reporting caught (trust)</td>
              <td colSpan={2} className="text-right text-sm text-gray-400">Not part of this comparison</td>
              <td className="text-right font-mono tabular text-sm">{fmtValue(data.trust.compromise_detection_rate, 'pct')}</td>
              <td className="text-sm whitespace-nowrap"><TargetCell check={checks.trust_compromise_detection} fmt="pct" /></td>
            </tr>
            <tr>
              <td className="text-sm">Honest readings wrongly doubted (trust)</td>
              <td colSpan={2} className="text-right text-sm text-gray-400">Not part of this comparison</td>
              <td className="text-right font-mono tabular text-sm">{fmtValue(data.trust.low_trust_rate_honest, 'pct')}</td>
              <td className="text-sm whitespace-nowrap"><TargetCell check={checks.trust_false_low_rate} fmt="pct" /></td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  );
}

function Charts({ results }: { results: Record<EvalDatasetName, EvaluationDataset> }) {
  const charts = CRITERIA.filter((c) => c.chart);
  return (
    <section aria-labelledby="charts-heading" className="space-y-3">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h3 id="charts-heading" className="text-base font-semibold text-gray-900">Side by side</h3>
        <ul className="flex gap-4 text-xs text-gray-600" aria-label="Legend">
          <li className="flex items-center gap-1.5">
            <svg width="16" height="12" aria-hidden><rect width="16" height="12" rx="2" fill={COLORS.normal} /></svg> Development
          </li>
          <li className="flex items-center gap-1.5">
            <svg width="16" height="12" aria-hidden>
              <defs>
                <pattern id="legend-hatch" width="4" height="4" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
                  <rect width="4" height="4" fill="#fff" />
                  <line x1="0" y1="0" x2="0" y2="4" stroke={COLORS.normal} strokeWidth="2" />
                </pattern>
              </defs>
              <rect x="0.75" y="0.75" width="14.5" height="10.5" rx="2" fill="url(#legend-hatch)" stroke={COLORS.normal} strokeWidth="1.5" />
            </svg> Held-out
          </li>
        </ul>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {charts.map((c, i) => {
          const data = SYSTEMS.map((s) => {
            const na = c.classification && s !== 'C';
            return {
              system: s,
              Development: na ? null : c.get(results.development, s) ?? null,
              'Held-out': na ? null : c.get(results.heldout, s) ?? null,
            };
          });
          const pid = `hatch-${i}`;
          return (
            <figure key={c.key} className="glass-card p-4">
              <figcaption className="text-sm font-semibold text-gray-900">{c.label}</figcaption>
              <div className="h-48 mt-2">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={data} margin={{ top: 4, right: 4, left: -16, bottom: 0 }}>
                    <defs>
                      <pattern id={pid} width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
                        <rect width="5" height="5" fill="#fff" />
                        <line x1="0" y1="0" x2="0" y2="5" stroke={COLORS.normal} strokeWidth="2.5" />
                      </pattern>
                    </defs>
                    <CartesianGrid stroke={COLORS.grid} vertical={false} />
                    <XAxis dataKey="system" stroke={COLORS.muted} fontSize={11} tickLine={false} tickFormatter={(s) => `System ${s}`} />
                    <YAxis domain={[0, 1]} tickFormatter={(v) => `${Math.round(v * 100)}`} stroke={COLORS.muted} fontSize={11} tickLine={false} />
                    <Tooltip formatter={(v: any) => fmtValue(typeof v === 'number' ? v : null, 'pct')} cursor={{ fill: '#F3F4F6' }} />
                    <Bar dataKey="Development" fill={COLORS.normal} isAnimationActive={false} radius={[3, 3, 0, 0]} />
                    <Bar dataKey="Held-out" fill={`url(#${pid})`} stroke={COLORS.normal} strokeWidth={1.5} isAnimationActive={false} radius={[3, 3, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <p className="text-xs text-gray-500">Percent.{c.classification ? ' Not available for A and B.' : ''}</p>
            </figure>
          );
        })}
      </div>
    </section>
  );
}

function Confusion({ data, title }: { data: EvaluationDataset; title: string }) {
  const conf = data.systems.C.investigation.confusion ?? {};
  const rows = Object.keys(conf);
  if (!rows.length) return null;
  const cols = Array.from(new Set([...rows, ...rows.flatMap((r) => Object.keys(conf[r]))]));
  const max = Math.max(1, ...rows.flatMap((r) => Object.values(conf[r])));
  const label = (k: string) => (CATEGORY_STYLE as Record<string, { label: string }>)[k]?.label ?? k;
  return (
    <section className="glass-card p-5" aria-labelledby={`conf-${title}`}>
      <h3 id={`conf-${title}`} className="text-base font-semibold text-gray-900">Confusion matrix for C, {title.toLowerCase()}</h3>
      <p className="text-xs text-gray-500 mb-3">Rows are the expected outcome, columns are what Sensify reported. The outlined diagonal is a correct outcome.</p>
      <div className="overflow-x-auto">
        <table className="text-sm border-separate border-spacing-1">
          <thead>
            <tr>
              <th className="text-left text-xs font-semibold text-gray-500 pr-2">Expected / reported</th>
              {cols.map((c) => <th key={c} className="text-xs font-semibold text-gray-600 max-w-[8rem] align-bottom">{label(c)}</th>)}
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r}>
                <th scope="row" className="text-left text-xs font-semibold text-gray-700 pr-2 max-w-[10rem]">{label(r)}</th>
                {cols.map((c) => {
                  const n = conf[r][c] ?? 0;
                  return (
                    <td key={c} className={`text-center font-mono tabular rounded-md px-2 py-1.5 ${r === c ? 'ring-2 ring-brand-400' : ''}`}
                      style={{ background: n ? `rgba(113,105,213,${0.1 + 0.6 * (n / max)})` : '#F9FAFB', color: n && n / max > 0.6 ? '#fff' : '#111827' }}>
                      {n}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
