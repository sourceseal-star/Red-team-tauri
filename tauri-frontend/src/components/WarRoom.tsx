import React, { useState } from 'react';
import { GripVertical, X, Maximize2, Minimize2 } from 'lucide-react';
import CameraCommandCenter from './CameraCommandCenter';
import IntelPanel from './IntelPanel';
import ExploitMatrix from './ExploitMatrix';
import TrafficMonitor from './TrafficMonitor';
import OSINTPanel from './OSINTPanel';
import WiFiPanel from './WiFiPanel';
import BlackMirrorPanel from './BlackMirrorPanel';
import ServiceControlPanel from './ServiceControlPanel';
import LeviathanWidget from './LeviathanWidget';
import UnifiedCommandHub from './UnifiedCommandHub';
// SolWidget desactivado aquí a pedido de Harold (2026-09-03): Sol se queda
// fuera del War Room mientras nos centramos en el Commander. Su acceso
// directo sigue vivo en el sidebar (Sidebar.tsx) y el avatar del header
// (AppShell.tsx) — solo se quitó de este grid mezclado con Commander.
// import { SolWidget } from './SolWidget';

// Paneles disponibles para el War Room
const PANELS = [
  { id: 'cam', label: 'Cámaras', component: CameraCommandCenter, default: true, span: 'lg:col-span-2 lg:row-span-2' },
  { id: 'intel', label: 'Threat Intel', component: IntelPanel, default: true, span: 'lg:col-span-1' },
  { id: 'exploit', label: 'Exploits', component: ExploitMatrix, default: true, span: 'lg:col-span-1' },
  { id: 'traffic', label: 'Tráfico', component: TrafficMonitor, default: true, span: 'lg:col-span-1' },
  { id: 'osint', label: 'OSINT', component: OSINTPanel, default: false, span: 'lg:col-span-1' },
  { id: 'wifi', label: 'WiFi', component: WiFiPanel, default: false, span: 'lg:col-span-1' },
  { id: 'mirror', label: 'Black Mirror', component: BlackMirrorPanel, default: false, span: 'lg:col-span-1' },
  { id: 'services', label: 'Servicios', component: ServiceControlPanel, default: false, span: 'lg:col-span-2' },
  { id: 'leviathan', label: 'LEVIATHAN', component: LeviathanWidget, default: true, span: 'lg:col-span-2 lg:row-span-2' },
];

export default function WarRoom({ onNavigate }: { onNavigate?: (module: string) => void }) {
  const [activePanels, setActivePanels] = useState<string[]>(
    PANELS.filter(p => p.default).map(p => p.id)
  );
  const [maximized, setMaximized] = useState<string | null>(null);

  const togglePanel = (id: string) => {
    setActivePanels(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]);
  };

  return (
    <div className="space-y-4">
      <UnifiedCommandHub onNavigate={onNavigate} />

      {/* Barra de control de paneles */}
      <div className="flex flex-wrap gap-2">
        {PANELS.map(p => {
          const isActive = activePanels.includes(p.id);
          return (
            <button
              key={p.id}
              onClick={() => togglePanel(p.id)}
              className={`px-3 py-1.5 rounded-lg text-[10px] font-bold transition-all border ${
                isActive 
                  ? 'bg-slate-800 border-slate-600 text-white' 
                  : 'bg-transparent border-slate-800 text-slate-600 hover:border-slate-700'
              }`}
            >
              {isActive ? '●' : '○'} {p.label}
            </button>
          );
        })}
      </div>

      {/* Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {PANELS.filter(p => activePanels.includes(p.id)).map(p => {
          const Component = p.component;
          const isMax = maximized === p.id;
          return (
            <div 
              key={p.id} 
              className={`relative bg-slate-900/40 border border-slate-800 rounded-xl overflow-hidden transition-all ${
                isMax ? 'fixed inset-4 z-50 col-span-full row-span-full' : p.span
              }`}
            >
              {/* Header del panel */}
              <div className="flex items-center justify-between px-3 py-2 border-b border-slate-800/50 bg-slate-900/60">
                <div className="flex items-center gap-2">
                  <GripVertical size={12} className="text-slate-700 cursor-grab" />
                  <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">{p.label}</span>
                </div>
                <div className="flex items-center gap-1">
                  <button 
                    onClick={() => setMaximized(isMax ? null : p.id)}
                    className="p-1 hover:bg-slate-800 rounded text-slate-600 hover:text-slate-300"
                  >
                    {isMax ? <Minimize2 size={10} /> : <Maximize2 size={10} />}
                  </button>
                  <button 
                    onClick={() => togglePanel(p.id)}
                    className="p-1 hover:bg-red-900/30 rounded text-slate-600 hover:text-red-400"
                  >
                    <X size={10} />
                  </button>
                </div>
              </div>

              {/* Contenido */}
              <div className={`${isMax ? 'h-[calc(100%-40px)]' : ''} overflow-auto`}>
                <Component />
              </div>
            </div>
          );
        })}
      </div>

      {activePanels.length === 0 && (
        <div className="flex flex-col items-center justify-center h-64 text-slate-600">
          <p className="text-sm">Ningún panel activo</p>
          <p className="text-xs mt-1">Selecciona módulos arriba para comenzar</p>
        </div>
      )}
    </div>
  );
}
