/**
 * HOLO 9.1 · Constellation Nexus
 * Evolución de Constellation V9:
 * - Cadenas causales (causa → efecto): nodos conectados causalmente parpadean juntos
 * - Interacción drag-and-drop: puedes mover nodos y encadenarlos
 * - Nodos maestro: un nodo puede ser "causa" de otros
 * - Estrella polar con score de Umbra Pulse (no solo Umbra 9.0)
 * - Panel lateral de cadenas activas
 * - Modo "tormenta": cuando Umbra está en ROJO, la constelación tiembla
 *
 * FIX 2026-10-01 (auditoría del bundle):
 * 1. AUTENTICACIÓN: los fetch van sin headers — el dashboard puede exigir
 *    token. Ahora se adjunta Authorization: Bearer desde localStorage
 *    (api_token, la misma clave del war room) si existe.
 * 2. PORTERO SIN INVENTAR: /api/portero/audit es una fuente aún no
 *    verificada. Si no responde, el panel muestra "Portero sin datos"
 *    en vez de fingir que no hay nada.
 * 3. RENDIMIENTO: el polling de 12s seguía corriendo con la pestaña
 *    oculta (consumo de batería/banda en el teléfono). Ahora se pausa
 *    cuando document.hidden, y los nodos tienen tope (60) — antes
 *    la lista crecía sin límite y la física O(n²) encarecía cada frame.
 * 4. Texto visible "Sin cadena 因č" corregido (caracteres corruptos).
 */

class ConstellationNexus {
    constructor(canvasId, panelId) {
        this.cv = document.getElementById(canvasId);
        this.ctx = this.cv.getContext('2d');
        this.panel = document.getElementById(panelId);  // panel lateral de cadenas
        this.nodos = [];
        this.cadenas = [];           // [{causa: id, efectos: [ids]}]
        this.dragNodo = null;
        this.dragOffset = { x: 0, y: 0 };
        this.seleccionado = null;
        this.tormenta = false;       // true cuando Umbra Pulse está en ROJO
        this.t = 0;                  // frame counter para animaciones
        this.latidoPulse = null;
        this.porteroDisponible = null;  // FIX: null = aún no se sabe; false = sin datos
        this.MAX_NODOS = 60;         // FIX: tope de nodos (rendimiento)

        this._bind();
    }

    // FIX: headers de auth — la misma clave del war room (api_token)
    _authHeaders() {
        const h = {};
        try {
            const t = localStorage.getItem('api_token');
            if (t) h['Authorization'] = 'Bearer ' + t;
        } catch (e) { /* localStorage puede estar bloqueado */ }
        return h;
    }

    _bind() {
        this.cv.addEventListener('mousedown', e => this._onDown(e));
        this.cv.addEventListener('mousemove', e => this._onMove(e));
        this.cv.addEventListener('mouseup', () => this._onUp());
        this.cv.addEventListener('touchstart', e => this._onDown(e.touches[0]));
        this.cv.addEventListener('touchmove', e => { e.preventDefault(); this._onMove(e.touches[0]); });
        this.cv.addEventListener('touchend', e => this._onUp());
    }

    _coords(e) {
        const r = this.cv.getBoundingClientRect();
        return {
            x: (e.clientX - r.left) * (this.cv.width / r.width),
            y: (e.clientY - r.top) * (this.cv.height / r.height),
        };
    }

    _nodoEn(x, y) {
        return this.nodos.find(n => Math.hypot(n.x - x, n.y - y) < Math.max(n.radio || 8, 12));
    }

    _nodoCausa(nodoId) {
        return this.cadenas.find(c => c.causa === nodoId);
    }

    _nodoEfecto(nodoId) {
        return this.cadenas.find(c => c.efectos.includes(nodoId));
    }

    _onDown(e) {
        const { x, y } = this._coords(e);
        const nodo = this._nodoEn(x, y);

        if (nodo) {
            // Click en nodo existente → selección
            this.seleccionado = nodo;
            this.dragNodo = nodo;
            this.dragOffset = { x: nodo.x - x, y: nodo.y - y };
            this._actualizarPanel();
        } else {
            // Click en vacío → deseleccionar
            this.seleccionado = null;
            this._actualizarPanel();
        }
    }

