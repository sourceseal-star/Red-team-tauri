import { useState, useEffect } from 'react';
import { Eye, FileText, Activity, Fingerprint, AlertTriangle, Clock } from 'lucide-react';
import { getApiKey } from '../lib/api';

function bmHeaders(): Record<string, string> {
  const key = getApiKey()
  return key ? { 'Authorization': `Bearer ${key}` } : {}
}

type BMTab = 'canary' | 'ghost' | 'chaos';

export default function BlackMirrorPanel() {
  const [activeTab, setActiveTab] = useState<BMTab>('canary');
  const [canaries, setCanaries] = useState<any[]>([]);
  const [ghostHost, setGhostHost] = useState('');
  const [ghostProfile, setGhostProfile] = useState<any>(null);
  const [ghostWindow, setGhostWindow] = useState<any>(null);
  const [chaosPort, setChaosPort] = useState('');
  const [chaosOS, setChaosOS] = useState('Windows Server 2019');
  const [recipient, setRecipient] = useState('');
  const [docTitle, setDocTitle] = useState('Informe Confidencial Q3');
  const [docType, setDocType] = useState<'pdf' | 'html'>('html');
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<string | null>(null);

  const forgeCanary = async () => {
    if (!recipient.trim()) return;
    setLoading(true);
    setStatus(null);
    try {
      const params = new URLSearchParams({
        recipient, doc_type: docType, title: docTitle,
        content: 'Documento altamente confidencial. Distribucion restringida.'
      });
      const res = await fetch(`/api/blackmirror/canary/forge?${params}`, { method: 'POST', headers: bmHeaders() });
      if (!res.ok) { const e = await res.json().catch(() => ({})); throw new Error(e.error || `HTTP ${res.status}`); }
      const data = await res.json();
      setStatus(`Canary forjado: ${data.recipient} | Token: ${data.token?.slice(0, 16)}...`);
      loadCanaries();
    } catch (e: any) {
      setStatus(`Error: ${e.message}`);
    } finally {
      setLoading(false);
      setTimeout(() => setStatus(null), 8000);
    }
  };

  const loadCanaries = async () => {
    try {
      const res = await fetch('/api/blackmirror/canary/status', { headers: bmHeaders() });
      if (!res.ok) return;
      const data = await res.json();
      setCanaries(data.canaries || []);
    } catch {}
  };

  const analyzeGhost = async () => {
    if (!ghostHost.trim()) return;
    setStatus('Analizando patron temporal...');
    try {
      const [profileRes, windowRes] = await Promise.all([
        fetch(`/api/blackmirror/ghostprint/profile/${ghostHost}`, { headers: bmHeaders() }),
        fetch(`/api/blackmirror/ghostprint/window/${ghostHost}`, { headers: bmHeaders() })
      ]);
      if (!profileRes.ok) { const e = await profileRes.json().catch(() => ({})); throw new Error(e.error || `HTTP ${profileRes.status}`); }
      setGhostProfile(await profileRes.json());
      setGhostWindow(await windowRes.json());
      setStatus(null);
    } catch (e: any) {
      setStatus(`Error: ${e.message}`);
    }
  };

  const applyChaos = async () => {
    if (!chaosPort.trim()) return;
    setLoading(true);
    setStatus(null);
    try {
      const res = await fetch(`/api/blackmirror/chaos/apply?real_port=${chaosPort}&fake_os=${encodeURIComponent(chaosOS)}`, { method: 'POST', headers: bmHeaders() });
      if (!res.ok) { const e = await res.json().catch(() => ({})); throw new Error(e.error || `HTTP ${res.status}`); }
      const data = await res.json();
      setStatus(`Chaos aplicado: puerto ${data.real_port} ahora simula ${data.fake_os}`);
    } catch (e: any) {
      setStatus(`Error: ${e.message}`);
    } finally {
      setLoading(false);
      setTimeout(() => setStatus(null), 8000);
    }
  };

  useEffect(() => { loadCanaries(); }, []);

  const days = ['Lun', 'Mar', 'Mie', 'Jue', 'Vie', 'Sab', 'Dom'];

  return (
    <div className="bg-[var(--ss-bg-2)] border border-[var(--ss-border)] rounded-lg p-3 h-full flex flex-col">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-xs uppercase tracking-widest text-purple-400 flex items-center gap-2">
          <Eye size={14} /> Black Mirror
        </h3>
        <div className="flex gap-1 bg-[var(--ss-bg-3)] rounded p-0.5">
          {(['canary', 'ghost', 'chaos'] as BMTab[]).map(tab => (
            <button key={tab} onClick={() => setActiveTab(tab)}
              className={`px-2 py-0.5 text-[9px] rounded font-mono transition ${
                activeTab === tab ? 'bg-purple-500/30 text-purple-200 border border-purple-500/40' : 'text-gray-500 hover:text-gray-300 border border-transparent'
              }`}>
              {tab === 'canary' ? 'Canary' : tab === 'ghost' ? 'Ghost' : 'Chaos'}
            </button>
          ))}
        </div>
      </div>

      {status && (
        <div className="mb-2 text-[10px] text-purple-300 font-mono bg-purple-500/10 border border-purple-500/20 rounded p-1.5">
          {status}
        </div>
      )}

      <div className="flex-1 overflow-y-auto min-h-0">
        {/* ─── CANARY FORGE ─── */}
        {activeTab === 'canary' && (
          <div className="space-y-3">
            <div className="bg-purple-500/5 border border-purple-500/15 rounded p-2">
              <p className="text-[10px] text-purple-300/70 mb-2 font-mono">
                Documentos con tokens invisibles. Si se filtran, sabes quien fue.
              </p>
              <div className="grid grid-cols-2 gap-1.5">
                <input value={recipient} onChange={e => setRecipient(e.target.value)}
                  placeholder="Destinatario (ej: juan.perez)"
                  className="bg-[var(--ss-bg-3)] border border-[var(--ss-border)] rounded px-2 py-1.5 text-[10px] text-gray-200 font-mono focus:border-purple-500 focus:outline-none" />
                <input value={docTitle} onChange={e => setDocTitle(e.target.value)}
                  placeholder="Titulo del documento"
                  className="bg-[var(--ss-bg-3)] border border-[var(--ss-border)] rounded px-2 py-1.5 text-[10px] text-gray-200 font-mono focus:border-purple-500 focus:outline-none" />
              </div>
              <div className="flex gap-1.5 mt-1.5">
                <button onClick={() => setDocType('html')}
                  className={`flex-1 px-2 py-1 text-[9px] rounded font-mono border transition ${docType === 'html' ? 'bg-purple-500/20 border-purple-500/40 text-purple-200' : 'border-[var(--ss-border)] text-gray-500'}`}>
                  HTML (web bug)
                </button>
                <button onClick={() => setDocType('pdf')}
                  className={`flex-1 px-2 py-1 text-[9px] rounded font-mono border transition ${docType === 'pdf' ? 'bg-purple-500/20 border-purple-500/40 text-purple-200' : 'border-[var(--ss-border)] text-gray-500'}`}>
                  PDF (watermark)
                </button>
              </div>
              <button onClick={forgeCanary} disabled={loading || !recipient.trim()}
                className="mt-1.5 w-full py-1.5 bg-purple-600/30 border border-purple-500/30 hover:bg-purple-600/50 text-purple-200 text-[10px] rounded font-mono flex items-center justify-center gap-1 disabled:opacity-50 transition">
                <FileText size={11} /> {loading ? 'Forjando...' : 'Forjar Documento Canary'}
              </button>
            </div>

            <div className="space-y-1">
              {canaries.map((c, i) => (
                <div key={i} className={`p-2 rounded border ${
                  c.compromised
                    ? 'bg-red-500/10 border-red-500/40'
                    : 'bg-[var(--ss-bg-3)] border-[var(--ss-border)]'
                }`}>
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-[10px] text-gray-300">{c.recipient}</span>
                    <span className={`text-[8px] px-1.5 py-0.5 rounded font-mono ${
                      c.compromised ? 'bg-red-500/30 text-red-300' : 'bg-green-500/20 text-green-300'
                    }`}>{c.compromised ? 'COMPROMETIDO' : 'SEGURO'}</span>
                  </div>
                  {c.compromised && (
                    <div className="mt-1 text-[9px] font-mono space-y-0.5">
                      <div className="text-red-400">IP: {c.trigger_ip}</div>
                      <div className="text-gray-500 truncate">UA: {c.trigger_ua}</div>
                      <div className="text-gray-500">{c.triggered ? new Date(c.triggered).toLocaleString() : ''}</div>
                    </div>
                  )}
                  <div className="mt-0.5 text-[8px] text-gray-600 font-mono">{c.token?.slice(0, 24)}...</div>
                </div>
              ))}
              {canaries.length === 0 && (
                <div className="text-center text-gray-600 text-[10px] py-3 font-mono">No hay canaries activos.</div>
              )}
            </div>
          </div>
        )}

        {/* ─── GHOSTPRINT ─── */}
        {activeTab === 'ghost' && (
          <div className="space-y-3">
            <div className="bg-[var(--ss-bg-3)] border border-[var(--ss-border)] rounded p-2">
              <p className="text-[10px] text-gray-400 mb-2 font-mono">
                Perfil temporal de hosts. Predice cuando operar y detecta anomalias.
              </p>
              <div className="flex gap-1.5">
                <input value={ghostHost} onChange={e => setGhostHost(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && analyzeGhost()}
                  placeholder="IP o Host (ej: 192.168.1.10)"
                  className="flex-1 bg-[var(--ss-bg-3)] border border-[var(--ss-border)] rounded px-2 py-1.5 text-[10px] text-gray-200 font-mono focus:border-purple-500 focus:outline-none" />
                <button onClick={analyzeGhost}
                  className="px-2 py-1.5 bg-cyan-600/30 border border-cyan-500/30 hover:bg-cyan-600/50 text-cyan-200 text-[10px] rounded font-mono flex items-center gap-1">
                  <Activity size={10} /> Analizar
                </button>
              </div>
            </div>

            {ghostProfile && (
              <div className="space-y-2">
                {ghostProfile.anomaly && (
                  <div className="bg-red-500/10 border border-red-500/40 rounded p-2 flex items-start gap-1.5">
                    <AlertTriangle size={12} className="text-red-400 mt-0.5 shrink-0" />
                    <div>
                      <div className="text-[10px] font-bold text-red-400 font-mono">{ghostProfile.anomaly.type}</div>
                      <div className="text-[9px] text-gray-400">{ghostProfile.anomaly.message}</div>
                    </div>
                  </div>
                )}

                {ghostProfile.profile && ghostProfile.profile !== 'insufficient_data' && (
                  <>
                    <div className="grid grid-cols-7 gap-0.5">
                      {days.map(d => (
                        <div key={d} className="text-center text-[8px] text-gray-500 font-mono">{d}</div>
                      ))}
                      {Array.from({length: 168}, (_, i) => {
                        const dow = Math.floor(i / 24);
                        const hour = i % 24;
                        const key = `${dow}:${hour}`;
                        const prob = ghostProfile.profile[key]?.probability || 0;
                        return (
                          <div key={i}
                            className={`h-2.5 rounded-sm ${
                              prob > 0.3 ? 'bg-purple-500' : prob > 0.1 ? 'bg-purple-800' : 'bg-[var(--ss-bg-3)]'
                            }`}
                            title={`${days[dow]} ${hour}:00 - ${(prob*100).toFixed(0)}%`}
                          />
                        );
                      })}
                    </div>
                    <div className="flex items-center justify-between text-[8px] text-gray-600 font-mono">
                      <span>00:00</span><span>12:00</span><span>23:00</span>
                    </div>
                    <div className="text-[9px] text-gray-500 font-mono">
                      Observaciones: {ghostProfile.total_observations} | Prob. actual: {(ghostProfile.current_hour_probability * 100).toFixed(1)}%
                    </div>
                  </>
                )}

                {ghostProfile.message && (
                  <div className="text-[10px] text-gray-500 font-mono text-center py-2">{ghostProfile.message}</div>
                )}

                {ghostWindow?.optimal_windows && (
                  <div className="bg-green-500/5 border border-green-500/20 rounded p-2">
                    <div className="text-[9px] text-green-400 font-bold mb-1 font-mono flex items-center gap-1">
                      <Clock size={10} /> Ventanas Optimas
                    </div>
                    {ghostWindow.optimal_windows.map((w: any, i: number) => (
                      <div key={i} className="text-[9px] text-gray-400 font-mono">
                        {w.day} @ {w.hour} (actividad: {w.historical_activity})
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* ─── CHAOS FINGERPRINT ─── */}
        {activeTab === 'chaos' && (
          <div className="space-y-3">
            <div className="bg-[var(--ss-bg-3)] border border-[var(--ss-border)] rounded p-2">
              <p className="text-[10px] text-gray-400 mb-2 font-mono">
                Envenena respuestas de escaneo. Tu Linux parecerá Windows IIS.
              </p>
              <input value={chaosPort} onChange={e => setChaosPort(e.target.value)}
                placeholder="Puerto real (ej: 80)"
                className="w-full bg-[var(--ss-bg-3)] border border-[var(--ss-border)] rounded px-2 py-1.5 text-[10px] text-gray-200 font-mono mb-1.5 focus:border-pink-500 focus:outline-none" />
              <select value={chaosOS} onChange={e => setChaosOS(e.target.value)}
                className="w-full bg-[var(--ss-bg-3)] border border-[var(--ss-border)] rounded px-2 py-1.5 text-[10px] text-gray-200 font-mono mb-1.5">
                <option>Windows Server 2019</option>
                <option>Cisco IOS 15.2</option>
                <option>Fortinet FortiOS 7.0</option>
                <option>JunOS 21.2</option>
                <option>Windows XP SP3</option>
              </select>
              <button onClick={applyChaos} disabled={loading || !chaosPort.trim()}
                className="w-full py-1.5 bg-pink-600/30 border border-pink-500/30 hover:bg-pink-600/50 text-pink-200 text-[10px] rounded font-mono flex items-center justify-center gap-1 disabled:opacity-50 transition">
                <Fingerprint size={11} /> {loading ? 'Aplicando...' : 'Aplicar Chaos Rule'}
              </button>
            </div>

            <div className="bg-[var(--ss-bg-3)] rounded p-2 border border-[var(--ss-border)]">
              <div className="text-[9px] text-gray-500 font-mono space-y-0.5">
                <div className="text-gray-400 font-bold mb-1">Efectos del envenenamiento:</div>
                <div>- nmap -O dira que eres {chaosOS}</div>
                <div>- Shodan te clasificara incorrectamente</div>
                <div>- El atacante perdera tiempo con exploits equivocados</div>
                <div>- Censys mostrara datos falsos</div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
