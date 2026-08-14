import { NavLink } from 'react-router-dom'
import { 
  LayoutDashboard, FileText, Shield, Bug, Workflow, 
  Globe, Smartphone, Terminal, Settings, Info 
} from 'lucide-react'
import { cn } from '../lib/utils'

const items = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/config', label: 'Config Editor', icon: FileText },
  { to: '/reports', label: 'Reports', icon: Shield },
  { to: '/honeypot', label: 'Deception', icon: Bug },
  { to: '/soar', label: 'SOAR', icon: Workflow },
  { to: '/tip', label: 'Threat Intel', icon: Globe },
  { to: '/rasp', label: 'RASP', icon: Smartphone },
  { to: '/terminal', label: 'Terminal', icon: Terminal },
  { to: '/settings', label: 'Settings', icon: Settings },
  { to: '/about', label: 'About', icon: Info },
]

export function Sidebar() {
  return (
    <aside className="w-56 border-r bg-muted/40 p-3">
      <nav className="space-y-1">
        {items.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              cn(
                'flex items-center space-x-2 px-3 py-2 rounded-md text-sm transition-colors',
                isActive ? 'bg-accent text-accent-foreground' : 'hover:bg-accent/50'
              )
            }
          >
            <Icon className="h-4 w-4" />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>
    </aside>
  )
}