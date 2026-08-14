import { useEffect } from 'react'
import { useServiceStore } from '../stores/serviceStore'
import { ServiceCard } from '../components/ServiceCard'
import { Card, CardContent } from '../components/ui/card'
import { Progress } from '../components/ui/progress'
import { useResourceStore } from '../stores/resourceStore'

export default function Dashboard() {
  const { services, fetchStatus } = useServiceStore()
  const { cpu, memory, fetchResources } = useResourceStore()

  useEffect(() => {
    fetchStatus()
    fetchResources()
    const interval = setInterval(() => {
      fetchStatus()
      fetchResources()
    }, 10000)
    return () => clearInterval(interval)
  }, [])

  const running = services.filter(s => s.status === 'running').length

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold">Dashboard</h2>
        <div className="flex space-x-4 text-sm">
          <span>CPU: {cpu.toFixed(0)}%</span>
          <Progress value={cpu} className="w-24" />
          <span>RAM: {(memory.used / 1024 / 1024).toFixed(0)} MB</span>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {services.map(service => (
          <ServiceCard key={service.name} service={service} />
        ))}
      </div>
    </div>
  )
}