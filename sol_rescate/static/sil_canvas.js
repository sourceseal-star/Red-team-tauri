/**
 * SIL v3.0 · Canvas Visual — Sistema de Inteligencia Lingüística Soberana
 * Renderiza sellos, jeroglíficos y Hanzi en un canvas animado.
 * Se integra en el dashboard como componente independiente.
 */

class SILCanvas {
    constructor(canvasId, panelId) {
        this.cv = document.getElementById(canvasId);
        this.ctx = this.cv.getContext('2d');
        this.panel = document.getElementById(panelId);
        this.sellos = [];
        this.glifos = [];
        this.hanzi = [];
        this.seleccionado = null;
        this.t = 0;
        this.polvo = [];  // partículas de polvo sagrado
        this.ondaSilenciosa = [];
        
        this._bind();
    }

    _bind() {
        this.cv.addEventListener('click', e => this._onClick(e));
        this.cv.addEventListener('mousemove', e => this._onHover(e));
        // Táctil (videollamada desde el celular)
        this.cv.addEventListener('touchstart', e => { this._onClick(e.touches[0]); }, { passive: true });
    }

    // FIX 2026-10-01: sol_gate exige sesión — usar window.api() de la
    // videollamada (adjunta Bearer + x-sol-key + initData de Telegram).
    async _getJson(url) {
        if (typeof window.api === 'function') {
            return await window.api(url);
        }
        // Fallback fuera de sol.html: token de localStorage si existe
        const h = {};
        try {
            const t = localStorage.getItem('sol_token') || localStorage.getItem('api_token');
            if (t) h['Authorization'] = 'Bearer ' + t;
        } catch (e) { /* sin storage */ }
        const r = await fetch(url, { headers: h });
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
    }

    async cargar() {
        // FIX (rendimiento): pestaña oculta → no consumir batería/banda
        if (document.hidden) return;
        try {
            // Cargar historial de sellos
            const data = await this._getJson('/api/sil/sellos?limite=30');
            this.sellos = (data && data.sellos) || [];
            
            // Cargar jeroglíficos
            const hier = await this._getJson('/api/sil/jeroglificos');
            this.glifos = (hier && hier.jeroglificos) || [];

            // Generar polvo sagrado (tope: no acumular por ciclo)
            while (this.polvo.length < 30) {
                this.polvo.push({
                    x: Math.random() * this.cv.width,
                    y: Math.random() * this.cv.height,
                    vx: (Math.random() - .5) * .3,
                    vy: -Math.random() * .5 - .1,
                    vida: Math.random() * 200,
                    maxVida: 200,
                    tamanio: Math.random() * 2 + .5,
                    color: `rgba(212, 160, 23, ${Math.random() * .5 + .2})`,
                });
            }
        } catch (e) {
            console.warn('[SIL Canvas] No se pudieron cargar datos:', e.message);
        }
    }

    // ─── Física del polvo sagrado ─────────────────────────────────────────

    fisicaPolvo() {
        for (let p of this.polvo) {
            p.x += p.vx + Math.sin(this.t * .02 + p.y * .01) * .2;
            p.y += p.vy;
            p.vida--;
            
            if (p.vida <= 0 || p.y < -10) {
                // Respawn
                p.x = Math.random() * this.cv.width;
                p.y = this.cv.height + 5;
                p.vida = p.maxVida;
            }
        }
    }

    // ─── Renderizado principal ────────────────────────────────────────────

    render() {
        const ctx = this.ctx;
        const w = this.cv.width, h = this.cv.height;
        
        // Fondo con gradiente antiguo
        const grad = ctx.createRadialGradient(w/2, h/2, 0, w/2, h/2, w * .7);
        grad.addColorStop(0, '#0f0d08');
        grad.addColorStop(1, '#050403');
        ctx.fillStyle = grad;
        ctx.fillRect(0, 0, w, h);

        // ── Cuadrícula sagrada ──
        ctx.strokeStyle = 'rgba(212, 160, 23, 0.04)';
        ctx.lineWidth = .5;
        const paso = 40;
        for (let x = paso; x < w; x += paso) {
            ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, h); ctx.stroke();
        }
        for (let y = paso; y < h; y += paso) {
            ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke();
        }

