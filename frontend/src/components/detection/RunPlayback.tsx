'use client';

import React, { useEffect, useState } from 'react';
import { Pause, Play, Radio } from 'lucide-react';
import { formatTick } from '@/lib/detection';

interface RunPlaybackProps {
  status: 'active' | 'completed';
  revealedTicks: number;
  durationTicks: number;
  playbackSpeed: number;
  tick: number;
  live: boolean;
  onTick: (tick: number) => void;
  onLive: () => void;
}

/** Where the viewer is in a run: the revealed part can be scrubbed and replayed; Live follows playback. */
export function RunPlayback({ status, revealedTicks, durationTicks, playbackSpeed, tick, live, onTick, onLive }: RunPlaybackProps) {
  const [replaying, setReplaying] = useState(false);
  const last = Math.max(revealedTicks - 1, 0);
  const revealedPct = (revealedTicks / durationTicks) * 100;

  useEffect(() => {
    if (!replaying) return;
    const id = window.setInterval(() => {
      if (tick >= last) {
        setReplaying(false);
        if (status === 'active') onLive();
        return;
      }
      onTick(Math.min(tick + 2, last));
    }, 200);
    return () => window.clearInterval(id);
  }, [replaying, tick, last, status, onTick, onLive]);

  const scrub = (value: number) => {
    setReplaying(false);
    onTick(Math.min(value, last));
  };

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3 text-sm">
          {status === 'active' ? (
            <span className="inline-flex items-center gap-2 font-semibold text-brand-600">
              <span className="relative flex h-2.5 w-2.5" aria-hidden>
                <span className="absolute inline-flex h-full w-full rounded-full bg-brand-400 opacity-60 motion-safe:animate-ping" />
                <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-brand-500" />
              </span>
              Playing at {playbackSpeed}×
            </span>
          ) : (
            <span className="font-semibold text-gray-700">Completed</span>
          )}
          <span className="font-mono tabular text-gray-900">{formatTick(tick)}</span>
          <span className="text-gray-500">of {formatTick(durationTicks - 1)}</span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => (replaying ? setReplaying(false) : (tick >= last ? (onTick(0), setReplaying(true)) : setReplaying(true)))}
            className="btn-secondary py-1.5 px-3 text-sm flex items-center gap-1.5"
            aria-label={replaying ? 'Pause replay' : 'Replay from the cursor'}
          >
            {replaying ? <Pause className="w-4 h-4" aria-hidden /> : <Play className="w-4 h-4" aria-hidden />}
            {replaying ? 'Pause' : 'Replay'}
          </button>
          <button
            onClick={() => { setReplaying(false); onLive(); }}
            disabled={live}
            aria-pressed={live}
            className={`py-1.5 px-3 text-sm rounded-xl flex items-center gap-1.5 border transition-colors ${
              live ? 'bg-brand-500 text-white border-brand-500' : 'bg-white text-gray-700 border-gray-200 hover:bg-gray-50'
            }`}
          >
            <Radio className="w-4 h-4" aria-hidden /> {status === 'active' ? 'Live' : 'Latest'}
          </button>
        </div>
      </div>

      <div className="relative h-6 flex items-center">
        <div className="absolute inset-x-0 h-1.5 rounded-full bg-gray-100 overflow-hidden" aria-hidden>
          <div className="h-full bg-brand-200" style={{ width: `${revealedPct}%` }} />
        </div>
        <input
          type="range"
          min={0}
          max={durationTicks - 1}
          value={tick}
          onChange={(e) => scrub(Number(e.target.value))}
          aria-label="Run time"
          aria-valuetext={`${formatTick(tick)} of ${formatTick(durationTicks - 1)}`}
          className="playback-range relative w-full"
        />
      </div>
    </div>
  );
}
