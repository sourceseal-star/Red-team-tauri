import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard, FileText, Shield, Bug, Workflow,
  Globe, Smartphone, Terminal, Settings, Info, MapPin
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
  { to: '/about',    label: 'About',       icon: Info },
]

export function Sidebar() {
  return (
    <aside className="w-52 border-r bg-muted/40 p-2 flex flex-col">
      <nav className="space-y-0.5 flex-1">
        {items.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
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
      </nav>
    </aside>
  )
}
