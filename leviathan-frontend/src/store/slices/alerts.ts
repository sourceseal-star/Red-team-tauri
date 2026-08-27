import { createSlice, createAsyncThunk } from '@reduxjs/toolkit'
import { apiClient } from '../../api'

export interface Alert {
  id: number
  severity: string
  title: string
  description: string
  source: string
  camera_ip?: string
  created_at: string
  acknowledged: number
}

interface AlertsState {
  alerts: Alert[]
  loading: boolean
  error: string | null
}

const initialState: AlertsState = { alerts: [], loading: false, error: null }

export const fetchAlerts = createAsyncThunk('alerts/fetchAll', async () => {
  const res = await apiClient.get('/api/leviathan/alerts')
  return res.data.alerts as Alert[]
})

const alertsSlice = createSlice({
  name: 'alerts',
  initialState,
  reducers: {},
  extraReducers: (builder) => {
    builder
      .addCase(fetchAlerts.pending, (state) => { state.loading = true })
      .addCase(fetchAlerts.fulfilled, (state, action) => { state.alerts = action.payload; state.loading = false })
      .addCase(fetchAlerts.rejected, (state) => { state.loading = false; state.alerts = [] })
  },
})

export default alertsSlice.reducer
