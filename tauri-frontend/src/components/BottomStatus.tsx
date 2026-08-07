import { useEffect, useState } from 'react'
import { api } from '../lib/api'

export function BottomStatus() {
  const [memory, setMemory]   = useState(0)
  const [cpu, setCpu]         = useState(0)
  const [svcCount, setSvc]    = useState(0)
  const [backendOk, setOk]    = useState<boolean>(true)

  useEffect(() => {
    const poll = async () => {
      try {
        const [res, svcs] = await Promise.all([api.getResources(), api.getServices()])
        setMemory(res.memory_used ? res.memory_used / 1024 / 1024 : 0)
        setCpu(res.cpu_usage ?? res.cpu_percent ?? 0)
        setSvc(svcs.filter(s => s.status === 'running').length)
        setOk(true)
      } catch {
        setOk(false)
      }
    }
    poll()
    const id = setInterval(poll, 5000)
    return () => clearInterval(id)
  }, [])

  return (
    <div className="border-t px-4 py-1 text-xs text-muted-foreground flex justify-between bg-card flex-wrap gap-2">
      <span className={`flex items-center gap-1 font-medium ${backendOk ? 'text-green-400' : 'text-red-400'}`}>
        <span className={`h-2 w-2 rounded-full ${backendOk ? 'bg-green-400' : 'bg-red-400 animate-pulse'}`} />
        Backend: {backendOk ? 'Conectado' : 'Desconectado'}
      </span>
      <span>Services running: <span className="text-foreground font-mono">{svcCount}</span></span>
      <span>CPU: <span className="font-mono">{cpu.toFixed(1)}%</span></span>
      <span>RAM: <span className="font-mono">{memory.toFixed(0)} MB</span></span>
    </div>
  )
}
