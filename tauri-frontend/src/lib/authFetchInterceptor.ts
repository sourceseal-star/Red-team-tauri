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
      // ── GUARD ANTI-LOOP (fix war room 2026-09-07) ──
      // BUG: antes se recargaba SIEMPRE que llegaba un 401. Como NO existe
      // pantalla de login montada en el router, tras la recarga la war room
      // volvía a montar, volvía a disparar /api/*, volvía a llegar 401 y
      // volvía a recargar -> loop infinito: la pantalla "temblaba", no cargaba
      // nunca y recalentaba el teléfono (cada recarga relanzaba además el
      // escaneo nmap automático). Ahora solo se recarga UNA vez cada 15 s;
      // si en esa ventana sigue llegando 401, se muestra un banner fijo con
      // opción de pegar el token nuevo a mano (no hay login UI todavía).
      const now = Date.now()
      const lastReload = Number(sessionStorage.getItem('auth_reload_ts') || 0)
      const hadToken = !!localStorage.getItem('api_token')
      if (hadToken) localStorage.removeItem('api_token')

      if (now - lastReload > 15000) {
        sessionStorage.setItem('auth_reload_ts', String(now))
        console.warn('[auth] Token invalido/vencido — recargando una sola vez')
        window.location.reload()
        return response
      }

      // Segundo 401 en <15s: NO recargar de nuevo (era el temblor). Banner manual.
      if (!document.getElementById('auth-loop-banner')) {
        const banner = document.createElement('div')
        banner.id = 'auth-loop-banner'
        banner.style.cssText =
          'position:fixed;top:0;left:0;right:0;z-index:99999;background:#7f1d1d;' +
          'color:#fecaca;font:12px/1.6 monospace;padding:10px 14px;display:flex;' +
          'flex-wrap:wrap;gap:8px;align-items:center;justify-content:space-between'
        const msg = document.createElement('span')
        msg.textContent = '⚠️ Token de sesión inválido — el backend rechaza las llamadas /api/*. Pega el token nuevo (REDTEAM_API_KEY del .env en Termux):'
        msg.style.flex = '1 1 260px'
        const btnToken = document.createElement('button')
        btnToken.textContent = 'Ingresar token'
        btnToken.style.cssText = 'background:#dc2626;color:#fff;border:none;padding:6px 12px;border-radius:6px;font-weight:bold;cursor:pointer'
        btnToken.onclick = () => {
          const t = window.prompt('Pega el valor de REDTEAM_API_KEY del .env (backend Termux):')
          if (t && t.trim()) {
            localStorage.setItem('api_token', t.trim())
            sessionStorage.removeItem('auth_reload_ts')
            window.location.reload()
          }
        }
        const btnRetry = document.createElement('button')
        btnRetry.textContent = 'Reintentar'
        btnRetry.style.cssText = 'background:#450a0a;color:#fecaca;border:1px solid #b91c1c;padding:6px 12px;border-radius:6px;cursor:pointer'
        btnRetry.onclick = () => { sessionStorage.removeItem('auth_reload_ts'); window.location.reload() }
        banner.appendChild(msg)
        banner.appendChild(btnToken)
        banner.appendChild(btnRetry)
        document.body.appendChild(banner)
      }
    }

    return response
  }) as typeof window.fetch
}
