import { useState } from 'react'
import { useServiceStore } from '../stores/serviceStore'
import { Button } from './ui/button'
import { Badge } from './ui/badge'
import { Moon, Sun, Shield } from 'lucide-react'

export function TopBar() {
  const { startAll, stopAll } = useServiceStore()
  const [dark, setDark] = useState(true)

  const toggleDark = () => {
    setDark(!dark)
    document.documentElement.classList.toggle('dark')
  }

  return (
    <header className="border-b px-4 py-2 flex items-center justify-between bg-card">
      <div className="flex items-center space-x-3">
        <Shield className="h-5 w-5 text-blue-400" />
        <h1 className="text-lg font-bold tracking-tight">SourceSeal Console</h1>
        <Badge variant="destructive">⚠️ DEFENSIVE USE ONLY</Badge>
      </div>
      <div className="flex items-center space-x-2">
        <Button size="sm" variant="outline" onClick={() => startAll()}>Start All</Button>
        <Button size="sm" variant="outline" onClick={() => stopAll()}>Stop All</Button>
        <Button variant="ghost" size="icon" onClick={toggleDark}>
          {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </Button>
      </div>
    </header>
  )
}
