import { useEffect } from 'react'
import { useServiceStore } from '../stores/serviceStore'
import { ServiceCard } from '../components/ServiceCard'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card'
import { Progress } from '../components/ui/progress'
import { useResourceStore } from '../stores/resourceStore'
import { NetworkScanner } from '../components/NetworkScanner'

export default function Dashboard() {
  const { services, fetchStatus } = useServiceStore()
  const { cpu, memory, fetchResources } = useResourceStore()

  useEffect(() => {
    fetchStatus()
    fetchResources()
    const id = setInterval(() => { fetchStatus(); fetchResources() }, 10000)
    return () => clearInterval(id)
  }, [])

  const running = services.filter(s => s.status === 'running').length
  const errored = services.filter(s => s.status === 'error').length
  const memPct = memory.total > 0 ? (memory.used / memory.total) * 100 : 0

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold">Dashboard</h2>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Card>
          <CardHeader><CardTitle>Services Running</CardTitle></CardHeader>
          <CardContent><p className="text-2xl font-bold text-green-400">{running}</p></CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Errors</CardTitle></CardHeader>
          <CardContent><p className="text-2xl font-bold text-red-400">{errored}</p></CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>CPU</CardTitle></CardHeader>
          <CardContent>
            <p className="text-2xl font-bold font-mono">{cpu.toFixed(1)}%</p>
            <Progress value={cpu} className="mt-2" />
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>RAM</CardTitle></CardHeader>
          <CardContent>
            <p className="text-2xl font-bold font-mono">{(memory.used / 1024 / 1024).toFixed(0)} MB</p>
            <Progress value={memPct} className="mt-2" />
          </CardContent>
        </Card>
      </div>

      {/* Service cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {services.map(service => (
          <ServiceCard key={service.name} service={service} />
        ))}
      </div>

      {/* ── Escaneo de red CCTV ────────────────────────────────────────── */}
      <div>
        <h3 className="text-sm font-semibold mb-2">Escaneo de red - Camaras IP / CCTV</h3>
        <NetworkScanner />
      </div>
    </div>
  )
}
