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
 *
 * BUG #2 QUE ESTO CORRIGE (token viejo atascado): el backend genera una
 * REDTEAM_API_KEY nueva cada vez que se borra/recrea .env (o en el primer
 * arranque). Si el navegador YA tenia un "api_token" guardado de una sesion
 * anterior (con la key vieja), App.tsx nunca vuelve a mostrar el login
 * (solo revisa si el token EXISTE, no si es VALIDO) -> el usuario queda
 * atrapado viendo la app pero con 401 en TODO para siempre, sin forma de
 * salir salvo tocar manualmente "Cerrar sesion". Ahora: si el backend
 * responde 401/403 a una llamada /api/* (fuera del propio login), se
 * asume que el token esta vencido/no coincide, se borra automaticamente
 * y se recarga -> el usuario cae directo en la pantalla de login para
 * autenticarse de nuevo con el token correcto, sin intervencion manual.
 */
export function installAuthFetchInterceptor() {
  const originalFetch = window.fetch.bind(window)

  window.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    const url =
      typeof input === 'string'
        ? input
        : input instanceof URL
          ? input.toString()
          : (input as Request).url

    const isApiCall = url.startsWith('/api/')
    const isAuthCall = url.startsWith('/api/auth/')

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

    const response = await originalFetch(input, init)

    // Token invalido/vencido (no coincide con la API key actual del backend):
    // limpiar sesion y forzar re-login en vez de dejar la app atascada en 401.
    if (isApiCall && !isAuthCall && (response.status === 401 || response.status === 403)) {
      const hadToken = !!localStorage.getItem('api_token')
      if (hadToken) {
        localStorage.removeItem('api_token')
        console.warn('[auth] Token invalido/vencido — cerrando sesion automaticamente')
        window.location.reload()
      }
    }

    return response
  }) as typeof window.fetch
}
