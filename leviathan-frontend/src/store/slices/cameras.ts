import { createSlice, createAsyncThunk } from '@reduxjs/toolkit'
import { apiClient } from '../../api'

export interface Camera {
  ip: string
  port: number
  vendor?: string
  model?: string
  is_accessible: boolean
  is_vulnerable: boolean
  rtsp_url?: string
  firmware?: string
}

interface CamerasState {
  cameras: Camera[]
  loading: boolean
  error: string | null
}

const initialState: CamerasState = { cameras: [], loading: false, error: null }

export const fetchCameras = createAsyncThunk('cameras/fetchAll', async () => {
  const res = await apiClient.get('/api/leviathan/cameras')
  return res.data.cameras as Camera[]
})

const camerasSlice = createSlice({
  name: 'cameras',
  initialState,
  reducers: {},
  extraReducers: (builder) => {
    builder
      .addCase(fetchCameras.pending, (state) => { state.loading = true })
      .addCase(fetchCameras.fulfilled, (state, action) => { state.cameras = action.payload; state.loading = false })
      .addCase(fetchCameras.rejected, (state, action) => { state.loading = false; state.error = action.error.message || 'Error'; state.cameras = [] })
  },
})

export default camerasSlice.reducer
