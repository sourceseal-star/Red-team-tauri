import { useCallback, useEffect, useRef, useState } from 'react';
import {
  Activity, AlertTriangle, Camera, Check, Globe2, Network, Radio,
  ChevronRight, Gauge, History, LocateFixed, Radar, RefreshCw, Save,
  ScanLine, Server, ShieldCheck, Wifi, Zap,
} from 'lucide-react';

type SupergateSnapshot = {
  config: Record<string, unknown>;
  version: string;
  mtime_ns: number;
  modified_at: string;
  file: string;
  probe: {
    available: boolean;
    status_code: number | null;
    url: string;
    error?: string;
  };
};

type NetworkInterface = {
  name: string;
  ip_address: string;
  network_cidr: string;
  is_up: boolean;
  type_hint: string;
};

type OperationActivity = {
  id: string;
  label: string;
  summary: string;
  at: string;
};

type OperationResult = {
  label: string;
  payload: unknown;
};

type ResultRow = {
  title: string;
  meta: string;
  badge?: string;
};

type SolSupergatePanelProps = {
  full?: boolean;
};

const API_PATH = '/api/ops/sol-supergate';

const operationDefinitions = [
  { id: 'topology', label: 'Topología IP', icon: Network, tone: 'cyan' },
  { id: 'discovery', label: 'Descubrimiento LAN', icon: Radar, tone: 'violet' },
  { id: 'cameras', label: 'Cámaras ONVIF / RTSP', icon: Camera, tone: 'rose' },
  { id: 'routers', label: 'Routers y gateways', icon: Server, tone: 'amber' },
  { id: 'wifi', label: 'Entorno Wi‑Fi', icon: Wifi, tone: 'emerald' },
  { id: 'cached', label: 'Última topología', icon: History, tone: 'slate' },
] as const;

const authHeaders = (): Record<string, string> => {
  const token = localStorage.getItem('api_token');
  return token ? { Authorization: `Bearer ${token}` } : {};
};

const resultRows = (payload: unknown): ResultRow[] => {
  if (!payload || typeof payload !== 'object') return [];
  const data = payload as { results?: unknown; networks?: unknown };
  const list = Array.isArray(data.results)
    ? data.results
    : Array.isArray(data.networks)
      ? data.networks
      : [];

  return list
    .filter(item => item && typeof item === 'object')
    .slice(0, 8)
    .map(item => {
      const value = item as Record<string, unknown>;
      const title = String(value.ip || value.ssid || value.bssid || value.name || 'Elemento detectado');
      const details = [
        value.type,
        value.vendor,
        value.protocol,
        value.channel ? `canal ${value.channel}` : null,
        value.signal != null ? `${value.signal} dBm` : null,
        Array.isArray(value.ports) ? `${value.ports.length} puertos` : null,
      ].filter(Boolean).map(String);
      return {
        title,
        meta: details.join(' · ') || 'respuesta recibida',
        badge: value.risk ? String(value.risk) : value.encryption ? String(value.encryption) : undefined,
      };
    });
};

