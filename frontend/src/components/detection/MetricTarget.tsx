import React from 'react';
import { CheckCircle2, XCircle } from 'lucide-react';

interface MetricTargetProps {
  label: string;
  value: number | null;
  target: number;
  op: '>=' | '<=';
  passed: boolean;
  format: (v: number) => string;
}

/** A measured value against its goal; pass/fail is spelled out, not just coloured. */
export function MetricTarget({ label, value, target, op, passed, format }: MetricTargetProps) {
  return (
    <div className={`rounded-xl border p-4 ${passed ? 'border-gray-200 bg-white' : 'border-amber-300 bg-amber-50/60'}`}>
      <p className="text-sm text-gray-600 leading-snug">{label}</p>
      <p className="mt-2 text-2xl font-bold text-gray-900 font-mono tabular">{value === null ? '—' : format(value)}</p>
      <div className="mt-1 flex items-center justify-between gap-2 text-xs">
        <span className="text-gray-500">Goal {op === '>=' ? '≥' : '≤'} {format(target)}</span>
        <span className={`inline-flex items-center gap-1 font-semibold ${passed ? 'text-brand-600' : 'text-amber-800'}`}>
          {passed ? <CheckCircle2 className="w-3.5 h-3.5" aria-hidden /> : <XCircle className="w-3.5 h-3.5" aria-hidden />}
          {passed ? 'Met' : 'Missed'}
        </span>
      </div>
    </div>
  );
}
