import React, { useState } from 'react';
import {
  Globe, Search, Mail, Server, Clock, FileText, Shield, AlertTriangle,
  Check, X, Download, Lock, Network, Fingerprint, Users, Globe2,
  ChevronDown, ChevronUp, RefreshCw, Cpu, ExternalLink
} from 'lucide-react';

export interface WhoisData { domain?: string; registrar?: string; created_date?: string; creation_date?: string; expiry_date?: string; expiration_date?: string; nameservers?: string[]; parsed?: Record<string, any>; }
export interface SubdomainItem { subdomain: string; ip?: string; source?: string; }
export interface EmailItem { email: string; source?: string; confidence?: number; }
export interface DnsRecord { type: string; value: string; ttl?: number; priority?: number; }
export interface HeaderData { headers?: Record<string, string>; technologies?: string[]; server?: string; tls_info?: { version?: string; cipher?: string; secure?: boolean }; }
export interface CertData { issuer?: string; valid_to?: string; days_remaining?: number; self_signed?: boolean; fingerprint?: string; }
export interface SocialPlatform { platform: string; url?: string; found: boolean; }
export interface ReverseIpData { ip?: string; hostname?: string; domains?: string[]; location?: string; isp?: string; }

const TOOLS = [
  { id: 'whois', label: 'WHOIS', icon: FileText, endpoint: (t: string) => `/api/osint/whois/${t}`, color: 'border-cyan-500/40 text-cyan-300 hover:bg-cyan-500/10', active: 'bg-cyan-500/20 text-cyan-300 border-cyan-500' },
  { id: 'subdomains', label: 'Subdominios', icon: Server, endpoint: (t: string) => `/api/osint/subdomains/${t}?brute=true`, color: 'border-purple-500/40 text-purple-300 hover:bg-purple-500/10', active: 'bg-purple-500/20 text-purple-300 border-purple-500' },
  { id: 'emails', label: 'Emails', icon: Mail, endpoint: (t: string) => `/api/osint/emails/${t}`, color: 'border-amber-500/40 text-amber-300 hover:bg-amber-500/10', active: 'bg-amber-500/20 text-amber-300 border-amber-500' },
  { id: 'dns', label: 'DNS', icon: Network, endpoint: (t: string) => `/api/osint/dns/${t}`, color: 'border-emerald-500/40 text-emerald-300 hover:bg-emerald-500/10', active: 'bg-emerald-500/20 text-emerald-300 border-emerald-500' },
  { id: 'headers', label: 'Headers', icon: Globe2, endpoint: (t: string) => `/api/osint/headers/${t}`, color: 'border-blue-500/40 text-blue-300 hover:bg-blue-500/10', active: 'bg-blue-500/20 text-blue-300 border-blue-500' },
  { id: 'cert', label: 'SSL Cert', icon: Lock, endpoint: (t: string) => `/api/osint/cert/${t}`, color: 'border-rose-500/40 text-rose-300 hover:bg-rose-500/10', active: 'bg-rose-500/20 text-rose-300 border-rose-500' },
  { id: 'social', label: 'Social', icon: Users, endpoint: (t: string) => `/api/osint/social/${t}`, color: 'border-indigo-500/40 text-indigo-300 hover:bg-indigo-500/10', active: 'bg-indigo-500/20 text-indigo-300 border-indigo-500' },
  { id: 'reverse', label: 'Reverse IP', icon: Fingerprint, endpoint: (t: string) => `/api/osint/reverse/${t}`, color: 'border-teal-500/40 text-teal-300 hover:bg-teal-500/10', active: 'bg-teal-500/20 text-teal-300 border-teal-500' },
  { id: 'full', label: 'Full Report', icon: Shield, endpoint: (t: string) => `/api/osint/full/${t}`, color: 'border-fuchsia-500/40 text-fuchsia-300 hover:bg-fuchsia-500/10', active: 'bg-fuchsia-500/20 text-fuchsia-300 border-fuchsia-500' },
];

