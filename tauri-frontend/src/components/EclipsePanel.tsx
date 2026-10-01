import { useState, useEffect, useCallback, useRef } from 'react';
import {
  Moon, Shield, Play, RefreshCw, Loader2, AlertTriangle,
  CheckCircle2, XCircle, FileText, History, RotateCcw
} from 'lucide-react';
import { getApiKey } from '../lib/api';

const API_BASE = (import.meta as any).env?.VITE_API_BASE || '';
const ECL = '/api/eclipse';

function eclHeaders(): Record<string, string> {
  const key = getApiKey();
  const h: Record<string, string> = { 'Content-Type': 'application/json' };
  if (key) h['Authorization'] = `Bearer ${key}`;
  return h;
}

const SUITES = ['auth', 'scope', 'stress', 'universe'];

export default function EclipsePanel() {
  const [status, setStatus] = useState<Record<string, any> | null>(null);
  const [history, setHistory] = useState<any[]>([]);
  const [runResult, setRunResult] = useState<Record<string, any> | null>(null);
  const [suites, setSuites] = useState<string[]>(['auth', 'scope', 'stress']);
  const [loading, setLoading] = useState<Record<string, boolean>>({});
  const [error, setError] = useState<string | null>(null);
  // FIX 2026-10-01 (Harold): la zona objetivo NUNCA debe quedar anclada a
  // una sola IP. Campo libre: una por línea o separadas por coma; vacío
  // usa el único fallback del backend (status.target_default).
  const [targetsText, setTargetsText] = useState<string>('');
  const [jobId, setJobId] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const parseTargets = () =>
    targetsText.split(/[\n,]/).map(s => s.trim()).filter(Boolean);

  const setLoadingKey = (k: string, v: boolean) => setLoading(prev => ({ ...prev, [k]: v }));

  const fetchStatus = useCallback(async () => {
    setLoadingKey('status', true);
    try {
      const sRes = await fetch(`${API_BASE}${ECL}/status`, { headers: eclHeaders() });
      if (!sRes.ok) {
        // Fix 2026-10-01: antes un 401/404 se tragaba en silencio y el panel
        // quedaba casi en blanco (solo guiones) sin decir por qué.
        const msg = sRes.status === 404
          ? 'El backend no tiene montado /api/eclipse (revisa que el import de eclipse.py no haya fallado en el server — "omni.sh logs" o reinicia).'
          : sRes.status === 401
          ? 'No autorizado (401) — tu sesión/token no es válido para esta ruta. Vuelve a iniciar sesión en el panel.'
          : `HTTP ${sRes.status} en /api/eclipse/status`;
        setStatus(null);
        setHistory([]);
        setError(msg);
        setLoadingKey('status', false);
        return;
      }
      const [s, h] = await Promise.all([
        sRes.json(),
        fetch(`${API_BASE}${ECL}/history?limit=20`, { headers: eclHeaders() }).then(r => r.ok ? r.json() : []),
      ]);
      setStatus(s);
      setHistory(Array.isArray(h) ? h : (h?.history || []));
      setError(null);
    } catch (e: any) {
      setError(e.message || 'Error de conexión con ECLIPSE');
    }
    setLoadingKey('status', false);
  }, []);

  useEffect(() => { fetchStatus(); }, [fetchStatus]);

  const toggleSuite = (s: string) =>
    setSuites(prev => prev.includes(s) ? prev.filter(x => x !== s) : [...prev, s]);

  // FIX 2026-10-01 (Harold): el 504 "tardó más de 25s" no era de red —
  // la propia suite 'auth' simula backoff exponencial real (~45-90s por
  // diseño). Ningún target lo iba a arreglar: hacía falta no bloquear la
  // petición. Ahora /run devuelve un job_id de inmediato y este panel lo
  // consulta solo, cada 2s, hasta que termine — nunca más 504.
  const stopPolling = () => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
  };

  const pollJob = (id: string) => {
    stopPolling();
    pollRef.current = setInterval(async () => {
      try {
        const r = await fetch(`${API_BASE}${ECL}/run/${id}`, { headers: eclHeaders() });
        const d = await r.json().catch(() => ({}));
        if (!r.ok) { stopPolling(); setRunResult({ error: `HTTP ${r.status}`, detail: d }); setLoadingKey('run', false); return; }
        if (d.status === 'done') {
          stopPolling(); setRunResult(d.result); setLoadingKey('run', false); fetchStatus();
        } else if (d.status === 'error') {
          stopPolling(); setRunResult({ error: d.error || 'el job falló' }); setLoadingKey('run', false);
        }
        // 'running' -> sigue consultando
      } catch (e: any) {
        stopPolling(); setRunResult({ error: e.message }); setLoadingKey('run', false);
      }
    }, 2000);
  };

  useEffect(() => () => stopPolling(), []);

  const runBattery = async () => {
    setLoadingKey('run', true); setRunResult(null); setJobId(null);
    const targets = parseTargets(); // nunca un solo valor obligatorio
    try {
      const res = await fetch(`${API_BASE}${ECL}/run`, {
        method: 'POST', headers: eclHeaders(),
        body: JSON.stringify({ suites, targets, autonomous: true }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) { setRunResult({ error: `HTTP ${res.status}`, detail: data }); setLoadingKey('run', false); return; }
      setJobId(data.job_id);
      pollJob(data.job_id);
    } catch (e: any) { setRunResult({ error: e.message }); setLoadingKey('run', false); }
  };

  const resetCircuit = async () => {
    setLoadingKey('reset', true);
    try {
      await fetch(`${API_BASE}${ECL}/reset-circuit`, { method: 'POST', headers: eclHeaders() });
      fetchStatus();
    } catch { /* no-op, el status refleja el fallo si persiste */ }
    setLoadingKey('reset', false);
  };

  return (
    <div className="p-4 md:p-6 space-y-4 text-slate-200">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <Moon className="w-6 h-6 text-indigo-300" />
          <h1 className="text-xl font-bold">ECLIPSE</h1>
          <span className="text-xs px-2 py-0.5 rounded bg-indigo-900/50 text-indigo-200">v2.0 · caos y seguridad</span>
        </div>
        <button onClick={fetchStatus} className="flex items-center gap-1 text-xs px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700">
          {loading.status ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />} Actualizar
        </button>
      </div>

      {error && (
        <div className="flex items-center gap-2 text-sm text-red-400 bg-red-950/30 border border-red-900/50 rounded-lg p-3">
          <AlertTriangle className="w-4 h-4" /> {error}
        </div>
      )}

      <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
        <div className="text-sm font-semibold mb-2 flex items-center gap-2"><Shield className="w-4 h-4 text-indigo-300" /> Estado del módulo</div>
        {status ? (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
            <div className="rounded-lg bg-slate-800/60 p-2"><div className="text-slate-500">Estado</div><div className="text-slate-200">{status.state || '—'}</div></div>
            <div className="rounded-lg bg-slate-800/60 p-2"><div className="text-slate-500">Zona objetivo por defecto</div><div className="text-slate-200 truncate">{status.target_default || '—'}</div></div>
            <div className="rounded-lg bg-slate-800/60 p-2"><div className="text-slate-500">Programador (6h)</div><div className={status.scheduler === 'active' ? 'text-emerald-400' : 'text-slate-400'}>{status.scheduler || '—'}</div></div>
            <div className="rounded-lg bg-slate-800/60 p-2"><div className="text-slate-500">Circuit breaker</div><div className="text-slate-200">{status.circuit_breaker?.state || JSON.stringify(status.circuit_breaker || {})}</div></div>
          </div>
        ) : <div className="text-xs text-slate-500">Sin datos aún</div>}
      </div>

      <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 space-y-3">
        <div className="text-sm font-semibold flex items-center gap-2"><Play className="w-4 h-4 text-indigo-300" /> Ejecutar batería</div>
        <div className="flex flex-wrap gap-2">
          {SUITES.map(s => (
            <button key={s} onClick={() => toggleSuite(s)}
              className={`text-xs px-3 py-1.5 rounded-lg border ${suites.includes(s) ? 'bg-indigo-900/50 border-indigo-700 text-indigo-200' : 'bg-slate-800/60 border-slate-700 text-slate-400'}`}>
              {s}{s === 'universe' && <span className="ml-1 text-amber-400" title="D1-D3 usan un contrato de telemetría que universe.py actual no implementa">⚠</span>}
            </button>
          ))}
        </div>
        <div className="space-y-1">
          <label className="text-[11px] text-slate-500">
            Zona(s) objetivo — una por línea o separadas por coma (vacío = usar el fallback por defecto, nunca anclado a una sola IP)
          </label>
          <textarea
            value={targetsText}
            onChange={e => setTargetsText(e.target.value)}
            placeholder={status?.target_default ? `ej: ${status.target_default}\nhttp://10.0.0.5:8001` : 'ej: http://10.0.0.5:8001'}
            rows={2}
            className="w-full text-xs bg-slate-950 border border-slate-700 rounded-lg p-2 text-slate-200 placeholder:text-slate-600"
          />
        </div>
        {suites.includes('universe') && (
          <p className="text-[11px] text-amber-400/80">
            ⚠ El sub-test "universe" (D1-D3) espera un endpoint de telemetría GPS con caché (mode/cache_age_s) que
            el módulo universe.py actual no implementa (solo mesh/sockets/medios). Esas 3 pruebas marcarán FAIL
            por diseño hasta que se decida si se construye ese endpoint; D0 (estado) sí es real.
          </p>
        )}
        <button onClick={runBattery} disabled={loading.run || suites.length === 0}
          className="flex items-center gap-2 text-sm px-4 py-2 rounded-lg bg-indigo-700 hover:bg-indigo-600 disabled:opacity-50">
          {loading.run ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />} Lanzar batería ({suites.length})
        </button>
        {jobId && loading.run && (
          <div className="flex items-center gap-2 text-xs text-indigo-300">
            <Loader2 className="w-3.5 h-3.5 animate-spin" /> Corriendo en background (job {jobId}) — no bloquea, puedes seguir usando el panel.
          </div>
        )}
        {runResult && (
          <div className={`rounded-lg border p-3 text-xs ${runResult.error ? 'border-red-900/50 bg-red-950/20' : 'border-slate-700 bg-slate-950'}`}>
            {runResult.error ? (
              <div className="text-red-400">❌ {runResult.error}{runResult.detail ? ` · ${JSON.stringify(runResult.detail)}` : ''}</div>
            ) : (
              <div>
                <div className="flex items-center gap-2">
                  {runResult.falls === 0 ? <CheckCircle2 className="w-4 h-4 text-emerald-400" /> : <XCircle className="w-4 h-4 text-red-400" />}
                  <span className="text-slate-200">{runResult.veredicto}</span>
                  <span className="text-slate-500">· {runResult.total - runResult.falls}/{runResult.total} OK</span>
                </div>
                {runResult.por_target && Object.keys(runResult.por_target).length > 0 && (
                  <div className="mt-2 space-y-1">
                    {Object.entries(runResult.por_target).map(([t, v]: [string, any]) => (
                      <div key={t} className="flex items-center justify-between text-[11px] text-slate-400">
                        <span className="truncate">{t}</span>
                        <span>{v.total - v.falls}/{v.total} OK</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 space-y-2">
        <div className="flex items-center justify-between">
          <div className="text-sm font-semibold flex items-center gap-2"><History className="w-4 h-4 text-indigo-300" /> Historial reciente</div>
          <button onClick={resetCircuit} disabled={loading.reset}
            className="flex items-center gap-1 text-xs px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700">
            {loading.reset ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RotateCcw className="w-3.5 h-3.5" />} Rearmar circuit breaker
          </button>
        </div>
        {history.length === 0 ? (
          <div className="text-xs text-slate-500">Sin registros todavía</div>
        ) : (
          <div className="space-y-1 max-h-64 overflow-auto">
            {history.slice().reverse().map((e, i) => (
              <div key={i} className="flex items-center gap-2 text-xs rounded bg-slate-800/40 px-2 py-1">
                {e.status === 'PASS' || e.status === 'FOUND' ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" /> : <XCircle className="w-3.5 h-3.5 text-red-400 shrink-0" />}
                <span className="text-slate-500">{e.suite}</span>
                <span className="text-slate-300 truncate flex-1">{e.scenario}: {e.detail}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      <a href={`${API_BASE}${ECL}/forensics`} target="_blank" rel="noreferrer"
        className="flex items-center gap-2 text-xs text-slate-400 hover:text-slate-200">
        <FileText className="w-3.5 h-3.5" /> Ver dumps forenses (JSON)
      </a>
    </div>
  );
}
