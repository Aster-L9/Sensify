import React from 'react';
import { CheckCircle2, CircleDot, Loader, Search } from 'lucide-react';
import type { IncidentStatus } from '@/lib/types';

const STATUS: Record<IncidentStatus, { label: string; icon: typeof Search; cls: string }> = {
  developing: { label: 'Developing', icon: Loader, cls: 'bg-amber-50 text-amber-800' },
  open: { label: 'Open', icon: CircleDot, cls: 'bg-gray-100 text-gray-700' },
  investigating: { label: 'Investigating', icon: Search, cls: 'bg-indigo-50 text-indigo-800' },
  resolved: { label: 'Resolved', icon: CheckCircle2, cls: 'bg-emerald-50 text-emerald-800' },
};

export const STATUS_OPTIONS: IncidentStatus[] = ['developing', 'investigating', 'resolved'];
export const statusLabel = (s: IncidentStatus) => STATUS[s]?.label ?? s;

/** Status as icon plus word plus colour. */
export function StatusBadge({ status }: { status: IncidentStatus }) {
  const s = STATUS[status] ?? STATUS.open;
  const Icon = s.icon;
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-semibold ${s.cls}`}>
      <Icon className="w-3.5 h-3.5" aria-hidden /> {s.label}
    </span>
  );
}