function WhoisView({ data }: { data?: WhoisData }) {
  if (!data || Object.keys(data).length === 0) return <div className="text-gray-500 text-xs font-mono italic">Sin datos WHOIS</div>;
  const registrar = data.registrar || data.parsed?.registrar || 'N/A';
  const created = data.created_date || data.creation_date || data.parsed?.creation_date || 'N/A';
  const expiry = data.expiry_date || data.expiration_date || data.parsed?.expiration_date || 'N/A';
  const ns = data.nameservers || data.parsed?.nameservers || [];

  return (
    <div className="space-y-2 font-mono text-xs">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2">
        <div className="bg-[var(--ss-bg-3)] border border-[var(--ss-border)] p-2 rounded">
          <span className="text-[10px] text-gray-400 block uppercase">Registrador</span>
          <span className="text-cyan-300 font-semibold truncate block">{registrar}</span>
        </div>
        <div className="bg-[var(--ss-bg-3)] border border-[var(--ss-border)] p-2 rounded">
          <span className="text-[10px] text-gray-400 block uppercase">Creación</span>
          <span className="text-gray-200 block">{created}</span>
        </div>
        <div className="bg-[var(--ss-bg-3)] border border-[var(--ss-border)] p-2 rounded">
          <span className="text-[10px] text-gray-400 block uppercase">Expiración</span>
          <span className="text-amber-300 block">{expiry}</span>
        </div>
        <div className="bg-[var(--ss-bg-3)] border border-[var(--ss-border)] p-2 rounded">
          <span className="text-[10px] text-gray-400 block uppercase">Servidores DNS</span>
          <span className="text-gray-300 block truncate">{Array.isArray(ns) ? ns.join(', ') : ns || 'N/A'}</span>
        </div>
      </div>
      {data.parsed && Object.keys(data.parsed).length > 0 && (
        <div className="bg-[var(--ss-bg-3)] border border-[var(--ss-border)] rounded p-2 max-h-32 overflow-y-auto text-[11px] space-y-1">
          {Object.entries(data.parsed).map(([k, v]) => (
            <div key={k} className="flex gap-2"><span className="text-gray-500 shrink-0">{k}:</span><span className="text-gray-300 truncate">{typeof v === 'object' ? JSON.stringify(v) : String(v)}</span></div>
          ))}
        </div>
      )}
    </div>
  );
}

