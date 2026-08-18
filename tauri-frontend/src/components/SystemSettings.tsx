import { useState, useEffect, useCallback } from 'react';
import { getApiKey, getBaseUrl, setBaseUrl } from '../lib/api';
import {
  Server, Network, Key, Eye, EyeOff, CheckCircle2, XCircle,
  Loader2, Save, RefreshCw, Wifi, Zap, Shield, AlertCircle, Globe
} from 'lucide-react';

type Tab = 'connection' | 'network' | 'apikeys' | 'system';

export default function SystemSettings() {
  const [tab, setTab] = useState<Tab>('connection');
  const [ops, setOps] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<{ type: 'ok' | 'err'; text: string } | null>(null);
  const [health, setHealth] = useState<'ok' | 'err' | 'checking' | 'unknown'>('unknown');

  const [backendUrl, setBackendUrl] = useState('');
  const [subnet, setSubnet] = useState('');
  const [scanPorts, setScanPorts] = useState('');
  const [scanTimeout, setScanTimeout] = useState(0.5);
  const [keys, setKeys] = useState({
    shodan_api_key: '', virustotal_api_key: '', abuseipdb_key: '', github_token: '',
  });
  const [showKeys, setShowKeys] = useState<Record<string, boolean>>({});
  const [testing, setTesting] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<Record<string, { ok: boolean; info: string }>>({});

  const authH = useCallback(() => {
    const k = getApiKey();
    return k ? { 'Authorization': `Bearer ${k}`, 'Content-Type': 'application/json' } : { 'Content-Type': 'application/json' };
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await fetch(getBaseUrl() + '/ops/config', { headers: authH() });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const data = await r.json();
      setOps(data);
      setSubnet(data.scan_subnet || '');
      setScanPorts(data.scan_ports || '');
      setScanTimeout(data.scan_timeout || 0.5);
      setKeys({
        shodan_api_key: data.shodan_api_key || '',
        virustotal_api_key: data.virustotal_api_key || '',
        abuseipdb_key: data.abuseipdb_key || '',
        github_token: data.github_token || '',
      });
    } catch (e: any) {
      setMsg({ type: 'err', text: `Error: ${e.message}` });
    } finally { setLoading(false); }
  }, [authH]);

  const checkHealth = useCallback(async () => {
    setHealth('checking');
    try {
      const r = await fetch(getBaseUrl() + '/health', { headers: authH() });
      setHealth(r.ok ? 'ok' : 'err');
    } catch { setHealth('err'); }
  }, [authH]);

  useEffect(() => { load(); checkHealth(); }, [load, checkHealth]);
  useEffect(() => { setBackendUrl(localStorage.getItem('backend_base_url') || ''); }, []);

  const saveConnection = () => {
    setBaseUrl(backendUrl.trim());
    setMsg({ type: 'ok', text: 'URL guardada. Recarga la pagina para aplicar.' });
    setTimeout(() => { setMsg(null); checkHealth(); }, 1500);
  };

  const saveNetwork = async () => {
    setSaving(true);
    try {
      const r = await fetch(getBaseUrl() + '/ops/config', {
        method: 'POST', headers: authH(),
        body: JSON.stringify({ scan_subnet: subnet, scan_ports: scanPorts, scan_timeout: scanTimeout })
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setMsg({ type: 'ok', text: 'Config de red guardada' });
      setTimeout(() => setMsg(null), 3000);
    } catch (e: any) { setMsg({ type: 'err', text: e.message }); }
    finally { setSaving(false); }
  };

  const saveKey = async (keyName: string, value: string) => {
    if (!value || value.includes('••••')) { setMsg({ type: 'err', text: 'Ingresa un valor nuevo' }); return; }
    setSaving(true);
    try {
      const r = await fetch(getBaseUrl() + '/ops/config', {
        method: 'POST', headers: authH(),
        body: JSON.stringify({ [keyName]: value })
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setMsg({ type: 'ok', text: 'API key guardada y activada' });
      setKeys(prev => ({ ...prev, [keyName]: value.slice(0,4) + '••••' + value.slice(-4) }));
      setTimeout(() => setMsg(null), 3000);
    } catch (e: any) { setMsg({ type: 'err', text: e.message }); }
    finally { setSaving(false); }
  };

  const testKey = async (service: string, key: string) => {
    if (!key || key.includes('••••')) { setTestResult(prev => ({ ...prev, [service]: { ok: false, info: 'Ingresa la key' } })); return; }
    setTesting(service);
    setTestResult(prev => ({ ...prev, [service]: { ok: false, info: 'Probando...' } }));
    try {
      const r = await fetch(getBaseUrl() + '/ops/test-key', {
        method: 'POST', headers: authH(),
        body: JSON.stringify({ service, key })
      });
      const data = await r.json();
      setTestResult(prev => ({ ...prev, [service]: { ok: data.ok, info: data.info || data.error || '' } }));
    } catch (e: any) { setTestResult(prev => ({ ...prev, [service]: { ok: false, info: e.message } })); }
    finally { setTesting(null); }
  };

  if (loading) return <div className="flex items-center justify-center py-20"><Loader2 className="animate-spin text-cyan-400" size={24} /></div>;

  const TABS: { id: Tab; icon: typeof Server; label: string }[] = [
    { id: 'connection', icon: Server, label: 'Conexion' },
    { id: 'network', icon: Network, label: 'Red y Escaneo' },
    { id: 'apikeys', icon: Key, label: 'API Keys' },
    { id: 'system', icon: Globe, label: 'Sistema' },
  ];

  return (
    <div className="space-y-4 max-w-2xl">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold text-slate-100 flex items-center gap-2">
          <Server size={20} className="text-cyan-400" /> Configuracion del Sistema
        </h2>
        <button onClick={() => { load(); checkHealth(); }} className="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300">
          <RefreshCw size={16} />
        </button>
      </div>

      <div className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-sm ${
        health === 'ok' ? 'bg-green-950/40 border-green-800 text-green-400' :
        health === 'err' ? 'bg-red-950/40 border-red-800 text-red-400' :
        'bg-slate-900 border-slate-700 text-slate-400'}`}>
        {health === 'ok' && <CheckCircle2 size={16} />}
        {health === 'err' && <XCircle size={16} />}
        {health === 'checking' && <Loader2 size={16} className="animate-spin" />}
        {health === 'unknown' && <AlertCircle size={16} />}
        {health === 'ok' ? 'Backend conectado' : health === 'err' ? 'Backend sin respuesta' :
         health === 'checking' ? 'Verificando...' : 'Estado desconocido'}
      </div>

      <div className="flex gap-1 flex-wrap">
        {TABS.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
              tab === t.id ? 'bg-cyan-600 text-white' : 'bg-slate-800 text-slate-400 hover:bg-slate-700'}`}>
            <t.icon size={15} /> {t.label}
          </button>
        ))}
      </div>

      {msg && (
        <div className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-sm ${
          msg.type === 'ok' ? 'bg-green-950/40 border-green-800 text-green-400' :
          'bg-red-950/40 border-red-800 text-red-400'}`}>
          {msg.type === 'ok' ? <CheckCircle2 size={16} /> : <AlertCircle size={16} />}
          {msg.text}
        </div>
      )}

      {tab === 'connection' && (
        <div className="space-y-4 bg-slate-900 border border-slate-800 rounded-lg p-4">
          <div>
            <label className="text-xs text-slate-400 font-medium block mb-1">
              URL del Backend (vacio = auto / proxy local)
            </label>
            <div className="flex gap-2">
              <input className="flex-1 bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm font-mono text-slate-200 placeholder-slate-600"
                placeholder="http://localhost:8001/api" value={backendUrl}
                onChange={e => setBackendUrl(e.target.value)} />
              <button onClick={saveConnection}
                className="px-4 py-2 bg-cyan-600 hover:bg-cyan-500 text-white text-sm rounded-lg flex items-center gap-1.5 shrink-0">
                <Save size={14} /> Aplicar
              </button>
            </div>
            <p className="text-[11px] text-slate-500 mt-1.5">
              Vacio = el frontend usa el proxy de Vite (recomendado en Termux).<br/>
              Si tu backend corre en otro dispositivo, pon la URL completa.
            </p>
          </div>
          <div className="border-t border-slate-800 pt-3 space-y-2">
            <div className="flex justify-between text-sm">
              <span className="text-slate-400">URL en uso</span>
              <span className="font-mono text-cyan-400 text-xs">{getBaseUrl()}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-slate-400">Token</span>
              <span className="font-mono text-xs text-slate-500">{getApiKey() ? 'Configurado' : 'Sin token'}</span>
            </div>
          </div>
        </div>
      )}

      {tab === 'network' && (
        <div className="space-y-4 bg-slate-900 border border-slate-800 rounded-lg p-4">
          <div>
            <label className="text-xs text-slate-400 font-medium block mb-1">
              Subred por defecto (vacio = auto-detectar)
            </label>
            <input className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm font-mono text-slate-200"
              placeholder="192.168.1.0/24" value={subnet}
              onChange={e => setSubnet(e.target.value)} />
            <p className="text-[11px] text-slate-500 mt-1">Vacio = detecta la red de tu telefono automaticamente.</p>
          </div>
          <div>
            <label className="text-xs text-slate-400 font-medium block mb-1">
              Puertos a escanear (coma-separados)
            </label>
            <input className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm font-mono text-slate-200"
              placeholder="80,443,22,554,8080,8000,23,21,445,37777,88"
              value={scanPorts} onChange={e => setScanPorts(e.target.value)} />
            <p className="text-[11px] text-slate-500 mt-1">554=RTSP camaras, 80/443/8080=HTTP/router, 37777=Dahua DVR, 23=Telnet.</p>
          </div>
          <div>
            <label className="text-xs text-slate-400 font-medium block mb-1">Timeout por puerto (segundos)</label>
            <input type="number" step="0.1" min="0.1" max="5"
              className="w-24 bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200"
              value={scanTimeout} onChange={e => setScanTimeout(parseFloat(e.target.value) || 0.5)} />
            <p className="text-[11px] text-slate-500 mt-1">0.5s recomendado. Mas bajo = mas rapido pero puede perder hosts lentos.</p>
          </div>
          <button onClick={saveNetwork} disabled={saving}
            className="px-4 py-2 bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 text-white text-sm rounded-lg flex items-center gap-1.5">
            {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />} Guardar
          </button>
        </div>
      )}

      {tab === 'apikeys' && (
        <div className="space-y-3">
          {[
            { key: 'shodan_api_key', label: 'Shodan API Key', service: 'shodan', hint: 'Gratuita en shodan.io — IPs publicas de internet' },
            { key: 'virustotal_api_key', label: 'VirusTotal API Key', service: 'virustotal', hint: 'Gratuita en virustotal.com — reputation de IPs' },
            { key: 'abuseipdb_key', label: 'AbuseIPDB Key', service: 'abuseipdb', hint: 'Gratuita en abuseipdb.com — IPs maliciosas' },
            { key: 'github_token', label: 'GitHub Token', service: 'github', hint: 'Para OSINT de usuarios/repos' },
          ].map(({ key, label, service, hint }) => (
            <div key={key} className="bg-slate-900 border border-slate-800 rounded-lg p-4 space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-sm font-medium text-slate-200 flex items-center gap-1.5">
                  <Shield size={14} className="text-slate-400" /> {label}
                </label>
                {testResult[service] && (
                  <span className={`text-xs flex items-center gap-1 ${testResult[service].ok ? 'text-green-400' : 'text-red-400'}`}>
                    {testResult[service].ok ? <CheckCircle2 size={12} /> : <XCircle size={12} />}
                    {testResult[service].info}
                  </span>
                )}
              </div>
              <div className="flex gap-2">
                <div className="flex-1 relative">
                  <input
                    type={showKeys[key] ? 'text' : 'password'}
                    className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 pr-10 text-sm font-mono text-slate-200"
                    placeholder={keys[key as keyof typeof keys]?.includes('••••') ? 'Ya configurada (escribe nueva para reemplazar)' : 'Pega tu API key'}
                    value={keys[key as keyof typeof keys]?.includes('••••') ? '' : keys[key as keyof typeof keys] || ''}
                    onChange={e => setKeys(prev => ({ ...prev, [key]: e.target.value }))}
                  />
                  <button onClick={() => setShowKeys(prev => ({ ...prev, [key]: !prev[key] }))}
                    className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300">
                    {showKeys[key] ? <EyeOff size={14} /> : <Eye size={14} />}
                  </button>
                </div>
                <button onClick={() => testKey(service, keys[key as keyof typeof keys] || '')}
                  disabled={testing === service}
                  className="px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-sm rounded-lg flex items-center gap-1 shrink-0">
                  {testing === service ? <Loader2 size={14} className="animate-spin" /> : <Zap size={14} />} Test
                </button>
                <button onClick={() => saveKey(key, keys[key as keyof typeof keys] || '')}
                  disabled={saving}
                  className="px-3 py-2 bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 text-white text-sm rounded-lg flex items-center gap-1 shrink-0">
                  <Save size={14} />
                </button>
              </div>
              <p className="text-[11px] text-slate-500">{hint}</p>
            </div>
          ))}
        </div>
      )}

      {tab === 'system' && ops && (
        <div className="space-y-3 bg-slate-900 border border-slate-800 rounded-lg p-4">
          <div className="flex justify-between text-sm">
            <span className="text-slate-400">PID backend</span>
            <span className="font-mono text-slate-200">{ops.backend_pid}</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-slate-400">Puerto backend</span>
            <span className="font-mono text-slate-200">{ops.backend_port}</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-slate-400">nmap</span>
            <span className={`font-mono ${ops.has_nmap ? 'text-green-400' : 'text-red-400'}`}>
              {ops.has_nmap ? 'Disponible' : 'No (pkg install nmap)'}
            </span>
          </div>
          <div className="border-t border-slate-800 pt-3">
            <p className="text-xs text-slate-400">Sin nmap, el sistema usa TCP connect scan como fallback (sin root).</p>
          </div>
        </div>
      )}
    </div>
  );
}
