import { useState, useCallback } from 'react';
import {
  Globe, Search, Server, Mail, Shield, FileText, Database,
  Download, RefreshCw, Loader2, AlertCircle, CheckCircle2,
  Eye, Network, Fingerprint, Github, Users, Zap
} from 'lucide-react';
import { useLanguage } from '../i18n/LanguageContext';
import { osintApi } from '../api/osintApi';

// ═══════════════════════════════════════════════════════════════════
// 开源情报高级版 — OSINT Advanced v4.0 Panel
// 14 endpoints: WHOIS, DNS, Subdomains, Threat Intel, Email,
//   Headers, Full, Results, Google, Shodan, VirusTotal, Censys, GitHub, Social
// ═══════════════════════════════════════════════════════════════════

type Tab = 'whois' | 'dns' | 'subdomains' | 'threat' | 'email' | 'headers' | 'full' | 'search' | 'shodan' | 'virustotal' | 'censys' | 'github' | 'social' | 'results';

type SearchEngine = 'duckduckgo' | 'bing' | 'yahoo' | 'brave' | 'yandex' | 'google' | 'tor' | 'all';

const SEARCH_ENGINES: { id: SearchEngine; label: string }[] = [
  { id: 'all',        label: '🌐 Todos' },
  { id: 'duckduckgo',  label: '🦆 DuckDuckGo' },
  { id: 'bing',        label: '🔍 Bing' },
  { id: 'yahoo',       label: '🔮 Yahoo' },
  { id: 'brave',       label: '🦁 Brave' },
  { id: 'yandex',     label: '🔴 Yandex' },
  { id: 'google',      label: '👔 Google CSE' },
  { id: 'tor',         label: '🧅 Tor (Ahmia)' },
];

const TABS: { id: Tab; icon: typeof Globe; color: string }[] = [
  { id: 'whois',      icon: Server,      color: 'text-cyan-400' },
  { id: 'dns',        icon: Network,     color: 'text-blue-400' },
  { id: 'subdomains', icon: Globe,       color: 'text-purple-400' },
  { id: 'threat',     icon: Shield,      color: 'text-red-400' },
  { id: 'email',      icon: Mail,        color: 'text-amber-400' },
  { id: 'headers',    icon: Fingerprint, color: 'text-indigo-400' },
  { id: 'full',       icon: FileText,    color: 'text-green-400' },
  { id: 'search',     icon: Search,      color: 'text-sky-400' },
  { id: 'shodan',     icon: Eye,         color: 'text-orange-400' },
  { id: 'virustotal', icon: Shield,      color: 'text-rose-400' },
  { id: 'censys',     icon: Database,    color: 'text-teal-400' },
  { id: 'github',     icon: Github,      color: 'text-slate-300' },
  { id: 'social',     icon: Users,       color: 'text-pink-400' },
  { id: 'results',    icon: Database,    color: 'text-zinc-400' },
];

