import React, { useState, useEffect, createContext, useContext } from 'react';
import {
  LayoutDashboard, Shield, Camera, Radio, Globe, Wifi, Activity,
  Terminal, Settings, Bell, Search, Menu, X, ChevronRight,
  Zap, Lock, Eye, Fingerprint, Bug, FileText, Network,
  Sun, Moon, LogOut
} from 'lucide-react'
import { LanguageSwitcher } from '../i18n/LanguageSwitcher';

// ==========================================
// CONTEXTOS GLOBALES
// ==========================================
interface Toast {
  id: string;
  type: 'success' | 'error' | 'warning' | 'info';
  title: string;
  message?: string;
}

const ToastContext = createContext<{
  toasts: Toast[];
  addToast: (t: Omit<Toast, 'id'>) => void;
  removeToast: (id: string) => void;
}>({ toasts: [], addToast: () => {}, removeToast: () => {} });

export const useToast = () => useContext(ToastContext);

// ==========================================
// SIDEBAR — Solo módulos que EXISTEN en el backend
// ==========================================
const MODULES = [
  { id: 'warroom', label: 'War Room', icon: LayoutDashboard, color: 'text-cyan-400', badge: null },
  { id: 'cameras', label: 'Cámaras', icon: Camera, color: 'text-red-400', badge: 'live' },
  { id: 'threat', label: 'Threat Intel', icon: Shield, color: 'text-amber-400', badge: null },
  { id: 'osint', label: 'OSINT', icon: Globe, color: 'text-purple-400', badge: null },
  { id: 'wifi', label: 'WiFi', icon: Wifi, color: 'text-green-400', badge: null },
  { id: 'ultra', label: 'Ultrasonidos', icon: Radio, color: 'text-pink-400', badge: null },
  { id: 'blackmirror', label: 'Black Mirror', icon: Eye, color: 'text-rose-400', badge: null },
  { id: 'services', label: 'Servicios', icon: Activity, color: 'text-blue-400', badge: null },
  { id: 'terminal', label: 'Terminal', icon: Terminal, color: 'text-slate-400', badge: null },
    { id: 'tower', label: 'Control Tower', icon: Radio, color: 'text-cyan-400', badge: null },
  { id: 'topology', label: 'Topología', icon: Network, color: 'text-cyan-400', badge: null },
  { id: 'settings', label: 'Config', icon: Settings, color: 'text-slate-500', badge: null },
  { id: 'osint_adv', label: 'OSINT Avanzado', icon: Globe, color: 'text-indigo-400', badge: 'v4.0' },
  { id: 'interceptor', label: 'Interceptor Avanzado', icon: Lock, color: 'text-red-400', badge: 'v4.0' },
];

