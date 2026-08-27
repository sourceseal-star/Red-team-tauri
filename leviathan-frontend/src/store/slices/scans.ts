import { createSlice, createAsyncThunk } from '@reduxjs/toolkit'
import { apiClient } from '../../api'

export interface Scan {
  id: string
  target: string
  modules: string
  status: string
  started_at: string
  finished_at?: string
  statistics?: string
}

interface ScansState {
  scans: Scan[]
  loading: boolean
  error: string | null
}

const initialState: ScansState = { scans: [], loading: false, error: null }

export const fetchScans = createAsyncThunk('scans/fetchAll', async () => {
  const res = await apiClient.get('/api/leviathan/scans')
  return res.data.scans as Scan[]
})

const scansSlice = createSlice({
  name: 'scans',
  initialState,
  reducers: {},
  extraReducers: (builder) => {
    builder
      .addCase(fetchScans.pending, (state) => { state.loading = true })
      .addCase(fetchScans.fulfilled, (state, action) => { state.scans = action.payload; state.loading = false })
      .addCase(fetchScans.rejected, (state) => { state.loading = false; state.scans = [] })
  },
})

export default scansSlice.reducer
