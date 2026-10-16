'use client';

import React, { useEffect, useRef } from 'react';
import { X } from 'lucide-react';
import { CATEGORY_STYLE, formatTick } from '@/lib/detection';
import type { RunEvent } from '@/lib/types';

const AUTHORIZATION: Record<RunEvent['authorized'], string> = {
  yes: 'Authorized',
  no: 'Not authorized',
  unknown: 'Authorization unknown',
  'n/a': 'Not applicable',
};

/** Details of one event; Escape or the close button dismisses it. */
export function EventDrawer({ event, onClose }: { event: RunEvent | null; onClose: () => void }) {
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!event) return;
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [event, onClose]);

  if (!event) return null;
  const style = CATEGORY_STYLE[event.category] ?? CATEGORY_STYLE.analysis;
  const unauthorized = event.authorized === 'no';

  return (
    <div className="fixed inset-0 z-[10000] flex items-end md:items-stretch md:justify-end" role="dialog" aria-modal="true" aria-labelledby="event-title">
      <button className="absolute inset-0 bg-gray-900/20 cursor-default" aria-label="Close event details" onClick={onClose} tabIndex={-1} />
      <aside className="relative w-full md:w-[26rem] bg-white md:h-full rounded-t-2xl md:rounded-none md:rounded-l-2xl shadow-2xl p-6 space-y-5 overflow-y-auto animate-slide-in-right">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-sm font-medium" style={{ color: style.color }}>{style.label} event</p>
            <h2 id="event-title" className="text-lg font-bold text-gray-900 mt-0.5">{event.event_type}</h2>
          </div>
          <button ref={closeRef} onClick={onClose} className="p-2 rounded-lg text-gray-500 hover:bg-gray-100 hover:text-gray-900" aria-label="Close">
            <X className="w-4 h-4" />
          </button>
        </div>

        {unauthorized && (
          <p className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
            This action was not authorized.
          </p>
        )}

        <dl className="grid grid-cols-[8rem_1fr] gap-y-2.5 text-sm">
          <dt className="text-gray-500">When</dt>
          <dd className="font-mono tabular text-gray-900">{formatTick(event.tick)}</dd>
          <dt className="text-gray-500">Where</dt>
          <dd className="text-gray-900">{event.segment_code ?? 'Whole pipeline'}</dd>
          <dt className="text-gray-500">Source</dt>
          <dd className="text-gray-900">{event.source}</dd>
          <dt className="text-gray-500">Authorization</dt>
          <dd className={unauthorized ? 'text-red-700 font-semibold' : 'text-gray-900'}>{AUTHORIZATION[event.authorized]}</dd>
          <dt className="text-gray-500">Severity</dt>
          <dd className="text-gray-900 capitalize">{event.severity}</dd>
        </dl>

        {event.details && (
          <div>
            <h3 className="text-sm font-semibold text-gray-800 mb-1">Details</h3>
            <p className="text-sm text-gray-600 leading-relaxed">{event.details}</p>
          </div>
        )}
        {event.origin === 'analysis' && (
          <p className="text-xs text-gray-500">Raised by Sensify&apos;s analysis, not by the pipeline&apos;s control system.</p>
        )}
      </aside>
    </div>
  );
}