// ==========================================
// COMPONENTE: TOAST PROVIDER
// ==========================================
function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const addToast = (t: Omit<Toast, 'id'>) => {
    const id = Math.random().toString(36).slice(2);
    setToasts(prev => [...prev, { ...t, id }]);
    setTimeout(() => removeToast(id), 5000);
  };
  const removeToast = (id: string) => setToasts(prev => prev.filter(x => x.id !== id));
  return (
    <ToastContext.Provider value={{ toasts, addToast, removeToast }}>
      {children}
      <div className="fixed top-4 right-4 z-[100] space-y-2 w-80">
        {toasts.map(t => (
          <div key={t.id} className={`p-3 rounded-lg border shadow-lg backdrop-blur animate-in slide-in-from-right ${
            t.type === 'success' ? 'bg-green-900/90 border-green-700 text-green-100' :
            t.type === 'error' ? 'bg-red-900/90 border-red-700 text-red-100' :
            t.type === 'warning' ? 'bg-amber-900/90 border-amber-700 text-amber-100' :
            'bg-blue-900/90 border-blue-700 text-blue-100'
          }`}>
            <div className="font-bold text-xs">{t.title}</div>
            {t.message && <div className="text-[10px] opacity-80 mt-0.5">{t.message}</div>}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

// ==========================================
// COMPONENTE: COMMAND PALETTE (Ctrl+K)
// ==========================================
function CommandPalette({ open, onClose, onNavigate }: { open: boolean; onClose: () => void; onNavigate: (id: string) => void }) {
  const [query, setQuery] = useState('');
  useEffect(() => {
    if (open) setQuery('');
  }, [open]);
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'k' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); onClose(); }
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);

  const filtered = MODULES.filter(m => m.label.toLowerCase().includes(query.toLowerCase()));

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-[90] bg-black/60 backdrop-blur-sm flex items-start justify-center pt-[15vh]" onClick={onClose}>
      <div className="w-full max-w-lg bg-slate-900 border border-slate-700 rounded-xl shadow-2xl overflow-hidden" onClick={e => e.stopPropagation()}>
        <div className="flex items-center gap-2 px-4 py-3 border-b border-slate-800">
          <Search size={16} className="text-slate-500" />
          <input
            autoFocus
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="Buscar módulo, lead, host..."
            className="flex-1 bg-transparent text-sm text-slate-200 outline-none placeholder:text-slate-600"
          />
          <kbd className="text-[10px] bg-slate-800 px-1.5 py-0.5 rounded text-slate-500">ESC</kbd>
        </div>
        <div className="max-h-64 overflow-y-auto py-1">
          {filtered.map(m => {
            const Icon = m.icon;
            return (
              <button
                key={m.id}
                onClick={() => { onNavigate(m.id); onClose(); }}
                className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-slate-800 transition-colors text-left"
              >
                <Icon size={16} className={m.color} />
                <span className="text-sm text-slate-200">{m.label}</span>
                <ChevronRight size={12} className="ml-auto text-slate-600" />
              </button>
            );
          })}
          {filtered.length === 0 && (
            <div className="px-4 py-3 text-xs text-slate-600">No se encontraron resultados</div>
          )}
        </div>
      </div>
    </div>
  );
}

// ==========================================
// COMPONENTE: STATUS BAR (Footer real)
// ==========================================
function StatusBar() {
  const [stats, setStats] = useState({ cpu: 0, ram: 0, disk: 0, services: 0, backend: false });
  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const res = await fetch('/api/health', { cache: 'no-store' });
        const data = await res.json();
        setStats({
          cpu: Math.floor(Math.random() * 30 + 5), // Reemplazar por endpoint real
          ram: Math.floor(Math.random() * 40 + 20),
          disk: 62,
          services: 4,
          backend: data.status === 'ok',
        });
      } catch {
        setStats(s => ({ ...s, backend: false, services: 0 }));
      }
    }, 3000);
    return () => clearInterval(interval);
  }, []);

  return (
    <footer className="h-8 bg-slate-950 border-t border-slate-800 flex items-center px-3 gap-4 text-[10px] font-mono">
      <div className="flex items-center gap-1.5">
        <div className={`w-1.5 h-1.5 rounded-full ${stats.backend ? 'bg-green-400 animate-pulse' : 'bg-red-400'}`} />
        <span className={stats.backend ? 'text-green-400' : 'text-red-400'}>
          {stats.backend ? 'Backend Online' : 'Backend Offline'}
        </span>
      </div>
      <div className="w-px h-3 bg-slate-800" />
      <span className="text-slate-500">Svcs: <span className="text-slate-300">{stats.services}</span></span>
      <span className="text-slate-500">CPU: <span className="text-cyan-400">{stats.cpu}%</span></span>
      <span className="text-slate-500">RAM: <span className="text-purple-400">{stats.ram}%</span></span>
      <span className="text-slate-500">Disk: <span className="text-amber-400">{stats.disk}%</span></span>
      <div className="ml-auto flex items-center gap-2">
        <span className="text-slate-600">v2.1.0</span>
        <span className="px-1.5 py-0.5 bg-red-900/30 border border-red-800 rounded text-red-400 text-[9px] font-bold">DEFENSIVE USE ONLY</span>
      </div>
    </footer>
  );
}

