'use client';

import React, { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { ChevronRight, Menu, Pause } from 'lucide-react';
import { getRuns } from '@/lib/api';
import type { RunOut } from '@/lib/types';
import { formatTick } from '@/lib/detection';
import { usePolling } from '@/hooks/usePolling';

const CRUMB_LABELS: Record<string, string> = {
  dashboard: 'Dashboard',
  map: 'Pipeline map',
  runs: 'Simulation runs',
  alerts: 'Alerts',
  incidents: 'Incidents',
  evaluation: 'Evaluation',
  scenarios: 'Scenario builder',
  models: 'Models',
  admin: 'Administration',
  users: 'Users',
  profile: 'Profile',
};

function crumbLabel(segment: string, parent?: string): string {
  if (CRUMB_LABELS[segment]) return CRUMB_LABELS[segment];
  const decoded = decodeURIComponent(segment);
  if (parent === 'incidents') return `Incident ${decoded}`;
  if (parent === 'runs' && /^\d+$/.test(decoded)) return `Run ${decoded.padStart(4, '0')}`;
  return decoded;
}

export function TopBar({ onMenuClick }: { onMenuClick?: () => void }) {
  const pathname = usePathname();
  const [run, setRun] = useState<RunOut | null>(null);

  // The run everyone is watching: a playing one first, otherwise a paused one.
  const fetchRun = useCallback(async () => {
    try {
      const playing = await getRuns('active');
      setRun(playing[0] ?? (await getRuns('paused'))[0] ?? null);
    } catch {
      setRun(null);
    }
  }, []);
  useEffect(() => { fetchRun(); }, [pathname, fetchRun]);
  usePolling(fetchRun, 10000);

  const parts = pathname.split('/').filter(Boolean);
  const paused = run?.status === 'paused';

  return (
    <header className="h-16 bg-canvas/85 backdrop-blur-md px-5 md:px-8 flex items-center justify-between gap-4 sticky top-0 z-[9997] md:ml-60">
      <div className="flex items-center gap-1.5 text-sm min-w-0">
        <button className="md:hidden mr-1 btn-ghost p-2" onClick={onMenuClick} aria-label="Open navigation">
          <Menu className="w-5 h-5" aria-hidden />
        </button>
        <nav aria-label="Breadcrumb" className="flex items-center gap-1.5 min-w-0">
          {parts.map((segment, index) => {
            const href = `/${parts.slice(0, index + 1).join('/')}`;
            const isLast = index === parts.length - 1;
            const label = crumbLabel(segment, parts[index - 1]);
            return (
              <React.Fragment key={href}>
                {index > 0 && <ChevronRight className="w-3.5 h-3.5 text-gray-400 shrink-0 hidden sm:block" aria-hidden />}
                {isLast ? (
                  <span className="font-medium text-gray-900 truncate" aria-current="page">{label}</span>
                ) : segment === 'admin' ? (
                  <span className="text-gray-500 hidden sm:inline">{label}</span>
                ) : (
                  <Link href={href} className="text-gray-500 hover:text-gray-900 transition-colors hidden sm:inline">{label}</Link>
                )}
              </React.Fragment>
            );
          })}
        </nav>
      </div>

      {run ? (
        <Link
          href={`/runs/${run.id}`}
          className="group flex items-center gap-2.5 rounded-full bg-white shadow-sheet pl-3 pr-4 py-1.5 text-sm hover:shadow-lift transition-shadow animate-pop-in"
          title={paused ? 'This run is paused for everyone' : 'This run is playing'}
        >
          {paused ? (
            <Pause className="w-3.5 h-3.5 text-gray-500" aria-hidden />
          ) : (
            <span className="relative flex h-2 w-2" aria-hidden>
              <span className="absolute inline-flex h-full w-full rounded-full bg-brand-400 opacity-70 motion-safe:animate-ping" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-brand-600" />
            </span>
          )}
          <span className="font-medium text-gray-900">{run.name}</span>
          <span className="text-gray-500 hidden sm:inline">
            {paused ? 'paused at' : 'playing,'} <span className="tabular">{formatTick(run.revealed_ticks - 1, run.tick_seconds)}</span>
          </span>
        </Link>
      ) : (
        <span className="text-sm text-gray-500 hidden sm:inline">No run playing</span>
      )}
    </header>
  );
}