    _onMove(e) {
        if (!this.dragNodo) return;
        const { x, y } = this._coords(e);
        this.dragNodo.x = x + this.dragOffset.x;
        this.dragNodo.y = y + this.dragOffset.y;
    }

    _onUp() {
        this.dragNodo = null;
    }

    async cargar() {
        // FIX: pestaña oculta → no consumir batería/banda
        if (document.hidden) return;

        try {
            const auth = this._authHeaders();

            // Cargar audit trail — fuente del Portero AÚN NO VERIFICADA:
            // si no existe o falla, se muestra el estado honesto en el panel.
            const res = await fetch('/api/portero/audit?n=80', { headers: auth });
            this.porteroDisponible = res.ok;
            const audit = res.ok ? await res.json() : { lineas: [] };
            if (!Array.isArray(audit.lineas)) audit.lineas = [];

            // Cargar latido de Umbra Pulse 9.1
            const pulseRes = await fetch('/api/umbra-pulse/latido', { headers: auth });
            const pulse = pulseRes.ok ? await pulseRes.json() : null;
            this.latidoPulse = pulse;
            this.tormenta = !!(pulse && pulse.nivel_umbra === 'ROJO');

            // Cargar anomalías como nodos especiales
            const anomRes = await fetch('/api/umbra-pulse/anomalias', { headers: auth });
            const anomalias = anomRes.ok ? await anomRes.json() : { anomalias: [] };
            if (!Array.isArray(anomalias.anomalias)) anomalias.anomalias = [];

            const ids = new Set(this.nodos.map(n => n.id));

            // Nodos del audit
            audit.lineas.forEach(linea => {
                const partes = String(linea).split('|');
                if (partes.length < 4) return;
                const [hash, ts, tool, ok] = partes;
                const id = hash.slice(0, 12);
                if (!ids.has(id)) {
                    this._agregarNodo({ id, tool, ts, ok: String(ok).includes('True') });
                }
            });

            // Nodos de anomalías (tipo especial, color púrpura)
            anomalias.anomalias.slice(-5).forEach((anom, i) => {
                const id = `anom_${i}_${anom.host}`;
                if (!ids.has(id)) {
                    this._agregarNodo({
                        id, tool: `⚠ ${anom.host}`, ts: anom.ts, ok: false,
                        tipo: 'anomalia', score: anom.score_gw
                    });
                }
            });

            // FIX: tope de nodos — los más viejos se van
            if (this.nodos.length > this.MAX_NODOS) {
                this.nodos = this.nodos.slice(-this.MAX_NODOS);
            }
        } catch (err) {
            console.warn('[Nexus] No se pudo cargar datos:', err.message);
        }
    }

    _agregarNodo(datos) {
        const cx = this.cv.width / 2, cy = this.cv.height / 2;

        const nodo = {
            id: datos.id,
            tool: datos.tool,
            ts: datos.ts,
            ok: datos.ok,
            tipo: datos.tipo || 'normal',
            score: datos.score,
            x: cx + (Math.random() - .5) * 320,
            y: cy + (Math.random() - .5) * 320,
            vx: (Math.random() - .5) * .4,
            vy: (Math.random() - .5) * .4,
            nacido: Date.now(),
            radio: 0,
            pulsoExtra: 0,       // para parpadeos visuales de cadenas
            cadenaIdx: -1,      // índice en cadenas[] si es causa
        };
        this.nodos.push(nodo);
    }

    // ─── Encadenamiento causal automático ────────────────────────────────

