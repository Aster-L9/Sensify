import React from 'react';
import {
  CheckCircle2,
  AlertTriangle,
  XCircle,
  WifiOff,
  Wrench,
  HelpCircle,
  Pause,
  Shield,
  User,
  type LucideIcon,
} from 'lucide-react';

export type StatusType =
  | 'operational'
  | 'warning'
  | 'critical'
  | 'offline'
  | 'maintenance'
  | 'active'
  | 'paused'
  | 'completed'
  | 'admin'
  | 'analyst';

interface StatusBadgeProps {
  status: StatusType | string;
  label?: string;
  showIcon?: boolean;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

interface Config { tone: string; icon: LucideIcon | 'live'; defaultLabel: string }

const CONFIG: Record<string, Config> = {
  operational: { tone: 'bg-brand-50 text-brand-700', icon: CheckCircle2, defaultLabel: 'Operational' },
  warning: { tone: 'bg-amber-50 text-amber-800', icon: AlertTriangle, defaultLabel: 'Warning' },
  critical: { tone: 'bg-red-50 text-red-700', icon: XCircle, defaultLabel: 'Critical' },
  offline: { tone: 'bg-gray-100 text-gray-600', icon: WifiOff, defaultLabel: 'Offline' },
  maintenance: { tone: 'bg-gray-100 text-gray-700', icon: Wrench, defaultLabel: 'Maintenance' },
  active: { tone: 'bg-brand-50 text-brand-700', icon: 'live', defaultLabel: 'Playing' },
  paused: { tone: 'bg-gray-100 text-gray-700', icon: Pause, defaultLabel: 'Paused' },
  completed: { tone: 'bg-gray-100 text-gray-600', icon: CheckCircle2, defaultLabel: 'Completed' },
  admin: { tone: 'bg-brand-600 text-white', icon: Shield, defaultLabel: 'Administrator' },
  analyst: { tone: 'bg-gray-100 text-gray-700', icon: User, defaultLabel: 'Analyst' },
};
const ALIASES: Record<string, string> = {
  healthy: 'operational', normal: 'operational', degraded: 'warning', failed: 'critical', error: 'critical',
  inactive: 'offline', running: 'active',
};

export function StatusBadge({ status, label, showIcon = true, size = 'md', className = '' }: StatusBadgeProps) {
  const key = String(status || 'unknown').toLowerCase();
  const config = CONFIG[ALIASES[key] ?? key] ?? { tone: 'bg-gray-100 text-gray-600', icon: HelpCircle, defaultLabel: String(status) };
  const Icon = config.icon;
  const iconSize = size === 'sm' ? 'w-3 h-3' : size === 'lg' ? 'w-4 h-4' : 'w-3.5 h-3.5';
  const sizeClasses = {
    sm: 'text-[11px] px-2 py-0.5 gap-1',
    md: 'text-xs px-2.5 py-1 gap-1.5',
    lg: 'text-sm px-3 py-1.5 gap-2',
  }[size];

  return (
    <span className={`inline-flex items-center font-medium rounded-full whitespace-nowrap ${config.tone} ${sizeClasses} ${className}`}>
      {showIcon && (Icon === 'live' ? (
        <span className="relative flex h-1.5 w-1.5" aria-hidden>
          <span className="absolute inline-flex h-full w-full rounded-full bg-brand-400 opacity-70 motion-safe:animate-ping" />
          <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-brand-600" />
        </span>
      ) : (
        <Icon className={iconSize} aria-hidden />
      ))}
      {label || config.defaultLabel}
    </span>
  );
}
