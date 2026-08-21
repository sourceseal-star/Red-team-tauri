import { createSlice, PayloadAction } from '@reduxjs/toolkit'

interface UIState {
  theme: 'dark' | 'light'
  sidebarOpen: boolean
}

const initialState: UIState = {
  theme: (localStorage.getItem('theme') as 'dark' | 'light') || 'dark',
  sidebarOpen: true,
}

const uiSlice = createSlice({
  name: 'ui',
  initialState,
  reducers: {
    setTheme: (state, action: PayloadAction<'dark' | 'light'>) => {
      state.theme = action.payload
      localStorage.setItem('theme', action.payload)
    },
    toggleSidebar: (state) => { state.sidebarOpen = !state.sidebarOpen },
  },
})

export const { setTheme, toggleSidebar } = uiSlice.actions
export default uiSlice.reducer
