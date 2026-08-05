import { useEffect, useRef } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import type { Ticket, DtOverview, DtTopology } from './types';

interface MapViewProps {
  selectedTicket: Ticket | null;
  allDts: DtOverview[];
  activeTickets: Ticket[];
  apiUrl: string;
}

const STATE_COLOR: Record<string, string> = {
  LIVE:      '#22c55e',
  DARK:      '#ef4444',
  UNKNOWN:   '#94a3b8',
  NO_DEVICE: '#475569',
};

export function MapView({ selectedTicket, allDts, activeTickets, apiUrl }: MapViewProps) {
  const containerRef  = useRef<HTMLDivElement>(null);
  const mapRef        = useRef<L.Map | null>(null);
  const dtLayerRef    = useRef<L.LayerGroup>(L.layerGroup());
  const topoLayerRef  = useRef<L.LayerGroup>(L.layerGroup());

  // ── Init map once ─────────────────────────────────────────────
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const map = L.map(containerRef.current, {
      center: [12.9, 77.5],   // Bangalore — matches simulator seed data
      zoom:   11,
      zoomControl: true,
    });

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      maxZoom: 19,
    }).addTo(map);

    dtLayerRef.current.addTo(map);
    topoLayerRef.current.addTo(map);
    mapRef.current = map;

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // ── DT overview markers (updates when fault list changes) ─────
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    dtLayerRef.current.clearLayers();
    const faultedDts = new Set(activeTickets.map(t => t.dt_id));

    allDts.forEach(dt => {
      if (dt.lat == null || dt.lon == null) return;
      const hasFault = faultedDts.has(dt.dt_id);

      L.circleMarker([dt.lat, dt.lon], {
        radius:      hasFault ? 9 : 5,
        color:       hasFault ? '#ef4444' : '#3b82f6',
        fillColor:   hasFault ? '#ef4444' : '#1d4ed8',
        fillOpacity: hasFault ? 0.85 : 0.55,
        weight: 1.5,
      })
        .addTo(dtLayerRef.current)
        .bindTooltip(hasFault ? `⚡ ${dt.dt_id} FAULT` : dt.dt_id);
    });
  }, [allDts, activeTickets]);

  // ── Selected ticket: full DT topology with state colours ──────
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    topoLayerRef.current.clearLayers();
    if (!selectedTicket) return;

    const { dt_id, fault_boundary } = selectedTicket;
    const firstDark = fault_boundary?.first_dark;
    const lastLive  = fault_boundary?.last_live;

    const controller = new AbortController();

    fetch(`${apiUrl}/topology/${encodeURIComponent(dt_id)}`, { signal: controller.signal })
      .then(async r => {
        if (!r.ok) throw new Error(`Unable to load topology (${r.status})`);
        return r.json();
      })
      .then((topo: DtTopology) => {
        const nodeMap: Record<string, DtTopology['nodes'][0]> = {};
        topo.nodes.forEach(n => { nodeMap[n.id] = n; });

        // 1. Draw edges first (below nodes)
        topo.edges.forEach(e => {
          const f = nodeMap[e.from];
          const t = nodeMap[e.to];
          if (f?.lat == null || f.lon == null || t?.lat == null || t.lon == null) return;

          const isFaultSpan = e.to === firstDark;

          L.polyline([[f.lat, f.lon], [t.lat, t.lon]], {
            color:     isFaultSpan ? '#f97316' : '#334155',
            weight:    isFaultSpan ? 5 : 1.5,
            opacity:   isFaultSpan ? 1 : 0.55,
            dashArray: isFaultSpan ? undefined : '3 5',
          }).addTo(topoLayerRef.current);
        });

        // 2. Draw nodes
        const bounds: L.LatLngTuple[] = [];
        topo.nodes.forEach(n => {
          if (n.lat == null || n.lon == null) return;
          bounds.push([n.lat, n.lon]);

          const isFirstDark = n.id === firstDark;
          const isLastLive  = n.id === lastLive;
          const isDT        = n.type === 'dt';

          const fill   = isDT ? '#f59e0b' : (STATE_COLOR[n.state] ?? '#94a3b8');
          const radius = isDT ? 11 : (isFirstDark || isLastLive ? 9 : 4);
          const weight = isFirstDark ? 3 : (isLastLive ? 2.5 : 1);
          const stroke = isFirstDark ? '#ff0000' : (isLastLive ? '#16a34a' : '#0f172a');

          const tip = isDT
            ? `${n.id} — Distribution Transformer`
            : `${n.id} | ${n.state}${isFirstDark ? '  ← FIRST DARK' : ''}${isLastLive ? '  ← LAST LIVE' : ''}`;

          L.circleMarker([n.lat, n.lon], {
            radius,
            color:       stroke,
            fillColor:   fill,
            fillOpacity: 0.92,
            weight,
          })
            .addTo(topoLayerRef.current)
            .bindTooltip(tip, {
              permanent:  isFirstDark || isLastLive || isDT,
              direction:  'top',
              className:  'map-tip',
            });
        });

        // 3. Zoom to this DT
        if (bounds.length > 0) {
          map.fitBounds(bounds, { padding: [40, 40], maxZoom: 17 });
        }
      })
      .catch(error => {
        if (error.name !== 'AbortError') console.error(error);
      });

    return () => controller.abort();
  }, [selectedTicket, apiUrl]);

  return (
    <div
      ref={containerRef}
      style={{ height: '100%', width: '100%' }}
    />
  );
}