    _detectarCadenas() {
        /**
         * Heurística simple: dos nodos se encadenan si:
         * 1. Un nodo fallido (ok=false) causa que el siguiente (mismo tool) se marque como efecto
         * 2. Contexto temporal: errores seguidos dentro de 2 min
         * 3. Mismo tool en <30s
         */
        const nuevo_hash = new Map(); // causa → efectos[]

        const porTool = new Map();
        for (const n of this.nodos) {
            if (!porTool.has(n.tool)) porTool.set(n.tool, []);
            porTool.get(n.tool).push(n);
        }

        for (const [tool, nodos] of porTool) {
            // Ordenar por timestamp
            nodos.sort((a, b) => (a.ts || '').localeCompare(b.ts || ''));

            for (let i = 0; i < nodos.length - 1; i++) {
                const a = nodos[i], b = nodos[i + 1];
                if (!a.ts || !b.ts) continue;

                const diff = this._tsDiff(a.ts, b.ts);
                if (diff === null) continue;

                // Regla: error seguido de cualquier acción → encadenar como causa
                if (!a.ok && diff < 120) {  // <2 min
                    if (!nuevo_hash.has(a.id)) nuevo_hash.set(a.id, []);
                    nuevo_hash.get(a.id).push(b.id);
                }

                // Regla: mismo tool en <30s → probable causalidad
                if (a.tool === b.tool && diff < 30 && a.id !== b.id) {
                    if (!nuevo_hash.has(a.id)) nuevo_hash.set(a.id, []);
                    if (!nuevo_hash.get(a.id).includes(b.id)) {
                        nuevo_hash.get(a.id).push(b.id);
                    }
                }
            }
        }

        // Construir objeto de cadenas
        this.cadenas = [];
        for (const [causa, efectos] of nuevo_hash) {
            this.cadenas.push({ causa, efectos });
        }

        // Asignar índice de cadena a nodos causa
        for (let i = 0; i < this.cadenas.length; i++) {
            const causaNodo = this.nodos.find(n => n.id === this.cadenas[i].causa);
            if (causaNodo) causaNodo.cadenaIdx = i;
        }
    }

    _tsDiff(tsA, tsB) {
        try {
            const a = new Date(tsA).getTime();
            const b = new Date(tsB).getTime();
            if (isNaN(a) || isNaN(b)) return null;
            return (b - a) / 1000;
        } catch { return null; }
    }

    // ─── Física con tormenta ────────────────────────────────────────────────

    fisica() {
        const cx = this.cv.width / 2, cy = this.cv.height / 2;
        const temblor = this.tormenta ? (Math.random() - .5) * 3 : 0;

        for (const n of this.nodos) {
            // Gravedad hacia el centro
            n.vx += (cx - n.x) * 0.00006;
            n.vy += (cy - n.y) * 0.00006;

            // Repulsión entre nodos
            for (const m of this.nodos) {
                if (n === m) continue;
                const dx = n.x - m.x, dy = n.y - m.y;
                const d2 = dx * dx + dy * dy;
                if (d2 < 4000 && d2 > 0) {
                    const f = 10 / d2;
                    n.vx += dx * f; n.vy += dy * f;
                }
            }

            // Amortiguación
            n.vx *= 0.97; n.vy *= 0.97;

            // Aplicar velocidad + temblor
            n.x += n.vx + temblor;
            n.y += n.vy + temblor;

            // Mantener dentro del canvas
            n.x = Math.max(20, Math.min(this.cv.width - 20, n.x));
            n.y = Math.max(20, Math.min(this.cv.height - 20, n.y));

            // Pulso de nacimiento
            const edad = Date.now() - n.nacido;
            n.radio = Math.min(n.ok ? 5 : (n.tipo === 'anomalia' ? 7 : 6), edad / 300);

            // Pulso extra en cadenas (causa/parpadeo de efecto)
            if (n.cadenaIdx >= 0) {
                // El efecto parpadea al ritmo de la causa
                n.pulsoExtra = Math.sin(this.t * 0.12 + n.cadenaIdx) * 2;
            } else if (this._nodoEfecto(n.id)) {
                // Nodo que es efecto: parpadeo suave
                n.pulsoExtra = Math.abs(Math.sin(this.t * 0.15)) * 3;
            } else {
                n.pulsoExtra = 0;
            }
        }

        this._detectarCadenas();
    }

    // ─── Renderizado ────────────────────────────────────────────────────────

