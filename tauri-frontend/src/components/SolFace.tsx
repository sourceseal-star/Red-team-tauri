import { useEffect, useRef } from 'react';

// ═══════════════════════════════════════════════════════════════
// SolFace — rostro animado real de Sol (canvas, no imagen estática)
// Parpadeo real, mirada que deriva sola, boca que se mueve al hablar,
// expresión que cambia según el ánimo. Reemplaza el <img> estático.
// ═══════════════════════════════════════════════════════════════

interface SolFaceProps {
  speaking?: boolean;
  mood?: number; // -2 (triste) .. 0 (neutral) .. 2 (feliz)
  size?: number; // resolución interna de dibujo en px (no el tamaño visual)
}

interface FaceState {
  blink: number;
  gazeX: number;
  gazeY: number;
  mouthOpen: number;
  lastTime: number;
}

export const SolFace = ({ speaking = false, mood = 0, size = 200 }: SolFaceProps) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const speakingRef = useRef(speaking);
  const moodRef = useRef(mood);
  speakingRef.current = speaking;
  moodRef.current = mood;

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const DPR = Math.min(window.devicePixelRatio || 1, 2);
    const W = size * DPR, H = size * DPR;
    canvas.width = W;
    canvas.height = H;
    canvas.style.width = '100%';
    canvas.style.height = '100%';

    const s: FaceState = { blink: 0, gazeX: 0, gazeY: 0, mouthOpen: 0, lastTime: 0 };
    let raf = 0;

    const drawEye = (ex: number, ey: number, er: number, pr: number) => {
      ctx.beginPath();
      ctx.ellipse(ex, ey, er, s.blink > 0 ? er * 0.08 : er * 0.85, 0, 0, Math.PI * 2);
      ctx.fillStyle = '#fefefe';
      ctx.fill();
      ctx.strokeStyle = 'rgba(150,130,110,0.5)';
      ctx.lineWidth = 1;
      ctx.stroke();
      if (s.blink > 0) return;
      const ix = ex + s.gazeX * er * 0.4;
      const iy = ey + s.gazeY * er * 0.3;
      const g = ctx.createRadialGradient(ix - pr * 0.4, iy - pr * 0.4, pr * 0.3, ix, iy, pr);
      g.addColorStop(0, '#8b6b4a');
      g.addColorStop(0.6, '#6a4f3a');
      g.addColorStop(1, '#3a281a');
      ctx.beginPath();
      ctx.ellipse(ix, iy, pr, pr * 1.05, 0, 0, Math.PI * 2);
      ctx.fillStyle = g;
      ctx.fill();
      ctx.beginPath();
      ctx.arc(ix, iy, pr * 0.5, 0, Math.PI * 2);
      ctx.fillStyle = '#1a0f0a';
      ctx.fill();
      ctx.beginPath();
      ctx.arc(ix - pr * 0.3, iy - pr * 0.4, pr * 0.35, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(255,255,255,0.4)';
      ctx.fill();
    };

    const draw = () => {
      const cx = W / 2, cy = H / 2, r = W * 0.42;
      ctx.clearRect(0, 0, W, H);
      const m = moodRef.current;

      // Piel: cálida por defecto, azulada si triste, dorada si feliz
      let c1 = '#fae5d6', c2 = '#f5d6a8', c3 = '#d9b896';
      if (m <= -1) { c1 = '#dce8f2'; c2 = '#b8cfe0'; c3 = '#8fa8bd'; }
      else if (m >= 1) { c1 = '#fff2d6'; c2 = '#ffdf9e'; c3 = '#e8b96a'; }

      const grad = ctx.createRadialGradient(cx - W * 0.08, cy - W * 0.08, r * 0.3, cx, cy, r);
      grad.addColorStop(0, c1); grad.addColorStop(0.8, c2); grad.addColorStop(1, c3);
      ctx.beginPath();
      ctx.ellipse(cx, cy, r, r, 0, 0, Math.PI * 2);
      ctx.fillStyle = grad;
      ctx.fill();

      // Ojos
      const eyeY = cy - r * 0.18, eyeSp = r * 0.42, eyeR = r * 0.16, pupilR = r * 0.065;
      drawEye(cx - eyeSp, eyeY, eyeR, pupilR);
      drawEye(cx + eyeSp, eyeY, eyeR, pupilR);

      // Cejas — según ánimo
      const browY = cy - r * 0.35;
      ctx.lineWidth = r * 0.02;
      ctx.strokeStyle = 'rgba(60,45,35,0.6)';
      ctx.lineCap = 'round';
      let browOffset = 0, browCurve = 0;
      if (m >= 1) { browOffset = -r * 0.05; browCurve = -r * 0.02; }
      else if (m <= -1) { browOffset = r * 0.04; browCurve = r * 0.05; }
      [-1, 1].forEach((side) => {
        const bx = cx + side * eyeSp;
        ctx.beginPath();
        ctx.moveTo(bx - side * r * 0.22, browY + browOffset);
        ctx.quadraticCurveTo(bx - side * r * 0.08, browY + browCurve - r * 0.02, bx + side * r * 0.04, browY + browOffset);
        ctx.stroke();
      });

      // Boca — se mueve de verdad cuando habla
      const my = cy + r * 0.32;
      ctx.strokeStyle = 'rgba(170,90,70,0.75)';
      ctx.lineWidth = r * 0.018;
      const talkAmp = speakingRef.current ? 0.15 + s.mouthOpen * 0.25 : 0.04;
      ctx.beginPath();
      if (m <= -1 && !speakingRef.current) {
        ctx.arc(cx, my + r * 0.08, r * 0.18, Math.PI * 1.15, Math.PI * 1.85);
      } else if (m >= 1 && !speakingRef.current) {
        ctx.arc(cx, my - r * 0.02, r * 0.2, Math.PI * 0.08, Math.PI * 0.92);
      } else {
        ctx.ellipse(cx, my, r * 0.16, r * talkAmp, 0, 0, Math.PI * 2);
      }
      ctx.stroke();
      if (speakingRef.current) {
        ctx.fillStyle = 'rgba(90,40,35,0.35)';
        ctx.beginPath();
        ctx.ellipse(cx, my, r * 0.13, r * talkAmp * 0.8, 0, 0, Math.PI * 2);
        ctx.fill();
      }
    };

    const loop = (t: number) => {
      const dt = s.lastTime ? (t - s.lastTime) / 1000 : 0.016;
      s.lastTime = t;

      // Parpadeo real, periódico y aleatorio
      if (s.blink > 0) { s.blink -= dt * 9; if (s.blink < 0) s.blink = 0; }
      else if (Math.random() < dt * 0.28) s.blink = 1;

      // Mirada que deriva sola, como alguien pensando
      s.gazeX *= 0.94; s.gazeY *= 0.94;
      if (Math.abs(s.gazeX) < 0.01 && Math.abs(s.gazeY) < 0.01 && Math.random() < dt * 0.06) {
        s.gazeX = (Math.random() - 0.5) * 0.6;
        s.gazeY = (Math.random() - 0.5) * 0.4;
      }

      // Boca al hablar — apertura pseudoaleatoria (pseudo lip-sync)
      if (speakingRef.current) {
        s.mouthOpen = 0.4 + Math.abs(Math.sin(t / 90)) * 0.6 * Math.random();
      } else {
        s.mouthOpen *= 0.9;
      }

      draw();
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);

    return () => cancelAnimationFrame(raf);
  }, [size]);

  return (
    <canvas
      ref={canvasRef}
      style={{ borderRadius: '50%', display: 'block', width: '100%', height: '100%' }}
    />
  );
};
