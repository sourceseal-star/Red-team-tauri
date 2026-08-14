import React, { useState, useEffect, useRef } from 'react';
import { Play, Square, RotateCw, Terminal, Activity, Cpu, HardDrive, Wifi, AlertTriangle, CheckCircle, XCircle } from 'lucide-react';

interface Service {
  name: string;
  status: 'running' | 'stopped' | 'error' | 'restarting';
  pid?: number;
  uptime: string;
  cpu: number;
  memory: number;
  port: number;
  lastLog?: string;
}

const MOCK_SERVICES: Service[] = [
  { name: 'dashboard_server', status: 'running', pid: 2847, uptime: '3d 4h', cpu: 12, memory: 128, port: 8000, lastLog: 'GET /health 200 OK' },
  { name: 'websocket_server', status: 'running', pid: 2851, uptime: '3d 4h', cpu: 3, memory: 45, port: 8001, lastLog: 'Client connected: 192.168.1.45' },
  { name: 'scan_worker', status: 'running', pid: 2860, uptime: '2h 15m', cpu: 67, memory: 256, port: 0, lastLog: 'nmap scan completed: 12 hosts found' },
  { name: 'stripe_webhook', status: 'running', pid: 2872, uptime: '3d 4h', cpu: 1, memory: 32, port: 8002, lastLog: 'Webhook received: checkout.session.completed' },
  { name: 'motion_detector', status: 'stopped', uptime: '-', cpu: 0, memory: 0, port: 0, lastLog: 'Process terminated by user' },
  { name: 'canary_listener', status: 'error', pid: 2899, uptime: '15m', cpu: 0, memory: 12, port: 8003, lastLog: 'ERROR: Port 8003 already in use' },
];

