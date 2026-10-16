import React from 'react';

interface StateProps {
  title?: string;
  message?: string;
  onRetry?: () => void;
  className?: string;
}

export function LoadingState({ message = 'Loading pipeline telemetry...' }: { message?: string }) {
  return (
    <div className="flex flex-col items-center justify-center p-12 text-center min-h-[250px]">
      <div className="relative w-12 h-12 mb-4">
        <div className="absolute inset-0 rounded-full border-2 border-brand-500/20 animate-ping"></div>
        <div className="w-12 h-12 rounded-full border-2 border-brand-500 border-t-transparent animate-spin"></div>
      </div>
      <p className="text-sm font-medium text-gray-500 animate-pulse">{message}</p>
    </div>
  );
}

export function EmptyState({
  title = 'No Data Found',
  message = 'There are no active records or simulation runs available.',
  action
}: StateProps & { action?: React.ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center p-12 text-center min-h-[250px] glass-card border-dashed border-gray-200">
      <div className="w-12 h-12 rounded-2xl bg-gray-50 border border-gray-200 flex items-center justify-center text-gray-500 mb-4">
        <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
        </svg>
      </div>
      <h3 className="text-base font-semibold text-gray-800 mb-1">{title}</h3>
      <p className="text-sm text-gray-500 max-w-sm mb-6">{message}</p>
      {action}
    </div>
  );
}

export function ErrorState({
  title = 'Connection Error',
  message = 'Failed to communicate with backend service. Please check your network or try again.',
  onRetry
}: StateProps) {
  return (
    <div className="flex flex-col items-center justify-center p-10 text-center min-h-[250px] glass-card border-red-500/20 bg-red-500/5">
      <div className="w-12 h-12 rounded-2xl bg-red-500/10 border border-red-500/20 flex items-center justify-center text-red-400 mb-4">
        <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>
      </div>
      <h3 className="text-base font-semibold text-gray-800 mb-1">{title}</h3>
      <p className="text-sm text-gray-500 max-w-md mb-6">{message}</p>
      {onRetry && (
        <button onClick={onRetry} className="btn-secondary text-sm py-2 px-4">
          Try Again
        </button>
      )}
    </div>
  );
}
