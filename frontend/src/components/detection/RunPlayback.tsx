'use client';

import React, { useEffect, useState } from 'react';
import { Pause, Play, Radio, RotateCcw, Rewind } from 'lucide-react';
import { formatTick } from '@/lib/detection';
import { pauseRun, resetRun, resumeRun } from '@/lib/api';
import type { RunStatus } from '@/lib/types';
import { useToast } from '@/components/ui/Toast';

interface RunPlaybackProps {
  runId: number;
  status: RunStatus;
  revealedTicks: number;
  durationTicks: number;
  playbackSpeed: number;
  tick: number;
  live: boolean;
  onTick: (tick: number) => void;
  onLive: () => void;
  /** Administrators control the shared run; everyone else only moves their own cursor. */
  canControl?: boolean;
  onControlled?: () => void;
}

/**
 * Two kinds of control, kept apart on purpose:
 * - the run itself (administrators): pause, resume and reset change what every viewer sees;
 * - this viewer's cursor: scrub, replay and live only move the view in this browser.
 */
export function RunPlayback({
  runId, status, revealedTicks, durationTicks, playbackSpeed, tick, live, onTick, onLive, canControl = false, onControlled,
}: RunPlaybackProps) {
  const { success, error: toastError } = useToast();
  const [replaying, setReplaying] = useState(false);
  const [busy, setBusy] = useState(false);
  const [confirmReset, setConfirmReset] = useState(false);
  const last = Math.max(revealedTicks - 1, 0);
  const revealedPct = (revealedTicks / durationTicks) * 100;
  const cursorPct = (tick / Math.max(durationTicks - 1, 1)) * 100;

  useEffect(() => {
    if (!replaying) return;
    const id = window.setInterval(() => {
      if (tick >= last) {
        setReplaying(false);
        if (status !== 'completed') onLive();
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

  const control = async (action: 'pause' | 'resume' | 'reset') => {
    setBusy(true);
    try {
      const fn = { pause: pauseRun, resume: resumeRun, reset: resetRun }[action];
      const run = await fn(runId);
      const at = formatTick(run.revealed_ticks - 1, run.tick_seconds);
      success(
        { pause: 'Run paused', resume: 'Run resumed', reset: 'Run reset' }[action],
        { pause: `Everyone now sees ${at}.`, resume: `Playing again from ${at}.`, reset: 'Rewound to T+00:00 and paused. Resume to play it again.' }[action],
      );
      setConfirmReset(false);
      setReplaying(false);
      onLive();
      onControlled?.();
    } catch (e: any) {
      toastError(`Could not ${action} the run`, e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3 text-sm">
          {status === 'active' ? (
            <span className="inline-flex items-center gap-2 font-semibold text-brand-700">
              <span className="relative flex h-2.5 w-2.5" aria-hidden>
                <span className="absolute inline-flex h-full w-full rounded-full bg-brand-400 opacity-60 motion-safe:animate-ping" />
                <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-brand-600" />
              </span>
              Playing at {playbackSpeed}×
            </span>
          ) : status === 'paused' ? (
            <span className="inline-flex items-center gap-1.5 font-semibold text-gray-800">
              <Pause className="w-4 h-4" aria-hidden /> Paused for everyone
            </span>
          ) : (
            <span className="font-semibold text-gray-700">Completed</span>
          )}
          <span className="tabular text-gray-900 font-medium">{formatTick(tick)}</span>
          <span className="text-gray-500">of {formatTick(durationTicks - 1)}</span>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {canControl && (
            <div className="flex items-center gap-1 rounded-[12px] bg-gray-100 p-1" role="group" aria-label="Run controls for everyone">
              {status === 'active' && (
                <button onClick={() => control('pause')} disabled={busy} className="btn-ghost py-1.5 bg-white shadow-sheet text-gray-900">
                  <Pause className="w-4 h-4" aria-hidden /> Pause run
                </button>
              )}
              {status === 'paused' && (
                <button onClick={() => control('resume')} disabled={busy} className="btn-ghost py-1.5 bg-white shadow-sheet text-gray-900">
                  <Play className="w-4 h-4" aria-hidden /> Resume run
                </button>
              )}
              {confirmReset ? (
                <span className="flex items-center gap-1 pl-2 text-sm animate-pop-in">
                  <span className="text-gray-700">Rewind for everyone?</span>
                  <button onClick={() => control('reset')} disabled={busy} className="btn-ghost py-1.5 text-red-700 hover:bg-red-50">Reset</button>
                  <button onClick={() => setConfirmReset(false)} className="btn-ghost py-1.5">Cancel</button>
                </span>
              ) : (
                <button onClick={() => setConfirmReset(true)} disabled={busy} className="btn-ghost py-1.5"
                  title="Rewind this run to T+00:00 for everyone; its seed, settings and data stay the same">
                  <RotateCcw className="w-4 h-4" aria-hidden /> Reset
                </button>
              )}
            </div>
          )}
          <button
            onClick={() => (replaying ? setReplaying(false) : (tick >= last ? (onTick(0), setReplaying(true)) : setReplaying(true)))}
            className="btn-secondary py-1.5 px-3"
            aria-label={replaying ? 'Stop replay in this view' : 'Replay from the cursor in this view'}
            title="Moves only your view; the run carries on for everyone"
          >
            {replaying ? <Pause className="w-4 h-4" aria-hidden /> : <Rewind className="w-4 h-4" aria-hidden />}
            {replaying ? 'Stop replay' : 'Replay'}
          </button>
          <button
            onClick={() => { setReplaying(false); onLive(); }}
            disabled={live}
            aria-pressed={live}
            className={`inline-flex items-center gap-1.5 py-1.5 px-3 text-sm font-medium rounded-[10px] transition-colors ${
              live ? 'bg-brand-600 text-white' : 'bg-white text-gray-700 shadow-sheet hover:bg-gray-50'
            }`}
          >
            <Radio className="w-4 h-4" aria-hidden /> {status === 'active' ? 'Live' : 'Latest'}
          </button>
        </div>
      </div>

      <div className="relative h-6 flex items-center">
        <div className="absolute inset-x-0 h-1.5 rounded-full bg-gray-100 overflow-hidden" aria-hidden>
          <div className="h-full bg-brand-200 transition-[width] duration-700 ease-out" style={{ width: `${revealedPct}%` }} />
          <div className="absolute inset-y-0 left-0 bg-brand-500/70 transition-[width] duration-200 ease-out" style={{ width: `${Math.min(cursorPct, revealedPct)}%` }} />
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
