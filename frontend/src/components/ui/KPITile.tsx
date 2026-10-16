import React from 'react';
import { LucideIcon, TrendingUp, TrendingDown, Minus } from 'lucide-react';

interface KPITileProps {
  title: string;
  value: string | number;
  unit?: string;
  subtitle?: string;
  change?: number;
  changePeriod?: string;
  icon?: LucideIcon;
  accentColor?: string;
  status?: 'operational' | 'warning' | 'critical' | 'neutral';
  loading?: boolean;
}

export function KPITile({
  title,
  value,
  unit,
  subtitle,
  change,
  changePeriod = 'vs last run',
  icon: Icon,
  accentColor = '#7169d5',
  status = 'neutral',
  loading = false,
}: KPITileProps) {
  if (loading) {
    return (
      <div className="glass-card p-5 space-y-3 animate-pulse">
        <div className="flex items-center justify-between">
          <div className="h-4 bg-gray-50 rounded w-24"></div>
          <div className="w-8 h-8 bg-gray-50 rounded-lg"></div>
        </div>
        <div className="h-8 bg-gray-50 rounded w-32"></div>
        <div className="h-3 bg-gray-50 rounded w-20"></div>
      </div>
    );
  }

  const statusGradients = {
    operational: 'from-brand-500/10 via-transparent to-transparent border-brand-500/30',
    warning: 'from-accent-peach/10 via-transparent to-transparent border-accent-peach/30',
    critical: 'from-red-500/10 via-transparent to-transparent border-red-500/30',
    neutral: 'from-brand-500/5 via-transparent to-transparent border-gray-200',
  };

  return (
    <div
      className={`glass-card p-5 relative overflow-hidden bg-gradient-to-br ${statusGradients[status]} transition-all duration-300 hover:border-brand-500/40 hover:shadow-lg hover:shadow-brand-500/5 group`}
      style={{ '--kpi-accent': accentColor } as React.CSSProperties}
    >
      {/* Accent top border highlight */}
      <div
        className="absolute top-0 left-0 w-full h-[2px] opacity-70 group-hover:opacity-100 transition-opacity"
        style={{ background: `linear-gradient(90deg, transparent, ${accentColor}, transparent)` }}
      />

      <div className="flex items-start justify-between">
        <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
          {title}
        </span>
        {Icon && (
          <div
            className="p-2 rounded-xl bg-gray-50 border border-gray-200 text-gray-600 group-hover:text-brand-500 transition-colors"
          >
            <Icon className="w-4 h-4" />
          </div>
        )}
      </div>

      <div className="mt-3 flex items-baseline gap-2">
        <span className="text-2xl font-bold tracking-tight text-gray-900 font-mono">
          {value}
        </span>
        {unit && (
          <span className="text-sm font-medium text-gray-500 font-sans">
            {unit}
          </span>
        )}
      </div>

      {(subtitle || change !== undefined) && (
        <div className="mt-2 flex items-center gap-2 text-xs">
          {change !== undefined && (
            <span className={`inline-flex items-center gap-0.5 font-medium ${
              change > 0 ? 'text-emerald-400' : change < 0 ? 'text-red-400' : 'text-gray-500'
            }`}>
              {change > 0 ? (
                <TrendingUp className="w-3 h-3" />
              ) : change < 0 ? (
                <TrendingDown className="w-3 h-3" />
              ) : (
                <Minus className="w-3 h-3" />
              )}
              {Math.abs(change)}%
            </span>
          )}
          {subtitle && (
            <span className="text-gray-500 font-normal">
              {subtitle} {change !== undefined && changePeriod}
            </span>
          )}
        </div>
      )}
    </div>
  );
}