function SubdomainsView({ data }: { data?: any }) {
  const list: SubdomainItem[] = Array.isArray(data) ? data : (data?.subdomains || []);
  if (!list.length) return <div className="text-gray-500 text-xs font-mono italic">No se encontraron subdominios</div>;
  return (
    <div className="space-y-2 font-mono">
      <div className="text-[10px] text-purple-400">Total subdominios: {list.length}</div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-1.5 max-h-56 overflow-y-auto">
        {list.map((item, idx) => (
          <div key={idx} className="bg-[var(--ss-bg-3)] border border-[var(--ss-border)] rounded p-1.5 flex items-center justify-between text-xs">
            <span className="text-gray-200 truncate mr-2" title={item.subdomain}>{item.subdomain}</span>
            <div className="flex items-center gap-1.5 shrink-0">
              {item.ip && <span className="text-cyan-400 text-[10px]">{item.ip}</span>}
              <span className="text-[9px] px-1 py-0.5 rounded bg-purple-500/10 text-purple-300 border border-purple-500/30">{item.source || 'crt.sh'}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function EmailsView({ data }: { data?: any }) {
  const list: EmailItem[] = Array.isArray(data) ? data : (data?.emails || []);
  if (!list.length) return <div className="text-gray-500 text-xs font-mono italic">No se encontraron emails</div>;
  return (
    <div className="space-y-2 font-mono">
      <div className="text-[10px] text-amber-400">Total emails: {list.length}</div>
      <div className="space-y-1.5 max-h-56 overflow-y-auto">
        {list.map((item, idx) => (
          <div key={idx} className="bg-[var(--ss-bg-3)] border border-[var(--ss-border)] rounded p-1.5 flex items-center justify-between text-xs">
            <span className="text-gray-200 truncate">{item.email}</span>
            <div className="flex items-center gap-2 text-[10px] shrink-0">
              {item.source && <span className="text-gray-400 bg-[var(--ss-bg-2)] px-1.5 py-0.5 rounded border border-[var(--ss-border)]">{item.source}</span>}
              {item.confidence !== undefined && <span className="text-amber-400 font-semibold">{item.confidence}% conf.</span>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function DnsView({ data }: { data?: any }) {
  const [activeType, setActiveType] = useState('ALL');
  let records: DnsRecord[] = [];
  if (Array.isArray(data)) records = data;
  else if (data?.records && Array.isArray(data.records)) records = data.records;
  else if (data && typeof data === 'object') {
    Object.entries(data).forEach(([type, vals]) => {
      if (type === 'target') return;
      (Array.isArray(vals) ? vals : [vals]).forEach((v: any) => {
        if (typeof v === 'object' && v.type) records.push(v);
        else records.push({ type: type.toUpperCase(), value: String(v) });
      });
    });
  }
  if (!records.length) return <div className="text-gray-500 text-xs font-mono italic">No hay registros DNS disponibles</div>;
  const types = ['ALL', ...Array.from(new Set(records.map(r => r.type)))];
  const filtered = activeType === 'ALL' ? records : records.filter(r => r.type === activeType);

  return (
    <div className="space-y-2 font-mono">
      <div className="flex gap-1 overflow-x-auto pb-1">
        {types.map(t => (
          <button key={t} onClick={() => setActiveType(t)} className={`px-2 py-0.5 text-[10px] rounded border transition ${activeType === t ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500' : 'bg-[var(--ss-bg-3)] text-gray-400 border-[var(--ss-border)] hover:text-gray-200'}`}>{t}</button>
        ))}
      </div>
      <div className="space-y-1.5 max-h-56 overflow-y-auto">
        {filtered.map((r, i) => (
          <div key={i} className="bg-[var(--ss-bg-3)] border border-[var(--ss-border)] rounded p-1.5 flex items-center justify-between text-xs">
            <div className="flex items-center gap-2 overflow-hidden">
              <span className="px-1.5 py-0.5 rounded text-[9px] bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 font-bold shrink-0">{r.type}</span>
              <span className="text-gray-200 truncate">{r.value}</span>
            </div>
            <div className="flex gap-2 text-[10px] text-gray-400 shrink-0">
              {r.ttl !== undefined && <span>TTL: {r.ttl}</span>}
              {r.priority !== undefined && <span>Prio: {r.priority}</span>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function HeadersView({ data }: { data?: HeaderData }) {
  if (!data || (!data.headers && !data.technologies)) return <div className="text-gray-500 text-xs font-mono italic">Sin cabeceras HTTP</div>;
  const headers = data.headers || {};
  const techs = data.technologies || [];
  const tls = data.tls_info;

  return (
    <div className="space-y-2 font-mono text-xs">
      {techs.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-[10px] text-gray-400 uppercase mr-1 flex items-center gap-1"><Cpu size={11} /> Tecnologías:</span>
          {techs.map((t, idx) => <span key={idx} className="px-2 py-0.5 text-[10px] rounded-full bg-blue-500/10 text-blue-300 border border-blue-500/30">{t}</span>)}
        </div>
      )}
      {tls && (
        <div className="bg-[var(--ss-bg-3)] border border-[var(--ss-border)] rounded p-2 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Lock size={13} className={tls.secure ? 'text-emerald-400' : 'text-amber-400'} />
            <span className="text-gray-300">TLS: {tls.version || 'v1.3'}</span>
            {tls.cipher && <span className="text-gray-400 text-[10px]">({tls.cipher})</span>}
          </div>
          <span className={`text-[10px] px-2 py-0.5 rounded ${tls.secure ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30' : 'bg-amber-500/10 text-amber-400 border border-amber-500/30'}`}>
            {tls.secure ? 'Cifrado Seguro' : 'Inseguro'}
          </span>
        </div>
      )}
      <div className="bg-[var(--ss-bg-3)] border border-[var(--ss-border)] rounded p-2 max-h-48 overflow-y-auto text-[11px] space-y-1">
        {Object.entries(headers).map(([k, v]) => (
          <div key={k} className="flex gap-2"><span className="text-blue-400 font-medium shrink-0">{k}:</span><span className="text-gray-300 truncate">{v}</span></div>
        ))}
      </div>
    </div>
  );
}

function CertView({ data }: { data?: CertData }) {
  if (!data || Object.keys(data).length === 0) return <div className="text-gray-500 text-xs font-mono italic">Sin certificado SSL</div>;
  const days = data.days_remaining ?? 999;
  const isExpiringSoon = days < 30;

  return (
    <div className="space-y-2 font-mono text-xs">
      {data.self_signed && (
        <div className="bg-rose-500/10 border border-rose-500/30 text-rose-300 rounded p-2 flex items-center gap-2">
          <AlertTriangle size={14} className="shrink-0 text-rose-400" />
          <span>Advertencia: Certificado Auto-firmado detectado</span>
        </div>
      )}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
        <div className="bg-[var(--ss-bg-3)] border border-[var(--ss-border)] p-2 rounded">
          <span className="text-[10px] text-gray-400 uppercase block">Emisor</span>
          <span className="text-rose-300 font-semibold truncate block">{data.issuer || 'N/A'}</span>
        </div>
        <div className="bg-[var(--ss-bg-3)] border border-[var(--ss-border)] p-2 rounded">
          <span className="text-[10px] text-gray-400 uppercase block">Expiración</span>
          <span className="text-gray-200 block">{data.valid_to || 'N/A'}</span>
        </div>
        <div className={`border p-2 rounded ${isExpiringSoon ? 'bg-rose-500/10 border-rose-500/30' : 'bg-emerald-500/10 border-emerald-500/30'}`}>
          <span className="text-[10px] text-gray-400 uppercase block">Días Restantes</span>
          <span className={`font-bold block ${isExpiringSoon ? 'text-rose-400' : 'text-emerald-400'}`}>
            {days !== 999 ? `${days} días` : 'N/A'} {isExpiringSoon && '⚠️'}
          </span>
        </div>
      </div>
      {data.fingerprint && <div className="bg-[var(--ss-bg-3)] border border-[var(--ss-border)] rounded p-2 text-[10px] text-gray-400">Fingerprint: <span className="text-gray-200">{data.fingerprint}</span></div>}
    </div>
  );
}

function SocialView({ data }: { data?: any }) {
  const list: SocialPlatform[] = Array.isArray(data) ? data : (data?.results || []);
  if (!list.length) return <div className="text-gray-500 text-xs font-mono italic">No hay resultados sociales</div>;

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2 max-h-56 overflow-y-auto font-mono text-xs">
      {list.map((s, idx) => (
        <div key={idx} className={`border rounded p-2 flex flex-col justify-between ${s.found ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300' : 'bg-[var(--ss-bg-3)] border-[var(--ss-border)] text-gray-500'}`}>
          <div className="flex items-center justify-between mb-1">
            <span className="font-semibold capitalize truncate">{s.platform}</span>
            {s.found ? <Check size={14} className="text-emerald-400 shrink-0" /> : <X size={14} className="text-gray-600 shrink-0" />}
          </div>
          <div className="text-[9px]">
            {s.found ? <a href={s.url || '#'} target="_blank" rel="noreferrer" className="hover:underline flex items-center gap-0.5 text-emerald-400">Ver perfil <ExternalLink size={8} /></a> : <span>No encontrado</span>}
          </div>
        </div>
      ))}
    </div>
  );
}

function ReverseIpView({ data }: { data?: ReverseIpData }) {
  if (!data || Object.keys(data).length === 0) return <div className="text-gray-500 text-xs font-mono italic">Sin datos Reverse IP</div>;
  return (
    <div className="space-y-2 font-mono text-xs">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
        <div className="bg-[var(--ss-bg-3)] border border-[var(--ss-border)] p-2 rounded"><span className="text-[10px] text-gray-400 block">IP</span><span className="text-teal-300 font-bold">{data.ip || 'N/A'}</span></div>
        <div className="bg-[var(--ss-bg-3)] border border-[var(--ss-border)] p-2 rounded"><span className="text-[10px] text-gray-400 block">Hostname</span><span className="text-gray-200 truncate block">{data.hostname || 'N/A'}</span></div>
        <div className="bg-[var(--ss-bg-3)] border border-[var(--ss-border)] p-2 rounded"><span className="text-[10px] text-gray-400 block">Ubicación / ISP</span><span className="text-gray-300 truncate block">{data.location || data.isp || 'N/A'}</span></div>
      </div>
      {data.domains && data.domains.length > 0 && (
        <div className="space-y-1">
          <span className="text-[10px] text-teal-400 uppercase">Dominios Co-alojados ({data.domains.length}):</span>
          <div className="bg-[var(--ss-bg-3)] border border-[var(--ss-border)] rounded p-2 max-h-28 overflow-y-auto text-gray-300 space-y-0.5">{data.domains.map((dom, i) => <div key={i} className="truncate">• {dom}</div>)}</div>
        </div>
      )}
    </div>
  );
}

export default function OSINTPanel() {
  const [target, setTarget] = useState('');
  const [selectedTool, setSelectedTool] = useState('whois');
  const [loadingTool, setLoadingTool] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<string>('whois');
  const [statusMsg, setStatusMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<Record<string, any>>({});
  const [accordionOpen, setAccordionOpen] = useState<Record<string, boolean>>({
    whois: true, subdomains: true, emails: true, dns: true, headers: true, cert: true, social: true, reverse: true
  });

  const runTool = async (toolId?: string) => {
    const id = toolId || selectedTool;
    if (!target.trim()) { setError('Ingresa un dominio, IP o usuario'); return; }
    setError(null);
    setLoadingTool(id);
    const tool = TOOLS.find(t => t.id === id);
    setStatusMsg(`Consultando ${tool?.label || id}...`);

    try {
      const url = tool ? tool.endpoint(target.trim()) : `/api/osint/${id}/${target.trim()}`;
      const res = await fetch(url);
      if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
      const data = await res.json();
      setResults(prev => ({ ...prev, [id]: data }));
      setActiveTab(id);
      setStatusMsg(`Operación ${tool?.label || id} completada.`);
    } catch (e: any) {
      setError(`Error en ${tool?.label || id}: ${e.message}`);
    } finally {
      setLoadingTool(null);
    }
  };

  const handleExport = async () => {
    if (!target.trim()) return;
    setLoadingTool('export');
    setError(null);
    try {
      const res = await fetch(`/api/osint/export/${target.trim()}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `osint_${target.replace(/[^a-zA-Z0-9]/g, '_')}.json`;
      a.click();
      URL.revokeObjectURL(url);
      setStatusMsg('Exportación JSON descargada');
    } catch (e: any) {
      setError(`Error al exportar: ${e.message}`);
    } finally {
      setLoadingTool(null);
    }
  };

  const toggleAccordion = (key: string) => setAccordionOpen(prev => ({ ...prev, [key]: !prev[key] }));

  return (
    <div className="bg-[var(--ss-bg-2)] border border-[var(--ss-border)] rounded-lg p-3.5 h-full flex flex-col font-sans space-y-3">
      {/* HEADER */}
      <div className="flex items-center justify-between pb-2 border-b border-[var(--ss-border)]">
        <h3 className="text-xs font-bold uppercase tracking-widest text-fuchsia-400 flex items-center gap-2 font-mono">
          <Globe size={15} /> Super OSINT Engine
        </h3>
        <button
          onClick={handleExport}
          disabled={!target.trim() || loadingTool === 'export'}
          className="px-2.5 py-1 text-[11px] font-mono border border-fuchsia-500/40 text-fuchsia-300 rounded hover:bg-fuchsia-500/10 disabled:opacity-40 transition flex items-center gap-1.5"
        >
          {loadingTool === 'export' ? <div className="animate-spin h-3 w-3 border-2 border-fuchsia-400 border-t-transparent rounded-full" /> : <Download size={12} />}
          Exportar JSON
        </button>
      </div>

      {/* INPUT BAR */}
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Search size={13} className="absolute left-2.5 top-2.5 text-gray-400" />
          <input
            type="text"
            value={target}
            onChange={e => setTarget(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && runTool()}
            placeholder="Dominio, IP o Usuario (ej: ejemplo.com / 1.1.1.1 / admin)"
            className="w-full bg-[var(--ss-bg-3)] border border-[var(--ss-border)] rounded pl-8 pr-2 py-1.5 text-xs text-gray-200 font-mono focus:border-fuchsia-500 focus:outline-none"
          />
        </div>
        <select
          value={selectedTool}
          onChange={e => setSelectedTool(e.target.value)}
          className="bg-[var(--ss-bg-3)] border border-[var(--ss-border)] rounded px-2 py-1.5 text-xs text-gray-300 font-mono focus:outline-none"
        >
          {TOOLS.map(t => <option key={t.id} value={t.id}>{t.label}</option>)}
        </select>
        <button
          onClick={() => runTool()}
          disabled={!target.trim() || !!loadingTool}
          className="px-3 py-1.5 text-xs font-mono font-semibold border border-fuchsia-500/50 text-fuchsia-300 rounded hover:bg-fuchsia-500/20 disabled:opacity-40 transition flex items-center gap-1.5 shrink-0"
        >
          {loadingTool ? <div className="animate-spin h-3 w-3 border-2 border-fuchsia-300 border-t-transparent rounded-full" /> : <RefreshCw size={12} />}
          Ejecutar
        </button>
      </div>

      {/* QUICK TOOL BUTTONS */}
      <div className="flex flex-wrap gap-1.5">
        {TOOLS.map(t => {
          const Icon = t.icon;
          const isLoading = loadingTool === t.id;
          const isActive = activeTab === t.id && results[t.id];
          return (
            <button
              key={t.id}
              onClick={() => runTool(t.id)}
              disabled={!target.trim() || !!loadingTool}
              className={`px-2 py-1 text-[10px] font-mono rounded border transition flex items-center gap-1 disabled:opacity-40 ${isActive ? t.active : t.color}`}
            >
              {isLoading ? <div className="animate-spin h-3 w-3 border-2 border-current border-t-transparent rounded-full" /> : <Icon size={11} />}
              {t.label}
            </button>
          );
        })}
      </div>

      {/* STATUS & ERROR BAR */}
      {error && (
        <div className="bg-rose-500/10 border border-rose-500/50 rounded p-2 text-xs font-mono text-rose-300 flex items-center gap-2">
          <AlertTriangle size={14} className="shrink-0 text-rose-400" />
          <span>{error}</span>
        </div>
      )}
      {!error && (statusMsg || loadingTool) && (
        <div className="bg-fuchsia-500/10 border border-fuchsia-500/30 rounded p-1.5 text-[11px] font-mono text-fuchsia-300 flex items-center gap-2">
          {loadingTool && <div className="animate-spin h-3 w-3 border-2 border-fuchsia-400 border-t-transparent rounded-full shrink-0" />}
          <span>{statusMsg || 'Procesando consulta OSINT...'}</span>
        </div>
      )}

      {/* RESULT TABS */}
      {Object.keys(results).length > 0 && (
        <div className="flex items-center gap-1 border-b border-[var(--ss-border)] pb-1.5 overflow-x-auto">
          <span className="text-[10px] font-mono text-gray-500 uppercase mr-1">Resultados:</span>
          {Object.keys(results).map(key => {
            const t = TOOLS.find(tool => tool.id === key);
            return (
              <button
                key={key}
                onClick={() => setActiveTab(key)}
                className={`px-2 py-0.5 text-[10px] font-mono rounded border ${activeTab === key ? 'bg-fuchsia-500/20 text-fuchsia-300 border-fuchsia-500' : 'bg-[var(--ss-bg-3)] text-gray-400 border-[var(--ss-border)] hover:text-gray-200'}`}
              >
                {t?.label || key}
              </button>
            );
          })}
        </div>
      )}

      {/* DATA EXPO SECTION */}
      <div className="flex-1 overflow-y-auto space-y-3 min-h-0 pr-1">
        {activeTab === 'whois' && results.whois && <WhoisView data={results.whois} />}
        {activeTab === 'subdomains' && results.subdomains && <SubdomainsView data={results.subdomains} />}
        {activeTab === 'emails' && results.emails && <EmailsView data={results.emails} />}
        {activeTab === 'dns' && results.dns && <DnsView data={results.dns} />}
        {activeTab === 'headers' && results.headers && <HeadersView data={results.headers} />}
        {activeTab === 'cert' && results.cert && <CertView data={results.cert} />}
        {activeTab === 'social' && results.social && <SocialView data={results.social} />}
        {activeTab === 'reverse' && results.reverse && <ReverseIpView data={results.reverse} />}

        {/* FULL REPORT ACCORDION */}
        {activeTab === 'full' && results.full && (
          <div className="space-y-2 font-mono">
            {[
              { k: 'whois', label: 'WHOIS', v: <WhoisView data={results.full.whois || results.whois} /> },
              { k: 'subdomains', label: 'Subdominios', v: <SubdomainsView data={results.full.subdomains || results.subdomains} /> },
              { k: 'emails', label: 'Emails', v: <EmailsView data={results.full.emails || results.emails} /> },
              { k: 'dns', label: 'Registros DNS', v: <DnsView data={results.full.dns || results.dns} /> },
              { k: 'headers', label: 'HTTP Headers', v: <HeadersView data={results.full.headers || results.headers} /> },
              { k: 'cert', label: 'Certificado SSL', v: <CertView data={results.full.cert || results.cert} /> },
              { k: 'social', label: 'Redes Sociales', v: <SocialView data={results.full.social || results.social} /> },
              { k: 'reverse', label: 'Reverse IP', v: <ReverseIpView data={results.full.reverse || results.reverse} /> },
            ].map(sec => {
              const isOpen = accordionOpen[sec.k] ?? true;
              return (
                <div key={sec.k} className="bg-[var(--ss-bg-3)] border border-[var(--ss-border)] rounded overflow-hidden">
                  <button
                    onClick={() => toggleAccordion(sec.k)}
                    className="w-full px-3 py-1.5 flex items-center justify-between text-xs font-bold text-gray-200 bg-[var(--ss-bg-2)] hover:bg-[var(--ss-bg-3)] transition"
                  >
                    <span className="flex items-center gap-2 uppercase tracking-wider text-fuchsia-400">
                      <Shield size={12} /> {sec.label}
                    </span>
                    {isOpen ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
                  </button>
                  {isOpen && <div className="p-2.5 border-t border-[var(--ss-border)]">{sec.v}</div>}
                </div>
              );
            })}
          </div>
        )}

        {/* EMPTY STATE */}
        {!Object.keys(results).length && !loadingTool && (
          <div className="text-gray-500 text-xs font-mono text-center py-10 border border-dashed border-[var(--ss-border)] rounded p-4">
            <Globe2 size={24} className="mx-auto mb-2 text-gray-600 animate-pulse" />
            Ingresa un objetivo (dominio, IP o usuario) y selecciona una herramienta para comenzar la investigación OSINT.
          </div>
        )}
      </div>
    </div>
  );
}
