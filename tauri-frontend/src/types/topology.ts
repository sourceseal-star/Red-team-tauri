// src/types/topology.ts
// Tipos para la visualización de topología de red con vis-network.
// Adaptados al formato del backend dashboard_server.py /api/scan/topology.

export interface TopologyDevice {
  ip: string;
  hostname?: string;
  ports: { port: number; service: string; state: string; banner?: string }[];
  type: 'router' | 'camera' | 'pc' | 'server' | 'iot' | 'unknown';
  mac?: string;
  vendor?: string;
  risk: 'low' | 'medium' | 'high' | 'critical';
  risk_reasons?: string[];
}

export interface VisNode {
  id: string;
  label: string;
  title: string;
  shape: 'box' | 'dot' | 'diamond' | 'star' | 'triangle';
  color: {
    background: string;
    border: string;
    highlight: { background: string; border: string };
  };
  size: number;
  ip?: string;
  port?: number;
  risk?: string;
  type?: string;
}

export interface VisEdge {
  from: string;
  to: string;
  label?: string;
  color?: string;
  dashes?: boolean;
}

export interface TopologyData {
  nodes: VisNode[];
  edges: VisEdge[];
}
