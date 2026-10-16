'use client';

import React from 'react';
import { StatusBadge } from '@/components/ui/StatusBadge';
import { KPITile } from '@/components/ui/KPITile';
import {
  Gauge,
  Wind,
  Thermometer,
  AlertTriangle,
  X,
  CheckCircle2,
  Activity,
  Layers,
  MapPin
} from 'lucide-react';

interface SegmentDetailProps {
  segment: any;
  telemetry?: any;
  onClose: () => void;
}

export function SegmentDetail({ segment, telemetry, onClose }: SegmentDetailProps) {
  if (!segment) return null;

  const currentPressure = telemetry?.pressure_bar || segment.design_pressure_bar * 0.9;
  const currentFlow = telemetry?.flow_m3h || 1250;
  const currentTemp = telemetry?.temp_c || 42.5;

  const pressureRatio = (currentPressure / segment.design_pressure_bar) * 100;

  return (
    <div className="glass-card p-6 border-brand-500/30 shadow-2xl space-y-6 animate-slide-in-right">
      {/* Header */}
      <div className="flex items-start justify-between border-b border-gray-200 pb-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-gray-50 text-brand-400 border border-gray-200">
              SEGMENT #{segment.id}
            </span>
            <StatusBadge status={segment.status} size="sm" />
          </div>
          <h2 className="text-lg font-bold text-gray-900">{segment.name}</h2>
          <p className="text-xs text-gray-500 font-mono mt-0.5 flex items-center gap-1">
            <MapPin className="w-3 h-3 text-brand-400" /> {segment.start_node?.name} ➔ {segment.end_node?.name}
          </p>
        </div>

        <button
          onClick={onClose}
          className="p-1.5 rounded-xl bg-gray-50 hover:bg-gray-50 text-gray-500 hover:text-gray-900 transition-colors"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Primary Telemetry Grid */}
      <div className="grid grid-cols-3 gap-3">
        <div className="glass-card p-3 bg-gray-50 text-center">
          <Gauge className="w-4 h-4 text-brand-400 mx-auto mb-1" />
          <span className="text-[10px] text-gray-500 uppercase font-semibold block">Pressure</span>
          <span className="text-base font-bold font-mono text-gray-900">{currentPressure.toFixed(1)}</span>
          <span className="text-[10px] text-gray-500 block">Bar</span>
        </div>

        <div className="glass-card p-3 bg-gray-50 text-center">
          <Wind className="w-4 h-4 text-blue-400 mx-auto mb-1" />
          <span className="text-[10px] text-gray-500 uppercase font-semibold block">Flow Rate</span>
          <span className="text-base font-bold font-mono text-gray-900">{Math.round(currentFlow)}</span>
          <span className="text-[10px] text-gray-500 block">m³/h</span>
        </div>

        <div className="glass-card p-3 bg-gray-50 text-center">
          <Thermometer className="w-4 h-4 text-amber-400 mx-auto mb-1" />
          <span className="text-[10px] text-gray-500 uppercase font-semibold block">Temperature</span>
          <span className="text-base font-bold font-mono text-gray-900">{currentTemp.toFixed(1)}</span>
          <span className="text-[10px] text-gray-500 block">°C</span>
        </div>
      </div>

      {/* Pressure Capacity Load Bar */}
      <div className="space-y-1.5">
        <div className="flex justify-between text-xs font-mono">
          <span className="text-gray-500">Design Capacity Load:</span>
          <span className={`font-semibold ${pressureRatio > 95 ? 'text-red-400' : 'text-brand-500'}`}>
            {pressureRatio.toFixed(1)}% ({currentPressure.toFixed(1)} / {segment.design_pressure_bar} Bar)
          </span>
        </div>
        <div className="w-full bg-gray-50 h-2 rounded-full overflow-hidden border border-gray-200">
          <div
            className={`h-full rounded-full transition-all duration-500 ${
              pressureRatio > 95 ? 'bg-red-500 shadow-[0_0_12px_rgba(239,68,68,0.8)]' : 'bg-brand-500'
            }`}
            style={{ width: `${Math.min(pressureRatio, 100)}%` }}
          />
        </div>
      </div>

      {/* Physical Attributes Table */}
      <div className="space-y-2 text-xs">
        <h3 className="font-semibold text-gray-600 flex items-center gap-1.5">
          <Layers className="w-3.5 h-3.5 text-brand-400" /> Segment Physical Specifications
        </h3>

        <div className="glass-card p-3 bg-gray-50 divide-y divide-dark-800/60 text-gray-600">
          <div className="flex justify-between py-1.5">
            <span className="text-gray-500">Pipe Diameter</span>
            <span className="font-mono font-medium">{segment.diameter_mm} mm</span>
          </div>
          <div className="flex justify-between py-1.5">
            <span className="text-gray-500">Pipeline Length</span>
            <span className="font-mono font-medium">{segment.length_km} km</span>
          </div>
          <div className="flex justify-between py-1.5">
            <span className="text-gray-500">Design Pressure Limit</span>
            <span className="font-mono font-medium">{segment.design_pressure_bar} Bar</span>
          </div>
          <div className="flex justify-between py-1.5">
            <span className="text-gray-500">Pipe Material</span>
            <span className="font-mono font-medium">Carbon Steel API 5L X70</span>
          </div>
        </div>
      </div>

      {/* Incident / Maintenance Banner */}
      {segment.status === 'critical' && (
        <div className="p-3 rounded-xl bg-red-500/10 border border-red-500/30 text-xs text-red-400 flex items-start gap-2">
          <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5 animate-pulse" />
          <div>
            <p className="font-semibold">CRITICAL PRESSURE DROP DETECTED</p>
            <p className="text-[11px] text-red-300/80 mt-0.5">
              Telemetry signals potential valve leakage or localized pressure loss along segment path.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