    render() {
        this.ctx.clearRect(0, 0, this.cv.width, this.cv.height);

        // Modo tormenta: fondo rojo oscuro pulsante
        if (this.tormenta) {
            const alfa = 0.08 + Math.sin(this.t * 0.1) * 0.03;
            this.ctx.fillStyle = `rgba(60, 0, 0, ${alfa})`;
            this.ctx.fillRect(0, 0, this.cv.width, this.cv.height);
        }

        // ── Líneas de cadena causal ──
        this.ctx.lineWidth = 1.5;
        for (const cadena of this.cadenas) {
            const causa = this.nodos.find(n => n.id === cadena.causa);
            if (!causa) continue;

            for (const efectoId of cadena.efectos) {
                const efecto = this.nodos.find(n => n.id === efectoId);
                if (!efecto) continue;

                const dist = Math.hypot(causa.x - efecto.x, causa.y - efecto.y);
                const alfa = Math.max(0.1, 1 - dist / 200);
                this.ctx.strokeStyle = `rgba(180, 80, 220, ${alfa})`;
                this.ctx.setLineDash([4, 3]);
                this.ctx.beginPath();
                this.ctx.moveTo(causa.x, causa.y);
                this.ctx.lineTo(efecto.x, efecto.y);
                this.ctx.stroke();
                this.ctx.setLineDash([]);
            }
        }

        // ── Conexiones de proximidad (como 9.0) ──
        this.ctx.strokeStyle = 'rgba(212, 160, 23, 0.18)';
        this.ctx.lineWidth = 0.8;
        for (let i = 0; i < this.nodos.length; i++) {
            for (let j = i + 1; j < this.nodos.length; j++) {
                const a = this.nodos[i], b = this.nodos[j];
                const d = Math.hypot(a.x - b.x, a.y - b.y);
                if (d < 120) {
                    this.ctx.globalAlpha = 1 - d / 120;
                    this.ctx.beginPath();
                    this.ctx.moveTo(a.x, a.y);
                    this.ctx.lineTo(b.x, b.y);
                    this.ctx.stroke();
                }
            }
        }
        this.ctx.globalAlpha = 1;
        this.ctx.lineWidth = 1;

        // ── Nodos ──
        for (const n of this.nodos) {
            const isCausa = n.cadenaIdx >= 0;
            const isEfecto = !!this._nodoEfecto(n.id);
            const r = n.radio + n.pulsoExtra;

            // Aura para nodos en cadenas
            if (isCausa || isEfecto) {
                const auraAlfa = 0.15 + Math.abs(Math.sin(this.t * 0.1)) * 0.1;
                this.ctx.beginPath();
                this.ctx.arc(n.x, n.y, r + 5, 0, Math.PI * 2);
                this.ctx.fillStyle = `rgba(180, 80, 220, ${auraAlfa})`;
                this.ctx.fill();
            }

            // Nodo
            this.ctx.beginPath();
            this.ctx.arc(n.x, n.y, Math.max(r, 1), 0, Math.PI * 2);
            if (n.tipo === 'anomalia') {
                this.ctx.fillStyle = '#b450dc';
            } else if (n.ok) {
                this.ctx.fillStyle = '#64b4ff';
            } else {
                this.ctx.fillStyle = '#ff5555';
            }
            this.ctx.fill();

            // Selección: anillo dorado
            if (this.seleccionado === n) {
                this.ctx.beginPath();
                this.ctx.arc(n.x, n.y, r + 4, 0, Math.PI * 2);
                this.ctx.strokeStyle = '#d4a017';
                this.ctx.lineWidth = 1.5;
                this.ctx.stroke();
                this.ctx.lineWidth = 1;
            }
        }

        // ── Estrella polar con score de Umbra Pulse ──
        if (this.latidoPulse) {
            const score = this.latidoPulse.score;
            if (typeof score === 'number') {
                const x = this.cv.width - 40, y = 40;
                const alfa = 0.5 + score * 0.5;
                this.ctx.save();
                this.ctx.translate(x, y);
                this.ctx.rotate(this.t * 0.01 * (this.tormenta ? 3 : 1));
                this.ctx.beginPath();
                for (let i = 0; i < 8; i++) {
                    const ang = (i * Math.PI) / 4;
                    const rr = i % 2 === 0 ? 14 : 5;
                    this.ctx.lineTo(Math.cos(ang) * rr, Math.sin(ang) * rr);
                }
                this.ctx.closePath();
                this.ctx.fillStyle = this.tormenta
                    ? `rgba(255, 68, 68, ${alfa})`
                    : `rgba(212, 160, 23, ${alfa})`;
                this.ctx.fill();
                this.ctx.restore();
            }
        }

        this.t++;
    }

