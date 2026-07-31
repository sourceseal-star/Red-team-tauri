import { useEffect, useState } from 'react'
import { invoke } from '@tauri-apps/api/tauri'

export function BottomStatus() {
  const [memory, setMemory] = useState(0)
  const [serviceCount, setServiceCount] = useState(0)
  const [cpu, setCpu] = useState(0)

  useEffect(() => {
    const poll = async () => {
      try {
        const res = await invoke('get_system_resources') as { cpu_usage: number; memory_used: number }
        setMemory(res.memory_used / 1024 / 1024)
        setCpu(res.cpu_usage)
        const services = await invoke('get_services_status') as { status: string }[]
        setServiceCount(services.filter(s => s.status === 'running').length)
      } catch (_) {}
    }
    poll()
    const id = setInterval(poll, 5000)
    return () => clearInterval(id)
  }, [])

  return (
    <div className="border-t px-4 py-1 text-xs text-muted-foreground flex justify-between bg-card">
      <span className="text-green-400">● Backend: OK</span>
      <span>Services running: <span className="text-foreground font-mono">{serviceCount}</span></span>
      <span>CPU: <span className="font-mono">{cpu.toFixed(1)}%</span></span>
      <span>RAM: <span className="font-mono">{memory.toFixed(0)} MB</span></span>
    </div>
  )
}
