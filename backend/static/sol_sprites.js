/* ═══════════════════════════════════════════════════════════════════
   ☀️ SOL SPRITES v5.3 — Módulo EXTRA de poses y direcciones
   ─────────────────────────────────────────────────────────────────
   FUNCIÓN EXTRA — NO REEMPLAZA NADA (🚧 regla de Harold 2026-09-07)

   Este módulo se carga DESPUÉS del holograma y AÑADE:
   · SPR: los 4 sprites de pose (offer / hold / side_walk / back)
   · DIR: mapa de direcciones → sprite + flip
   · interactUntil: estado de pose al tocar su rostro
   · stepSol(): asigna sprite según movimiento o reposo
   · setSprite(): crossfade suave con FALLBACK triple — ruta del
     backend → assets/ → sol_avatar_full.png. Si un sprite aún
     no existe (404), el holograma sigue vivo igual. Nunca rompe.

   Si el holograma ya tiene su propio sistema de movimiento, este
   módulo no lo toca: solo expone window.SolSprites para que la
   lógica existente lo use si quiere.
   ═══════════════════════════════════════════════════════════════════ */
(function () {
  'use strict';

  // ── El mapa de direcciones y estados (v5.3) ──────────────────
  // Cada sprite tiene sus paths candidatos en orden: ruta del
  // backend (sol_api.py) → assets/ estático → nada (fallback full).
  const SPR = {
    offer: ['/sol_offer.png', 'assets/sol_offer.png'],      // frontal ofreciendo rosa
    hold:  ['/sol_hold.png', 'assets/sol_hold.png'],       // frontal rosa al pecho (reposo)
    side:  ['/sol_side_walk.png', 'assets/sol_side_walk.png'], // perfil en paso
    back:  ['/sol_back.png', 'assets/sol_back.png']        // espalda
  };
  const DIR = {
    S: ['offer', 0], SW: ['side', 0], SE: ['side', 1],
    W: ['side', 0],  E: ['side', 1],
    N: ['back', 0],  NW: ['back', 0], NE: ['back', 1]
  };

  let interactUntil = 0;

  // ── Detección del host ────────────────────────────────────────
  const img = document.getElementById('sol-body') ||
              document.querySelector('img[id*="sol"]');
  const FALLBACK = '/sol_avatar_full.png';

  // ── Precarga con resolución multi-path y fallback silencioso ──
  const loaded = {};
  function tryLoad(src) {
    return new Promise(resolve => {
      const im = new Image();
      im.onload = () => resolve(im);
      im.onerror = () => resolve(null);       // 404 → probar siguiente
      im.src = src;
    });
  }
  function preload(name) {
    if (loaded[name] !== undefined) return loaded[name];
    const paths = SPR[name] || [];
    loaded[name] = (async () => {
      for (const p of paths) {
        const im = await tryLoad(p);
        if (im) return im;
      }
      return null;                            // no existe → fallback
    })();
    return loaded[name];
  }
  Object.keys(SPR).forEach(preload);

  // ── setSprite: crossfade suave, nunca rompe ────────────────────
  let curName = null, curFlip = 0;
  async function setSprite(name, flip) {
    if (!img) return;                        // sin host, sin problema
    if (curName === name && curFlip === flip) return;
    const im = await preload(name);
    curName = name; curFlip = flip || 0;
    const src = im ? im.src : FALLBACK;
    img.style.transition = 'opacity .18s ease';
    img.style.opacity = '0';
    setTimeout(() => {
      img.src = src;
      img.style.transform = curFlip
        ? 'translate(-50%,-50%) scaleX(-1)'
        : 'translate(-50%,-50%)';
      img.style.opacity = '1';
    }, 180);
  }

  // ── stepSol: camina o descansa, con poses ──────────────────────
  // moving: bool — si se está desplazando
  // dx,dy: dirección del movimiento en píxeles
  function stepSol(t, moving, dx, dy) {
    if (moving) {
      // lógica de dirección: elige sprite según el vector de avance
      let d = 'S';
      if (dx < -2 && Math.abs(dy) < Math.abs(dx)) d = 'W';
      else if (dx > 2 && Math.abs(dy) < Math.abs(dx)) d = 'E';
      else if (dy < -2) d = Math.abs(dx) > 2 ? (dx > 0 ? 'NE' : 'NW') : 'N';
      else if (dy > 2) d = Math.abs(dx) > 2 ? (dx > 0 ? 'SE' : 'SW') : 'S';
      const m = DIR[d] || DIR.S;
      setSprite(m[0], m[1]);
    } else {
      // quieta: ofrece la rosa si interactuaste hace <2.5 s, si no, reposo
      setSprite(t < interactUntil ? 'offer' : 'hold', 0);
    }
  }

  // ── Zona de corazones: tocar su rostro ────────────────────────
  // Añade SU propio listener (no reemplaza los del holograma):
  // un toque en su zona la hace ofrecerte la rosa un momento.
  if (img) {
    document.addEventListener('pointerdown', ev => {
      const r = img.getBoundingClientRect();
      const cx = r.left + r.width / 2, top = r.top + r.height * 0.28;
      const dist = Math.hypot(ev.clientX - cx, ev.clientY - top);
      if (dist < r.width * 0.35) {
        interactUntil = performance.now() / 1000 + 2.5; // se queda ofreciéndote la rosa
      }
    }, { passive: true });
  }

  // ── API pública: función EXTRA para ella ──────────────────────
  window.SolSprites = {
    SPR, DIR,
    get interactUntil() { return interactUntil; },
    touch()      { interactUntil = performance.now() / 1000 + 2.5; },
    stepSol,     // para que el holograma existente lo llame si quiere
    setSprite,
    // versión del reloj del holograma (t en segundos) por si no la tienen
    now: () => performance.now() / 1000
  };

  // ── Auto-integración NO INVASIVA ───────────────────────────────
  // Si el holograma NO tiene sistema de movimiento propio (v5.2 repo),
  // este módulo NO impone nada: Sol sigue con su sway idle de siempre.
  // Solo cuando algo llama a SolSprites.stepSol() entran las poses.
  // Así es función extra de verdad: se activa cuando ella la usa. 🌹
})();
