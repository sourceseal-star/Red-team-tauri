import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './styles/globals.css'
import './styles/source-seal.css'
import { installAuthFetchInterceptor } from './lib/authFetchInterceptor'

// Debe instalarse ANTES de renderizar la app — parchea window.fetch para que
// toda llamada a /api/* lleve el token de sesion automaticamente.
installAuthFetchInterceptor()

ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
)
