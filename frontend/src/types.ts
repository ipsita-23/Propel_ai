// ─── Ticket / fault data ─────────────────────────────────────────

export interface FaultBoundary {
  type: 'SPAN_FAULT' | 'DT_FAULT';
  last_live: string;
  first_dark: string;
  dt_id?: string;
  affected?: number;
}

export interface Ticket {
  id: number;
  dt_id: string;
  status: 'detected' | 'acknowledged' | 'assigned' | 'resolved' | 'verified' | 'closed';
  fault_boundary: FaultBoundary;
  confidence: 'High' | 'Medium';
  confidence_reason: string;  // derived by backend — not a DB column
  affected_poles_count: number;
  is_geometric_inference: boolean;
  created_at: string;
  resolved_at: string | null;
  // Enriched by backend JOIN
  fault_lat:       number | null;
  fault_lon:       number | null;
  fault_pincode:   string | null;
  last_live_lat:   number | null;
  last_live_lon:   number | null;
  dt_lat:          number | null;
  dt_lon:          number | null;
  feeder_id:       string | null;
}

// ─── Topology ────────────────────────────────────────────────────

export type NodeState = 'LIVE' | 'DARK' | 'UNKNOWN' | 'NO_DEVICE';

export interface TopologyNode {
  id: string;
  type: 'dt' | 'pole';
  lat: number | null;
  lon: number | null;
  state: NodeState;
  has_device: boolean;
}

export interface TopologyEdge {
  from: string;
  to: string;
}

export interface DtTopology {
  dt_id: string;
  is_geometric: boolean;
  nodes: TopologyNode[];
  edges: TopologyEdge[];
}

export interface DtOverview {
  dt_id: string;
  lat: number | null;
  lon: number | null;
  pole_count: number;
  is_geometric: boolean;
}

// ─── Simulator ──────────────────────────────────────────────────

export interface SimDt {
  dt_id: string;
  feeder_id: string;
  pole_count: number;
}
