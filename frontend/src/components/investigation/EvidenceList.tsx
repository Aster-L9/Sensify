'use client';

import React, { useMemo, useState } from 'react';
import Link from 'next/link';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { formatTick } from '@/lib/detection';
import type { EvidenceItem } from '@/lib/types';

interface EvidenceListProps {
  evidence: EvidenceItem[];
  runId: number;
  /** Id of an item to open and highlight (for example from a rail selection). */
  selectedId?: string | null;
}

export function evidenceHref(runId: number, e: EvidenceItem): string {
  const params = new URLSearchParams({ t: String(e.link?.tick ?? e.tick) });
  const seg = e.link?.segment ?? e.segment;
  if (seg) params.set('seg', seg);
  return `/runs/${runId}?${params}`;
}

/** Evidence grouped by kind; each item expands to show what it means and links to the run view. */
export function EvidenceList({ evidence, runId, selectedId }: EvidenceListProps) {
  const [open, setOpen] = useState<Record<string, boolean>>({});
  const groups = useMemo(() => {
    const m = new Map<string, EvidenceItem[]>();
    for (const e of evidence) m.set(e.kind, [...(m.get(e.kind) ?? []), e]);
    return Array.from(m.entries());
  }, [evidence]);

  if (evidence.length === 0) return <p className="text-sm text-gray-500">No evidence recorded.</p>;

  return (
    <div className="space-y-4">
      {groups.map(([kind, items]) => (
        <section key={kind}>
          <h4 className="text-sm font-semibold text-gray-800 mb-1.5">
            {kind.charAt(0).toUpperCase() + kind.slice(1)} <span className="tabular text-gray-500 font-normal">({items.length})</span>
          </h4>
          <ul className="divide-y divide-gray-100 rounded-xl border border-gray-100 bg-white/60">
            {items.map((e) => {
              const isOpen = open[e.id] || selectedId === e.id;
              return (
                <li key={e.id} id={`evidence-${e.id}`} className={selectedId === e.id ? 'bg-indigo-50/60' : ''}>
                  <button
                    type="button"
                    aria-expanded={isOpen}
                    onClick={() => setOpen((o) => ({ ...o, [e.id]: !o[e.id] }))}
                    className="w-full flex items-start gap-2 px-3 py-2 text-left"
                  >
                    {isOpen ? <ChevronDown size={16} className="mt-0.5 shrink-0 text-gray-400" aria-hidden="true" />
                      : <ChevronRight size={16} className="mt-0.5 shrink-0 text-gray-400" aria-hidden="true" />}
                    <span className="tabular text-xs text-gray-500 w-16 shrink-0 pt-0.5">{formatTick(e.tick)}</span>
                    <span className="text-sm text-gray-900">{e.observation}</span>
                  </button>
                  {isOpen && (
                    <div className="px-3 pb-3 pl-[5.75rem] space-y-1.5">
                      {e.interpretation && <p className="text-sm text-gray-500">{e.interpretation}</p>}
                      <p className="text-xs text-gray-500">
                        {e.segment ? `Segment ${e.segment}` : 'Pipeline-wide'}
                        {e.end_tick > e.tick ? `, until ${formatTick(e.end_tick)}` : ''}
                      </p>
                      <Link href={evidenceHref(runId, e)} className="text-sm font-medium text-indigo-700 hover:underline">
                        {e.link?.type === 'event' ? 'Show event in run' : 'Show in run'}
                      </Link>
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        </section>
      ))}
    </div>
  );
}
