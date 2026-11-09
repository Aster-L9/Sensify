import React from 'react';
import { AlertTriangle, Inbox, SearchX } from 'lucide-react';

interface StateProps {
  title?: string;
  message?: string;
  onRetry?: () => void;
  className?: string;
}

/** A short flowing line instead of a spinner: the same motion as the live pipeline. */
export function LoadingState({ message = 'Loading' }: { message?: string }) {
  return (
    <div className="flex flex-col items-center justify-center p-12 text-center min-h-[240px]" role="status" aria-live="polite">
      <svg width="120" height="8" viewBox="0 0 120 8" aria-hidden className="mb-4">
        <line x1="4" y1="4" x2="116" y2="4" stroke="#e3e5ed" strokeWidth="6" strokeLinecap="round" />
        <line x1="4" y1="4" x2="116" y2="4" stroke="#7169d5" strokeWidth="6" strokeLinecap="round" className="schematic-flow" />
      </svg>
      <p className="text-sm text-gray-500">{message}</p>
    </div>
  );
}

export function EmptyState({
  title = 'Nothing here yet',
  message = 'There is nothing to show for now.',
  action,
  icon = 'empty',
  className = '',
}: StateProps & { action?: React.ReactNode; icon?: 'empty' | 'search' }) {
  const Icon = icon === 'search' ? SearchX : Inbox;
  return (
    <div className={`flex flex-col items-center justify-center px-6 py-12 text-center animate-fade-in ${className}`} role="status">
      <span className="w-11 h-11 rounded-full bg-gray-100 text-gray-500 grid place-items-center mb-3">
        <Icon className="w-5 h-5" aria-hidden />
      </span>
      <h3 className="text-base font-semibold text-gray-900">{title}</h3>
      <p className="mt-1 text-sm text-gray-500 max-w-sm">{message}</p>
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function ErrorState({
  title = 'Could not reach Sensify',
  message = 'The server did not answer. Check that the backend is running, then try again.',
  onRetry,
  className = '',
}: StateProps) {
  return (
    <div className={`glass-card flex flex-col items-center justify-center px-6 py-10 text-center min-h-[220px] animate-fade-in ${className}`} role="alert">
      <span className="w-11 h-11 rounded-full bg-red-50 text-red-700 grid place-items-center mb-3">
        <AlertTriangle className="w-5 h-5" aria-hidden />
      </span>
      <h3 className="text-base font-semibold text-gray-900">{title}</h3>
      <p className="mt-1 text-sm text-gray-500 max-w-md">{message}</p>
      {onRetry && (
        <button onClick={onRetry} className="btn-secondary mt-4">
          Try again
        </button>
      )}
    </div>
  );
}
