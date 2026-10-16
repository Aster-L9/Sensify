import React from 'react';
import {
  CheckCircle2,
  AlertTriangle,
  XCircle,
  WifiOff,
  Wrench,
  PlayCircle,
  HelpCircle
} from 'lucide-react';

export type StatusType =
  | 'operational'
  | 'warning'
  | 'critical'
  | 'offline'
  | 'maintenance'
  | 'active'
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

export function StatusBadge({
  status,
  label,
  showIcon = true,
  size = 'md',
  className = ''
}: StatusBadgeProps) {
  const normalized = String(status || 'unknown').toLowerCase();

  const getConfig = () => {
    switch (normalized) {
      case 'operational':
      case 'healthy':
      case 'normal':
        return {
          bg: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
          dot: 'bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.6)]',
          icon: CheckCircle2,
          defaultLabel: 'Operational'
        };
      case 'warning':
      case 'degraded':
        return {
          bg: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
          dot: 'bg-amber-400 shadow-[0_0_8px_rgba(251,191,36,0.6)]',
          icon: AlertTriangle,
          defaultLabel: 'Warning'
        };
      case 'critical':
      case 'failed':
      case 'error':
        return {
          bg: 'bg-red-500/10 text-red-400 border-red-500/20',
          dot: 'bg-red-400 shadow-[0_0_8px_rgba(248,113,113,0.6)] animate-pulse',
          icon: XCircle,
          defaultLabel: 'Critical'
        };
      case 'offline':
      case 'inactive':
        return {
          bg: 'bg-gray-500/10 text-gray-500 border-gray-500/20',
          dot: 'bg-gray-400',
          icon: WifiOff,
          defaultLabel: 'Offline'
        };
      case 'maintenance':
        return {
          bg: 'bg-cyan-500/10 text-cyan-400 border-cyan-500/20',
          dot: 'bg-cyan-400',
          icon: Wrench,
          defaultLabel: 'Maintenance'
        };
      case 'active':
      case 'running':
        return {
          bg: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
          dot: 'bg-blue-400 shadow-[0_0_8px_rgba(96,165,250,0.6)] animate-pulse',
          icon: PlayCircle,
          defaultLabel: 'Active'
        };
      case 'completed':
        return {
          bg: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
          dot: 'bg-emerald-400',
          icon: CheckCircle2,
          defaultLabel: 'Completed'
        };
      case 'admin':
        return {
          bg: 'bg-purple-500/10 text-purple-400 border-purple-500/20',
          dot: 'bg-purple-400',
          icon: CheckCircle2,
          defaultLabel: 'Admin'
        };
      case 'analyst':
        return {
          bg: 'bg-cyan-500/10 text-cyan-400 border-cyan-500/20',
          dot: 'bg-cyan-400',
          icon: CheckCircle2,
          defaultLabel: 'Analyst'
        };
      default:
        return {
          bg: 'bg-gray-500/10 text-gray-600 border-gray-500/20',
          dot: 'bg-gray-400',
          icon: HelpCircle,
          defaultLabel: status
        };
    }
  };

  const config = getConfig();
  const Icon = config.icon;
  const displayText = label || config.defaultLabel;

  const sizeClasses = {
    sm: 'text-[10px] px-2 py-0.5 gap-1',
    md: 'text-xs px-2.5 py-1 gap-1.5',
    lg: 'text-sm px-3 py-1.5 gap-2',
  }[size];

  return (
    <span className={`inline-flex items-center font-medium rounded-full border ${config.bg} ${sizeClasses} ${className}`}>
      {showIcon ? (
        <Icon className={size === 'sm' ? 'w-3 h-3' : size === 'lg' ? 'w-4 h-4' : 'w-3.5 h-3.5'} />
      ) : (
        <span className={`w-1.5 h-1.5 rounded-full ${config.dot}`} />
      )}
      {displayText}
    </span>
  );
}
