import React from 'react';
import { CATEGORY_STYLE, confidenceWord } from '@/lib/investigation';
import type { Classification, Hypothesis } from '@/lib/types';

interface ConfidenceMeterProps {
  confidence: number;
  label?: string;
  hypotheses?: Hypothesis[];
  classification?: Classification;
}

function Bar({ value, color, dashed }: { value: number; color: string; dashed?: boolean }) {
  const pct = Math.round(Math.max(0, Math.min(1, value)) * 100);
  return (
    <div className="h-2 flex-1 rounded-full bg-gray-100 overflow-hidden" role="presentation">
      <div
        className="h-full rounded-full"
        style={{
          width: `${pct}%`,
          backgroundColor: dashed ? 'transparent' : color,
          backgroundImage: dashed
            ? `repeating-linear-gradient(90deg, ${color} 0 6px, transparent 6px 9px)`
            : undefined,
        }}
      />
    </div>
  );
}

/** Short meter with a number and a word. Uncertain shows the top two hypotheses as bars instead. */
export function ConfidenceMeter({ confidence, label, hypotheses, classification }: ConfidenceMeterProps) {
  const word = label ?? confidenceWord(confidence);
  const showHypotheses = classification === 'uncertain' && hypotheses && hypotheses.length > 0;

  if (showHypotheses) {
    const top = [...hypotheses!].sort((a, b) => b.score - a.score).slice(0, 2);
    return (
      <div className="space-y-1.5" aria-label={`Confidence: ${word}. Two hypotheses are close`}>
        <p className="text-xs text-gray-500">Two hypotheses are close</p>
        {top.map((h) => {
          const style = CATEGORY_STYLE[h.category] ?? CATEGORY_STYLE.uncertain;
          return (
            <div key={h.category} className="flex items-center gap-2">
              <span className="w-48 shrink-0 truncate text-xs text-gray-700" title={style.label}>{style.label}</span>
              <Bar value={h.score} color={style.color} />
              <span className="tabular text-xs text-gray-600 w-9 text-right">{Math.round(h.score * 100)} %</span>
            </div>
          );
        })}
      </div>
    );
  }

  const color = classification ? CATEGORY_STYLE[classification].color : '#4B4AA3';
  return (
    <div className="flex items-center gap-2" aria-label={`Confidence: ${word}, ${Math.round(confidence * 100)} percent`}>
      <div className="w-24">
        <Bar value={confidence} color={color} />
      </div>
      <span className="tabular text-sm text-gray-800">{Math.round(confidence * 100)} %</span>
      <span className="text-sm text-gray-500">{word}</span>
    </div>
  );
}
