import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard, FileText, Shield, Bug, Workflow,
  Globe, Smartphone, Terminal, Settings, Info, MapPin, Camera, Network, TrendingUp,
  Server, Sun
} from 'lucide-react'
import { cn } from '../lib/utils'

const items = [
  { to: '/',         label: 'Dashboard',   icon: LayoutDashboard },
  { to: '/config',   label: 'Config',      icon: FileText },
  { to: '/reports',  label: 'Reports',     icon: Shield },
  { to: '/honeypot', label: 'Deception',   icon: Bug },
  { to: '/soar',     label: 'SOAR',        icon: Workflow },
  { to: '/tip',      label: 'Threat Intel',icon: Globe },
  { to: '/geo',      label: 'Geo / Intel', icon: MapPin },
  { to: '/rasp',     label: 'RASP',        icon: Smartphone },
  { to: '/terminal', label: 'Terminal',    icon: Terminal },
  { to: '/settings', label: 'Settings',    icon: Settings },
  { to: '/cameras',  label: 'Cameras',     icon: Camera },
  { to: '/topology', label: 'Topology',    icon: Network },
  { to: '/about',    label: 'About',       icon: Info },
  { to: '/services',      label: 'Servicios',    icon: Server },
  { to: '/ventas',  label: 'Ventas',      icon: TrendingUp },
]

interface SidebarProps {
  open: boolean
  onClose: () => void
}

export function Sidebar({ open, onClose }: SidebarProps) {
  return (
    <>
      {/* Backdrop — solo en mobile cuando el drawer esta abierto */}
      {open && (
        <div
          className="fixed inset-0 z-40 bg-black/60 lg:hidden"
          onClick={onClose}
          aria-hidden="true"
        />
      )}

      <aside
        className={cn(
          'fixed inset-y-0 left-0 z-50 w-64 border-r bg-muted/40 p-2 flex flex-col overflow-y-auto',
          'transition-transform duration-200 ease-in-out',
          'lg:static lg:z-auto lg:w-52 lg:translate-x-0',
          open ? 'translate-x-0' : '-translate-x-full'
        )}
      >
        <nav className="space-y-0.5 flex-1">
          {items.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              onClick={onClose}
              className={({ isActive }) =>
                cn(
                  'flex items-center space-x-2 px-3 py-2 rounded-md text-sm transition-colors',
                  isActive
                    ? 'bg-blue-600/20 text-blue-400 border border-blue-600/30'
                    : 'text-muted-foreground hover:bg-accent hover:text-foreground'
                )
              }
            >
              <Icon className="h-4 w-4 shrink-0" />
              <span>{label}</span>
            </NavLink>
          ))}
          {/* Sol vive en backend/static/sol.html — pagina estatica fuera del SPA,
              por eso es un <a> normal (recarga completa) y no un NavLink de react-router. */}
          <a
            href="/sol"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center space-x-2 px-3 py-2 rounded-md text-sm transition-colors text-amber-400/90 hover:bg-accent hover:text-amber-300 border-t mt-1 pt-3"
          >
            <Sun className="h-4 w-4 shrink-0" />
            <span>Sol</span>
          </a>
        </nav>
      </aside>
    </>
  )
}
