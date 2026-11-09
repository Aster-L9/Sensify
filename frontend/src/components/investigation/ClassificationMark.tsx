import React from 'react';
import { CATEGORY_STYLE } from '@/lib/investigation';
import type { Classification } from '@/lib/types';

interface ClassificationMarkProps {
  classification: Classification;
  size?: 'sm' | 'md' | 'lg';
}

const SIZES = {
  sm: { icon: 14, text: 'text-xs', pad: 'px-2 py-0.5 gap-1.5' },
  md: { icon: 16, text: 'text-sm', pad: 'px-2.5 py-1 gap-2' },
  lg: { icon: 20, text: 'text-base', pad: 'px-3 py-1.5 gap-2' },
};

/** Outcome as icon plus word plus colour; Uncertain gets a dashed outline. */
export function ClassificationMark({ classification, size = 'md' }: ClassificationMarkProps) {
  const style = CATEGORY_STYLE[classification] ?? CATEGORY_STYLE.uncertain;
  const s = SIZES[size];
  const Icon = style.icon;
  return (
    <span
      className={`inline-flex items-center rounded-full font-medium ${s.text} ${s.pad}`}
      style={{
        color: style.color,
        backgroundColor: style.dashed ? 'transparent' : `${style.color}12`,
        border: style.dashed ? `1.5px dashed ${style.color}` : '1.5px solid transparent',
      }}
    >
      <Icon size={s.icon} aria-hidden="true" className="shrink-0" />
      <span>{style.label}</span>
    </span>
  );
}
