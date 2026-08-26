import React from 'react'
import { useSelector, useDispatch } from 'react-redux'
import { toggleTheme } from '../store/slices/ui'
import { RootState } from '../store'

interface NavbarProps {
  toggleSidebar: () => void
}

const Navbar: React.FC<NavbarProps> = ({ toggleSidebar }) => {
  const dispatch = useDispatch()
  const theme = useSelector((state: RootState) => state.ui.theme)
  const isConnected = useSelector((state: RootState) => state.ui.isConnected)
  
  const toggleThemeHandler = () => {
    const newTheme = theme === 'dark' ? 'light' : 'dark'
    dispatch(toggleTheme(newTheme))
    localStorage.setItem('theme', newTheme)
  }
  
  return (
    <nav className="navbar">
      <div className="navbar-left">
        <button className="menu-toggle" onClick={toggleSidebar}>
          <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="3" y1="12" x2="21" y2="12"></line>
            <line x1="3" y1="6" x2="21" y2="6"></line>
            <line x1="3" y1="18" x2="21" y2="18"></line>
          </svg>
        </button>
        
        <div className="logo">
          <span className="logo-icon">🦑</span>
          <span className="logo-text">LEVIATHAN</span>
        </div>
      </div>
      
      <div className="navbar-right">
        <div className="status-indicator">
          <span className={`status-dot ${isConnected ? 'connected' : 'disconnected'}`}></span>
          <span className="status-text">{isConnected ? 'Conectado' : 'Desconectado'}</span>
        </div>
        
        <button className="theme-toggle" onClick={toggleThemeHandler} title="Cambiar tema">
          {theme === 'dark' ? (
            <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="5"></circle>
              <line x1="12" y1="1" x2="12" y2="3"></line>
              <line x1="12" y1="21" x2="12" y2="23"></line>
              <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line>
              <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line>
              <line x1="1" y1="12" x2="3" y2="12"></line>
              <line x1="21" y1="12" x2="23" y2="12"></line>
              <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line>
              <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>
            </svg>
          ) : (
            <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>
            </svg>
          )}
        </button>
      </div>
    </nav>
  )
}

export default Navbar
