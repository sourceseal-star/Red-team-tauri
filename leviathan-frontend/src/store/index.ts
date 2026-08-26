import { configureStore } from '@reduxjs/toolkit'
import ui from './slices/ui'
import cameras from './slices/cameras'
import scans from './slices/scans'
import alerts from './slices/alerts'

export const store = configureStore({
  reducer: { ui, cameras, scans, alerts },
})

export type RootState = ReturnType<typeof store.getState>
export type AppDispatch = typeof store.dispatch