function authHeaders(): Record<string, string> {
  const token = localStorage.getItem('api_token');
  return token ? { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' } : { 'Content-Type': 'application/json' };
}

async function apiCall<T>(url: string, opts?: RequestInit): Promise<T> {
  const r = await fetch(url, { ...opts, headers: authHeaders() });
  if (!r.ok) {
    const errBody = await r.json().catch(() => ({}))
    const detail = errBody.error || r.statusText
    if (r.status === 401) throw new Error('Token invalido. Cierra sesion y vuelve a entrar.')
    if (r.status === 503) throw new Error(`${detail}. Verifica que el binario o API key este configurado.`)
    if (r.status === 504) throw new Error('Timeout — intenta con un objetivo mas simple.')
    throw new Error(`HTTP ${r.status}: ${detail}`)
  }
  return r.json();
}

export default function OSINTAdvancedPanel() {
  const { t, lang } = useLanguage();
  const [activeTab, setActiveTab] = useState<Tab>('whois');
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [showJson, setShowJson] = useState(false);
  const [selectedEngine, setSelectedEngine] = useState<SearchEngine>('all');
  const [fullScanLoading, setFullScanLoading] = useState(false);
  const [fullScanResult, setFullScanResult] = useState<any>(null);

  const runFullScanV2 = async () => {
    if (!input.trim()) return;
    setFullScanLoading(true);
    setError(null);
    setResult(null);
    setFullScanResult(null);
    try {
      const data = await osintApi.fullScan(input.trim());
      setFullScanResult(data);
    } catch (e: any) {
      setError(e?.message || 'Error en Full Scan v2');
    } finally {
      setFullScanLoading(false);
    }
  };

  const PRIVATE_IP_RE = /^(10\.|127\.|169\.254\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.)/;

  const execute = useCallback(async () => {
    if (!input.trim() && activeTab !== 'results') return;
    // Shodan/Censys solo indexan direcciones PUBLICAS de internet -- jamas
    // van a tener datos de una IP de tu red local (192.168.x, 10.x, etc.),
    // no es un bug, es como funcionan esos servicios. Avisar antes de pegarle
    // a la API para no confundir 'sin datos' con 'esta roto'.
    // Shodan: las IPs privadas ahora se enriquecen localmente (puertos, MAC, latencia)
    // Censys: si sigue solo indexando publicas, avisar
    if (activeTab === 'censys' && PRIVATE_IP_RE.test(input.trim())) {
      setError(`${input.trim()} es una IP privada. Censys solo indexa IPs publicas. Para escaneo local usa el tab Shodan.`);
      return;
    }
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const base = '/api/osint';
      let data: any;

      switch (activeTab) {
        case 'whois':
          data = await apiCall(`${base}/whois/${encodeURIComponent(input)}`);
          break;
        case 'dns':
          data = await apiCall(`${base}/dns/${encodeURIComponent(input)}`);
          break;
        case 'subdomains':
          data = await apiCall(`${base}/subdomains`, {
            method: 'POST',
            body: JSON.stringify({ domain: input })
          });
          break;
        case 'threat':
          data = await apiCall(`${base}/threat-intel/${encodeURIComponent(input)}`);
          break;
        case 'email':
          data = await apiCall(`${base}/email`, {
            method: 'POST',
            body: JSON.stringify({ target: input })
          });
          break;
        case 'headers':
          data = await apiCall(`${base}/headers?url=${encodeURIComponent(input)}`);
          break;
        case 'full':
          data = await apiCall(`${base}/full/${encodeURIComponent(input)}`);
          break;
        case 'search':
          data = await apiCall(`${base}/search?q=${encodeURIComponent(input)}&engine=${selectedEngine}&num=15`);
          break;
        case 'shodan':
          data = await apiCall(`${base}/shodan/${encodeURIComponent(input)}`);
          break;
        case 'virustotal':
          data = await apiCall(`${base}/virustotal/${encodeURIComponent(input)}`);
          break;
        case 'censys':
          data = await apiCall(`${base}/censys/${encodeURIComponent(input)}`);
          break;
        case 'github':
          data = await apiCall(`${base}/github/${encodeURIComponent(input)}`);
          break;
        case 'social':
          data = await apiCall(`${base}/social`, {
            method: 'POST',
            body: JSON.stringify({ target: input })
          });
          break;
        case 'results':
          data = await apiCall(`${base}/results`);
          break;
      }
      // Varios endpoints (shodan, virustotal, censys, github) devuelven
      // HTTP 200 con un campo 'error' embebido en vez de un status HTTP de
      // error (ej sin API key, o key invalida -> HTTP 401 de Shodan pasado
      // como texto). apiCall() solo revisa el status HTTP, así que sin esto
      // se mostraba 'Exito' en verde con un error adentro -- confuso y
      // parecia que el sistema devolvia datos falsos/simulados.
      if (data && typeof data === 'object' && !Array.isArray(data) && data.error) {
        setError(typeof data.error === 'string' ? data.error : JSON.stringify(data.error));
        setResult(null);
      } else {
        setResult(data);
      }
    } catch (e: any) {
      setError(e?.message || 'Error');
    } finally {
      setLoading(false);
    }
  }, [input, activeTab]);

  const exportJson = () => {
    if (!result) return;
    const blob = new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `osint_${activeTab}_${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const placeholder = activeTab === 'threat' || activeTab === 'censys'
    ? '8.8.8.8'
    : activeTab === 'shodan'
    ? '8.8.8.8 o 192.168.1.1 (local)'
    : activeTab === 'headers' ? 'https://example.com'
    : activeTab === 'email' ? 'user@example.com'
    : activeTab === 'social' || activeTab === 'github' ? 'username'
    : activeTab === 'virustotal' ? '8.8.8.8 or domain.com'
    : activeTab === 'search' ? 'search query (site:target.com, intitle:admin, etc.)'
    : 'example.com';

  return (
    <div className="space-y-4 p-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Globe className="h-6 w-6 text-indigo-400" />
          <div>
            <h2 className="text-lg font-bold text-white">开源情报高级版</h2>
            <p className="text-xs text-slate-500">OSINT Advanced v4.0 — 14 endpoints</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {result && (
            <button onClick={exportJson} className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg bg-slate-800 border border-slate-700 text-slate-300 hover:bg-slate-700 transition">
              <Download size={14} /> {t('export')}
            </button>
          )}
          <button
            onClick={runFullScanV2}
            disabled={fullScanLoading || !input.trim()}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg bg-indigo-600/80 border border-indigo-500 text-white hover:bg-indigo-500 disabled:opacity-50 transition"
            title="Escaneo combinado v2: WHOIS + DNS + Subdominios + Threat Intel en una sola llamada"
          >
            {fullScanLoading ? <Loader2 size={14} className="animate-spin" /> : <Zap size={14} />}
            Full Scan v2
          </button>
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

      {/* Engine selector (only for search tab) */}
      {activeTab === 'search' && (
        <div className="flex flex-wrap gap-1.5">
          {SEARCH_ENGINES.map(eng => (
            <button
              key={eng.id}
              onClick={() => setSelectedEngine(eng.id)}
              className={`px-2.5 py-1 text-xs rounded-md transition ${
                selectedEngine === eng.id
                  ? 'bg-sky-900/50 border border-sky-700 text-sky-300'
                  : 'bg-slate-900 border border-slate-800 text-slate-500 hover:text-slate-300'
              }`}
            >
              {eng.label}
            </button>
          ))}
        </div>
      )}

      {/* Search bar */}
      {activeTab !== 'results' && (
        <div className="flex gap-2">
          <div className="relative flex-1">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-600" />
            <input
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && execute()}
              placeholder={placeholder}
              className="w-full pl-9 pr-3 py-2 text-sm bg-slate-900 border border-slate-800 rounded-lg text-slate-200 placeholder:text-slate-600 focus:border-cyan-700 focus:outline-none"
            />
          </div>
          <button
            onClick={execute}
            disabled={loading || !input.trim()}
            className="flex items-center gap-1.5 px-4 py-2 text-sm rounded-lg bg-cyan-900/40 border border-cyan-800 text-cyan-300 hover:bg-cyan-900/60 disabled:opacity-40 transition"
          >
            {loading ? <Loader2 size={15} className="animate-spin" /> : <Search size={15} />}
            {loading ? t('loading') : t('analyze')}
          </button>
        </div>
      )}

      {activeTab === 'results' && (
        <button onClick={execute} disabled={loading}
          className="flex items-center gap-1.5 px-4 py-2 text-sm rounded-lg bg-slate-800 border border-slate-700 text-slate-300 hover:bg-slate-700 disabled:opacity-40">
          {loading ? <Loader2 size={15} className="animate-spin" /> : <RefreshCw size={15} />}
          {t('refresh')}
        </button>
      )}

      {/* Error */}
      {error && (
        <div className="flex items-center gap-2 p-3 rounded-lg bg-red-950/40 border border-red-800 text-red-400 text-sm">
          <AlertCircle size={16} /> {error}
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="flex items-center justify-center py-12">
          <Loader2 size={24} className="animate-spin text-cyan-400" />
          <span className="ml-2 text-sm text-slate-500">{t('loading')}...</span>
        </div>
      )}

      {/* Results */}
      {result && !loading && (
        <div className="space-y-3">
          {/* Summary card */}
          <div className="p-4 rounded-lg bg-slate-900 border border-slate-800">
            <div className="flex items-center gap-2 mb-3">
              <CheckCircle2 size={16} className="text-green-400" />
              <span className="text-sm font-medium text-slate-300">{t('success')}</span>
            </div>
            <ResultRenderer data={result} lang={lang} t={t} />
          </div>

          {/* JSON toggle */}
          <button
            onClick={() => setShowJson(!showJson)}
            className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-300"
          >
            <Eye size={13} /> {showJson ? 'Hide' : 'Show'} JSON
          </button>
          {showJson && (
            <pre className="p-3 rounded-lg bg-slate-950 border border-slate-800 text-xs text-slate-400 overflow-x-auto max-h-96">
              {JSON.stringify(result, null, 2)}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════
// Result Renderer — renders structured data nicely
// ═══════════════════════════════════════════════════════════════════

function ResultRenderer({ data, lang, t }: { data: any; lang: string; t: (k: string) => string }) {
  if (Array.isArray(data)) {
    if (data.length === 0) return <p className="text-sm text-slate-500">No data</p>;
    return (
      <div className="space-y-2">
        {data.map((item, i) => (
          <div key={i} className="p-2 rounded bg-slate-800/50 border border-slate-800 text-sm">
            <ResultRenderer data={item} lang={lang} t={t} />
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
              <ResultRenderer data={val} lang={lang} t={t} />
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
