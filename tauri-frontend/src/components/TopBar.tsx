import { useState } from 'react'
import { useServiceStore } from '../stores/serviceStore'
import { Button } from './ui/button'
import { Badge } from './ui/badge'
import { Moon, Sun, Shield, Loader2, CheckCircle2, AlertCircle } from 'lucide-react'

export function TopBar() {
  const { startAll, stopAll } = useServiceStore()
  const [dark, setDark] = useState(true)
  const [loadingAction, setLoadingAction] = useState<'start' | 'stop' | null>(null)
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null)

  const toggleDark = () => {
    setDark(!dark)
    document.documentElement.classList.toggle('dark')
  }

  const handleStartAll = async () => {
    setLoadingAction('start')
    setToast(null)
    try {
      await startAll()
      setToast({ message: 'Todos los servicios fueron iniciados', type: 'success' })
    } catch (err: any) {
      setToast({ message: err?.message || 'Error al iniciar todos los servicios', type: 'error' })
    } finally {
      setLoadingAction(null)
      setTimeout(() => setToast(null), 3500)
    }
  }

  const handleStopAll = async () => {
    setLoadingAction('stop')
    setToast(null)
    try {
      await stopAll()
      setToast({ message: 'Todos los servicios fueron detenidos', type: 'success' })
    } catch (err: any) {
      setToast({ message: err?.message || 'Error al detener todos los servicios', type: 'error' })
    } finally {
      setLoadingAction(null)
      setTimeout(() => setToast(null), 3500)
    }
  }

  const isOperating = loadingAction !== null

  return (
    <header className="border-b px-4 py-2 flex items-center justify-between bg-card relative">
      <div className="flex items-center space-x-3">
        <Shield className="h-5 w-5 text-blue-400" />
        <h1 className="text-lg font-bold tracking-tight">SourceSeal Console</h1>
        <Badge variant="destructive">⚠️ DEFENSIVE USE ONLY</Badge>
      </div>

      <div className="flex items-center space-x-2">
        {toast && (
          <div className={`text-xs px-2.5 py-1 rounded border flex items-center gap-1.5 transition-all ${
            toast.type === 'success' 
              ? 'bg-green-950/40 text-green-400 border-green-800' 
              : 'bg-red-950/40 text-red-400 border-red-800'
          }`}>
            {toast.type === 'success' ? <CheckCircle2 className="h-3 w-3 shrink-0" /> : <AlertCircle className="h-3 w-3 shrink-0" />}
            <span>{toast.message}</span>
          </div>
        )}

        <Button
          size="sm"
          variant="outline"
          disabled={isOperating}
          onClick={handleStartAll}
        >
          {loadingAction === 'start' && <Loader2 className="h-3 w-3 mr-1 animate-spin text-green-400" />}
          Start All
        </Button>
        <Button
          size="sm"
          variant="outline"
          disabled={isOperating}
          onClick={handleStopAll}
        >
          {loadingAction === 'stop' && <Loader2 className="h-3 w-3 mr-1 animate-spin text-yellow-400" />}
          Stop All
        </Button>
        <Button variant="ghost" size="icon" onClick={toggleDark}>
          {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </Button>
      </div>
    </header>
  )
}
