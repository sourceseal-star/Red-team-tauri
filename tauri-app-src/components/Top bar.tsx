import { useState } from 'react'
import { useServiceStore } from '../stores/serviceStore'
import { Button } from './ui/button'
import { Badge } from './ui/badge'
import { Moon, Sun } from 'lucide-react'

export function TopBar() {
  const { startAll, stopAll } = useServiceStore()
  const [dark, setDark] = useState(false)

  return (
    <header className="border-b px-4 py-2 flex items-center justify-between bg-card">
      <div className="flex items-center space-x-4">
        <h1 className="text-xl font-bold">SourceSeal Console</h1>
        <Badge variant="destructive" className="bg-red-600">⚠️ DEFENSIVE USE ONLY</Badge>
      </div>
      <div className="flex items-center space-x-2">
        <Button size="sm" variant="outline" onClick={() => startAll()}>Start All</Button>
        <Button size="sm" variant="outline" onClick={() => stopAll()}>Stop All</Button>
        <Button
          variant="ghost"
          size="icon"
          onClick={() => setDark(!dark)}
          className="ml-2"
        >
          {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </Button>
      </div>
    </header>
  )
}