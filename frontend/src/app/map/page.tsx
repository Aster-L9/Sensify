'use client';

import React, { useEffect, useState } from 'react';
import dynamic from 'next/dynamic';
import { getTopology } from '@/lib/api';
import { LoadingState, ErrorState } from '@/components/ui/States';
import { SegmentDetail } from '@/components/SegmentDetail';
import { StatusBadge } from '@/components/ui/StatusBadge';
import { MapPin, Layers, Filter, Eye, Activity } from 'lucide-react';

// Dynamic import Leaflet components to prevent SSR window reference issues
const MapContainer = dynamic(
  () => import('react-leaflet').then((m) => m.MapContainer),
  { ssr: false }
);
const TileLayer = dynamic(
  () => import('react-leaflet').then((m) => m.TileLayer),
  { ssr: false }
);
const Marker = dynamic(
  () => import('react-leaflet').then((m) => m.Marker),
  { ssr: false }
);
const Popup = dynamic(
  () => import('react-leaflet').then((m) => m.Popup),
  { ssr: false }
);
const Polyline = dynamic(
  () => import('react-leaflet').then((m) => m.Polyline),
  { ssr: false }
);

export default function MapPage() {
  const [nodes, setNodes] = useState<any[]>([]);
  const [segments, setSegments] = useState<any[]>([]);
  const [selectedSegment, setSelectedSegment] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [leafletReady, setLeafletReady] = useState(false);

  useEffect(() => {
    // Fix marker icons client-side
    import('leaflet').then((L) => {
      // @ts-ignore
      delete L.Icon.Default.prototype._getIconUrl;
      L.Icon.Default.mergeOptions({
        iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
        iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
        shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
      });
      setLeafletReady(true);
    });

    getTopology()
      .then((data) => {
        const segs = data.segments || [];

        // Generate nodes dynamically from segments
        const nodesMap = new Map<string, any>();
        let nodeId = 1;

        segs.forEach((seg: any) => {
          const startKey = `${seg.lat_start},${seg.lon_start}`;
          if (!nodesMap.has(startKey)) {
            nodesMap.set(startKey, {
              id: nodeId++,
              name: seg.name + (seg.segment_type === 'pump_station' ? ' (Pump)' : ' (Start)'),
              type: seg.segment_type,
              latitude: seg.lat_start,
              longitude: seg.lon_start,
              elevation_m: Math.floor(Math.random() * 50) + 10, // dummy elevation
            });
          }
          seg.start_node_id = nodesMap.get(startKey).id;

          const endKey = `${seg.lat_end},${seg.lon_end}`;
          if (!nodesMap.has(endKey)) {
            nodesMap.set(endKey, {
              id: nodeId++,
              name: seg.name + ' (End)',
              type: 'junction',
              latitude: seg.lat_end,
              longitude: seg.lon_end,
              elevation_m: Math.floor(Math.random() * 50) + 10,
            });
          }
          seg.end_node_id = nodesMap.get(endKey).id;
        });

        const generatedNodes = Array.from(nodesMap.values());
        setNodes(generatedNodes);
        setSegments(segs);
      })
      .catch((e) => setErr(e.message || 'Failed to load GIS pipeline topology'))
      .finally(() => setLoading(false));
  }, []);

  if (loading || !leafletReady) {
    return <LoadingState message="Initializing Leaflet GIS Engine & Saudi Network Map..." />;
  }

  if (err) {
    return <ErrorState message={err} />;
  }

  const filteredSegments = statusFilter === 'all'
    ? segments
    : segments.filter(s => s.status === statusFilter);

  // Status color helper for polylines
  const getPolylineColor = (status: string) => {
    switch (status) {
      case 'operational': return '#7169d5';
      case 'warning': return '#e9aa93';
      case 'critical': return '#ef4444';
      case 'offline': return '#64748b';
      default: return '#b09fe8';
    }
  };

  return (
    <div className="space-y-6">
      {/* Map Header Controls */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 glass-card p-4">
        <div>
          <h1 className="text-xl font-bold text-gray-900 flex items-center gap-2">
            <MapPin className="w-5 h-5 text-brand-400" /> GIS Pipeline Network Topology
          </h1>
          <p className="text-xs text-gray-500">
            Geospatial visualization of Master Gas System nodes, processing plants & compressor pipelines.
          </p>
        </div>

        {/* Filter Controls */}
        <div className="flex flex-wrap items-center gap-2 text-xs font-medium">
          <Filter className="w-4 h-4 text-gray-500" />
          <span className="text-gray-500">Filter Status:</span>
          {['all', 'operational', 'warning', 'critical'].map((st) => (
            <button
              key={st}
              onClick={() => setStatusFilter(st)}
              className={`px-3 py-1.5 rounded-xl capitalize transition-all ${
                statusFilter === st
                  ? 'bg-brand-500 text-white font-bold shadow-md shadow-brand-500/20'
                  : 'bg-gray-50 text-gray-600 hover:bg-gray-50'
              }`}
            >
              {st}
            </button>
          ))}
        </div>
      </div>

      {/* Main Interactive Map & Segment Sidebar View */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
        <div className={`${selectedSegment ? 'lg:col-span-2' : 'lg:col-span-3'} glass-card overflow-hidden h-[620px] relative`}>
          <MapContainer
            center={[25.3, 49.5]} // Center around Saudi Master Gas Network region
            zoom={6}
            style={{ width: '100%', height: '100%' }}
            scrollWheelZoom={true}
          >
            {/* Esri Light Gray Canvas Tile Layer */}
            <TileLayer
              attribution='&copy; <a href="https://www.esri.com">Esri</a>'
              url="https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}"
            />

            {/* Nodes Markers */}
            {nodes.map((node) => (
              <Marker key={node.id} position={[node.latitude, node.longitude]}>
                <Popup>
                  <div className="p-1 space-y-1">
                    <span className="text-[10px] font-mono text-brand-400 uppercase font-semibold block">
                      NODE #{node.id} • {node.type}
                    </span>
                    <h3 className="text-sm font-bold text-gray-900">{node.name}</h3>
                    <p className="text-xs text-gray-500">Lat: {node.latitude}, Lon: {node.longitude}</p>
                    <p className="text-xs text-gray-600 font-mono">Elevation: {node.elevation_m}m</p>
                  </div>
                </Popup>
              </Marker>
            ))}

            {/* Pipeline Polyline Segments */}
            {filteredSegments.map((seg) => {
              const startNode = nodes.find((n) => n.id === seg.start_node_id);
              const endNode = nodes.find((n) => n.id === seg.end_node_id);
              if (!startNode || !endNode) return null;

              const positions: [number, number][] = [
                [startNode.latitude, startNode.longitude],
                [endNode.latitude, endNode.longitude],
              ];

              return (
                <Polyline
                  key={seg.id}
                  positions={positions}
                  pathOptions={{
                    color: getPolylineColor(seg.status),
                    weight: selectedSegment?.id === seg.id ? 6 : 4,
                    opacity: 0.85,
                    dashArray: seg.status === 'critical' ? '10, 10' : undefined,
                  }}
                  eventHandlers={{
                    click: () => {
                      setSelectedSegment({
                        ...seg,
                        start_node: startNode,
                        end_node: endNode,
                      });
                    },
                  }}
                />
              );
            })}
          </MapContainer>
        </div>

        {/* Selected Segment Drawer / Details Sidebar */}
        {selectedSegment && (
          <div className="lg:col-span-1">
            <SegmentDetail
              segment={selectedSegment}
              onClose={() => setSelectedSegment(null)}
            />
          </div>
        )}
      </div>

      {/* Pipeline Network List */}
      <div className="glass-card p-6">
        <h2 className="text-base font-semibold text-gray-900 mb-4 flex items-center gap-2">
          <Layers className="w-4 h-4 text-brand-400" /> Pipeline Asset Directory ({filteredSegments.length} Segments)
        </h2>

        <div className="overflow-x-auto">
          <table className="data-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Name</th>
                <th>Status</th>
                <th>Length</th>
                <th>Diameter</th>
                <th>Design Pressure</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {filteredSegments.map((seg) => {
                const startNode = nodes.find((n) => n.id === seg.start_node_id);
                const endNode = nodes.find((n) => n.id === seg.end_node_id);
                return (
                  <tr key={seg.id}>
                    <td className="font-mono text-xs">#{seg.id}</td>
                    <td className="font-semibold text-gray-800">{seg.name}</td>
                    <td><StatusBadge status={seg.status} size="sm" /></td>
                    <td className="font-mono text-xs">{seg.length_km} km</td>
                    <td className="font-mono text-xs">{seg.diameter_mm} mm</td>
                    <td className="font-mono text-xs">{seg.design_pressure_bar} Bar</td>
                    <td>
                      <button
                        onClick={() => setSelectedSegment({ ...seg, start_node: startNode, end_node: endNode })}
                        className="btn-ghost py-1 px-2.5 text-xs flex items-center gap-1"
                      >
                        <Eye className="w-3.5 h-3.5" /> Inspect
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
