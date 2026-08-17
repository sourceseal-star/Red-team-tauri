// src/hooks/useTopology.ts
// Transforma los hosts del store de Zustand (useScanStore) al formato que
// consume vis-network. No hace fetch propio — lee de useScanStore que ya es
// poblado por DashboardProV2.runScan('Topología', '/api/scan/topology').
import { useMemo, useCallback } from 'react';
import { useScanStore, Host } from './useScanStore';
import { getApiKey } from '../lib/api';
import { TopologyData, VisNode, VisEdge } from '../types/topology';

// ── Colores SourceSeal ──────────────────────────────────────────────────────
const SS = {
  cyan:    '#00e5ff',
  gold:    '#d4af37',
  red:     '#ff3b5c',
  green:   '#00ff88',
  amber:   '#fbbf24',
};

const RISK_COLOR: Record<Host['risk'], { bg: string; border: string }> = {
  low:      { bg: 'rgba(0,255,136,0.15)',  border: SS.green },
  medium:   { bg: 'rgba(251,191,36,0.15)', border: SS.amber },
  high:     { bg: 'rgba(255,140,66,0.15)',  border: '#ff8c42' },
  critical: { bg: 'rgba(255,59,92,0.20)',   border: SS.red },
};

const TYPE_SHAPE: Record<Host['type'], VisNode['shape']> = {
  router: 'box',
  camera: 'diamond',
  iot: 'triangle',
  unknown: 'dot',
};

export function useTopology() {
  const hosts = useScanStore(s => s.hosts);
  const loading = useScanStore(s => s.loading);
  const error = useScanStore(s => s.error);
  const selectHost = useScanStore(s => s.selectHost);

  const data: TopologyData = useMemo(() => {
    if (!hosts || hosts.length === 0) return { nodes: [], edges: [] };

    // 1. Nodos
    const nodes: VisNode[] = hosts.map(h => {
      const label = h.ip.split('.').pop() as string;
      const portsStr = h.ports.map(p => `${p.port}/${p.service}`).join(', ') || 'Ninguno';
      const rc = RISK_COLOR[h.risk];
      return {
        id: h.ip,
        label,
        title: `IP: ${h.ip}\nTipo: ${h.type}\nVendor: ${h.vendor || '—'}\nRiesgo: ${h.risk}\nPuertos: ${portsStr}`,
        shape: TYPE_SHAPE[h.type] || 'dot',
        color: {
          background: rc.bg,
          border: rc.border,
          highlight: { background: rc.bg, border: SS.cyan },
        },
        size: h.type === 'router' ? 30 : h.type === 'camera' ? 25 : 20,
        ip: h.ip,
        risk: h.risk,
        type: h.type,
      };
    });

    // 2. Centro = router o primer host
    const router = hosts.find(h => h.type === 'router');
    const centerId = router ? router.ip : (hosts[0]?.ip || '');

    // 3. Aristas: del centro hacia los demás
    const edges: VisEdge[] = hosts
      .filter(h => h.ip !== centerId)
      .map(h => ({
        from: centerId,
        to: h.ip,
        label: h.ports[0]?.port?.toString() || '',
        color: h.risk === 'critical' ? SS.red : h.risk === 'high' ? '#ff8c42' : 'rgba(0,229,255,0.3)',
      }));

    // 4. Cámaras conectadas entre sí (clustering RTSP)
    const cameras = hosts.filter(h => h.type === 'camera');
    for (let i = 0; i < cameras.length - 1; i++) {
      edges.push({
        from: cameras[i].ip,
        to: cameras[i + 1].ip,
        label: 'RTSP',
        color: 'rgba(255,59,92,0.4)',
        dashes: true,
      });
    }

    return { nodes, edges };
  }, [hosts]);

  const refetch = useCallback(async () => {
    const store = useScanStore.getState();
    store.setLoading(true);
    store.setError(null);
    store.pushLog('⏳ Refrescando topología...');
    try {
      const key = useScanStore.getState().apiKey || localStorage.getItem('api_token')
      const res = await fetch('/api/scan/topology', {
        method: 'POST',
        headers: key ? { 'Authorization': `Bearer ${key}`, 'Content-Type': 'application/json' } : { 'Content-Type': 'application/json' },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      const items = (json.results || json.hosts || []).map((h: any) => ({
        ip: h.ip, mac: h.mac, vendor: h.vendor,
        ports: h.ports || [], risk: h.risk || 'low',
        risk_reasons: h.risk_reasons || [],
        first_seen: h.first_seen || new Date().toISOString(),
        type: h.type || 'unknown',
      }));
      store.setHosts(items);
      store.pushLog(`✔ Topología refrescada: ${items.length} hosts`);
    } catch (e: any) {
      store.setError(e.message);
      store.pushLog(`✘ Topología: ${e.message}`);
    } finally {
      store.setLoading(false);
    }
  }, []);

  return { data, loading, error, refetch, selectHost };
}
