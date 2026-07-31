import { create } from 'zustand'
import { api, type Service } from '../lib/api'

interface ServiceStore {
  services: Service[]
  loading: boolean
  fetchStatus: () => Promise<void>
  startService: (name: string) => Promise<void>
  stopService: (name: string) => Promise<void>
  restartService: (name: string) => Promise<void>
  startAll: () => Promise<void>
  stopAll: () => Promise<void>
}

export const useServiceStore = create<ServiceStore>((set, get) => ({
  services: [],
  loading: false,
  fetchStatus: async () => {
    set({ loading: true })
    try {
      const data = await api.getServices()
      set({ services: data, loading: false })
    } catch (e) {
      console.error('[serviceStore] fetchStatus:', e)
      set({ loading: false })
    }
  },
  startService:   async (name) => { await api.startService(name);   await get().fetchStatus() },
  stopService:    async (name) => { await api.stopService(name);    await get().fetchStatus() },
  restartService: async (name) => { await api.restartService(name); await get().fetchStatus() },
  startAll:       async ()     => { await api.startAll();           await get().fetchStatus() },
  stopAll:        async ()     => { await api.stopAll();            await get().fetchStatus() },
}))
