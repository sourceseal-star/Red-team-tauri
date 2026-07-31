import { create } from 'zustand'
import { invoke } from '@tauri-apps/api/tauri'

interface ResourceStore {
  cpu: number
  memory: { used: number; total: number }
  fetchResources: () => Promise<void>
}

export const useResourceStore = create<ResourceStore>((set) => ({
  cpu: 0,
  memory: { used: 0, total: 1 },
  fetchResources: async () => {
    try {
      const res = await invoke('get_system_resources') as { cpu_usage: number; memory_used: number; memory_total: number }
      set({ cpu: res.cpu_usage, memory: { used: res.memory_used, total: res.memory_total } })
    } catch (e) {
      console.error(e)
    }
  },
}))