export default function SolSupergatePanel({ full = false }: SolSupergatePanelProps) {
  const [snapshot, setSnapshot] = useState<SupergateSnapshot | null>(null);
  const [draft, setDraft] = useState('');
  const [dirty, setDirty] = useState(false);
  const [externalChange, setExternalChange] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');
  const [interfaces, setInterfaces] = useState<NetworkInterface[]>([]);
  const [interfacesLoading, setInterfacesLoading] = useState(false);
  const [selectedInterface, setSelectedInterface] = useState('');
  const [scope, setScope] = useState('');
  const [operationLoading, setOperationLoading] = useState('');
  const [operationMessage, setOperationMessage] = useState('');
  const [activity, setActivity] = useState<OperationActivity[]>([]);
  const [lastResult, setLastResult] = useState<OperationResult | null>(null);
  const dirtyRef = useRef(false);
  const versionRef = useRef('');

  const syncNow = useCallback(async (replaceDraft: boolean) => {
    setLoading(true);
    try {
      const response = await fetch(API_PATH, { cache: 'no-store', headers: authHeaders() });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const next = await response.json() as SupergateSnapshot;
      const changedWhileEditing =
        dirtyRef.current &&
        !!versionRef.current &&
        next.version !== versionRef.current;

      setSnapshot(next);
      versionRef.current = next.version;
      if (replaceDraft || !dirtyRef.current) {
        setDraft(JSON.stringify(next.config, null, 2));
        dirtyRef.current = false;
        setDirty(false);
        setExternalChange(false);
      } else if (changedWhileEditing) {
        setExternalChange(true);
      }
      setMessage(`Sincronizado ${new Date().toLocaleTimeString()}`);
    } catch (error) {
      setMessage(`No se pudo sincronizar: ${error instanceof Error ? error.message : 'error desconocido'}`);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void syncNow(true);
    const interval = window.setInterval(() => void syncNow(false), 4000);
    return () => window.clearInterval(interval);
  }, [syncNow]);

  const loadInterfaces = useCallback(async () => {
    setInterfacesLoading(true);
    try {
      const response = await fetch('/api/network/interfaces', { cache: 'no-store', headers: authHeaders() });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const next = await response.json() as NetworkInterface[];
      const usable = Array.isArray(next)
        ? next.filter(item => item.is_up !== false && item.network_cidr && item.type_hint !== 'loopback')
        : [];
      setInterfaces(usable);
      const allScopes = Array.from(new Set(usable.map(item => item.network_cidr))).join(', ');
      if (allScopes) {
        setSelectedInterface(current => current || '__all__');
        setScope(current => current || allScopes);
      }
    } catch (error) {
      setOperationMessage(`No se pudieron cargar las interfaces: ${error instanceof Error ? error.message : 'error desconocido'}`);
    } finally {
      setInterfacesLoading(false);
    }
  }, []);

  useEffect(() => {
    if (full) void loadInterfaces();
  }, [full, loadInterfaces]);

  const selectedNetwork = interfaces.find(item => item.name === selectedInterface);
  const allScopes = Array.from(new Set(interfaces.map(item => item.network_cidr))).join(', ');
  const effectiveScope = scope.trim()
    || (selectedInterface === '__all__' ? allScopes : selectedNetwork?.network_cidr)
    || '';

  const responsePayload = async (response: Response) => {
    const payload: unknown = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = typeof payload === 'object' && payload !== null
        ? (payload as { detail?: string; error?: string }).detail || (payload as { error?: string }).error
        : '';
      throw new Error(detail || `HTTP ${response.status}`);
    }
    return payload;
  };

  const resultCount = (payload: unknown) => {
    if (!payload || typeof payload !== 'object') return '';
    const data = payload as { hosts_up?: number; count?: number; results?: unknown[]; networks?: unknown[] };
    const count = data.hosts_up ?? data.count ?? data.results?.length ?? data.networks?.length;
    return typeof count === 'number' ? `${count} elementos` : 'respuesta recibida';
  };

  const runOperation = async (id: typeof operationDefinitions[number]['id']) => {
    const definition = operationDefinitions.find(item => item.id === id);
    if (!definition) return;
    setOperationLoading(id);
    setOperationMessage('');
    try {
      let response: Response;
      if (id === 'topology') {
        const query = effectiveScope ? `?subnets=${encodeURIComponent(effectiveScope)}` : '';
        response = await fetch(`/api/scan/topology${query}`, { method: 'POST', headers: authHeaders() });
      } else if (id === 'discovery') {
        const query = effectiveScope ? `?subnets=${encodeURIComponent(effectiveScope)}` : '';
        response = await fetch(`/api/discover/network${query}`, { cache: 'no-store', headers: authHeaders() });
      } else if (id === 'cameras') {
        response = await fetch('/api/scan/cameras', {
          method: 'POST',
          headers: { ...authHeaders(), 'Content-Type': 'application/json' },
          body: JSON.stringify({ subnets: effectiveScope }),
        });
      } else if (id === 'routers') {
        const query = effectiveScope ? `?subnets=${encodeURIComponent(effectiveScope)}` : '';
        response = await fetch(`/api/scan/routers${query}`, { method: 'POST', headers: authHeaders() });
      } else if (id === 'cached') {
        response = await fetch('/api/scan/topology/last', { cache: 'no-store', headers: authHeaders() });
      } else {
        response = await fetch('/api/wifi/scan', { cache: 'no-store', headers: authHeaders() });
      }
      const payload = await responsePayload(response);
      const summary = resultCount(payload);
      const entry = {
        id,
        label: definition.label,
        summary,
        at: new Date().toLocaleTimeString(),
      };
      setActivity(previous => [entry, ...previous].slice(0, 8));
      setLastResult({ label: definition.label, payload });
      setOperationMessage(`${definition.label}: ${summary}.`);
    } catch (error) {
      setOperationMessage(`${definition.label}: ${error instanceof Error ? error.message : 'error desconocido'}`);
    } finally {
      setOperationLoading('');
    }
  };

  const gateMode = String(snapshot?.config?.mode || 'protected');
  const gatePort = String(snapshot?.config?.port || 8012);
  const scopeLabel = effectiveScope || 'detección automática';
  const quickScanActive = operationLoading === 'topology';

  const editDraft = (value: string) => {
    dirtyRef.current = true;
    setDirty(true);
    setExternalChange(false);
    setDraft(value);
  };

  const save = async () => {
    let config: Record<string, unknown>;
    try {
      const parsed: unknown = JSON.parse(draft);
      if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
        throw new Error('la raíz debe ser un objeto JSON');
      }
      config = parsed as Record<string, unknown>;
    } catch (error) {
      setMessage(`JSON inválido: ${error instanceof Error ? error.message : 'revisa el formato'}`);
      return;
    }

    setSaving(true);
    try {
      const response = await fetch(API_PATH, {
        method: 'PUT',
        headers: { ...authHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({
          config,
          expected_version: versionRef.current,
        }),
      });
      if (response.status === 409) {
        setExternalChange(true);
        setMessage('El archivo cambió con nano. Sincroniza antes de guardar.');
        return;
      }
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const next = await response.json() as SupergateSnapshot;
      setSnapshot(next);
      versionRef.current = next.version;
      dirtyRef.current = false;
      setDirty(false);
      setExternalChange(false);
      setDraft(JSON.stringify(next.config, null, 2));
      setMessage('Cambios guardados en el archivo local.');
    } catch (error) {
      setMessage(`No se pudo guardar: ${error instanceof Error ? error.message : 'error desconocido'}`);
    } finally {
      setSaving(false);
    }
  };

  const probe = snapshot?.probe;
  const probeLabel = probe?.available ? 'Portero accesible' : 'Portero no accesible';

  return (
    <div className={full ? 'p-5 sm:p-6 space-y-5' : 'p-4 space-y-4'}>
      <div className="rounded-2xl border border-amber-500/20 bg-gradient-to-br from-amber-500/[0.09] via-slate-950/80 to-cyan-500/[0.05] p-4 shadow-[0_0_32px_rgba(245,158,11,0.05)]">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="mb-1 flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.2em] text-amber-300/80">
              <Gauge size={13} /> Centro de control local
            </div>
            <div className="flex items-center gap-2 text-amber-200">
              <ShieldCheck size={18} />
              <h2 className={full ? 'text-lg font-bold tracking-wide' : 'text-sm font-bold tracking-wide'}>SOL SUPERGATE</h2>
              <span className="rounded-full border border-amber-400/25 bg-amber-400/10 px-1.5 py-0.5 text-[9px] font-bold tracking-widest text-amber-200">LIVE</span>
            </div>
            <p className="mt-1 max-w-2xl text-[11px] leading-5 text-slate-400">
              {full
                ? 'Reconocimiento bajo demanda para IP, routers, cámaras y Wi‑Fi. El portero local decide qué puede salir.'
                : 'Configuración local sincronizada con cambios hechos desde Termux.'}
            </p>
          </div>
          <div className="flex w-full flex-wrap items-center gap-2 sm:w-auto sm:justify-end">
            <span className={`rounded-full border px-2.5 py-1.5 text-[10px] font-bold ${
              probe?.available
                ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
                : 'border-slate-700 bg-slate-950/50 text-slate-500'
            }`}>
              <span className="mr-1">●</span>{probeLabel}
            </span>
            {full && (
              <button
                type="button"
                onClick={() => void runOperation('topology')}
                disabled={!!operationLoading}
                className="inline-flex items-center justify-center gap-1.5 rounded-lg bg-amber-400 px-3 py-2 text-[10px] font-bold text-slate-950 shadow-[0_0_18px_rgba(251,191,36,0.15)] transition hover:bg-amber-300 disabled:cursor-wait disabled:opacity-50"
              >
                {quickScanActive ? <RefreshCw size={12} className="animate-spin" /> : <Zap size={12} />}
                {quickScanActive ? 'Reconociendo…' : 'Escaneo rápido'}
                {!quickScanActive && <ChevronRight size={12} />}
              </button>
            )}
            <button
              type="button"
              onClick={() => void syncNow(true)}
              disabled={loading}
              className="inline-flex items-center justify-center gap-1 rounded-lg border border-slate-700 px-2.5 py-2 text-[10px] font-bold text-slate-300 transition hover:border-slate-500 disabled:opacity-50"
            >
              <RefreshCw size={12} className={loading ? 'animate-spin' : ''} />
              Sincronizar
            </button>
          </div>
        </div>
      </div>

      {full && (
        <>
          <section className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/[0.04] p-3">
              <div className="flex items-center gap-1.5 text-[9px] font-bold uppercase tracking-widest text-emerald-300/80">
                <LocateFixed size={11} /> Portero
              </div>
              <div className="mt-1 font-mono text-sm text-emerald-200">{probe?.available ? `HTTP ${probe.status_code ?? 200}` : 'offline'}</div>
            </div>
            <div className="rounded-xl border border-cyan-500/20 bg-cyan-500/[0.04] p-3">
              <div className="flex items-center gap-1.5 text-[9px] font-bold uppercase tracking-widest text-cyan-300/80">
                <Network size={11} /> Interfaces
              </div>
              <div className="mt-1 font-mono text-sm text-cyan-200">{interfacesLoading ? '…' : interfaces.length}</div>
            </div>
            <div className="rounded-xl border border-amber-500/20 bg-amber-500/[0.04] p-3">
              <div className="flex items-center gap-1.5 text-[9px] font-bold uppercase tracking-widest text-amber-300/80">
                <Globe2 size={11} /> Alcance
              </div>
              <div className="mt-1 truncate font-mono text-xs text-amber-200" title={scopeLabel}>{scopeLabel}</div>
            </div>
            <div className="rounded-xl border border-slate-700 bg-slate-950/50 p-3">
              <div className="flex items-center gap-1.5 text-[9px] font-bold uppercase tracking-widest text-slate-400">
                <ShieldCheck size={11} /> Política
              </div>
              <div className="mt-1 font-mono text-sm text-slate-200">{gateMode} · :{gatePort}</div>
            </div>
          </section>

          <section className="grid grid-cols-1 gap-3 xl:grid-cols-[1.15fr_0.85fr]">
            <div className="rounded-xl border border-amber-500/20 bg-amber-500/[0.04] p-4">
              <div className="mb-3 flex items-center gap-2 text-xs font-bold uppercase tracking-[0.18em] text-amber-200">
                <Globe2 size={15} /> Ámbito de operación
              </div>
              <div className="grid grid-cols-1 gap-3 md:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
                <label className="space-y-1.5">
                  <span className="flex items-center justify-between text-[10px] uppercase tracking-widest text-slate-500">
                    <span>Interfaz activa</span>
                    <button
                      type="button"
                      onClick={() => void loadInterfaces()}
                      disabled={interfacesLoading}
                      className="inline-flex items-center gap-1 normal-case tracking-normal text-cyan-300 hover:text-cyan-200 disabled:opacity-50"
                    >
                      <RefreshCw size={10} className={interfacesLoading ? 'animate-spin' : ''} /> actualizar
                    </button>
                  </span>
                  <select
                    value={selectedInterface}
                    onChange={event => {
                      const name = event.target.value;
                      setSelectedInterface(name);
                      const next = interfaces.find(item => item.name === name);
                       setScope(name === '__all__' ? allScopes : next?.network_cidr || '');
                    }}
                    className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-slate-200 outline-none focus:border-amber-500/60"
                  >
                    {interfacesLoading && <option value="">Detectando interfaces…</option>}
                    {!interfacesLoading && interfaces.length === 0 && <option value="">No se detectaron interfaces</option>}
                    {interfaces.length > 0 && <option value="__all__">Todas las interfaces activas</option>}
                    {interfaces.map(item => (
                      <option key={`${item.name}-${item.ip_address}`} value={item.name}>
                        {item.name} · {item.type_hint || 'red'}
                      </option>
                    ))}
                  </select>
                  {!interfacesLoading && interfaces.length === 0 && (
                    <button
                      type="button"
                      onClick={() => void loadInterfaces()}
                      className="text-[10px] text-cyan-300 hover:text-cyan-200"
                    >
                      Reintentar detección
                    </button>
                  )}
                </label>
                <label className="space-y-1.5">
                  <span className="text-[10px] uppercase tracking-widest text-slate-500">IPs / subredes objetivo</span>
                  <input
                    value={scope}
                    onChange={event => setScope(event.target.value)}
                    placeholder="192.168.1.0/24, 10.0.0.0/24"
                    className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 font-mono text-xs text-slate-200 outline-none focus:border-amber-500/60"
                    aria-label="IPs y subredes objetivo"
                  />
                </label>
              </div>
              <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-[10px] text-slate-500">
                <span>IP local: <b className="font-mono text-slate-300">{selectedNetwork?.ip_address || (selectedInterface === '__all__' ? 'múltiples' : '—')}</b></span>
                <span>Redes detectadas: <b className="font-mono text-slate-300">{allScopes || 'automática'}</b></span>
                <span className="inline-flex items-center gap-1 text-emerald-300"><Activity size={11} /> Consultas manuales</span>
              </div>
              {!interfacesLoading && interfaces.length === 0 && (
                <div className="mt-3 rounded-lg border border-amber-500/20 bg-amber-500/[0.06] px-3 py-2 text-[10px] leading-4 text-amber-200">
                  No hay una interfaz LAN confirmada todavía. Puedes introducir una subred manualmente; el backend no ejecutará nada automáticamente.
                </div>
              )}
            </div>

            <div className="rounded-xl border border-slate-800 bg-slate-950/50 p-4">
              <div className="mb-3 flex items-center gap-2 text-xs font-bold uppercase tracking-[0.18em] text-slate-300">
                <Server size={15} /> Estado del portero
              </div>
              <div className="grid grid-cols-2 gap-2 text-[10px]">
                <div className="rounded-lg border border-slate-800 bg-slate-900/70 p-2.5">
                  <div className="text-slate-600">Modo</div>
                  <div className="mt-1 font-mono text-amber-200">{String(snapshot?.config?.mode || 'protected')}</div>
                </div>
                <div className="rounded-lg border border-slate-800 bg-slate-900/70 p-2.5">
                  <div className="text-slate-600">Puerto</div>
                  <div className="mt-1 font-mono text-cyan-200">{String(snapshot?.config?.port || 8012)}</div>
                </div>
                <div className="col-span-2 rounded-lg border border-slate-800 bg-slate-900/70 p-2.5">
                  <div className="text-slate-600">Sonda</div>
                  <div className={`mt-1 font-mono ${probe?.available ? 'text-emerald-300' : 'text-slate-400'}`}>
                    {probe?.available ? `${probe.url} · HTTP ${probe.status_code ?? 'OK'}` : 'Portero local no accesible desde este dashboard'}
                  </div>
                </div>
              </div>
            </div>
          </section>

          <section>
            <div className="mb-2 flex items-center gap-2 text-xs font-bold uppercase tracking-[0.18em] text-slate-400">
              <ScanLine size={14} /> Operaciones de reconocimiento
            </div>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-3">
              {operationDefinitions.map(operation => {
                const Icon = operation.icon;
                const active = operationLoading === operation.id;
                const tone = operation.tone === 'cyan'
                  ? 'border-cyan-500/30 text-cyan-200 hover:bg-cyan-500/10'
                  : operation.tone === 'violet'
                    ? 'border-violet-500/30 text-violet-200 hover:bg-violet-500/10'
                  : operation.tone === 'rose'
                    ? 'border-rose-500/30 text-rose-200 hover:bg-rose-500/10'
                    : operation.tone === 'amber'
                      ? 'border-amber-500/30 text-amber-200 hover:bg-amber-500/10'
                      : operation.tone === 'slate'
                        ? 'border-slate-600 text-slate-200 hover:bg-slate-500/10'
                      : 'border-emerald-500/30 text-emerald-200 hover:bg-emerald-500/10';
                const operationHint = operation.id === 'wifi'
                  ? 'Radios y redes visibles'
                  : operation.id === 'cached'
                    ? 'Sin generar tráfico nuevo'
                    : operation.id === 'discovery'
                      ? 'TCP + ARP · LAN local'
                      : effectiveScope || 'Red detectada automáticamente';
                return (
                  <button
                    key={operation.id}
                    type="button"
                    onClick={() => void runOperation(operation.id)}
                    disabled={!!operationLoading}
                    className={`flex min-h-20 items-center gap-3 rounded-xl border bg-slate-950/60 px-4 py-3 text-left transition disabled:cursor-wait disabled:opacity-50 ${tone}`}
                  >
                    {active ? <RefreshCw size={18} className="shrink-0 animate-spin" /> : <Icon size={18} className="shrink-0" />}
                    <span>
                      <span className="block text-xs font-bold">{active ? 'Procesando…' : operation.label}</span>
                      <span className="mt-1 block text-[10px] text-slate-500">
                        {operationHint}
                      </span>
                    </span>
                  </button>
                );
              })}
            </div>
          </section>

          <section className="grid grid-cols-1 gap-3 xl:grid-cols-[0.85fr_1.15fr]">
            <div className="rounded-xl border border-slate-800 bg-slate-950/50 p-4">
              <div className="mb-3 flex items-center gap-2 text-xs font-bold uppercase tracking-[0.18em] text-slate-400">
                <Radio size={14} /> Actividad reciente
              </div>
              {activity.length === 0 ? (
                <div className="rounded-lg border border-dashed border-slate-800 p-5 text-center text-[11px] text-slate-600">
                  Selecciona un ámbito y ejecuta una operación manual.
                </div>
              ) : (
                <div className="space-y-1.5">
                  {activity.map(item => (
                    <div key={`${item.id}-${item.at}`} className="flex items-center gap-2 rounded-lg bg-slate-900/70 px-2.5 py-2 text-[10px]">
                      <Check size={12} className="text-emerald-300" />
                      <span className="min-w-0 flex-1 truncate text-slate-300">{item.label} · {item.summary}</span>
                      <span className="font-mono text-slate-600">{item.at}</span>
                    </div>
                  ))}
                </div>
              )}
              {operationMessage && (
                <div className={`mt-3 text-[10px] ${operationMessage.includes(': HTTP') || operationMessage.includes('No se pudieron') ? 'text-red-300' : 'text-amber-200'}`}>
                  {operationMessage}
                </div>
              )}
            </div>
            <div className="rounded-xl border border-slate-800 bg-slate-950/50 p-4">
              <div className="mb-3 flex items-center justify-between gap-3">
                <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-[0.18em] text-slate-400">
                  <Activity size={14} /> Última respuesta
                </div>
                {lastResult && (
                  <span className="rounded-full border border-emerald-500/20 bg-emerald-500/10 px-2 py-1 text-[9px] font-mono text-emerald-300">
                    {lastResult.label}
                  </span>
                )}
              </div>
              {lastResult ? (
                <>
                  <div className="mb-2 flex items-center gap-2 text-[10px] text-slate-500">
                    <span className="font-mono text-slate-300">{resultCount(lastResult.payload)}</span>
                    <span>·</span>
                    <span>resultado real del backend</span>
                  </div>
                  {resultRows(lastResult.payload).length > 0 ? (
                    <div className="space-y-1.5">
                      {resultRows(lastResult.payload).map((row, index) => (
                        <div key={`${row.title}-${index}`} className="flex items-center gap-2 rounded-lg border border-slate-800/80 bg-black/20 px-2.5 py-2">
                          <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-cyan-300" />
                          <div className="min-w-0 flex-1">
                            <div className="truncate font-mono text-[10px] text-slate-200">{row.title}</div>
                            <div className="truncate text-[9px] text-slate-500">{row.meta}</div>
                          </div>
                          {row.badge && <span className="rounded border border-slate-700 px-1.5 py-0.5 text-[9px] text-slate-400">{row.badge}</span>}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="rounded-lg border border-dashed border-slate-800 p-4 text-center text-[10px] text-slate-500">
                      La operación respondió, pero no devolvió elementos listables.
                    </div>
                  )}
                  <details className="mt-3">
                    <summary className="cursor-pointer text-[10px] text-cyan-300 hover:text-cyan-200">Ver respuesta JSON completa</summary>
                    <pre className="mt-2 max-h-48 overflow-auto rounded-lg border border-slate-800 bg-black/30 p-3 font-mono text-[10px] leading-5 text-slate-400">
                      {JSON.stringify(lastResult.payload, null, 2).slice(0, 12000)}
                    </pre>
                  </details>
                </>
              ) : (
                <div className="rounded-lg border border-dashed border-slate-800 p-5 text-center text-[11px] text-slate-600">
                  Sin operaciones ejecutadas. Elige una acción para obtener evidencia.
                </div>
              )}
            </div>
          </section>

          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 rounded-lg border border-slate-800 bg-slate-950/30 px-3 py-2 text-[10px] text-slate-500">
            <span className="inline-flex items-center gap-1.5 text-emerald-300"><ShieldCheck size={11} /> Sin barrido automático</span>
            <span>·</span>
            <span>Loopback :{gatePort}</span>
            <span>·</span>
            <span>Acciones explícitas del operador</span>
          </div>
        </>
      )}

      {externalChange && (
        <div className="flex items-start gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-[11px] text-amber-200">
          <AlertTriangle size={14} className="mt-0.5 shrink-0" />
          <span>Se detectó una edición externa. Pulsa «Sincronizar» antes de guardar para no sobrescribir lo que cambiaste con nano.</span>
        </div>
      )}

      <details className="group rounded-xl border border-slate-800 bg-slate-950/40">
        <summary className="flex cursor-pointer list-none items-center justify-between gap-3 p-3 text-[10px] font-bold uppercase tracking-[0.16em] text-slate-400 marker:hidden">
          <span className="inline-flex items-center gap-2"><Server size={13} /> Configuración avanzada</span>
          <ChevronRight size={14} className="transition group-open:rotate-90" />
        </summary>
        <div className="border-t border-slate-800 p-3">
          <textarea
            value={draft}
            onChange={(event) => editDraft(event.target.value)}
            spellCheck={false}
            aria-label="Configuración JSON de sol_supergate"
            className="min-h-56 w-full resize-y rounded-lg border border-slate-800 bg-slate-950/80 p-3 font-mono text-xs leading-5 text-slate-200 outline-none focus:border-amber-500/50"
            placeholder={loading ? 'Cargando configuración…' : '{ }'}
          />

          <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
            <div className="text-[10px] text-slate-600">
              <div>Archivo: <span className="text-slate-400">{snapshot?.file ?? 'cargando…'}</span></div>
              <div>
                Última modificación: <span className="text-slate-400">{snapshot?.modified_at ?? '—'}</span>
                {probe?.url ? <> · Puerto: <span className="text-slate-400">{probe.url}</span></> : null}
              </div>
              <div className="mt-1 text-slate-500">También puedes editar este JSON con nano; el panel revisa cambios cada 4 segundos.</div>
            </div>
            <button
              type="button"
              onClick={() => void save()}
              disabled={saving || !dirty || externalChange}
              className="inline-flex items-center gap-2 rounded-lg bg-amber-500 px-3 py-2 text-[11px] font-bold text-slate-950 hover:bg-amber-400 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {saving ? <RefreshCw size={13} className="animate-spin" /> : <Save size={13} />}
              Guardar cambios
            </button>
          </div>
        </div>
      </details>

      <div className={`flex items-center gap-2 text-[10px] ${message.startsWith('No se pudo') || message.startsWith('JSON inválido') ? 'text-red-300' : 'text-slate-500'}`}>
        {message && !message.startsWith('No se pudo') && !message.startsWith('JSON inválido') ? <Check size={12} /> : null}
        {message}
      </div>
    </div>
  );
}