import { create } from 'zustand'
import { invoke } from '@tauri-apps/api/tauri'

export interface Service {
  name: string
  status: 'running' | 'stopped' | 'error'
  pid?: number
  uptime?: string
  lastLogs: string[]
}

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
      const data = await invoke('get_services_status') as any[]
      set({ services: data, loading: false })
    } catch (e) {
      console.error(e)
      set({ loading: false })
    }
  },
  startService: async (name) => {
    await invoke('start_service', { name })
    await get().fetchStatus()
  },
  stopService: async (name) => {
    await invoke('stop_service', { name })
    await get().fetchStatus()
  },
  restartService: async (name) => {
    await invoke('restart_service', { name })
    await get().fetchStatus()
  },
  startAll: async () => {
    await invoke('start_all_services')
    await get().fetchStatus()
  },
  stopAll: async () => {
    await invoke('stop_all_services')
    await get().fetchStatus()
  },
}))