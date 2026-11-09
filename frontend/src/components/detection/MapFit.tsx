'use client';

import { useEffect, useRef } from 'react';
import { useMap } from 'react-leaflet';

/**
 * Leaflet measures its container once, at creation; if the layout is still settling then (fonts,
 * the page's entrance, a panel opening beside it) the line ends up off-centre. Re-measure whenever
 * the container changes size, and fit the line the first time it has a real size.
 */
export default function MapFit({ bounds }: { bounds: [[number, number], [number, number]] }) {
  const map = useMap();
  const fitted = useRef(false);
  const key = JSON.stringify(bounds);

  useEffect(() => {
    const el = map.getContainer();
    const observer = new ResizeObserver(() => {
      map.invalidateSize();
      if (!fitted.current && el.clientWidth > 0 && el.clientHeight > 0) {
        map.fitBounds(bounds, { padding: [40, 40] });
        fitted.current = true;
      }
    });
    observer.observe(el);
    return () => observer.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map, key]);

  return null;
}
