'use client';

import { useEffect, useRef } from 'react';

/** Call `fn` now and then every `intervalMs` while `enabled`; always calls the latest `fn`. */
export function usePolling(fn: () => void | Promise<void>, intervalMs: number, enabled: boolean = true) {
  const saved = useRef(fn);

  useEffect(() => {
    saved.current = fn;
  }, [fn]);

  useEffect(() => {
    if (!enabled) return;
    let stopped = false;
    const tick = () => {
      if (!stopped && document.visibilityState !== 'hidden') void saved.current();
    };
    const id = window.setInterval(tick, intervalMs);
    return () => {
      stopped = true;
      window.clearInterval(id);
    };
  }, [intervalMs, enabled]);
}
