import { create } from 'zustand'
import { api } from '../lib/api'

interface ResourceStore {
  cpu: number
  memory: { used: number; total: number; percent: number }
  fetchResources: () => Promise<void>
}

export const useResourceStore = create<ResourceStore>((set) => ({
  cpu: 0,
  memory: { used: 0, total: 1, percent: 0 },
  fetchResources: async () => {
    try {
      const res = await api.getResources()
      set({
        cpu: res.cpu_usage,
        memory: { used: res.memory_used, total: res.memory_total, percent: res.memory_percent },
      })
    } catch (e) {
      console.error('[resourceStore] fetchResources:', e)
    }
  },
}))
