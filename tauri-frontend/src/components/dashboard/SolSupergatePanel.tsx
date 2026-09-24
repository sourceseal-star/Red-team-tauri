import { useCallback, useEffect, useRef, useState } from 'react';
import {
  Activity, AlertTriangle, Camera, Check, Globe2, Network, Radio,
  RefreshCw, Save, ScanLine, Server, ShieldCheck, Wifi,
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

type SolSupergatePanelProps = {
  full?: boolean;
};

const API_PATH = '/api/ops/sol-supergate';

const operationDefinitions = [
  { id: 'topology', label: 'Topología IP', icon: Network, tone: 'cyan' },
  { id: 'cameras', label: 'Cámaras ONVIF / RTSP', icon: Camera, tone: 'rose' },
  { id: 'routers', label: 'Routers y gateways', icon: Server, tone: 'amber' },
  { id: 'wifi', label: 'Entorno Wi‑Fi', icon: Wifi, tone: 'emerald' },
] as const;

const authHeaders = (): Record<string, string> => {
  const token = localStorage.getItem('api_token');
  return token ? { Authorization: `Bearer ${token}` } : {};
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
      } else if (id === 'cameras') {
        response = await fetch('/api/scan/cameras', {
          method: 'POST',
          headers: { ...authHeaders(), 'Content-Type': 'application/json' },
          body: JSON.stringify({ subnets: effectiveScope }),
        });
      } else if (id === 'routers') {
        response = await fetch('/api/scan/routers', { method: 'POST', headers: authHeaders() });
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
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-amber-300">
            <ShieldCheck size={16} />
            <h2 className={full ? 'text-lg font-bold tracking-wide' : 'text-sm font-bold tracking-wide'}>SOL SUPERGATE</h2>
          </div>
          <p className="mt-1 text-[11px] text-slate-500">
            {full
              ? 'Centro operativo para observar y consultar redes, IP, routers, cámaras y Wi‑Fi desde el portero local.'
              : 'Configuración local sincronizada con cambios hechos desde Termux.'}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className={`rounded-full border px-2 py-1 text-[10px] ${
            probe?.available
              ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
              : 'border-slate-700 bg-slate-950/50 text-slate-500'
          }`}>
            <span className="mr-1">●</span>{probeLabel}
          </span>
          <button
            type="button"
            onClick={() => void syncNow(true)}
            disabled={loading}
            className="inline-flex items-center gap-1 rounded-lg border border-slate-700 px-2.5 py-1.5 text-[10px] font-bold text-slate-300 hover:border-slate-500 disabled:opacity-50"
          >
            <RefreshCw size={12} className={loading ? 'animate-spin' : ''} />
            Sincronizar
          </button>
        </div>
      </div>

      {full && (
        <>
          <section className="grid grid-cols-1 gap-3 xl:grid-cols-[1.15fr_0.85fr]">
            <div className="rounded-xl border border-amber-500/20 bg-amber-500/[0.04] p-4">
              <div className="mb-3 flex items-center gap-2 text-xs font-bold uppercase tracking-[0.18em] text-amber-200">
                <Globe2 size={15} /> Ámbito de operación
              </div>
              <div className="grid grid-cols-1 gap-3 md:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
                <label className="space-y-1.5">
                  <span className="text-[10px] uppercase tracking-widest text-slate-500">Interfaz activa</span>
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
                    {interfaces.length === 0 && <option value="">Detectando interfaces…</option>}
                    {interfaces.length > 0 && <option value="__all__">Todas las interfaces activas</option>}
                    {interfaces.map(item => (
                      <option key={`${item.name}-${item.ip_address}`} value={item.name}>
                        {item.name} · {item.type_hint || 'red'}
                      </option>
                    ))}
                  </select>
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
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-4">
              {operationDefinitions.map(operation => {
                const Icon = operation.icon;
                const active = operationLoading === operation.id;
                const tone = operation.tone === 'cyan'
                  ? 'border-cyan-500/30 text-cyan-200 hover:bg-cyan-500/10'
                  : operation.tone === 'rose'
                    ? 'border-rose-500/30 text-rose-200 hover:bg-rose-500/10'
                    : operation.tone === 'amber'
                      ? 'border-amber-500/30 text-amber-200 hover:bg-amber-500/10'
                      : 'border-emerald-500/30 text-emerald-200 hover:bg-emerald-500/10';
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
                        {operation.id === 'wifi' ? 'Radios y redes visibles' : effectiveScope || 'Red detectada automáticamente'}
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
              <div className="mb-3 flex items-center gap-2 text-xs font-bold uppercase tracking-[0.18em] text-slate-400">
                <Activity size={14} /> Última respuesta
              </div>
              <pre className="max-h-48 overflow-auto rounded-lg border border-slate-800 bg-black/30 p-3 font-mono text-[10px] leading-5 text-slate-400">
                {lastResult ? JSON.stringify(lastResult.payload, null, 2).slice(0, 12000) : 'Sin operaciones ejecutadas.'}
              </pre>
            </div>
          </section>
        </>
      )}

      {externalChange && (
        <div className="flex items-start gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-[11px] text-amber-200">
          <AlertTriangle size={14} className="mt-0.5 shrink-0" />
          <span>Se detectó una edición externa. Pulsa «Sincronizar» antes de guardar para no sobrescribir lo que cambiaste con nano.</span>
        </div>
      )}

      <textarea
        value={draft}
        onChange={(event) => editDraft(event.target.value)}
        spellCheck={false}
        aria-label="Configuración JSON de sol_supergate"
        className="min-h-56 w-full resize-y rounded-lg border border-slate-800 bg-slate-950/80 p-3 font-mono text-xs leading-5 text-slate-200 outline-none focus:border-amber-500/50"
        placeholder={loading ? 'Cargando configuración…' : '{ }'}
      />

      <div className="flex flex-wrap items-center justify-between gap-3">
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

      <div className={`flex items-center gap-2 text-[10px] ${message.startsWith('No se pudo') || message.startsWith('JSON inválido') ? 'text-red-300' : 'text-slate-500'}`}>
        {message && !message.startsWith('No se pudo') && !message.startsWith('JSON inválido') ? <Check size={12} /> : null}
        {message}
      </div>
    </div>
  );
}