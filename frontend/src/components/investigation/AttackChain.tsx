import React from 'react';
import { ArrowRight } from 'lucide-react';
import { formatTick } from '@/lib/detection';
import type { ChainStage } from '@/lib/types';

interface AttackChainProps {
  chain: ChainStage[];
  onSelect?: (stage: ChainStage) => void;
}

/** Ordered stages linked by arrows. Renders nothing when there is no chain. */
export function AttackChain({ chain, onSelect }: AttackChainProps) {
  if (!chain || chain.length === 0) return null;
  return (
    <ol className="flex flex-wrap items-stretch gap-y-2" aria-label="Sequence of observed stages">
      {chain.map((s, i) => (
        <li key={`${s.stage}-${i}`} className="flex items-center">
          {i > 0 && <ArrowRight size={16} className="mx-1.5 text-gray-400 shrink-0" aria-hidden="true" />}
          <button
            type="button"
            onClick={() => onSelect?.(s)}
            disabled={!onSelect}
            className="text-left rounded-lg border border-indigo-200 bg-indigo-50/60 px-3 py-1.5 enabled:hover:bg-indigo-50 enabled:cursor-pointer disabled:cursor-default"
          >
            <span className="block text-sm font-medium text-gray-800">{s.label}</span>
            <span className="block text-xs text-gray-500 tabular">
              {formatTick(s.tick)}{s.segment ? ` at ${s.segment}` : ''}
            </span>
          </button>
        </li>
      ))}
    </ol>
  );
}
