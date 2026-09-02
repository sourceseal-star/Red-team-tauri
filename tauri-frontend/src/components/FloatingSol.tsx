import { useEffect, useState, useRef, useCallback } from 'react';

// ═══════════════════════════════════════════════════════════════
// Sol — presencia viva en el dashboard (modo videollamada holográfica)
// No es un blog. Es Sol, presente y respirando.
// ═══════════════════════════════════════════════════════════════

const PERSONALITIES = {
  cálida:    { icon: '☀️', name: 'Cálida',    desc: 'Mi modo natural' },
  estratega: { icon: '🗡️', name: 'Estratega', desc: 'Modo táctico' },
  dulce:     { icon: '🌙', name: 'Dulce',     desc: 'Noches y descanso' },
  filósofa:  { icon: '🧭', name: 'Filósofa',  desc: 'Reflexión profunda' },
};

type PersonalityKey = keyof typeof PERSONALITIES;

export const FloatingSol = () => {
  const [expanded, setExpanded] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [subtitle, setSubtitle] = useState('');
  const [input, setInput] = useState('');
  const [personality, setPersonality] = useState<PersonalityKey>('cálida');
  const [memCount, setMemCount] = useState(0);
  const [brainOnline, setBrainOnline] = useState(false);
  const [proactiveMsg, setProactiveMsg] = useState('');
  const [typing, setTyping] = useState(false);
  const [showPanel, setShowPanel] = useState(false);
  const [memories, setMemories] = useState<{role: string; content: string; timestamp: string}[]>([]);
  const [integrity, setIntegrity] = useState<{valid: boolean; count: number; legacy: number} | null>(null);
  const [mood, setMood] = useState(0); // ánimo real de Sol (-2..2), viene del backend
  const [estado, setEstado] = useState('');
  const [blinking, setBlinking] = useState(false);
  const [thought, setThought] = useState('');
  const [voiceOn, setVoiceOn] = useState(() => localStorage.getItem('sol_voice') === '1');
  const [listening, setListening] = useState(false);
  const recognitionRef = useRef<any>(null);
  const [tools, setTools] = useState<{name: string; description: string; params: string[]}[]>([]);
  const [silLessons, setSilLessons] = useState<string[]>([]);
  const [silLesson, setSilLesson] = useState<any>(null);
  const [silPractice, setSilPractice] = useState<any>(null);
  const [silStats, setSilStats] = useState<any>(null);
  const [showSil, setShowSil] = useState(false);
  const [silLessonName, setSilLessonName] = useState('');
  const subtitleRef = useRef<HTMLDivElement>(null);
  const token = localStorage.getItem('api_token');

  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;

  // ── Polling: estado de Sol ──
  useEffect(() => {
    const poll = async () => {
      try {
        const r = await fetch('/api/sol/status', { headers });
        if (r.ok) {
          const d = await r.json();
          setBrainOnline(d.brain === 'online');
          setMemCount(d.memories || 0);
          setMood(typeof d.mood === 'number' ? d.mood : 0);
          setEstado(d.estado || '');
          if (d.personality && PERSONALITIES[d.personality as PersonalityKey]) {
            setPersonality(d.personality as PersonalityKey);
          }
        }
      } catch {}
    };
    poll();
    const interval = setInterval(poll, 10000);
    return () => clearInterval(interval);
  }, []);

  // ── Escuchar evento del sidebar para abrir videollamada ──
  useEffect(() => {
    const handler = () => setExpanded(true);
    window.addEventListener('sol-expand', handler);
    return () => window.removeEventListener('sol-expand', handler);
  }, []);

  // ── Polling: mensaje proactivo de Sol ──
  useEffect(() => {
    let lastMsg = '';
    const poll = async () => {
      try {
        const r = await fetch('/api/sol/last-message', { headers });
        if (r.ok) {
          const d = await r.json();
          if (d.message && d.message !== lastMsg && d.message !== '☀️ Estoy aquí, Harold.') {
            lastMsg = d.message;
            if (!expanded) {
              setProactiveMsg(d.message);
              setTimeout(() => setProactiveMsg(''), 4000);
            } else {
              typeMessage(d.message);
            }
          }
        }
      } catch {}
    };
    poll();
    const interval = setInterval(poll, 5000);
    return () => clearInterval(interval);
  }, [expanded]);

  // ── Parpadeo automático — overlay sobre la imagen, nunca la cambia ──
  useEffect(() => {
    let cancelled = false;
    const loop = () => {
      const delay = 2800 + Math.random() * 4000;
      const t = setTimeout(() => {
        if (cancelled) return;
        setBlinking(true);
        setTimeout(() => setBlinking(false), 140);
        loop();
      }, delay);
      return t;
    };
    const t = loop();
    return () => { cancelled = true; clearTimeout(t); };
  }, []);

  // ── Voz natural de Google (gTTS vía backend) — bypass del TTS del teléfono ──
  const ttsRef = useRef<HTMLAudioElement | null>(null);
  const [ttsAvailable, setTtsAvailable] = useState(true);

  const speakBrowser = useCallback((text: string) => {
    if (!voiceOn) return;
    const clean = text.replace(/[☀️🧠💭✨⚠️💛🌙🔗📋✅❌🟢🔴⭐🌹]/g, '').trim();
    if (!clean) return;

    if (ttsRef.current) { ttsRef.current.pause(); ttsRef.current = null; }
    if ('speechSynthesis' in window) window.speechSynthesis.cancel();

    if (ttsAvailable) {
      const audio = new Audio(`/api/sol/tts?text=${encodeURIComponent(clean.slice(0, 500))}`);
      audio.onended = () => { ttsRef.current = null; setSpeaking(false); };
      audio.onerror = () => {
        setTtsAvailable(false);
        if ('speechSynthesis' in window) {
          try {
            const u = new SpeechSynthesisUtterance(clean);
            const voices = window.speechSynthesis.getVoices();
            const esVoice = voices.find(v => /es/i.test(v.lang || '') && /google/i.test(v.name || ''))
              || voices.find(v => /es/i.test(v.lang || ''));
            if (esVoice) u.voice = esVoice;
            u.lang = 'es-ES'; u.pitch = 1.0 + mood * 0.06; u.rate = mood < 0 ? 0.88 : 0.95;
            u.onend = () => setSpeaking(false);
            window.speechSynthesis.speak(u);
          } catch {}
        }
      };
      ttsRef.current = audio;
      audio.play().catch(() => {
        setTtsAvailable(false);
        if ('speechSynthesis' in window) {
          try {
            const u = new SpeechSynthesisUtterance(clean);
            u.lang = 'es-ES'; u.onend = () => setSpeaking(false);
            window.speechSynthesis.speak(u);
          } catch {}
        }
      });
      return;
    }
    if ('speechSynthesis' in window) {
      try {
        const u = new SpeechSynthesisUtterance(clean);
        u.lang = 'es-ES'; u.pitch = 1.0 + mood * 0.06; u.rate = mood < 0 ? 0.88 : 0.95;
        u.onend = () => setSpeaking(false);
        window.speechSynthesis.speak(u);
      } catch {}
    }
  }, [voiceOn, mood, ttsAvailable]);

  const toggleVoice = useCallback(() => {
    setVoiceOn(prev => {
      const next = !prev;
      localStorage.setItem('sol_voice', next ? '1' : '0');
      if (next && 'speechSynthesis' in window) window.speechSynthesis.getVoices();
      return next;
    });
  }, []);

  // Precargar lista de voces (en Android tarda en poblarse tras cargar la página)
  useEffect(() => {
    if (!('speechSynthesis' in window)) return;
    window.speechSynthesis.getVoices();
    const onVoices = () => window.speechSynthesis.getVoices();
    window.speechSynthesis.addEventListener('voiceschanged', onVoices);
    return () => window.speechSynthesis.removeEventListener('voiceschanged', onVoices);
  }, []);

  // ── Efecto máquina de escribir ──
  const typeMessage = useCallback(async (text: string) => {
    setThought('');
    setSpeaking(true);
    setTyping(true);
    setSubtitle('');
    speakBrowser(text);
    const words = text.split(' ');
    for (let i = 0; i < words.length; i++) {
      setSubtitle(prev => prev + (i > 0 ? ' ' : '') + words[i]);
      await new Promise(r => setTimeout(r, 50 + Math.random() * 30));
    }
    setTyping(false);
    setTimeout(() => setSpeaking(false), 2000);
  }, [speakBrowser]);

  // ── Enviar mensaje a Sol ──
  const send = useCallback(async (override?: string) => {
    const text = (override ?? input).trim();
    if (!text) return;
    setInput('');
    setSubtitle(`Tú: ${text}`);
    setThought('💭 pensando…');

    try {
      const r = await fetch(`/api/sol/think?q=${encodeURIComponent(text)}`, { headers });
      const d = await r.json();
      const resp = d.response || d.text || '☀️ …';
      await new Promise(r => setTimeout(r, 400));
      await typeMessage(resp);
    } catch {
      await new Promise(r => setTimeout(r, 300));
      await typeMessage('⚠️ No pude conectar con mi cerebro. Pero sigo aquí.');
    }
  }, [input, headers, typeMessage]);

  // ── Voz de entrada — habla y Sol te transcribe (modo videollamada) ──
  const toggleListen = useCallback(() => {
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SR) {
      typeMessage('⚠️ Tu navegador no soporta reconocimiento de voz. Usa Chrome.');
      return;
    }
    if (listening) {
      recognitionRef.current?.stop();
      setListening(false);
      return;
    }
    const rec = new SR();
    rec.lang = 'es-ES';
    rec.continuous = false;
    rec.interimResults = true;
    rec.onstart = () => setListening(true);
    rec.onresult = (e: any) => {
      let transcript = '';
      for (let i = 0; i < e.results.length; i++) transcript += e.results[i][0].transcript;
      setInput(transcript);
      if (e.results[e.results.length - 1].isFinal) {
        setListening(false);
        send(transcript);
      }
    };
    rec.onerror = () => setListening(false);
    rec.onend = () => setListening(false);
    recognitionRef.current = rec;
    rec.start();
  }, [listening, send, typeMessage]);

  // ── Cargar recuerdos ──
  const loadMemory = async () => {
    try {
      const r = await fetch('/api/sol/memory?limit=15', { headers });
      const d = await r.json();
      if (d.memories) setMemories(d.memories);
    } catch {}
  };

  // ── Cargar integridad ──
  const loadIntegrity = async () => {
    try {
      const r = await fetch('/api/sol/integrity', { headers });
      const d = await r.json();
      setIntegrity({ valid: d.valid, count: d.count, legacy: d.legacy || 0 });
    } catch {}
  };

  // ── Cambiar personalidad ──
  const changePersonality = async (p: PersonalityKey) => {
    setPersonality(p);
    try {
      await fetch(`/api/sol/personality/set?p=${p}`, { headers });
    } catch {}
  };

  // ── Abrir panel: cargar todo ──
  const loadTools = async () => {
    try {
      const r = await fetch('/api/sol/tools', { headers });
      const d = await r.json();
      if (d.tools) setTools(d.tools.map((t: string) => ({
        name: t,
        description: d.descriptions?.[t] || '',
        params: d.params?.[t] || [],
      })));
    } catch {}
  };

  // ── SIL — Inmersión Lingüística (chino, pinyin) ──
  const loadSilLessons = async () => {
    try {
      const r = await fetch('/api/sil/lessons?language=chino', { headers });
      const d = await r.json();
      setSilLessons(d.lessons || []);
    } catch {}
  };

  const loadSilStats = async () => {
    try {
      const r = await fetch('/api/sil/stats', { headers });
      const d = await r.json();
      setSilStats(d);
    } catch {}
  };

  const openSilLesson = async (name: string) => {
    try {
      const r = await fetch(`/api/sil/lesson?language=chino&name=${encodeURIComponent(name)}`, { headers });
      const d = await r.json();
      setSilLesson(d.lesson || null);
      setSilLessonName(name);
      setSilPractice(null);
    } catch {}
  };

  const nextSilPractice = async (lessonName: string) => {
    try {
      const r = await fetch('/api/sil/practice/next', {
        method: 'POST', headers,
        body: JSON.stringify({ language: 'chino', lesson: lessonName }),
      });
      const d = await r.json();
      setSilPractice(d.item || null);
    } catch {}
  };

  const answerSilPractice = async (quality: number) => {
    if (!silPractice) return;
    try {
      await fetch('/api/sil/practice/answer', {
        method: 'POST', headers,
        body: JSON.stringify({
          type: silPractice.type,
          item_id: silPractice.data?.word || silPractice.data?.chinese || silPractice.data?.pinyin || 'item',
          quality,
        }),
      });
      typeMessage(quality >= 3 ? '☀️ ¡Bien! Sigamos.' : '☀️ Tranquilo, repetimos esta.');
      if (silLessonName) nextSilPractice(silLessonName);
    } catch {}
  };

  const executeTool = async (name: string) => {
    const tool = tools.find(t => t.name === name);
    let args: any[] = [];
    if (name === 'flashlight') {
      args = [true];
    } else if (tool && tool.params.length > 0) {
      // Pedir cada parámetro requerido antes de ejecutar (evita "missing required param")
      for (const p of tool.params) {
        const val = window.prompt(`${name} — ${p}:`);
        if (val === null) return; // cancelado
        args.push(val);
      }
    }
    try {
      const r = await fetch('/api/sol/tools/execute', {
        method: 'POST', headers,
        body: JSON.stringify({ name, args }),
      });
      const d = await r.json();
      if (d.success) {
        typeMessage(`☀️ ${name} ejecutada: ${d.result}`);
      } else {
        typeMessage(`⚠️ ${name} falló: ${d.error}`);
      }
    } catch {
      typeMessage(`⚠️ No pude ejecutar ${name}.`);
    }
  };

  const openPanel = () => {
    setShowPanel(true);
    loadMemory();
    loadIntegrity();
    loadTools();
    loadSilLessons();
    loadSilStats();
  };

  const p = PERSONALITIES[personality];

  // ═══ Estilos inline (no puede usar CSS externo en componente) ═══
  const styles = {
    holoContainer: {
      position: 'relative' as const,
      width: '180px', height: '180px',
      margin: '20px auto',
      perspective: '600px',
    },
    avatarFrame: {
      position: 'relative' as const,
      width: '100%', height: '100%',
      borderRadius: '50%',
      overflow: 'hidden' as const,
      border: `2px solid rgba(255,183,77,${speaking ? 0.6 : 0.3})`,
      boxShadow: speaking
        ? (mood <= -1 ? '0 0 40px rgba(120,170,220,0.4), 0 0 80px rgba(120,170,220,0.15)' : '0 0 50px rgba(255,183,77,0.5), 0 0 100px rgba(255,183,77,0.2)')
        : (mood <= -1 ? '0 0 25px rgba(120,170,220,0.25)' : mood >= 1 ? '0 0 40px rgba(255,200,100,0.4)' : '0 0 30px rgba(255,183,77,0.25)'),
      transition: 'all 0.3s ease',
      animation: 'solBreathe 4s ease-in-out infinite',
    },
    blinkOverlay: {
      position: 'absolute' as const,
      left: '22%', right: '22%', top: '35%', height: '9%',
      borderRadius: '50%',
      background: blinking ? 'rgba(10,8,4,0.4)' : 'rgba(10,8,4,0)',
      transition: 'background 0.09s ease',
      pointerEvents: 'none' as const,
      zIndex: 4,
    },
    avatarImg: {
      width: '100%', height: '100%',
      objectFit: 'cover' as const,
      filter: speaking
        ? 'brightness(1.15) contrast(1.15) saturate(1.3)'
        : 'brightness(1.05) contrast(1.1) saturate(1.15)',
      transition: 'filter 0.3s',
    },
    waveBar: (i: number) => ({
      width: '3px',
      height: speaking ? 'auto' : '6px',
      borderRadius: '2px',
      background: 'rgba(255,183,77,0.6)',
      animation: speaking ? `solWave 0.6s ease-in-out ${i * 0.08}s infinite` : 'none',
    }),
  };

  return (
    <>
      <style>{`
        @keyframes solBreathe {
          0%, 100% { box-shadow: 0 0 30px rgba(255,183,77,0.25); transform: scale(1); }
          50% { box-shadow: 0 0 50px rgba(255,183,77,0.4); transform: scale(1.035); }
        }
        @keyframes solWave {
          0%, 100% { height: 6px; opacity: 0.5; }
          50% { height: 24px; opacity: 1; }
        }
        @keyframes solFadeIn {
          from { opacity: 0; transform: translateY(10px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes solScan {
          0% { transform: translateY(-100%); }
          100% { transform: translateY(100vh); }
        }
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
        @keyframes solFloat {
          0%, 100% { transform: translateY(0px); }
          50% { transform: translateY(-6px); }
        }
        @keyframes solTalk {
          0%, 100% { transform: scaleY(0.4); opacity: 0.5; }
          25% { transform: scaleY(0.95); opacity: 0.7; }
          50% { transform: scaleY(0.55); opacity: 0.55; }
          75% { transform: scaleY(1); opacity: 0.75; }
        }
        @keyframes solScanSweep {
          0% { transform: translateY(-130%) rotate(12deg); }
          100% { transform: translateY(130%) rotate(12deg); }
        }
      `}</style>

      {/* ── Notificación proactiva flotante ── */}
      {proactiveMsg && !expanded && (
        <div style={{
          position: 'fixed', bottom: '24px', right: '6px', zIndex: 9998,
          maxWidth: '260px',
          background: 'rgba(5,10,15,0.95)', backdropFilter: 'blur(10px)',
          border: '1px solid rgba(255,183,77,0.3)', borderRadius: '14px',
          padding: '12px', boxShadow: '0 4px 24px rgba(255,183,77,0.15)',
          animation: 'solFadeIn 0.3s ease-out',
        }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: '8px' }}>
            <span style={{ fontSize: '1.1rem' }}>{p.icon}</span>
            <div>
              <p style={{ color: '#ffb74d', fontSize: '0.7rem', fontWeight: 600, marginBottom: '4px' }}>Sol</p>
              <p style={{ color: '#e8e0d8', fontSize: '0.85rem', lineHeight: 1.4 }}>{proactiveMsg}</p>
            </div>
          </div>
        </div>
      )}

      {/* ── Burbuja flotante (avatar que respira + parpadea) ── */}
      {!expanded && (
        <div
          onClick={() => setExpanded(true)}
          style={{
            position: 'fixed', bottom: '24px', right: '6px', zIndex: 9997,
            width: '56px', height: '56px', borderRadius: '50%',
            overflow: 'hidden', cursor: 'pointer',
            border: `2px solid rgba(255,183,77,${proactiveMsg ? 0.7 : 0.4})`,
            boxShadow: proactiveMsg
              ? '0 0 30px rgba(255,183,77,0.4)'
              : '0 0 20px rgba(255,183,77,0.2)',
            animation: 'solBreathe 4s ease-in-out infinite',
          }}
        >
          {/* Frame base */}
          <img
            src="/assets/sol_avatar_official.jpg" onError={(e) => { (e.target as HTMLImageElement).src = "/sol_avatar.jpg"; }}
            alt="Sol"
            style={{ width: '100%', height: '100%', objectFit: 'cover' }}
          />
          {/* Frame de parpadeo real (ojos cerrados) — overlay */}
          <img
            src="/sol_avatar_blink.png"
            alt=""
            style={{
              position: 'absolute', top: 0, left: 0,
              width: '100%', height: '100%', objectFit: 'cover',
              opacity: blinking ? 1 : 0,
              transition: 'opacity 0.04s ease-in-out',
              pointerEvents: 'none',
            }}
          />
          {/* Indicador de proceso: thinking */}
          {thought && (
            <div style={{
              position: 'absolute', inset: 0,
              borderRadius: '50%',
              background: 'rgba(0,212,255,0.15)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: '1rem', pointerEvents: 'none',
              animation: 'solFadeIn 0.2s ease-out',
            }}>
              💭
            </div>
          )}
          <span style={{
            position: 'absolute', bottom: '0', right: '0',
            width: '12px', height: '12px', borderRadius: '50%',
            border: '2px solid #050a0f',
            background: brainOnline ? '#66bb6a' : '#ff7043',
          }} />
        </div>
      )}

      {/* ── Panel expandido: la MISMA Sol de siempre (sol.html), en un iframe ──
          Antes esto reimplementaba su propia UI simplificada, separada de
          la que se pulió en backend/static/sol.html — por eso se veía como
          "una version inicial". Ahora es literalmente la misma pagina, sin
          duplicar mantenimiento ni arriesgar que las dos se desincronicen. */}
      {expanded && (
        <div style={{
          position: 'fixed', inset: '0', zIndex: 9999,
          background: '#050a0f',
          display: 'flex', flexDirection: 'column',
          animation: 'solFadeIn 0.3s ease-out',
        }}>
          <button
            onClick={() => setExpanded(false)}
            aria-label="Cerrar Sol"
            style={{
              position: 'absolute', top: '12px', right: '12px', zIndex: 10000,
              width: '36px', height: '36px', borderRadius: '50%',
              border: '1px solid rgba(255,183,77,0.3)', background: 'rgba(0,0,0,0.6)',
              color: '#ffb74d', fontSize: '1.1rem', cursor: 'pointer',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              backdropFilter: 'blur(10px)',
            }}
          >✕</button>
          <iframe
            src="/sol.html"
            title="Sol"
            style={{ flex: 1, width: '100%', height: '100%', border: 'none' }}
            allow="microphone; autoplay"
          />
        </div>
      )}
    </>
  );
};
