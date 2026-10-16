import React from 'react';
import { AlertTriangle, ShieldAlert } from 'lucide-react';
import { SEVERITY_STYLE, STATE_STYLE } from '@/lib/detection';
import type { AlertKind, Severity } from '@/lib/types';

export function SeverityChip({ severity }: { severity: Severity }) {
  const s = SEVERITY_STYLE[severity];
  const bars = severity === 'critical' ? 3 : severity === 'high' ? 2 : 1;
  return (
    <span className="inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 text-xs font-semibold" style={{ background: s.soft, color: s.color }}>
      <span className="flex items-end gap-[2px]" aria-hidden>
        {[1, 2, 3].map((b) => (
          <span key={b} className="w-[3px] rounded-sm" style={{ height: 4 + b * 2, background: b <= bars ? s.color : 'currentColor', opacity: b <= bars ? 1 : 0.2 }} />
        ))}
      </span>
      {s.label}
    </span>
  );
}

export function KindIcons({ kinds }: { kinds: AlertKind[] }) {
  return (
    <span className="inline-flex items-center gap-2 text-xs text-gray-600">
      {kinds.includes('anomaly') && (
        <span className="inline-flex items-center gap-1">
          <AlertTriangle className="w-3.5 h-3.5" style={{ color: STATE_STYLE.anomalous.color }} aria-hidden /> Anomaly
        </span>
      )}
      {kinds.includes('low_trust') && (
        <span className="inline-flex items-center gap-1">
          <ShieldAlert className="w-3.5 h-3.5" style={{ color: STATE_STYLE.low_trust.color }} aria-hidden /> Low trust
        </span>
      )}
    </span>
  );
}
