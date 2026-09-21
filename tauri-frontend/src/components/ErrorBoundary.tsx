import React from 'react'

// ── ErrorBoundary (fix pantalla negra 2026-09-21) ──
// BUG: cuando un panel crashea durante el render (ej. MurcielagoPanel leyendo
// .capabilities de un objeto de error), React desmonta TODO el arbol y la
// pantalla queda NEGADA/negra sin ningun mensaje. Sin este boundary el
// usuario no ve ni el error ni como salir. Ahora: pantalla clara con el
// error REAL y boton de reintentar.
interface State { error: Error | null }

export default class ErrorBoundary extends React.Component<{ children: React.ReactNode }, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error('[ErrorBoundary] crash de render:', error, info)
  }

  render() {
    if (this.state.error) {
      return (
        <div style={{ minHeight: '100vh', background: '#020617', color: '#e2e8f0', fontFamily: 'monospace', padding: '24px', display: 'flex', flexDirection: 'column', gap: '12px', boxSizing: 'border-box' }}>
          <h2 style={{ color: '#f87171', fontSize: '18px', margin: 0 }}>💥 Un panel dejó de renderizar</h2>
          <p style={{ color: '#94a3b8', fontSize: '13px', margin: 0 }}>
            Este es el error real (antes esto era una pantalla negra sin explicación):
          </p>
          <pre style={{ background: '#0f172a', border: '1px solid #334155', borderRadius: '8px', padding: '12px', fontSize: '12px', overflow: 'auto', color: '#fca5a5', whiteSpace: 'pre-wrap', margin: 0 }}>
            {this.state.error.message}
          </pre>
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            <button onClick={() => window.location.reload()} style={{ background: '#dc2626', color: '#fff', border: 'none', padding: '8px 16px', borderRadius: '6px', fontWeight: 'bold', cursor: 'pointer' }}>
              Reintentar (recargar)
            </button>
            <button onClick={() => this.setState({ error: null })} style={{ background: '#1e293b', color: '#94a3b8', border: '1px solid #334155', padding: '8px 16px', borderRadius: '6px', cursor: 'pointer' }}>
              Volver a renderizar sin recargar
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}
