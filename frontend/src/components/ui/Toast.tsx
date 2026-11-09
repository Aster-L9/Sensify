'use client';

import React, { createContext, useContext, useState, useCallback } from 'react';
import { CheckCircle2, AlertCircle, XCircle, Info, X } from 'lucide-react';

export type ToastType = 'success' | 'error' | 'warning' | 'info';

interface ToastMessage {
  id: string;
  type: ToastType;
  title: string;
  description?: string;
}

interface ToastContextType {
  toast: (options: { type?: ToastType; title: string; description?: string }) => void;
  success: (title: string, description?: string) => void;
  error: (title: string, description?: string) => void;
}

const TOAST_MS = 4000;
const TONES: Record<ToastType, { icon: typeof Info; icon_class: string; bar: string }> = {
  success: { icon: CheckCircle2, icon_class: 'text-brand-600', bar: 'bg-brand-500' },
  error: { icon: XCircle, icon_class: 'text-red-600', bar: 'bg-red-500' },
  warning: { icon: AlertCircle, icon_class: 'text-amber-600', bar: 'bg-amber-500' },
  info: { icon: Info, icon_class: 'text-brand-600', bar: 'bg-brand-500' },
};

const ToastContext = createContext<ToastContextType | undefined>(undefined);

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const toast = useCallback(({ type = 'info', title, description }: { type?: ToastType; title: string; description?: string }) => {
    const id = Math.random().toString(36).substring(2, 9);
    setToasts((prev) => [...prev, { id, type, title, description }]);

    setTimeout(() => {
      removeToast(id);
    }, TOAST_MS);
  }, [removeToast]);

  const success = useCallback((title: string, description?: string) => {
    toast({ type: 'success', title, description });
  }, [toast]);

  const error = useCallback((title: string, description?: string) => {
    toast({ type: 'error', title, description });
  }, [toast]);

  return (
    <ToastContext.Provider value={{ toast, success, error }}>
      {children}
      <div className="fixed bottom-6 right-6 z-[100] flex flex-col gap-2 max-w-sm w-[calc(100%-3rem)] pointer-events-none" aria-live="polite">
        {toasts.map((t) => {
          const tone = TONES[t.type];
          const Icon = tone.icon;
          return (
            <div
              key={t.id}
              role={t.type === 'error' ? 'alert' : 'status'}
              className="pointer-events-auto relative overflow-hidden flex items-start gap-3 p-4 pr-3 rounded-2xl bg-white shadow-lift animate-slide-in-up"
            >
              <Icon className={`w-5 h-5 shrink-0 mt-0.5 ${tone.icon_class}`} aria-hidden />
              <div className="flex-1 min-w-0">
                <h4 className="text-sm font-semibold text-gray-900">{t.title}</h4>
                {t.description && <p className="text-sm text-gray-600 mt-0.5 leading-snug">{t.description}</p>}
              </div>
              <button
                onClick={() => removeToast(t.id)}
                className="text-gray-400 hover:text-gray-800 p-1 rounded-lg hover:bg-gray-100 transition-colors"
                aria-label="Dismiss"
              >
                <X className="w-4 h-4" aria-hidden />
              </button>
              {/* How long until it goes away on its own. */}
              <span className={`absolute left-0 bottom-0 h-0.5 ${tone.bar} origin-left`} style={{ width: '100%', animation: `toast-life ${TOAST_MS}ms linear forwards` }} aria-hidden />
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error('useToast must be used within a ToastProvider');
  }
  return context;
}