    // ─── Panel lateral de cadenas ─────────────────────────────────────────

    _actualizarPanel() {
        if (!this.panel) return;
        const comoCausa = this.cadenas.filter(c => c.causa === (this.seleccionado && this.seleccionado.id));
        const comoEfecto = this.seleccionado ? this.cadenas.filter(c => c.efectos.includes(this.seleccionado.id)) : [];

        this.panel.innerHTML = `
            <div class="nexus-panel-header">⛓ NEXUS 9.1</div>
            <div class="nexus-panel-sub">${this.nodos.length} nodos · ${this.cadenas.length} cadenas</div>
            ${this.porteroDisponible === false ? '<div class="nexus-no-chain">Portero sin datos (fuente aún no verificada)</div>' : ''}
            ${this.latidoPulse && this.latidoPulse.nivel_umbra ? `<div class="nexus-detail">Umbra: ${this.latidoPulse.nivel_umbra} (${this.latidoPulse.score ?? '—'})</div>` : '<div class="nexus-detail">Umbra: SIN_DATOS</div>'}
            ${this.seleccionado ? `
                <div class="nexus-section-title">Nodo</div>
                <div class="nexus-detail">${this.seleccionado.tool}</div>
                ${this.seleccionado.ts ? `<div class="nexus-detail">${this.seleccionado.ts}</div>` : ''}
            ` : ''}
            ${comoCausa.length > 0 ? `
                <div class="nexus-section-title">Causa de:</div>
                ${comoCausa.map(c => c.efectos.map(eid => {
                    const e = this.nodos.find(n => n.id === eid);
                    return `<div class="nexus-chain"><span class="chain-effect">${e ? e.tool.slice(0, 15) : eid}</span></div>`;
                }).join('')).join('')}
            ` : ''}
            ${comoEfecto.length > 0 ? `
                <div class="nexus-section-title">Efecto de:</div>
                ${comoEfecto.map(c => {
                    const causa = this.nodos.find(n => n.id === c.causa);
                    return `<div class="nexus-cause-item">${causa ? causa.tool.slice(0, 15) : c.causa}</div>`;
                }).join('')}
            ` : ''}
            ${this.seleccionado && comoCausa.length === 0 && comoEfecto.length === 0 ? '<div class="nexus-no-chain">Sin cadena causal</div>' : ''}
            ${this.tormenta ? '<div class="nexus-tormenta">⛈ TORMENTA</div>' : ''}
        `;
    }

    // ─── Drag para encadenar manualmente ──────────────────────────────────

    crearCadenaManual(causaId, efectoId) {
        if (causaId === efectoId) return;
        const existente = this.cadenas.find(c =>
            c.causa === causaId && c.efectos.includes(efectoId)
        );
        if (!existente) {
            this.cadenas.push({ causa: causaId, efectos: [efectoId] });
            this._actualizarPanel();
        }
    }

    // ─── Loop principal ────────────────────────────────────────────────────

    async iniciar() {
        await this.cargar();
        setInterval(() => this.cargar(), 12000);  // 12s — se auto-pausa si document.hidden

        const loop = () => {
            this.fisica();
            this.render();
            requestAnimationFrame(loop);
        };
        loop();
    }
}

// Auto-iniciar
document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('audit-canvas')) {
        const nexus = new ConstellationNexus('audit-canvas', 'nexus-panel');
        nexus.iniciar();
        window._nexus = nexus;  // export para consola
    }
});
