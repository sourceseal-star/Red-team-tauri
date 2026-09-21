/**
 * Interceptor global de fetch() — inyecta el token de autenticacion
 * automaticamente en TODAS las llamadas a /api/*.
 *
 * FIX 2026-09-21 (pantalla negra tras ingresar la clave):
 * 1) Al pegar el token en el banner ya NO recarga a ciegas: primero VALIDA
 *    la clave contra /api/scan/status. Solo si el backend la acepta (200)
 *    la guarda y recarga. Si no, dice EXACTAMENTE que paso:
 *    - 401 -> la clave no coincide (sacala de Termux: grep REDTEAM_API_KEY
 *      ~/Red-team-tauri/.env)
 *    - 403 -> el backend NO tiene REDTEAM_API_KEY en su entorno — NINGUNA
 *      clave servira hasta reiniciar: bash omni.sh restart
 *    - null -> no hay conexion con :8001 (backend caido)
 * 2) El 403 del backend ya no dispara reload-loop: muestra su mensaje
 *    propio (pegar claves no sirve, hay que reiniciar el backend).
 */
export function installAuthFetchInterceptor() {
  const originalFetch = window.fetch.bind(window)

  // Valida un token candidato contra el backend SIN tocar localStorage.
  // Devuelve 200/401/403 o null (sin conexion).
  async function validateToken(token: string): Promise<number | null> {
    try {
      const r = await originalFetch('/api/scan/status', {
        headers: { 'Authorization': `Bearer ${token}` }
      })
      return r.status
    } catch {
      return null
    }
  }

  function setBannerMsg(text: string) {
    const m = document.getElementById('auth-loop-msg')
    if (m) m.textContent = text
  }

  function ensureBanner() {
    if (document.getElementById('auth-loop-banner')) return

    const banner = document.createElement('div')
    banner.id = 'auth-loop-banner'
    banner.style.cssText =
      'position:fixed;top:0;left:0;right:0;z-index:99999;background:#7f1d1d;' +
      'color:#fecaca;font:12px/1.6 monospace;padding:10px 14px;display:flex;' +
      'flex-wrap:wrap;gap:8px;align-items:center;justify-content:space-between'

    const msg = document.createElement('span')
    msg.id = 'auth-loop-msg'
    msg.style.flex = '1 1 260px'
    msg.textContent = '⚠️ Token de sesión inválido — el backend rechaza las llamadas /api/*. Pega el token nuevo (REDTEAM_API_KEY del .env en Termux):'

    const btnToken = document.createElement('button')
    btnToken.textContent = 'Ingresar token'
    btnToken.style.cssText = 'background:#dc2626;color:#fff;border:none;padding:6px 12px;border-radius:6px;font-weight:bold;cursor:pointer'
    btnToken.onclick = async () => {
      const t = window.prompt('Pega el valor de REDTEAM_API_KEY del .env (backend Termux):')
      if (!t || !t.trim()) return
      btnToken.textContent = 'Verificando…'
      btnToken.disabled = true
      const status = await validateToken(t.trim())
      btnToken.textContent = 'Ingresar token'
      btnToken.disabled = false
      if (status === 200) {
        localStorage.setItem('api_token', t.trim())
        sessionStorage.removeItem('auth_reload_ts')
        window.location.reload()
      } else if (status === 401) {
        setBannerMsg('❌ Esa clave NO coincide con el backend. Saca la clave EXACTA en Termux: grep REDTEAM_API_KEY ~/Red-team-tauri/.env (cuidado con espacios/comillas) y pégala de nuevo.')
      } else if (status === 403) {
        setBannerMsg('🔒 El backend NO tiene REDTEAM_API_KEY configurada en su entorno — NINGUNA clave servirá. En Termux corre: bash omni.sh restart (o curar.sh) y vuelve a intentar.')
      } else {
        setBannerMsg('❌ No hay conexión con el backend en :8001. Verifica que esté corriendo: pgrep -f dashboard_server.py — si no está, en Termux: bash curar.sh')
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

    if (isApiCall && !isAuthCall && (response.status === 401 || response.status === 403)) {
      const now = Date.now()
      const lastReload = Number(sessionStorage.getItem('auth_reload_ts') || 0)
      const hadToken = !!localStorage.getItem('api_token')
      if (hadToken) localStorage.removeItem('api_token')

      // 403: el backend mismo no tiene la clave configurada — pegar claves
      // NO sirve. Mensaje directo, sin reload (evita el loop negro).
      if (response.status === 403) {
        ensureBanner()
        setBannerMsg('🔒 El backend respondió 403: NO tiene REDTEAM_API_KEY en su entorno. Ninguna clave pegada servirá — en Termux corre: bash omni.sh restart (o curar.sh) y luego Reintentar.')
        return response
      }

      // 401: token vencido/no coincide — recargar UNA vez cada 15 s.
      if (now - lastReload > 15000) {
        sessionStorage.setItem('auth_reload_ts', String(now))
        console.warn('[auth] Token invalido/vencido — recargando una sola vez')
        window.location.reload()
        return response
      }

      // Segundo 401 en <15s: banner con validacion real del token.
      ensureBanner()
    }

    return response
  }) as typeof window.fetch
}
