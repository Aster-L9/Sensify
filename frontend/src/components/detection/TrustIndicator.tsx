'use client';

import React from 'react';
import { ShieldAlert, ShieldCheck, ShieldX } from 'lucide-react';
import { TRUST_STYLE } from '@/lib/detection';
import type { TrustFactor, TrustStatus } from '@/lib/types';

const ZONES: { status: TrustStatus; from: number; to: number; fill: string }[] = [
  { status: 'Contradicted', from: 0, to: 0.4, fill: '#FBCFE8' },
  { status: 'Review', from: 0.4, to: 0.7, fill: '#FCE7F3' },
  { status: 'Supported', from: 0.7, to: 1, fill: '#EEF0FB' },
];

const ICONS: Record<TrustStatus, typeof ShieldCheck> = {
  Supported: ShieldCheck,
  Review: ShieldAlert,
  Contradicted: ShieldX,
};

interface TrustIndicatorProps {
  score: number | null;
  status: TrustStatus | null;
  factors: TrustFactor[];
  compact?: boolean;
}

/** How believable a segment's reported readings are, and what lowered that belief. */
export function TrustIndicator({ score, status, factors, compact = false }: TrustIndicatorProps) {
  if (score === null || status === null) {
    return <p className="text-sm text-gray-500">Trust is shown once the run has been scored by a model.</p>;
  }
  const tone = TRUST_STYLE[status];
  const Icon = ICONS[status];
  const pct = Math.min(Math.max(score, 0), 1) * 100;

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <span className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-sm font-semibold"
          style={{ background: tone.soft, color: tone.color }}>
          <Icon className="w-4 h-4" aria-hidden /> {tone.label}
        </span>
        <span className="font-mono tabular text-sm text-gray-700" aria-label={`Trust score ${score.toFixed(2)} out of 1`}>
          {score.toFixed(2)}
        </span>
      </div>

      <div className="relative" aria-hidden>
        <div className="flex h-2.5 rounded-full overflow-hidden">
          {ZONES.map((z) => (
            <div key={z.status} style={{ width: `${(z.to - z.from) * 100}%`, background: z.fill }} />
          ))}
        </div>
        <div className="absolute -top-1 h-[18px] w-[3px] rounded-full bg-gray-900" style={{ left: `calc(${pct}% - 1.5px)` }} />
        {!compact && (
          <div className="flex text-[11px] text-gray-500 mt-1.5">
            {ZONES.map((z) => (
              <span key={z.status} style={{ width: `${(z.to - z.from) * 100}%` }} className="text-center">{z.status}</span>
            ))}
          </div>
        )}
      </div>

      {factors.length === 0 ? (
        <p className="text-sm text-gray-500">Nothing is lowering trust: readings agree with the neighbouring segments.</p>
      ) : (
        <ul className="space-y-2.5">
          {factors.slice(0, compact ? 2 : 6).map((f) => (
            <li key={f.code + f.detail} className="text-sm">
              <div className="flex items-center justify-between gap-3">
                <span className="font-semibold text-gray-800">{f.label}</span>
                <span className="flex items-center gap-1.5 text-xs text-gray-500" title="Weight of this factor">
                  <span className="block h-1.5 w-14 rounded-full bg-gray-100 overflow-hidden" aria-hidden>
                    <span className="block h-full rounded-full" style={{ width: `${f.weight * 100}%`, background: tone.color }} />
                  </span>
                  −{f.penalty.toFixed(2)}
                </span>
              </div>
              <p className="text-gray-600 leading-snug mt-0.5">{f.detail}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
