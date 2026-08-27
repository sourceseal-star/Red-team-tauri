import { useState, useEffect, useCallback } from 'react';
import {
  Shield, AlertTriangle, Eye, Activity, Trash2, Download,
  RefreshCw, Loader2, KeyRound, FileWarning, Bug, Key
} from 'lucide-react';
import { useLanguage } from '../i18n/LanguageContext';
import { interceptorApi } from '../api/interceptorApi';

// ═══════════════════════════════════════════════════════════════════
// 网络拦截高级版 — Interceptor Advanced v4.0 Panel
// 10 endpoints: Analyze Request/Response, Flows, Alerts, Stats,
//   Decode, Certificate, User-Agent, Rate Check
// ═══════════════════════════════════════════════════════════════════

type Tab = 'request' | 'response' | 'flows' | 'alerts' | 'stats' | 'decode' | 'cert' | 'useragent' | 'ratecheck' | 'capture';

const TABS: { id: Tab; icon: typeof Shield; color: string }[] = [
  { id: 'request',   icon: FileWarning,  color: 'text-red-400' },
  { id: 'response',   icon: Shield,       color: 'text-amber-400' },
  { id: 'flows',      icon: Eye,           color: 'text-cyan-400' },
  { id: 'alerts',     icon: AlertTriangle, color: 'text-orange-400' },
  { id: 'stats',      icon: Activity,     color: 'text-green-400' },
  { id: 'decode',     icon: Key,          color: 'text-purple-400' },
  { id: 'cert',       icon: KeyRound,     color: 'text-blue-400' },
  { id: 'useragent',  icon: Bug,          color: 'text-pink-400' },
  { id: 'ratecheck',  icon: Activity,     color: 'text-teal-400' },
  { id: 'capture',    icon: Eye,          color: 'text-emerald-400' },
];

const SEVERITY_COLORS: Record<string, string> = {
  critical: 'bg-red-950/60 border-red-800 text-red-400',
  high: 'bg-orange-950/60 border-orange-800 text-orange-400',
  medium: 'bg-amber-950/60 border-amber-800 text-amber-400',
  low: 'bg-blue-950/60 border-blue-800 text-blue-400',
  info: 'bg-slate-800 border-slate-700 text-slate-400',
};

const CWE_MAP: Record<string, string> = {
  'SQL Injection': 'CWE-89',
  'XSS': 'CWE-79',
  'Command Injection': 'CWE-78',
  'Path Traversal': 'CWE-22',
  'SSRF': 'CWE-918',
  'XXE': 'CWE-611',
  'LFI/RFI': 'CWE-98',
  'LDAP Injection': 'CWE-90',
  'NoSQL Injection': 'CWE-943',
};

