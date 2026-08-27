import { create } from 'zustand';

export interface Host {
  ip: string;
  mac?: string;
  vendor?: string;
  ports: { port: number; service: string; state: string; banner?: string }[];
  risk: 'low' | 'medium' | 'high' | 'critical';
  risk_reasons?: string[];
  first_seen: string;
  type: 'router' | 'camera' | 'iot' | 'unknown';
}

interface State {
  hosts: Host[];
  loading: boolean;
  error: string | null;
  selectedIp: string | null;
  log: string[];
  setHosts: (h: Host[]) => void;
  setLoading: (v: boolean) => void;
  setError: (e: string | null) => void;
  selectHost: (ip: string | null) => void;
  pushLog: (m: string) => void;
  clear: () => void;
}

const classifyRisk = (ports: Host['ports']): Host['risk'] => {
  const p = ports.map(x => x.port);
  if (p.includes(23) || p.includes(21) || ports.some(x => /admin|default/i.test(x.banner || ''))) return 'critical';
  if (p.includes(554) || p.includes(37777) || p.includes(8000)) return 'high';
  if (p.includes(80) || p.includes(8080)) return 'medium';
  return 'low';
};

export const useScanStore = create<State>((set) => ({
  hosts: [], loading: false, error: null, selectedIp: null, log: [],
  setHosts: (h) => set({ hosts: h.map(x => ({ ...x, risk: classifyRisk(x.ports) })) }),
  setLoading: (v) => set({ loading: v }),
  setError: (e) => set({ error: e }),
  selectHost: (ip) => set({ selectedIp: ip }),
  pushLog: (m) => set((s) => ({ log: [`[${new Date().toLocaleTimeString()}] ${m}`, ...s.log].slice(0, 80) })),
  clear: () => set({ hosts: [], error: null, selectedIp: null }),
}));
