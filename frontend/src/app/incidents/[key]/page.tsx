'use client';

import React, { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { ArrowLeft, Download, FileSearch, ShieldCheck } from 'lucide-react';
import { ApiError, downloadReport, getIncident, getRun, setIncidentStatus } from '@/lib/api';
import type { EvidenceItem, IncidentDetail, RunOut } from '@/lib/types';
import { CATEGORY_STYLE, OT_LAYER_LABELS } from '@/lib/investigation';
import { formatTick } from '@/lib/detection';
import { usePolling } from '@/hooks/usePolling';
import { useToast } from '@/components/ui/Toast';
import { EmptyState, ErrorState, LoadingState } from '@/components/ui/States';
import { SeverityChip } from '@/components/detection/SeverityChip';
import { AttackChain } from '@/components/investigation/AttackChain';
import { ClassificationMark } from '@/components/investigation/ClassificationMark';
import { ConfidenceMeter } from '@/components/investigation/ConfidenceMeter';
import { EvidenceList } from '@/components/investigation/EvidenceList';
import { EvidenceRail } from '@/components/investigation/EvidenceRail';
import { TimelineList } from '@/components/investigation/TimelineList';
import { StatusBadge } from '../StatusBadge';

export default function IncidentPage() {
  const params = useParams();
  const key = decodeURIComponent(String(params.key));
  const { success, error: toastError } = useToast();

  const [inc, setInc] = useState<IncidentDetail | null>(null);
  const [run, setRun] = useState<RunOut | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const d = await getIncident(key);
      setInc(d);
      setErr(null);
      getRun(d.run_id).then(setRun).catch(() => undefined);
    } catch (e: any) {
      if (e instanceof ApiError && e.status === 404) setNotFound(true);
      else setErr(e.message || 'Could not load the incident');
    }
  }, [key]);

  useEffect(() => { load(); }, [load]);
  usePolling(load, 3000, Boolean(inc?.developing) && !notFound);

  // Scroll to #evidence once the content exists.
  useEffect(() => {
    if (inc && window.location.hash === '#evidence') {
      document.getElementById('evidence')?.scrollIntoView();
    }
  }, [inc?.key]); // eslint-disable-line react-hooks/exhaustive-deps

  if (notFound) {
    return (
      <EmptyState
        title="Incident not found"
        message="This incident does not exist, or the link was edited."
        action={<Link href="/incidents" className="btn-primary px-4 py-2 text-sm">Back to incidents</Link>}
      />
    );
  }
  if (!inc && !err) return <LoadingState message="Loading incident..." />;
  if (!inc) return <ErrorState message={err ?? undefined} onRetry={load} />;

  const developing = inc.developing || inc.status === 'developing';
  const resolved = inc.status === 'resolved';
  const uncertain = inc.classification === 'uncertain';
  const duration = run?.duration_ticks ?? Math.max(inc.end_tick + 1, 2);
  const unc = inc.uncertainty as { hypotheses?: string[]; discriminators?: string[] } | null;

  const change = async () => {
    setBusy(true);
    try {
      const next = await setIncidentStatus(inc.key, resolved ? 'investigating' : 'resolved', note.trim() || undefined);
      setInc(next);
      setNote('');
      success(resolved ? 'Incident reopened' : 'Incident resolved');
    } catch (e: any) {
      toastError('Could not change the status', e.message);
    } finally {
      setBusy(false);
    }
  };

  const download = async (format: 'pdf' | 'csv') => {
    try {
      await downloadReport('incident', inc.key, format);
    } catch (e: any) {
      toastError('Report download failed', e.message);
    }
  };

  const select = (e: EvidenceItem) => {
    setSelected(e.id);
    document.getElementById(`evidence-${e.id}`)?.scrollIntoView({ block: 'center' });
  };

  return (
    <div className="space-y-6">
      <Link href="/incidents" className="inline-flex items-center gap-1.5 text-sm text-gray-600 hover:text-brand-600">
        <ArrowLeft className="w-4 h-4" aria-hidden /> Incidents
      </Link>

      <header className="glass-card p-5 space-y-4">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="space-y-3">
            <h1 className="sr-only">Incident in {inc.run_name}</h1>
            <ClassificationMark classification={inc.classification} size="lg" />
            <ConfidenceMeter confidence={inc.confidence} classification={inc.classification} hypotheses={inc.hypotheses} />
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button onClick={() => download('pdf')} className="btn-ghost py-1.5 px-3 text-sm flex items-center gap-1.5">
              <Download className="w-4 h-4" aria-hidden /> PDF
            </button>
            <button onClick={() => download('csv')} className="btn-ghost py-1.5 px-3 text-sm flex items-center gap-1.5">
              <Download className="w-4 h-4" aria-hidden /> CSV
            </button>
          </div>
        </div>

        <dl className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-4 border-t border-gray-100 text-sm">
          <div>
            <dt className="text-xs font-semibold text-gray-600 mb-1">Location</dt>
            <dd>
              {inc.segment_code ? (
                <>
                  <p className="font-semibold text-gray-900">{inc.segment_code}, {inc.segment_name}</p>
                  {inc.ot_layers.length > 0 && (
                    <p className="text-gray-600">{inc.ot_layers.map((l) => OT_LAYER_LABELS[l] ?? l).join(', ')}</p>
                  )}
                </>
              ) : (
                <p className="text-gray-700">Not localised</p>
              )}
              {inc.localisation_note && <p className="text-xs text-gray-500 mt-0.5">{inc.localisation_note}</p>}
            </dd>
          </div>
          <div>
            <dt className="text-xs font-semibold text-gray-600 mb-1">Severity and run</dt>
            <dd className="space-y-1.5">
              <SeverityChip severity={inc.severity} />
              <p>
                <Link href={`/runs/${inc.run_id}`} className="text-gray-900 hover:text-brand-600 hover:underline">{inc.run_name}</Link>
              </p>
              <p className="font-mono tabular text-xs text-gray-500">
                {formatTick(inc.start_tick, run?.tick_seconds)} to {developing ? 'now' : formatTick(inc.end_tick, run?.tick_seconds)}
              </p>
            </dd>
          </div>
          <div>
            <dt className="text-xs font-semibold text-gray-600 mb-1">Status</dt>
            <dd className="space-y-2">
              <StatusBadge status={developing ? 'developing' : inc.status} />
              {inc.status_note && <p className="text-xs text-gray-600">Note: {inc.status_note}</p>}
              <label className="block">
                <span className="sr-only">Note (optional)</span>
                <input
                  value={note} onChange={(e) => setNote(e.target.value)} disabled={developing || busy}
                  placeholder="Note (optional)" maxLength={500} className="input-field py-1.5 text-sm"
                />
              </label>
              <button onClick={change} disabled={developing || busy} className="btn-primary py-1.5 px-3 text-sm disabled:opacity-50">
                {resolved ? 'Reopen incident' : 'Resolve incident'}
              </button>
              {developing && (
                <p className="text-xs text-gray-500">
                  The status can be changed once the run has finished playing, because the evidence is still arriving.
                </p>
              )}
            </dd>
          </div>
        </dl>
      </header>

      <section className="glass-card p-5" aria-label="Summary">
        <h2 className="text-base font-semibold text-gray-900">Summary</h2>
        <p className="text-sm text-gray-700 mt-1.5">{inc.summary}</p>
      </section>

      <section className="glass-card p-5 space-y-3" aria-label="Evidence rail">
        <AttackChain chain={inc.chain} onSelect={(s) => {
          const t = s.evidence_ids.map((id) => inc.evidence.find((e) => e.id === id)).find(Boolean);
          if (t) select(t);
        }} />
        <EvidenceRail durationTicks={duration} evidence={inc.evidence} chain={inc.chain} onSelect={select} />
      </section>

      {uncertain && (
        <section className="rounded-2xl border border-dashed border-gray-400 bg-white p-5 space-y-3" aria-label="Why Sensify is uncertain">
          <h2 className="text-base font-semibold text-gray-900">Why Sensify is uncertain</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {(unc?.hypotheses ?? inc.hypotheses.slice(0, 2).map((h) => h.category)).map((c) => {
              const h = inc.hypotheses.find((x) => x.category === c);
              const st = CATEGORY_STYLE[c as keyof typeof CATEGORY_STYLE] ?? CATEGORY_STYLE.uncertain;
              const Icon = st.icon;
              return (
                <div key={c} className="rounded-xl border border-gray-200 p-3">
                  <p className="flex items-center gap-2 text-sm font-semibold" style={{ color: st.color }}>
                    <Icon className="w-4 h-4" aria-hidden /> {st.label}
                  </p>
                  {h && <p className="text-xs text-gray-600 mt-1 tabular">Score {Math.round(h.score * 100)} %, {h.evidence_ids.length} supporting evidence</p>}
                </div>
              );
            })}
          </div>
          {unc?.discriminators && unc.discriminators.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-gray-800">What would tell them apart</h3>
              <ul className="list-disc pl-5 mt-1 text-sm text-gray-700 space-y-0.5">
                {unc.discriminators.map((d) => <li key={d}>{d}</li>)}
              </ul>
            </div>
          )}
        </section>
      )}

      <section id="evidence" className="glass-card p-5 space-y-3 scroll-mt-4" aria-label="Evidence">
        <h2 className="text-base font-semibold text-gray-900">Evidence</h2>
        <EvidenceList evidence={inc.evidence} runId={inc.run_id} selectedId={selected} />
      </section>

      <section className="glass-card p-5 space-y-3" aria-label="Timeline">
        <h2 className="text-base font-semibold text-gray-900">Timeline</h2>
        <TimelineList timeline={inc.timeline} />
      </section>

      <section className="glass-card p-5 space-y-3" aria-label="MITRE context">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="text-base font-semibold text-gray-900">MITRE context</h2>
          <span className="text-xs text-gray-500">Context, not attribution</span>
        </div>
        {inc.mitre.length === 0 ? (
          <p className="text-sm text-gray-500">No techniques are associated with this incident.</p>
        ) : (
          <ul className="divide-y divide-gray-100">
            {inc.mitre.map((t) => (
              <li key={t.technique_id} className="py-2">
                <p className="text-sm text-gray-900">
                  <span className="font-mono tabular">{t.technique_id}</span> {t.name}
                  <span className="text-gray-500">, {t.tactic}</span>
                </p>
                <p className="text-sm text-gray-600">{t.reason}</p>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="glass-card p-5 space-y-3" aria-label="Verification actions">
        <h2 className="text-base font-semibold text-gray-900 flex items-center gap-2">
          <ShieldCheck className="w-5 h-5 text-brand-500" aria-hidden /> Verification actions
        </h2>
        {inc.actions.length === 0 ? (
          <p className="text-sm text-gray-500">No checks suggested.</p>
        ) : (
          <ul className="list-disc pl-5 text-sm text-gray-700 space-y-1">
            {inc.actions.map((a) => <li key={a}>{a}</li>)}
          </ul>
        )}
      </section>
    </div>
  );
}