// ==========================================
// COMPONENTE: APP SHELL COMPLETO
// ==========================================
interface AppShellProps {
  activeModule: string;
  onNavigate: (id: string) => void;
  children: React.ReactNode;
  breadcrumbs?: string[];
}

export default function AppShell({ activeModule, onNavigate, children, breadcrumbs = [] }: AppShellProps) {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [commandOpen, setCommandOpen] = useState(false);
  const [darkMode, setDarkMode] = useState(true);
  const [mobileOpen, setMobileOpen] = useState(false);
  const { addToast } = useToast();

  // Atajo Ctrl+K
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'k' && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setCommandOpen(true);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  const activeLabel = MODULES.find(m => m.id === activeModule)?.label || 'War Room';

  return (
    <ToastProvider>
      <div className={`h-screen flex flex-col ${darkMode ? 'dark' : ''}`}>
        {/* TopBar */}
        <header className="h-12 bg-slate-900 border-b border-slate-800 flex items-center px-3 gap-3 shrink-0">
          <button 
            onClick={() => setMobileOpen(!mobileOpen)}
            className="lg:hidden p-1.5 hover:bg-slate-800 rounded-lg text-slate-400"
          >
            <Menu size={18} />
          </button>

          <div className="flex items-center gap-2">
            <Shield size={18} className="text-cyan-400" />
            <span className="text-sm font-bold text-white tracking-tight hidden sm:inline">SourceSeal</span>
          <LanguageSwitcher />
          </div>

          {/* Breadcrumbs */}
          <div className="hidden md:flex items-center gap-1 text-xs text-slate-500 ml-4">
            <span>Console</span>
            {breadcrumbs.map((crumb, i) => (
              <React.Fragment key={i}>
                <ChevronRight size={12} />
                <span className={i === breadcrumbs.length - 1 ? 'text-slate-300 font-medium' : ''}>{crumb}</span>
              </React.Fragment>
            ))}
            {!breadcrumbs.length && (
              <><ChevronRight size={12} /><span className="text-slate-300 font-medium">{activeLabel}</span></>
            )}
          </div>

          <div className="ml-auto flex items-center gap-2">
            {/* Búsqueda global */}
            <button 
              onClick={() => setCommandOpen(true)}
              className="hidden sm:flex items-center gap-2 px-3 py-1.5 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-500 hover:text-slate-300 transition-colors"
            >
              <Search size={12} /> Buscar...
              <kbd className="ml-2 text-[10px] bg-slate-700 px-1 rounded">Ctrl K</kbd>
            </button>

            <button 
              onClick={() => setDarkMode(!darkMode)}
              className="p-1.5 hover:bg-slate-800 rounded-lg text-slate-400 transition-colors"
            >
              {darkMode ? <Sun size={16} /> : <Moon size={16} />}
            </button>

            <button 
              onClick={() => addToast({ type: 'info', title: 'Sin notificaciones nuevas' })}
              className="p-1.5 hover:bg-slate-800 rounded-lg text-slate-400 relative transition-colors"
            >
              <Bell size={16} />
              <span className="absolute top-1 right-1 w-1.5 h-1.5 bg-red-400 rounded-full" />
            </button>

            <button 
              onClick={() => { localStorage.removeItem('api_token'); window.location.reload(); }}
              className="p-1.5 hover:bg-red-900/30 rounded-lg text-slate-400 hover:text-red-400 transition-colors"
              title="Cerrar sesión"
            >
              <LogOut size={16} />
            </button>
          </div>
        </header>

        <div className="flex flex-1 overflow-hidden">
          {/* Sidebar Desktop */}
          <aside className={`hidden lg:flex flex-col w-56 bg-slate-900 border-r border-slate-800 transition-all ${sidebarOpen ? '' : 'w-14'}`}>
            <div className="flex-1 overflow-y-auto py-2 space-y-0.5">
              {MODULES.map(m => {
                const Icon = m.icon;
                const isActive = activeModule === m.id;
                return (
                  <button
                    key={m.id}
                    onClick={() => onNavigate(m.id)}
                    className={`w-full flex items-center gap-3 px-3 py-2 mx-2 rounded-lg transition-all text-left ${
                      isActive 
                        ? 'bg-slate-800 border border-slate-700' 
                        : 'hover:bg-slate-800/50 border border-transparent'
                    }`}
                  >
                    <Icon size={16} className={isActive ? m.color : 'text-slate-500'} />
                    {sidebarOpen && (
                      <>
                        <span className={`text-xs font-medium ${isActive ? 'text-white' : 'text-slate-400'}`}>
                          {m.label}
                        </span>
                        {m.badge === 'live' && (
                          <span className="ml-auto w-1.5 h-1.5 bg-red-400 rounded-full animate-pulse" />
                        )}
                      </>
                    )}
                  </button>
                );
              })}
            </div>
            <button 
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="p-2 border-t border-slate-800 text-slate-500 hover:text-slate-300 flex justify-center"
            >
              {sidebarOpen ? <X size={14} /> : <Menu size={14} />}
            </button>
          </aside>

          {/* Sidebar Mobile */}
          {mobileOpen && (
            <div className="fixed inset-0 z-50 lg:hidden">
              <div className="absolute inset-0 bg-black/60" onClick={() => setMobileOpen(false)} />
              <aside className="absolute left-0 top-0 bottom-0 w-64 bg-slate-900 border-r border-slate-800 py-2 space-y-0.5">
                <div className="px-4 py-3 border-b border-slate-800 mb-2">
                  <span className="text-sm font-bold text-white">SourceSeal Console</span>
                </div>
                {MODULES.map(m => {
                  const Icon = m.icon;
                  const isActive = activeModule === m.id;
                  return (
                    <button
                      key={m.id}
                      onClick={() => { onNavigate(m.id); setMobileOpen(false); }}
                      className={`w-full flex items-center gap-3 px-4 py-2.5 transition-colors text-left ${
                        isActive ? 'bg-slate-800 text-white' : 'text-slate-400 hover:bg-slate-800/50'
                      }`}
                    >
                      <Icon size={18} className={isActive ? m.color : ''} />
                      <span className="text-sm">{m.label}</span>
                    </button>
                  );
                })}
              </aside>
            </div>
          )}

          {/* Main Content */}
          <main className="flex-1 overflow-y-auto bg-slate-950">
            <div className="p-4 lg:p-6 max-w-[1600px] mx-auto">
              {/* Header de página */}
              <div className="flex items-center justify-between mb-6">
                <div>
                  <h1 className="text-xl font-bold text-white">{activeLabel}</h1>
                  <p className="text-xs text-slate-500 mt-0.5">
                    {activeModule === 'warroom' && 'Vista unificada de todos los sistemas'}
                    {activeModule === 'cameras' && 'Descubrimiento y control de cámaras IP'}
                    {activeModule === 'threat' && 'Inteligencia de amenazas y reputación'}
                  </p>
                </div>
                <div className="flex gap-2">
                  {activeModule === 'warroom' && (
                    <button 
                      onClick={() => addToast({ type: 'success', title: 'Layout guardado' })}
                      className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-xs text-slate-300 rounded-lg transition-colors"
                    >
                      Guardar Layout
                    </button>
                  )}
                </div>
              </div>

              {children}
            </div>
          </main>
        </div>

        <StatusBar />
        <CommandPalette 
          open={commandOpen} 
          onClose={() => setCommandOpen(false)} 
          onNavigate={onNavigate}
        />
      </div>
    </ToastProvider>
  );
}
