import { useEffect, useState } from 'react'
import { invoke } from '@tauri-apps/api/tauri'

export function BottomStatus() {
  const [memory, setMemory] = useState(0)
  const [serviceCount, setServiceCount] = useState(0)

  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const res = await invoke('get_system_resources') as any
        setMemory(res.memory_used / 1024 / 1024) // MB
        const services = await invoke('get_services_status') as any[]
        setServiceCount(services.filter(s => s.status === 'running').length)
      } catch (e) {}
    }, 5000)
    return () => clearInterval(interval)
  }, [])

  return (
    <div className="border-t px-4 py-1 text-xs text-muted-foreground flex justify-between bg-card">
      <span>Backend: OK</span>
      <span>Running services: {serviceCount}</span>
      <span>Memory: {memory.toFixed(0)} MB</span>
    </div>
  )
}