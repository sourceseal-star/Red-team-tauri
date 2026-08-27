/**
 * SEAL Panel - SEAL SUPER PACK
 * Escaneo, ataque, fingerprinting y orquestación de dispositivos de red.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { sealApi } from '../api/sealApi';

type Tab = 'devices' | 'scan' | 'alerts' | 'hikvision' | 'onvif' | 'stats' | 'integrated';

export default function SealPanel() {
  const [tab, setTab] = useState<Tab>('devices');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [network, setNetwork] = useState('192.168.1.0/24');
  const [targetIp, setTargetIp] = useState('');
  const [devices, setDevices] = useState<any[]>([]);
  const [scanResults, setScanResults] = useState<any>(null);
  const [alerts, setAlerts] = useState<any[]>([]);
  const [status, setStatus] = useState<any>(null);
  const [stats, setStats] = useState<any>(null);
  const [hikvisionResults, setHikvisionResults] = useState<any>(null);
  const [onvifResults, setOnvifResults] = useState<any>(null);
  const [integratedResults, setIntegratedResults] = useState<any>(null);
  const [showJson, setShowJson] = useState(false);

  const wrap = async (fn: () => Promise<any>) => {
    setLoading(true); setError(null);
    try { return await fn(); }
    catch (e: any) { setError(e.message || String(e)); return null; }
    finally { setLoading(false); }
  };

  const loadDevices = useCallback(async () => {
    const r = await wrap(() => sealApi.getDevices());
    if (r?.devices) setDevices(r.devices);
  }, []);

  const loadAlerts = useCallback(async () => {
    const r = await wrap(() => sealApi.getAlerts());
    if (r?.alerts) setAlerts(r.alerts);
  }, []);

  const loadStatus = useCallback(async () => {
    const r = await wrap(() => sealApi.getStatus());
    if (r?.status) setStatus(r.status);
  }, []);

  const loadStats = useCallback(async () => {
    const r = await wrap(() => sealApi.getStats());
    if (r) setStats(r);
  }, []);

  useEffect(() => {
    loadStatus();
    if (tab === 'devices') loadDevices();
    if (tab === 'alerts') loadAlerts();
    if (tab === 'stats') loadStats();
  }, [tab]);

  const doScan = async () => setScanResults(await wrap(() => sealApi.scanNetwork(network)));
  const doQuickScan = async () => setScanResults(await wrap(() => sealApi.quickScan(network)));
  const doHikvisionScan = async () => setHikvisionResults(await wrap(() => sealApi.scanHikvision(network)));
  const doHikvisionAttack = async () => {
    if (!targetIp) { setError('Ingresa una IP'); return; }
    setHikvisionResults(await wrap(() => sealApi.attackHikvision(targetIp)));
  };
  const doOnvifScan = async () => setOnvifResults(await wrap(() => sealApi.scanOnvif(network)));
  const doIntegratedScan = async () => setIntegratedResults(await wrap(() => sealApi.integratedScan(network)));
  const doIntegratedAttack = async () => {
    if (!targetIp) { setError('Ingresa una IP'); return; }
    setIntegratedResults(await wrap(() => sealApi.integratedAttack(targetIp)));
  };
  const resolveAlert = async (id: number) => { await wrap(() => sealApi.resolveAlert(id)); loadAlerts(); };

  const riskColor = (risk: string) => ({
    low: '#22c55e', medium: '#eab308', high: '#f97316', critical: '#ef4444'
  } as Record<string, string>)[risk] || '#64748b';

  const tabs: { id: Tab; label: string; icon: string }[] = [
    { id: 'devices', label: 'Devices', icon: '🖥' },
    { id: 'scan', label: 'Scan', icon: '🔍' },
    { id: 'alerts', label: 'Alerts', icon: '⚠' },
    { id: 'hikvision', label: 'Hikvision', icon: '📷' },
    { id: 'onvif', label: 'ONVIF', icon: '📹' },
    { id: 'stats', label: 'Stats', icon: '📊' },
    { id: 'integrated', label: 'ARTO+SEAL', icon: '🔗' },
  ];

  const btn: React.CSSProperties = { padding: '8px 16px', borderRadius: '6px', backgroundColor: '#334155', color: '#cbd5e1', border: 'none', cursor: 'pointer', fontSize: '14px' };
  const btnP: React.CSSProperties = { ...btn, backgroundColor: '#0ea5e9', color: '#fff', fontWeight: 'bold' };
  const inp: React.CSSProperties = { padding: '8px 12px', borderRadius: '6px', backgroundColor: '#0f172a', border: '1px solid #334155', color: '#e2e8f0', fontSize: '14px', flex: 1, minWidth: '200px' };
  const th: React.CSSProperties = { textAlign: 'left', padding: '10px', color: '#94a3b8', borderBottom: '2px solid #334155', fontSize: '12px', textTransform: 'uppercase' };
  const td: React.CSSProperties = { padding: '10px', color: '#e2e8f0', fontSize: '13px' };

  return (
    <div style={{ fontFamily: 'Segoe UI, sans-serif', maxWidth: '1400px', margin: '0 auto', padding: '20px', backgroundColor: '#0f172a', borderRadius: '10px', color: '#e2e8f0', minHeight: '80vh' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', paddingBottom: '15px', borderBottom: '1px solid #334155' }}>
        <div>
          <h1 style={{ fontSize: '28px', fontWeight: 'bold', color: '#fff', margin: 0 }}>🛡 SEAL SUPER PACK</h1>
          <p style={{ fontSize: '14px', color: '#94a3b8', marginTop: '5px' }}>Escaneo · Ataque · Fingerprinting · Orquestación</p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          {status ? (
            <span style={{ padding: '8px 16px', borderRadius: '20px', backgroundColor: '#1e293b', fontSize: '14px' }}>
              <span style={{ color: status.running ? '#22c55e' : '#64748b' }}>●</span> {status.running ? 'Activo' : 'Inactivo'}
            </span>
          ) : (
            <span style={{ padding: '8px 16px', borderRadius: '20px', backgroundColor: '#1e293b', fontSize: '14px', color: '#64748b' }}>● Sin conexión</span>
          )}
          <button onClick={() => setShowJson(!showJson)} style={{ ...btn, fontSize: '13px' }}>{showJson ? 'Hide' : 'Show'} JSON</button>
        </div>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: '4px', marginBottom: '20px', flexWrap: 'wrap' }}>
        {tabs.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)} style={{
            padding: '10px 18px', borderRadius: '8px 8px 0 0', border: 'none', cursor: 'pointer', fontSize: '14px',
            fontWeight: tab === t.id ? 'bold' : 'normal', backgroundColor: tab === t.id ? '#1e293b' : 'transparent',
            color: tab === t.id ? '#38bdf8' : '#64748b', borderBottom: tab === t.id ? '2px solid #38bdf8' : '2px solid transparent'
          }}>{t.icon} {t.label}</button>
        ))}
      </div>

      {/* Error */}
      {error && <div style={{ padding: '12px 16px', backgroundColor: '#7f1d1d', borderRadius: '8px', marginBottom: '15px', color: '#fca5a5', fontSize: '14px' }}>⚠ {error}</div>}

      {/* Loading */}
      {loading && <div style={{ textAlign: 'center', padding: '40px', color: '#64748b' }}><div style={{ fontSize: '32px', display: 'inline-block' }}>⟳</div><p style={{ marginTop: '10px' }}>Procesando...</p></div>}

      {/* Content */}
      {!loading && (
        <div style={{ backgroundColor: '#1e293b', borderRadius: '8px', padding: '20px' }}>
          {/* DEVICES */}
          {tab === 'devices' && (
            <>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '15px' }}>
                <h2 style={{ color: '#38bdf8', margin: 0 }}>Dispositivos Detectados ({devices.length})</h2>
                <button onClick={loadDevices} style={btn}>↻ Refresh</button>
              </div>
              {devices.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '40px', color: '#64748b' }}>No hay dispositivos. Ejecuta un scan primero.</div>
              ) : (
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                  <thead><tr>{['IP', 'Vendor', 'Tipo', 'Modelo', 'Riesgo', 'Puertos', 'Servicios'].map(h => <th key={h} style={th}>{h}</th>)}</tr></thead>
                  <tbody>
                    {devices.map((d, i) => (
                      <tr key={i} style={{ borderBottom: '1px solid #334155' }}>
                        <td style={td}>{d.ip}</td>
                        <td style={td}>{d.vendor || 'Unknown'}</td>
                        <td style={td}>{d.type || 'Unknown'}</td>
                        <td style={td}>{d.model || '-'}</td>
                        <td style={{ ...td, color: riskColor(d.risk) }}>{d.risk || 'low'}</td>
                        <td style={td}>{(d.ports || []).join(', ') || '-'}</td>
                        <td style={td}>{(d.services || []).join(', ') || '-'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
              {showJson && <pre style={{ marginTop: '15px', padding: '15px', backgroundColor: '#0f172a', borderRadius: '8px', color: '#94a3b8', fontSize: '12px', overflow: 'auto', maxHeight: '400px' }}>{JSON.stringify(devices, null, 2)}</pre>}
            </>
          )}

          {/* SCAN */}
          {tab === 'scan' && (
            <>
              <h2 style={{ color: '#38bdf8', marginTop: 0 }}>Escaneo de Red</h2>
              <div style={{ display: 'flex', gap: '10px', marginBottom: '15px', flexWrap: 'wrap' }}>
                <input value={network} onChange={e => setNetwork(e.target.value)} placeholder="192.168.1.0/24" style={inp} />
                <button onClick={doScan} style={btnP}>🔍 Scan Completo</button>
                <button onClick={doQuickScan} style={btn}>⚡ Quick Scan</button>
              </div>
              {scanResults && (
                <>
                  {scanResults.success ? (
                    <div>
                      <div style={{ display: 'flex', gap: '20px', marginBottom: '15px', flexWrap: 'wrap' }}>
                        <div style={{ padding: '12px 20px', backgroundColor: '#0f172a', borderRadius: '8px', minWidth: '120px' }}>
                          <div style={{ fontSize: '12px', color: '#64748b', textTransform: 'uppercase' }}>Red</div>
                          <div style={{ fontSize: '22px', fontWeight: 'bold', color: '#38bdf8' }}>{scanResults.network}</div>
                        </div>
                        <div style={{ padding: '12px 20px', backgroundColor: '#0f172a', borderRadius: '8px', minWidth: '120px' }}>
                          <div style={{ fontSize: '12px', color: '#64748b', textTransform: 'uppercase' }}>IPs Escaneadas</div>
                          <div style={{ fontSize: '22px', fontWeight: 'bold', color: '#38bdf8' }}>{scanResults.scanned || (scanResults.active_ips || []).length || 0}</div>
                        </div>
                        <div style={{ padding: '12px 20px', backgroundColor: '#0f172a', borderRadius: '8px', minWidth: '120px' }}>
                          <div style={{ fontSize: '12px', color: '#64748b', textTransform: 'uppercase' }}>Targets</div>
                          <div style={{ fontSize: '22px', fontWeight: 'bold', color: '#38bdf8' }}>{(scanResults.targets || []).length}</div>
                        </div>
                      </div>
                      {scanResults.targets && scanResults.targets.length > 0 && (
                        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                          <thead><tr>{['IP', 'Puertos', 'Servicios', 'Vendor', 'Riesgo'].map(h => <th key={h} style={th}>{h}</th>)}</tr></thead>
                          <tbody>
                            {scanResults.targets.map((t: any, i: number) => (
                              <tr key={i} style={{ borderBottom: '1px solid #334155' }}>
                                <td style={td}>{t.ip}</td>
                                <td style={td}>{(t.services || []).map((s: any) => s.port).join(', ') || '-'}</td>
                                <td style={td}>{(t.services || []).map((s: any) => s.service).join(', ') || '-'}</td>
                                <td style={td}>{t.fingerprint?.vendor || 'Unknown'}</td>
                                <td style={{ ...td, color: riskColor(t.fingerprint?.risk || 'low') }}>{t.fingerprint?.risk || 'low'}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      )}
                      {scanResults.active_ips && (
                        <div style={{ marginTop: '15px' }}>
                          <h3 style={{ color: '#94a3b8' }}>IPs Activas</h3>
                          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                            {scanResults.active_ips.map((ip: string, i: number) => (
                              <span key={i} style={{ padding: '4px 10px', backgroundColor: '#334155', borderRadius: '4px', fontSize: '13px', color: '#22c55e' }}>{ip}</span>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  ) : (
                    <div style={{ color: '#fca5a5' }}>Error: {scanResults.error}</div>
                  )}
                  {showJson && <pre style={{ marginTop: '15px', padding: '15px', backgroundColor: '#0f172a', borderRadius: '8px', color: '#94a3b8', fontSize: '12px', overflow: 'auto', maxHeight: '400px' }}>{JSON.stringify(scanResults, null, 2)}</pre>}
                </>
              )}
            </>
          )}

          {/* ALERTS */}
          {tab === 'alerts' && (
            <>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '15px' }}>
                <h2 style={{ color: '#38bdf8', margin: 0 }}>Alertas ({alerts.length})</h2>
                <button onClick={loadAlerts} style={btn}>↻ Refresh</button>
              </div>
              {alerts.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '40px', color: '#64748b' }}>No hay alertas registradas.</div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  {alerts.map((a, i) => (
                    <div key={i} style={{ padding: '12px 16px', backgroundColor: '#0f172a', borderRadius: '8px', borderLeft: `4px solid ${riskColor(a.severity)}` }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <div>
                          <span style={{ color: riskColor(a.severity), fontWeight: 'bold', fontSize: '13px' }}>{(a.severity || '').toUpperCase()}</span>
                          <span style={{ color: '#e2e8f0', marginLeft: '10px' }}>{a.message || a.title}</span>
                        </div>
                        {!a.resolved && <button onClick={() => resolveAlert(a.id)} style={{ ...btn, fontSize: '12px', padding: '4px 10px' }}>✓ Resolver</button>}
                      </div>
                      {a.timestamp && <span style={{ color: '#64748b', fontSize: '12px' }}>{a.timestamp}</span>}
                    </div>
                  ))}
                </div>
              )}
              {showJson && <pre style={{ marginTop: '15px', padding: '15px', backgroundColor: '#0f172a', borderRadius: '8px', color: '#94a3b8', fontSize: '12px', overflow: 'auto', maxHeight: '400px' }}>{JSON.stringify(alerts, null, 2)}</pre>}
            </>
          )}

          {/* HIKVISION */}
          {tab === 'hikvision' && (
            <>
              <h2 style={{ color: '#38bdf8', marginTop: 0 }}>Hikvision Scanner</h2>
              <div style={{ display: 'flex', gap: '10px', marginBottom: '15px', flexWrap: 'wrap' }}>
                <input value={network} onChange={e => setNetwork(e.target.value)} placeholder="192.168.1.0/24" style={inp} />
                <button onClick={doHikvisionScan} style={btnP}>📷 Scan Hikvision</button>
              </div>
              <div style={{ display: 'flex', gap: '10px', marginBottom: '15px', flexWrap: 'wrap' }}>
                <input value={targetIp} onChange={e => setTargetIp(e.target.value)} placeholder="192.168.1.7" style={inp} />
                <button onClick={doHikvisionAttack} style={{ ...btnP, backgroundColor: '#dc2626' }}>⚔ Attack</button>
              </div>
              {hikvisionResults && (
                <>
                  {hikvisionResults.success ? (
                    <div style={{ padding: '15px', backgroundColor: '#0f172a', borderRadius: '8px' }}>
                      <pre style={{ color: '#e2e8f0', fontSize: '13px', overflow: 'auto', whiteSpace: 'pre-wrap' }}>{JSON.stringify(hikvisionResults.result || hikvisionResults, null, 2)}</pre>
                    </div>
                  ) : (
                    <div style={{ color: '#fca5a5' }}>Error: {hikvisionResults.error}</div>
                  )}
                  {showJson && <pre style={{ marginTop: '15px', padding: '15px', backgroundColor: '#0f172a', borderRadius: '8px', color: '#94a3b8', fontSize: '12px', overflow: 'auto', maxHeight: '400px' }}>{JSON.stringify(hikvisionResults, null, 2)}</pre>}
                </>
              )}
            </>
          )}

          {/* ONVIF */}
          {tab === 'onvif' && (
            <>
              <h2 style={{ color: '#38bdf8', marginTop: 0 }}>ONVIF Scanner</h2>
              <div style={{ display: 'flex', gap: '10px', marginBottom: '15px', flexWrap: 'wrap' }}>
                <input value={network} onChange={e => setNetwork(e.target.value)} placeholder="192.168.1.0/24" style={inp} />
                <button onClick={doOnvifScan} style={btnP}>📹 Scan ONVIF</button>
              </div>
              {onvifResults && (
                <>
                  {onvifResults.success ? (
                    <div style={{ padding: '15px', backgroundColor: '#0f172a', borderRadius: '8px' }}>
                      <pre style={{ color: '#e2e8f0', fontSize: '13px', overflow: 'auto', whiteSpace: 'pre-wrap' }}>{JSON.stringify(onvifResults.result || onvifResults, null, 2)}</pre>
                    </div>
                  ) : (
                    <div style={{ color: '#fca5a5' }}>Error: {onvifResults.error}</div>
                  )}
                  {showJson && <pre style={{ marginTop: '15px', padding: '15px', backgroundColor: '#0f172a', borderRadius: '8px', color: '#94a3b8', fontSize: '12px', overflow: 'auto', maxHeight: '400px' }}>{JSON.stringify(onvifResults, null, 2)}</pre>}
                </>
              )}
            </>
          )}

          {/* STATS */}
          {tab === 'stats' && (
            <>
              <h2 style={{ color: '#38bdf8', marginTop: 0 }}>Estadísticas</h2>
              {!stats ? (
                <div style={{ textAlign: 'center', padding: '40px', color: '#64748b' }}>Cargando estadísticas...</div>
              ) : (
                <div>
                  {stats.stats && (
                    <div style={{ display: 'flex', gap: '15px', flexWrap: 'wrap', marginBottom: '20px' }}>
                      <div style={{ padding: '12px 20px', backgroundColor: '#0f172a', borderRadius: '8px', minWidth: '120px' }}>
                        <div style={{ fontSize: '12px', color: '#64748b', textTransform: 'uppercase' }}>Vendors</div>
                        <div style={{ fontSize: '22px', fontWeight: 'bold', color: '#38bdf8' }}>{Object.keys(stats.stats.vendors || {}).length}</div>
                      </div>
                      <div style={{ padding: '12px 20px', backgroundColor: '#0f172a', borderRadius: '8px', minWidth: '120px' }}>
                        <div style={{ fontSize: '12px', color: '#64748b', textTransform: 'uppercase' }}>Tipos</div>
                        <div style={{ fontSize: '22px', fontWeight: 'bold', color: '#38bdf8' }}>{Object.keys(stats.stats.types || {}).length}</div>
                      </div>
                      <div style={{ padding: '12px 20px', backgroundColor: '#0f172a', borderRadius: '8px', minWidth: '120px' }}>
                        <div style={{ fontSize: '12px', color: '#64748b', textTransform: 'uppercase' }}>Criticos</div>
                        <div style={{ fontSize: '22px', fontWeight: 'bold', color: '#ef4444' }}>{stats.stats.risks?.critical || 0}</div>
                      </div>
                      <div style={{ padding: '12px 20px', backgroundColor: '#0f172a', borderRadius: '8px', minWidth: '120px' }}>
                        <div style={{ fontSize: '12px', color: '#64748b', textTransform: 'uppercase' }}>Altos</div>
                        <div style={{ fontSize: '22px', fontWeight: 'bold', color: '#f97316' }}>{stats.stats.risks?.high || 0}</div>
                      </div>
                    </div>
                  )}
                  {stats.stats?.vendors && (
                    <div style={{ marginBottom: '20px' }}>
                      <h3 style={{ color: '#94a3b8' }}>Por Vendor</h3>
                      {Object.entries(stats.stats.vendors).map(([vendor, count]: any) => (
                        <div key={vendor} style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid #334155' }}>
                          <span style={{ color: '#e2e8f0' }}>{vendor}</span>
                          <span style={{ color: '#38bdf8' }}>{count}</span>
                        </div>
                      ))}
                    </div>
                  )}
                  {stats.stats?.types && (
                    <div>
                      <h3 style={{ color: '#94a3b8' }}>Por Tipo</h3>
                      {Object.entries(stats.stats.types).map(([type, count]: any) => (
                        <div key={type} style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid #334155' }}>
                          <span style={{ color: '#e2e8f0' }}>{type}</span>
                          <span style={{ color: '#38bdf8' }}>{count}</span>
                        </div>
                      ))}
                    </div>
                  )}
                  {showJson && <pre style={{ marginTop: '15px', padding: '15px', backgroundColor: '#0f172a', borderRadius: '8px', color: '#94a3b8', fontSize: '12px', overflow: 'auto', maxHeight: '400px' }}>{JSON.stringify(stats, null, 2)}</pre>}
                </div>
              )}
            </>
          )}

          {/* INTEGRATED */}
          {tab === 'integrated' && (
            <>
              <h2 style={{ color: '#38bdf8', marginTop: 0 }}>🔗 Integración ARTO + SEAL</h2>
              <p style={{ color: '#94a3b8', marginBottom: '15px' }}>Escaneo integrado: SEAL detecta dispositivos y ARTO analiza amenazas.</p>
              <div style={{ display: 'flex', gap: '10px', marginBottom: '15px', flexWrap: 'wrap' }}>
                <input value={network} onChange={e => setNetwork(e.target.value)} placeholder="192.168.1.0/24" style={inp} />
                <button onClick={doIntegratedScan} style={btnP}>🔗 Scan Integrado</button>
              </div>
              <div style={{ display: 'flex', gap: '10px', marginBottom: '15px', flexWrap: 'wrap' }}>
                <input value={targetIp} onChange={e => setTargetIp(e.target.value)} placeholder="192.168.1.7" style={inp} />
                <button onClick={doIntegratedAttack} style={{ ...btnP, backgroundColor: '#7c3aed' }}>🧠 Attack + ARTO</button>
              </div>
              {integratedResults && (
                <>
                  {integratedResults.success ? (
                    <div style={{ padding: '15px', backgroundColor: '#0f172a', borderRadius: '8px' }}>
                      <div style={{ display: 'flex', gap: '20px', marginBottom: '15px', flexWrap: 'wrap' }}>
                        <div style={{ padding: '12px 20px', backgroundColor: '#1e293b', borderRadius: '8px', minWidth: '120px' }}>
                          <div style={{ fontSize: '12px', color: '#64748b', textTransform: 'uppercase' }}>Red</div>
                          <div style={{ fontSize: '22px', fontWeight: 'bold', color: '#38bdf8' }}>{integratedResults.network}</div>
                        </div>
                        <div style={{ padding: '12px 20px', backgroundColor: '#1e293b', borderRadius: '8px', minWidth: '120px' }}>
                          <div style={{ fontSize: '12px', color: '#64748b', textTransform: 'uppercase' }}>IPs</div>
                          <div style={{ fontSize: '22px', fontWeight: 'bold', color: '#38bdf8' }}>{integratedResults.scanned || 0}</div>
                        </div>
                        <div style={{ padding: '12px 20px', backgroundColor: '#1e293b', borderRadius: '8px', minWidth: '120px' }}>
                          <div style={{ fontSize: '12px', color: '#64748b', textTransform: 'uppercase' }}>Targets</div>
                          <div style={{ fontSize: '22px', fontWeight: 'bold', color: '#38bdf8' }}>{(integratedResults.targets || []).length}</div>
                        </div>
                      </div>
                      {integratedResults.targets && integratedResults.targets.length > 0 && (
                        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                          <thead><tr>{['IP', 'Puertos', 'Servicios', 'Vendor'].map(h => <th key={h} style={th}>{h}</th>)}</tr></thead>
                          <tbody>
                            {integratedResults.targets.map((t: any, i: number) => (
                              <tr key={i} style={{ borderBottom: '1px solid #334155' }}>
                                <td style={td}>{t.ip}</td>
                                <td style={td}>{(t.services || []).map((s: any) => s.port).join(', ') || '-'}</td>
                                <td style={td}>{(t.services || []).map((s: any) => s.service).join(', ') || '-'}</td>
                                <td style={td}>{t.fingerprint?.vendor || 'Unknown'}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      )}
                      {integratedResults.result && (
                        <div style={{ marginTop: '15px' }}>
                          <h3 style={{ color: '#a78bfa' }}>Resultado ARTO</h3>
                          <pre style={{ color: '#e2e8f0', fontSize: '13px', overflow: 'auto', whiteSpace: 'pre-wrap' }}>{JSON.stringify(integratedResults.result, null, 2)}</pre>
                        </div>
                      )}
                    </div>
                  ) : (
                    <div style={{ color: '#fca5a5' }}>Error: {integratedResults.error}</div>
                  )}
                  {showJson && <pre style={{ marginTop: '15px', padding: '15px', backgroundColor: '#0f172a', borderRadius: '8px', color: '#94a3b8', fontSize: '12px', overflow: 'auto', maxHeight: '400px' }}>{JSON.stringify(integratedResults, null, 2)}</pre>}
                </>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
