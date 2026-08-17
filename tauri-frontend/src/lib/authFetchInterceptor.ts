/**
 * Interceptor global de fetch() — inyecta el token de autenticacion
 * automaticamente en TODAS las llamadas a /api/*.
 *
 * BUG QUE ESTO CORRIGE: mas de 10 componentes (OSINTPanel, CameraCommandCenter,
 * NetworkTopology, BlackMirrorPanel, WarRoom, WiFiPanel, CameraViewer,
 * TrafficMonitor, CameraGrid, ExploitMatrix, CanarySVG, LeafletMap,
 * EvidenceExporter...) hacian fetch() crudo sin ningun header de auth.
 * Con el middleware de seguridad del backend exigiendo token, TODAS esas
 * llamadas fallaban con 401 silencioso -> paneles vacios, "undefined" en
 * los logs, y en el caso de MurcielagoPanel un crash de render (pagina
 * en blanco) porque intentaba leer .capabilities de un objeto de error.
 *
 * En vez de editar cada componente uno por uno (15+ archivos, alto riesgo
 * de introducir bugs nuevos), se parchea window.fetch UNA sola vez aqui:
 * cualquier request a /api/* que no traiga ya un header de auth explicito
 * recibe automaticamente "Authorization: Bearer <token>" del localStorage.
 */
export function installAuthFetchInterceptor() {
  const originalFetch = window.fetch.bind(window)

  window.fetch = ((input: RequestInfo | URL, init?: RequestInit) => {
    const url =
      typeof input === 'string'
        ? input
        : input instanceof URL
          ? input.toString()
          : (input as Request).url

    const isApiCall = url.startsWith('/api/')

    if (isApiCall) {
      const token = localStorage.getItem('api_token')
      if (token) {
        const headers = new Headers(
          init?.headers ?? (input instanceof Request ? input.headers : undefined)
        )
        if (!headers.has('Authorization') && !headers.has('X-API-Key') && !headers.has('X-Api-Key')) {
          headers.set('Authorization', `Bearer ${token}`)
        }
        init = { ...init, headers }
      }
    }

    return originalFetch(input, init)
  }) as typeof window.fetch
}