function authHeaders(): Record<string, string> {
  const token = localStorage.getItem('api_token');
  return token ? { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' } : { 'Content-Type': 'application/json' };
}

async function apiCall<T>(url: string, opts?: RequestInit): Promise<T> {
  const r = await fetch(url, { ...opts, headers: authHeaders() });
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}

export default function InterceptorAdvancedPanel() {
  const { t, lang } = useLanguage();
  const [activeTab, setActiveTab] = useState<Tab>('request');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [showJson, setShowJson] = useState(false);

  // Request analysis form
  const [reqMethod, setReqMethod] = useState('GET');
  const [reqPath, setReqPath] = useState('/test?id=1');
  const [reqHeaders, setReqHeaders] = useState('{}');
  const [reqBody, setReqBody] = useState('');

  // Response analysis form
  const [respStatus, setRespStatus] = useState('200');
  const [respHeaders, setRespHeaders] = useState('{}');
  const [respBody, setRespBody] = useState('');

  // Decode form
  const [decodeInput, setDecodeInput] = useState('');

  // Cert form
  const [certHost, setCertHost] = useState('');

  // User-Agent form
  const [uaInput, setUaInput] = useState('');

  // Rate check form
  const [rateIp, setRateIp] = useState('');

  // Capture form
  const [captureActive, setCaptureActive] = useState(false);
  const [capturePort, setCapturePort] = useState('8888');
  const [captureFlows, setCaptureFlows] = useState<any[]>([]);

  // V2: Full stats and flow analysis
  const [v2Stats, setV2Stats] = useState<any>(null);
  const [v2Flows, setV2Flows] = useState<any[]>([]);
  const [v2Alerts, setV2Alerts] = useState<any[]>([]);
  const [selectedFlowAnalysis, setSelectedFlowAnalysis] = useState<any>(null);
  const [analyzingFlow, setAnalyzingFlow] = useState(false);

  // Auto-refresh for flows/alerts
  const [autoRefresh, setAutoRefresh] = useState(false);

  const execute = useCallback(async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const base = '/api/interceptor';
      let data: any;

      switch (activeTab) {
        case 'request':
          data = await apiCall(`${base}/analyze/request`, {
            method: 'POST',
            body: JSON.stringify({
              method: reqMethod,
              path: reqPath,
              headers: JSON.parse(reqHeaders || '{}'),
              body: reqBody
            })
          });
          break;
        case 'response':
          data = await apiCall(`${base}/analyze/response`, {
            method: 'POST',
            body: JSON.stringify({
              status_code: parseInt(respStatus),
              headers: JSON.parse(respHeaders || '{}'),
              body: respBody
            })
          });
          break;
        case 'flows':
          data = await apiCall(`${base}/flows?limit=50`);
          break;
        case 'alerts':
          data = await apiCall(`${base}/alerts?limit=100`);
          break;
        case 'stats':
          data = await apiCall(`${base}/stats`);
          break;
        case 'decode':
          data = await apiCall(`${base}/decode`, {
            method: 'POST',
            body: JSON.stringify({ payload: decodeInput })
          });
          break;
        case 'cert':
          data = await apiCall(`${base}/cert/${encodeURIComponent(certHost)}`);
          break;
        case 'useragent':
          data = await apiCall(`${base}/analyze/user-agent`, {
            method: 'POST',
            body: JSON.stringify({ user_agent: uaInput })
          });
          break;
        case 'ratecheck':
          data = await apiCall(`${base}/rate-check/${encodeURIComponent(rateIp)}`);
          break;
        case 'capture':
          data = await apiCall(`${base}/capture/status`);
          break;
      }
      setResult(data);
    } catch (e: any) {
      setError(e?.message || 'Error — check JSON format');
    } finally {
      setLoading(false);
    }
  }, [activeTab, reqMethod, reqPath, reqHeaders, reqBody, respStatus, respHeaders, respBody, decodeInput, certHost, uaInput, rateIp]);

  // Auto-refresh
  useEffect(() => {
    if (!autoRefresh || (activeTab !== 'flows' && activeTab !== 'alerts' && activeTab !== 'capture')) return;
    const interval = setInterval(() => execute(), 5000);
    return () => clearInterval(interval);
  }, [autoRefresh, activeTab, execute]);

  const clearFlows = async () => {
    try {
      await apiCall('/api/interceptor/flows', { method: 'DELETE' });
      setResult(null);
    } catch (e: any) {
      setError(e?.message || 'Error');
    }
  };

  const startCapture = async () => {
    try {
      await apiCall(`/api/interceptor/capture/start?port=${capturePort}`, { method: 'POST' });
      setCaptureActive(true);
    } catch (e: any) {
      setError(e?.message || 'Error al iniciar captura');
    }
  };

  const stopCapture = async () => {
    try {
      const data = await apiCall('/api/interceptor/capture/stop', { method: 'POST' });
      setCaptureActive(false);
      setResult(data);
      await loadV2Data();
    } catch (e: any) {
      setError(e?.message || 'Error al detener captura');
    }
  };

  // V2: Load stats, flows, and alerts from the bridge
  const loadV2Data = async () => {
    try {
      const [stats, flows, alerts] = await Promise.all([
        interceptorApi.getStats(),
        interceptorApi.getFlows(50),
        interceptorApi.getAlerts(50),
      ]);
      setV2Stats(stats);
      setV2Flows(flows.flows || []);
      setV2Alerts(alerts.alerts || []);
    } catch (e: any) {
      // Silencioso - el proxy puede no estar activo
    }
  };

  // V2: Analyze a specific flow in depth
  const analyzeFlowV2 = async (flowId: string) => {
    setAnalyzingFlow(true);
    setSelectedFlowAnalysis(null);
    try {
      const analysis = await interceptorApi.analyzeFlow(flowId);
      setSelectedFlowAnalysis(analysis);
    } catch (e: any) {
      setError(e?.message || 'Error al analizar flujo');
    } finally {
      setAnalyzingFlow(false);
    }
  };

  // Auto-load v2 data when capture tab is active
  useEffect(() => {
    if (activeTab === 'capture') {
      loadV2Data();
      const interval = setInterval(loadV2Data, 5000);
      return () => clearInterval(interval);
    }
  }, [activeTab]);

  const exportJson = () => {
    if (!result) return;
    const blob = new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `interceptor_${activeTab}_${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-4 p-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Shield className="h-6 w-6 text-red-400" />
          <div>
            <h2 className="text-lg font-bold text-white">网络拦截高级版</h2>
            <p className="text-xs text-slate-500">Interceptor Advanced v4.0 — 10 endpoints · MITM + SIEM</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {result && (
            <button onClick={exportJson} className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg bg-slate-800 border border-slate-700 text-slate-300 hover:bg-slate-700 transition">
              <Download size={14} /> {t('export')}
            </button>
          )}
          {(activeTab === 'flows') && (
            <button onClick={clearFlows} className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg bg-red-950/40 border border-red-800 text-red-400 hover:bg-red-950/60 transition">
              <Trash2 size={14} /> {t('clear')}
            </button>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex flex-wrap gap-1.5 border-b border-slate-800 pb-2">
        {TABS.map(tab => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              onClick={() => { setActiveTab(tab.id); setResult(null); setError(null); }}
              className={`flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-md transition ${
                activeTab === tab.id
                  ? 'bg-slate-800 border border-slate-600 text-white'
                  : 'text-slate-500 hover:text-slate-300 hover:bg-slate-800/50'
              }`}
            >
              <Icon size={13} className={activeTab === tab.id ? tab.color : ''} />
              {t(tab.id)}
            </button>
          );
        })}
      </div>

      {/* Auto-refresh toggle for flows/alerts */}
      {(activeTab === 'flows' || activeTab === 'alerts') && (
        <label className="flex items-center gap-2 text-xs text-slate-400 cursor-pointer">
          <input
            type="checkbox"
            checked={autoRefresh}
            onChange={e => setAutoRefresh(e.target.checked)}
            className="accent-cyan-500"
          />
          Auto-refresh (5s)
        </label>
      )}

      {/* Capture tab */}
      {activeTab === 'capture' && (
        <div className="space-y-3">
          <div className="bg-emerald-950/30 border border-emerald-800/40 rounded-lg p-3 space-y-2">
            <p className="text-xs text-emerald-400 font-mono">
              Captura de tráfico REAL — honeypot TCP que registra conexiones entrantes con análisis de inyecciones.
            </p>
            <div className="flex gap-2">
              <input value={capturePort} onChange={e => setCapturePort(e.target.value)} disabled={captureActive}
                placeholder="Puerto (8888)"
                className="px-3 py-2 text-sm bg-slate-900 border border-slate-800 rounded-lg text-slate-200 font-mono w-32 disabled:opacity-50" />
              {!captureActive ? (
                <button onClick={startCapture}
                  className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs rounded-lg">
                  ▶ Iniciar Captura
                </button>
              ) : (
                <button onClick={stopCapture}
                  className="px-4 py-2 bg-red-600 hover:bg-red-500 text-white text-xs rounded-lg">
                  ⏹ Detener
                </button>
              )}
              {captureActive && (
                <span className="text-xs text-emerald-400 flex items-center gap-1 animate-pulse">● CAPTURANDO</span>
              )}
            </div>
          </div>

          {result?.flows && result.flows.length > 0 ? (
            <div className="space-y-1.5">
              <div className="text-xs text-slate-500 font-mono">Conexiones capturadas: {result.flows.length}</div>
              {result.flows.slice().reverse().map((flow: any, i: number) => (
                <div key={i} className={`p-2 rounded border text-xs font-mono ${
                  flow.alerts && flow.alerts !== '[]' ? 'bg-red-950/40 border-red-800' : 'bg-slate-900 border-slate-700'
                }`}>
                  <div className="flex items-center justify-between">
                    <span className="text-cyan-400">{flow.src_ip}:{flow.dst_port}</span>
                    <span className="text-slate-500">{flow.timestamp?.split('T')[1]?.split('.')[0]}</span>
                  </div>
                  {flow.path && <div className="text-slate-300 truncate mt-0.5">{flow.path}</div>}
                  {flow.raw_data && <div className="text-slate-500 truncate mt-0.5 text-[10px]">{flow.raw_data}</div>}
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center text-slate-600 text-sm py-6">
              {captureActive ? 'Esperando conexiones entrantes...' : 'Inicia la captura para ver tráfico real.'}
            </div>
          )}

          {autoRefresh && activeTab === 'capture' && (
            <div className="text-[10px] text-slate-500 font-mono">Auto-refresh activo (5s) — las conexiones aparecen automáticamente.</div>
          )}
        </div>
      )}

      {/* Forms per tab */}
      {activeTab === 'request' && (
        <div className="space-y-2">
          <div className="flex gap-2">
            <select value={reqMethod} onChange={e => setReqMethod(e.target.value)}
              className="px-2 py-2 text-sm bg-slate-900 border border-slate-800 rounded-lg text-slate-200 focus:border-cyan-700 focus:outline-none">
              {['GET', 'POST', 'PUT', 'DELETE', 'PATCH'].map(m => <option key={m} value={m}>{m}</option>)}
            </select>
            <input value={reqPath} onChange={e => setReqPath(e.target.value)} placeholder="/path?query=value"
              className="flex-1 px-3 py-2 text-sm bg-slate-900 border border-slate-800 rounded-lg text-slate-200 placeholder:text-slate-600 focus:border-cyan-700 focus:outline-none font-mono" />
          </div>
          <textarea value={reqHeaders} onChange={e => setReqHeaders(e.target.value)} placeholder='{"Content-Type": "application/json"}'
            className="w-full px-3 py-2 text-xs bg-slate-900 border border-slate-800 rounded-lg text-slate-200 placeholder:text-slate-600 focus:border-cyan-700 focus:outline-none font-mono h-16" />
          <textarea value={reqBody} onChange={e => setReqBody(e.target.value)} placeholder="Request body..."
            className="w-full px-3 py-2 text-xs bg-slate-900 border border-slate-800 rounded-lg text-slate-200 placeholder:text-slate-600 focus:border-cyan-700 focus:outline-none font-mono h-16" />
          <button onClick={execute} disabled={loading}
            className="flex items-center gap-1.5 px-4 py-2 text-sm rounded-lg bg-red-900/40 border border-red-800 text-red-300 hover:bg-red-900/60 disabled:opacity-40 transition">
            {loading ? <Loader2 size={15} className="animate-spin" /> : <Shield size={15} />}
            {t('analyze')}
          </button>
        </div>
      )}

      {activeTab === 'response' && (
        <div className="space-y-2">
          <input value={respStatus} onChange={e => setRespStatus(e.target.value)} placeholder="200"
            className="w-32 px-3 py-2 text-sm bg-slate-900 border border-slate-800 rounded-lg text-slate-200 focus:border-amber-700 focus:outline-none font-mono" />
          <textarea value={respHeaders} onChange={e => setRespHeaders(e.target.value)} placeholder='{"Content-Type": "text/html"}'
            className="w-full px-3 py-2 text-xs bg-slate-900 border border-slate-800 rounded-lg text-slate-200 placeholder:text-slate-600 focus:border-amber-700 focus:outline-none font-mono h-16" />
          <textarea value={respBody} onChange={e => setRespBody(e.target.value)} placeholder="Response body..."
            className="w-full px-3 py-2 text-xs bg-slate-900 border border-slate-800 rounded-lg text-slate-200 placeholder:text-slate-600 focus:border-amber-700 focus:outline-none font-mono h-16" />
          <button onClick={execute} disabled={loading}
            className="flex items-center gap-1.5 px-4 py-2 text-sm rounded-lg bg-amber-900/40 border border-amber-800 text-amber-300 hover:bg-amber-900/60 disabled:opacity-40 transition">
            {loading ? <Loader2 size={15} className="animate-spin" /> : <Shield size={15} />}
            {t('analyze')}
          </button>
        </div>
      )}

      {activeTab === 'decode' && (
        <div className="space-y-2">
          <textarea value={decodeInput} onChange={e => setDecodeInput(e.target.value)} placeholder="Base64 or encoded payload..."
            className="w-full px-3 py-2 text-sm bg-slate-900 border border-slate-800 rounded-lg text-slate-200 placeholder:text-slate-600 focus:border-purple-700 focus:outline-none font-mono h-20" />
          <button onClick={execute} disabled={loading || !decodeInput.trim()}
            className="flex items-center gap-1.5 px-4 py-2 text-sm rounded-lg bg-purple-900/40 border border-purple-800 text-purple-300 hover:bg-purple-900/60 disabled:opacity-40 transition">
            {loading ? <Loader2 size={15} className="animate-spin" /> : <Key size={15} />}
            {t('analyze')}
          </button>
        </div>
      )}

      {activeTab === 'cert' && (
        <div className="flex gap-2">
          <input value={certHost} onChange={e => setCertHost(e.target.value)} placeholder="example.com"
            className="flex-1 px-3 py-2 text-sm bg-slate-900 border border-slate-800 rounded-lg text-slate-200 placeholder:text-slate-600 focus:border-blue-700 focus:outline-none font-mono" />
          <button onClick={execute} disabled={loading || !certHost.trim()}
            className="flex items-center gap-1.5 px-4 py-2 text-sm rounded-lg bg-blue-900/40 border border-blue-800 text-blue-300 hover:bg-blue-900/60 disabled:opacity-40 transition">
            {loading ? <Loader2 size={15} className="animate-spin" /> : <KeyRound size={15} />}
            {t('analyze')}
          </button>
        </div>
      )}

      {activeTab === 'useragent' && (
        <div className="space-y-2">
          <textarea value={uaInput} onChange={e => setUaInput(e.target.value)} placeholder="Mozilla/5.0 (Windows NT 10.0; Win64; x64)..."
            className="w-full px-3 py-2 text-sm bg-slate-900 border border-slate-800 rounded-lg text-slate-200 placeholder:text-slate-600 focus:border-pink-700 focus:outline-none font-mono h-16" />
          <button onClick={execute} disabled={loading || !uaInput.trim()}
            className="flex items-center gap-1.5 px-4 py-2 text-sm rounded-lg bg-pink-900/40 border border-pink-800 text-pink-300 hover:bg-pink-900/60 disabled:opacity-40 transition">
            {loading ? <Loader2 size={15} className="animate-spin" /> : <Bug size={15} />}
            {t('analyze')}
          </button>
        </div>
      )}

      {activeTab === 'ratecheck' && (
        <div className="flex gap-2">
          <input value={rateIp} onChange={e => setRateIp(e.target.value)} placeholder="192.168.1.1"
            className="flex-1 px-3 py-2 text-sm bg-slate-900 border border-slate-800 rounded-lg text-slate-200 placeholder:text-slate-600 focus:border-teal-700 focus:outline-none font-mono" />
          <button onClick={execute} disabled={loading || !rateIp.trim()}
            className="flex items-center gap-1.5 px-4 py-2 text-sm rounded-lg bg-teal-900/40 border border-teal-800 text-teal-300 hover:bg-teal-900/60 disabled:opacity-40 transition">
            {loading ? <Loader2 size={15} className="animate-spin" /> : <Activity size={15} />}
            {t('analyze')}
          </button>
        </div>
      )}

      {(activeTab === 'flows' || activeTab === 'alerts' || activeTab === 'stats') && (
        <button onClick={execute} disabled={loading}
          className="flex items-center gap-1.5 px-4 py-2 text-sm rounded-lg bg-slate-800 border border-slate-700 text-slate-300 hover:bg-slate-700 disabled:opacity-40">
          {loading ? <Loader2 size={15} className="animate-spin" /> : <RefreshCw size={15} />}
          {t('refresh')}
        </button>
      )}

      {/* Error */}
      {error && (
        <div className="flex items-center gap-2 p-3 rounded-lg bg-red-950/40 border border-red-800 text-red-400 text-sm">
          <AlertTriangle size={16} /> {error}
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="flex items-center justify-center py-12">
          <Loader2 size={24} className="animate-spin text-red-400" />
          <span className="ml-2 text-sm text-slate-500">{t('loading')}...</span>
        </div>
      )}

      {/* Results */}
      {result && !loading && (
        <div className="space-y-3">
          {/* Alerts with severity badges */}
          {activeTab === 'alerts' && Array.isArray(result) && result.length > 0 && (
            <div className="space-y-2">
              {result.map((alert: any, i: number) => (
                <div key={i} className={`p-3 rounded-lg border ${SEVERITY_COLORS[alert.severity] || SEVERITY_COLORS.info}`}>
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">{alert.type || alert.alert_type || 'Alert'}</span>
                    <span className="text-xs uppercase font-bold opacity-70">{alert.severity}</span>
                  </div>
                  {alert.cwe && <span className="text-xs opacity-60">{alert.cwe}</span>}
                  {alert.detail && <p className="text-xs mt-1 opacity-80">{alert.detail}</p>}
                  {alert.payload && <code className="text-xs mt-1 block font-mono opacity-70">{alert.payload}</code>}
                </div>
              ))}
            </div>
          )}

          {/* Stats dashboard */}
          {activeTab === 'stats' && typeof result === 'object' && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {Object.entries(result).slice(0, 8).map(([key, val]) => (
                <div key={key} className="p-3 rounded-lg bg-slate-900 border border-slate-800">
                  <p className="text-xs text-slate-500 uppercase">{key.replace(/_/g, ' ')}</p>
                  {/* val puede ser numero/string (render directo), array (lista de badges),
                      o un objeto anidado como by_severity:{critical:1,high:2} -- String(val)
                      en ese caso da literalmente "[object Object]". Desglosar cada caso. */}
                  {val === null || val === undefined ? (
                    <p className="text-lg font-bold text-slate-200 mt-1">-</p>
                  ) : Array.isArray(val) ? (
                    val.length === 0 ? (
                      <p className="text-lg font-bold text-slate-200 mt-1">-</p>
                    ) : (
                      <div className="mt-1 space-y-0.5">
                        {val.slice(0, 5).map((item, i) => (
                          <p key={i} className="text-xs font-mono text-slate-300 truncate">
                            {typeof item === 'object' ? JSON.stringify(item) : String(item)}
                          </p>
                        ))}
                      </div>
                    )
                  ) : typeof val === 'object' ? (
                    Object.keys(val).length === 0 ? (
                      <p className="text-lg font-bold text-slate-200 mt-1">-</p>
                    ) : (
                      <div className="mt-1 space-y-0.5">
                        {Object.entries(val).slice(0, 5).map(([subKey, subVal]) => (
                          <p key={subKey} className="text-xs text-slate-300 flex justify-between gap-2">
                            <span className="text-slate-500 truncate">{subKey}</span>
                            <span className="font-mono font-bold text-slate-200">{String(subVal)}</span>
                          </p>
                        ))}
                      </div>
                    )
                  ) : (
                    <p className="text-lg font-bold text-slate-200 mt-1">{String(val)}</p>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Flows table */}
          {activeTab === 'flows' && Array.isArray(result) && result.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-slate-500 border-b border-slate-800">
                    <th className="text-left p-2">Time</th>
                    <th className="text-left p-2">Source</th>
                    <th className="text-left p-2">Dest</th>
                    <th className="text-left p-2">Method</th>
                    <th className="text-left p-2">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {result.map((flow: any, i: number) => (
                    <tr key={i} className="border-b border-slate-800/50 hover:bg-slate-800/30">
                      <td className="p-2 text-slate-400">{flow.timestamp || flow.created_at || '-'}</td>
                      <td className="p-2 text-cyan-400 font-mono">{flow.src_ip || '-'}</td>
                      <td className="p-2 text-amber-400 font-mono">{flow.dst_host || flow.dst_ip || '-'}</td>
                      <td className="p-2 text-slate-300">{flow.method || '-'}</td>
                      <td className="p-2 text-slate-300">{flow.status_code || '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Default: show structured data */}
          {!(activeTab === 'alerts' && Array.isArray(result)) &&
           !(activeTab === 'stats' && typeof result === 'object') &&
           !(activeTab === 'flows' && Array.isArray(result)) && (
            <div className="p-4 rounded-lg bg-slate-900 border border-slate-800">
              <ResultRenderer data={result} />
            </div>
          )}

          {/* JSON toggle */}
          <button onClick={() => setShowJson(!showJson)}
            className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-300">
            <Eye size={13} /> {showJson ? 'Hide' : 'Show'} JSON
          </button>
          {showJson && (
            <pre className="p-3 rounded-lg bg-slate-950 border border-slate-800 text-xs text-slate-400 overflow-x-auto max-h-96">
              {JSON.stringify(result, null, 2)}
            </pre>
          )}
        </div>
      )}

      {/* CWE Reference */}
      <div className="flex flex-wrap gap-1.5 pt-2 border-t border-slate-800">
        {Object.entries(CWE_MAP).map(([name, cwe]) => (
          <span key={cwe} className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 border border-slate-700 text-slate-500">
            {name} ({cwe})
          </span>
        ))}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════
// Result Renderer
// ═══════════════════════════════════════════════════════════════════

function ResultRenderer({ data }: { data: any }) {
  if (Array.isArray(data)) {
    if (data.length === 0) return <p className="text-sm text-slate-500">No data</p>;
    return (
      <div className="space-y-2">
        {data.map((item, i) => (
          <div key={i} className="p-2 rounded bg-slate-800/50 border border-slate-800 text-sm">
            <ResultRenderer data={item} />
          </div>
        ))}
      </div>
    );
  }

  if (typeof data === 'object' && data !== null) {
    const entries = Object.entries(data);
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        {entries.map(([key, val]) => (
          <div key={key} className="flex flex-col">
            <span className="text-xs text-slate-500 uppercase tracking-wide">{key.replace(/_/g, ' ')}</span>
            {typeof val === 'object' && val !== null ? (
              <ResultRenderer data={val} />
            ) : Array.isArray(val) ? (
              <span className="text-sm text-slate-300">{(val as any[]).join(', ')}</span>
            ) : (
              <span className="text-sm text-slate-200 font-mono">{String(val)}</span>
            )}
          </div>
        ))}
      </div>
    );
  }

  return <p className="text-sm text-slate-300 font-mono">{String(data)}</p>;
}