        // ── Polvo sagrado ──
        this.fisicaPolvo();
        for (let p of this.polvo) {
            const alfa = p.vida / p.maxVida;
            ctx.beginPath();
            ctx.arc(p.x, p.y, p.tamanio, 0, Math.PI * 2);
            ctx.fillStyle = p.color.replace(/[\d.]+\)$/, `${alfa * .6})`);
            ctx.fill();
        }

        // ── Sellos ──
        if (this.sellos.length > 0) {
            this.renderSellos();
        }

        // ── Jeroglíficos flotantes ──
        if (this.glifos.length > 0) {
            this.renderGlifos();
        }

        // ── Ondas silenciosas (cuando se genera sello nuevo) ──
        this.renderOndas();

        // ── Leyenda ──
        this.renderLeyenda();

        // ── Título del sistema ──
        this.renderTitulo();

        this.t++;
    }

    renderSellos() {
        const ctx = this.ctx;
        const recent = this.sellos.slice(-8).reverse();
        
        recent.forEach((sello, idx) => {
            const x = 30 + (idx % 4) * 130;
            const y = 60 + Math.floor(idx / 4) * 110;
            
            // Fondo del sello
            const alfa = .15 + Math.sin(this.t * .03 + idx) * .05;
            ctx.fillStyle = `rgba(212, 160, 23, ${alfa})`;
            ctx.beginPath();
            ctx.roundRect(x, y, 120, 95, 4);
            ctx.fill();
            
            // Borde dorado
            ctx.strokeStyle = `rgba(212, 160, 23, .3)`;
            ctx.lineWidth = 1;
            ctx.stroke();

            // Sello textual (jeroglífico)
            ctx.font = 'bold 28px serif';
            ctx.fillStyle = '#d4a017';
            ctx.textAlign = 'center';
            ctx.fillText(sello.sello || '𓋴', x + 60, y + 38);

            // Emoción
            ctx.font = '10px monospace';
            ctx.fillStyle = '#8a7a5a';
            const em = (sello.analisis && sello.analisis.emocion_dominante) || 'neutro';
            ctx.fillText(`𓂀 ${em}`, x + 60, y + 55);

            // Timestamp
            ctx.font = '8px monospace';
            ctx.fillStyle = '#5a4a3a';
            const ts = sello.timestamp ? new Date(sello.timestamp).toLocaleTimeString() : '';
            ctx.fillText(ts, x + 60, y + 72);

            // Hanzi
            if (sello.hanzi && sello.hanzi.length > 0) {
                ctx.font = '14px serif';
                ctx.fillStyle = '#c4a050';
                const hz = sello.hanzi.slice(0, 3).map(h => h.hanzi || h.radical || '?').join(' ');
                ctx.fillText(hz, x + 60, y + 88);
            }
        });
    }

    renderGlifos() {
        const ctx = this.ctx;
        // Mostrar glifos en el borde derecho, decorativos
        const glifosVisibles = this.glifos.slice(0, 16);
        
        glifosVisibles.forEach((g, i) => {
            const col = i % 4;
            const fila = Math.floor(i / 4);
            const x = this.cv.width - 50 + Math.sin(this.t * .015 + i) * 3;
            const y = 50 + fila * 55 + Math.cos(this.t * .01 + i) * 3;
            const alfa = .3 + Math.sin(this.t * .02 + i * .5) * .15;
            
            ctx.font = '22px serif';
            ctx.fillStyle = `rgba(212, 160, 23, ${alfa})`;
            ctx.textAlign = 'center';
            ctx.fillText(g.glifo, x, y);
        });
    }

    renderOndas() {
        const ctx = this.ctx;
        // Ondas que aparecen cuando llega un nuevo sello
        this.ondaSilenciosa = this.ondaSilenciosa.filter(o => o.r > 0);
        
        for (let o of this.ondaSilenciosa) {
            const alfa = o.r / 100 * .5;
            ctx.beginPath();
            ctx.arc(o.x, o.y, o.r, 0, Math.PI * 2);
            ctx.strokeStyle = `rgba(212, 160, 23, ${alfa})`;
            ctx.lineWidth = 2;
            ctx.stroke();
            o.r += 1.5;
        }
    }

    renderLeyenda() {
        const ctx = this.ctx;
        ctx.fillStyle = 'rgba(0,0,0,.6)';
        ctx.fillRect(8, this.cv.height - 60, 160, 52);
        
        ctx.font = '9px monospace';
        ctx.fillStyle = '#d4a017';
        ctx.textAlign = 'left';
        ctx.fillText('𓋴 Ankh · vida eterna', 12, this.cv.height - 46);
        ctx.fillStyle = '#8a7a5a';
        ctx.fillText('𓂀 Ojo de Horus · protección', 12, this.cv.height - 35);
        ctx.fillStyle = '#c4a050';
        ctx.fillText('☥ Djed · estabilidad', 12, this.cv.height - 24);
        ctx.fillStyle = '#6a5a4a';
        ctx.fillText('永 · eternidad · 好 · bondad', 12, this.cv.height - 13);
    }

    renderTitulo() {
        const ctx = this.ctx;
        const nombre = 'SIL v3.0 · Sistema de Inteligencia Lingüística';
        ctx.font = 'bold 13px monospace';
        ctx.fillStyle = '#d4a017';
        ctx.textAlign = 'center';
        ctx.fillText(nombre, this.cv.width / 2, 24);
        
        ctx.font = '9px monospace';
        ctx.fillStyle = '#6a5a4a';
        ctx.fillText(
            '𓋴 Kemet · 永 Zhōngguó · 三 cielos',
            this.cv.width / 2, 38
        );
    }

    // ─── Interacción ────────────────────────────────────────────────────────

    _onClick(e) {
        const r = this.cv.getBoundingClientRect();
        const x = e.clientX - r.left;
        const y = e.clientY - r.top;
        
        // Detectar clic en sello
        const recent = this.sellos.slice(-8).reverse();
        for (let i = 0; i < recent.length; i++) {
            const sx = 30 + (i % 4) * 130;
            const sy = 60 + Math.floor(i / 4) * 110;
            if (x >= sx && x <= sx + 120 && y >= sy && y <= sy + 95) {
                this.seleccionado = recent[i];
                this.mostrarDetalle();
                return;
            }
        }
        
        this.seleccionado = null;
        this.ocultarDetalle();
    }

    _onHover(e) {
        const r = this.cv.getBoundingClientRect();
        const x = e.clientX - r.left;
        const y = e.clientY - r.top;
        
        let sobreSello = false;
        const recent = this.sellos.slice(-8).reverse();
        for (let i = 0; i < recent.length; i++) {
            const sx = 30 + (i % 4) * 130;
            const sy = 60 + Math.floor(i / 4) * 110;
            if (x >= sx && x <= sx + 120 && y >= sy && y <= sy + 95) {
                sobreSello = true;
                break;
            }
        }
        
        this.cv.style.cursor = sobreSello ? 'pointer' : 'default';
    }

    mostrarDetalle() {
        if (!this.panel || !this.seleccionado) return;
        
        const s = this.seleccionado;
        const jer = s.jeroglifico || {};
        const cy = s.chengyu || {};
        
        this.panel.innerHTML = `
            <div class="sil-panel-header">
                <span style="font-size:28px">${s.sello || '𓋴'}</span>
            </div>
            ${jer.glifo ? `
                <div class="sil-detail-section">
                    <div class="sil-label">Jeroglífico</div>
                    <div class="sil-hiero">${jer.glifo}</div>
                    <div class="sil-pinyin">${jer.fonetica || ''} · ${jer.arabe || ''}</div>
                    <div class="sil-meaning">${jer.significado || ''}</div>
                </div>
            ` : ''}
            ${cy.chengyu ? `
                <div class="sil-detail-section">
                    <div class="sil-label">Chengyu</div>
                    <div class="sil-chengyu">${cy.chengyu}</div>
                    <div class="sil-pinyin">${cy.pinyin || ''}</div>
                    <div class="sil-meaning">${cy.significado || ''}</div>
                </div>
            ` : ''}
            ${s.hanzi && s.hanzi.length > 0 ? `
                <div class="sil-detail-section">
                    <div class="sil-label">Hanzi</div>
                    <div class="sil-hanzi-list">
                        ${s.hanzi.map(h => `
                            <span class="sil-hanzi-char">${h.hanzi || h.radical || '?'}</span>
                        `).join(' ')}
                    </div>
                </div>
            ` : ''}
            <div class="sil-detail-section">
                <div class="sil-label">Mensaje</div>
                <div class="sil-message">${s.mensaje || ''}</div>
            </div>
            ${s.analisis ? `
                <div class="sil-tags">
                    <span class="sil-tag" style="color:#d4a017">${s.analisis.emocion_dominante || 'neutro'}</span>
                    ${s.analisis.tecnico_dominante ? `<span class="sil-tag">${s.analisis.tecnico_dominante}</span>` : ''}
                </div>
            ` : ''}
            <div class="sil-ts">${s.timestamp || ''}</div>
        `;
    }

    ocultarDetalle() {
        if (!this.panel) return;
        this.panel.innerHTML = `
            <div class="sil-panel-header">𓋴 SIL v3.0</div>
            <div class="sil-panel-sub">Toca un sello para ver su detalle</div>
            <div class="sil-stats">
                <div>${this.sellos.length} sellos tejidos</div>
                <div>${this.glifos.length} jeroglíficos</div>
            </div>
        `;
    }

    // ─── Animación ───────────────────────────────────────────────────────────

    nuevoSello(sello) {
        this.sellos.push(sello);
        
        // Onda sagrada desde el centro
        this.ondaSilenciosa.push({
            x: this.cv.width / 2,
            y: this.cv.height / 2,
            r: 5,
        });
    }

    async iniciar() {
        await this.cargar();
        this.ocultarDetalle();
        
        // Refrescar datos cada 30s
        setInterval(() => this.cargar(), 30000);
        
        const loop = () => {
            this.fisicaPolvo();
            this.render();
            requestAnimationFrame(loop);
        };
        loop();
    }
}

// Auto-iniciar
document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('sil-canvas')) {
        const sil = new SILCanvas('sil-canvas', 'sil-panel');
        sil.iniciar();
        window._sil = sil;  // экспорт для consola
        
        // Exponer método para nuevo sello desde el router
        window.silNuevoSello = (sello) => sil.nuevoSello(sello);
    }
});