export default function ServiceControlPanel() {
  const [services, setServices] = useState<Service[]>(MOCK_SERVICES);
  const [selectedService, setSelectedService] = useState<string | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const [systemStats, setSystemStats] = useState({ cpu: 23, ram: 45, disk: 62, net: 1.2 });
  const logsEndRef = useRef<HTMLDivElement>(null);

  // Simular logs en vivo
  useEffect(() => {
    const interval = setInterval(() => {
      const newLogs = [
        `[${new Date().toISOString().split('T')[1].slice(0,8)}] GET /api/scan/topology 200`,
        `[${new Date().toISOString().split('T')[1].slice(0,8)}] WebSocket broadcast: scan_complete`,
        `[${new Date().toISOString().split('T')[1].slice(0,8)}] Stripe webhook verified`,
        `[${new Date().toISOString().split('T')[1].slice(0,8)}] Memory usage: ${Math.floor(Math.random() * 30 + 20)}%`,
      ];
      setLogs(prev => [...prev.slice(-50), newLogs[Math.floor(Math.random() * newLogs.length)]]);

      // Stats fluctuantes
      setSystemStats(prev => ({
        cpu: Math.min(100, Math.max(5, prev.cpu + (Math.random() - 0.5) * 10)),
        ram: Math.min(100, Math.max(20, prev.ram + (Math.random() - 0.5) * 5)),
        disk: prev.disk,
        net: Math.max(0, prev.net + (Math.random() - 0.5) * 0.5),
      }));
    }, 2000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  const toggleService = async (name: string, action: 'start' | 'stop' | 'restart') => {
    setServices(prev => prev.map(s => {
      if (s.name === name) {
        return { ...s, status: action === 'stop' ? 'stopped' : action === 'restart' ? 'restarting' : 'running' };
      }
      return s;
    }));

    // Simular llamada API
    setTimeout(() => {
      setServices(prev => prev.map(s => {
        if (s.name === name) {
          return { ...s, status: action === 'stop' ? 'stopped' : 'running', lastLog: `Service ${action}ed manually` };
        }
        return s;
      }));
    }, 1500);
  };

  const statusConfig: Record<string, { color: string; icon: any }> = {
    running: { color: 'text-green-400 bg-green-900/20 border-green-800', icon: CheckCircle },
    stopped: { color: 'text-slate-400 bg-slate-800 border-slate-700', icon: XCircle },
    error: { color: 'text-red-400 bg-red-900/20 border-red-800', icon: AlertTriangle },
    restarting: { color: 'text-amber-400 bg-amber-900/20 border-amber-800 animate-pulse', icon: RotateCw },
  };

  return (
    <div className="space-y-4">
      {/* Stats del sistema */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { label: 'CPU', value: systemStats.cpu, icon: Cpu, color: 'text-cyan-400' },
          { label: 'RAM', value: systemStats.ram, icon: Activity, color: 'text-purple-400' },
          { label: 'Disco', value: systemStats.disk, icon: HardDrive, color: 'text-amber-400' },
          { label: 'Red', value: systemStats.net.toFixed(1) + ' MB/s', icon: Wifi, color: 'text-green-400' },
        ].map(stat => {
          const Icon = stat.icon;
          return (
            <div key={stat.label} className="bg-slate-900/60 border border-slate-800 rounded-xl p-3">
              <div className="flex items-center justify-between mb-2">
                <span className="text-[10px] text-slate-500 font-bold">{stat.label}</span>
                <Icon size={14} className={stat.color} />
              </div>
              <div className="text-xl font-bold text-white">
                {typeof stat.value === 'number' ? `${Math.round(stat.value)}%` : stat.value}
              </div>
              <div className="mt-1.5 h-1 bg-slate-800 rounded-full overflow-hidden">
                <div 
                  className={`h-full rounded-full transition-all duration-500 ${stat.color.replace('text-', 'bg-')}`}
                  style={{ width: `${typeof stat.value === 'number' ? stat.value : 50}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Lista de servicios */}
        <div className="lg:col-span-2 space-y-2">
          <h3 className="text-sm font-bold text-slate-200 mb-2 flex items-center gap-2">
            <Terminal size={14} className="text-cyan-400" />
            Servicios Activos
          </h3>
          {services.map(svc => {
            const cfg = statusConfig[svc.status];
            const StatusIcon = cfg.icon;
            return (
              <div 
                key={svc.name}
                onClick={() => setSelectedService(svc.name)}
                className={`p-3 rounded-xl border transition-all cursor-pointer ${
                  selectedService === svc.name ? 'bg-slate-800 border-cyan-700' : 'bg-slate-900/40 border-slate-800 hover:border-slate-700'
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className={`w-2 h-2 rounded-full ${
                      svc.status === 'running' ? 'bg-green-400' :
                      svc.status === 'error' ? 'bg-red-400' :
                      svc.status === 'restarting' ? 'bg-amber-400 animate-pulse' :
                      'bg-slate-600'
                    }`} />
                    <div>
                      <div className="text-xs font-mono font-bold text-slate-200">{svc.name}</div>
                      <div className="text-[10px] text-slate-500">
                        PID: {svc.pid || '—'} | Uptime: {svc.uptime} | Port: {svc.port || '—'}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={`text-[10px] px-2 py-0.5 rounded-full border flex items-center gap-1 ${cfg.color}`}>
                      <StatusIcon size={10} /> {svc.status}
                    </span>
                    <div className="flex gap-1">
                      {svc.status !== 'running' && (
                        <button 
                          onClick={e => { e.stopPropagation(); toggleService(svc.name, 'start'); }}
                          className="p-1 bg-green-600/20 hover:bg-green-600/40 text-green-400 rounded transition-colors"
                        >
                          <Play size={12} />
                        </button>
                      )}
                      {svc.status === 'running' && (
                        <button 
                          onClick={e => { e.stopPropagation(); toggleService(svc.name, 'stop'); }}
                          className="p-1 bg-red-600/20 hover:bg-red-600/40 text-red-400 rounded transition-colors"
                        >
                          <Square size={12} />
                        </button>
                      )}
                      <button 
                        onClick={e => { e.stopPropagation(); toggleService(svc.name, 'restart'); }}
                        className="p-1 bg-amber-600/20 hover:bg-amber-600/40 text-amber-400 rounded transition-colors"
                      >
                        <RotateCw size={12} />
                      </button>
                    </div>
                  </div>
                </div>
                {svc.lastLog && (
                  <div className="mt-2 text-[10px] text-slate-600 font-mono truncate">
                    → {svc.lastLog}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* Terminal de logs */}
        <div className="bg-slate-950 border border-slate-800 rounded-xl overflow-hidden flex flex-col h-[500px]">
          <div className="px-3 py-2 bg-slate-900 border-b border-slate-800 flex items-center justify-between">
            <span className="text-[10px] font-bold text-slate-400 flex items-center gap-1.5">
              <Terminal size={10} /> Logs en vivo
            </span>
            <div className="flex gap-1">
              <div className="w-2 h-2 rounded-full bg-red-500" />
              <div className="w-2 h-2 rounded-full bg-amber-500" />
              <div className="w-2 h-2 rounded-full bg-green-500" />
            </div>
          </div>
          <div className="flex-1 overflow-y-auto p-3 font-mono text-[11px] space-y-1">
            {logs.map((log, i) => (
              <div key={i} className="text-slate-400">
                <span className="text-slate-600">{log.split(']')[0]}]</span>
                <span className="text-cyan-500/70">{log.split(']')[1] || ''}</span>
              </div>
            ))}
            <div ref={logsEndRef} />
          </div>
          <div className="px-3 py-2 bg-slate-900 border-t border-slate-800">
            <div className="flex items-center gap-2">
              <span className="text-green-400 text-xs">$</span>
              <input 
                placeholder="Comando..."
                className="flex-1 bg-transparent text-xs text-slate-300 outline-none placeholder:text-slate-700"
                onKeyDown={e => {
                  if (e.key === 'Enter') {
                    setLogs(prev => [...prev, `[${new Date().toISOString().split('T')[1].slice(0,8)}] CMD: ${(e.target as HTMLInputElement).value}`]);
                    (e.target as HTMLInputElement).value = '';
                  }
                }}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
