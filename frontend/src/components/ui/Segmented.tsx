'use client';

import React, { useLayoutEffect, useRef, useState } from 'react';

interface Option<T extends string> { value: T; label: string }

/** Tabs or a small exclusive choice; the white thumb slides to the chosen option. */
export function Segmented<T extends string>({
  options, value, onChange, label, role = 'tablist',
}: { options: Option<T>[]; value: T; onChange: (v: T) => void; label: string; role?: 'tablist' | 'group' }) {
  const ref = useRef<HTMLDivElement>(null);
  const [thumb, setThumb] = useState<{ left: number; width: number } | null>(null);

  useLayoutEffect(() => {
    const el = ref.current?.querySelector<HTMLElement>(`[data-value="${value}"]`);
    if (el) setThumb({ left: el.offsetLeft, width: el.offsetWidth });
  }, [value, options.length]);

  return (
    <div ref={ref} className="segmented" role={role} aria-label={label}>
      {thumb && <span className="segmented-thumb" style={{ left: thumb.left, width: thumb.width }} aria-hidden />}
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          data-value={o.value}
          role={role === 'tablist' ? 'tab' : undefined}
          aria-selected={role === 'tablist' ? o.value === value : undefined}
          aria-pressed={role === 'group' ? o.value === value : undefined}
          onClick={() => onChange(o.value)}
          className="segmented-option"
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
