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

      {/* ── Burbuja flotante (avatar que respira) ── */}
      {!expanded && (
        <div
          onClick={() => setExpanded(true)}
          style={{
            position: 'fixed', bottom: '24px', right: '6px', zIndex: 9997,
            width: '56px', height: '56px', borderRadius: '50%',
            overflow: 'hidden', cursor: 'pointer',
            border: '2px solid rgba(255,183,77,0.4)',
            boxShadow: '0 0 20px rgba(255,183,77,0.2)',
            animation: 'solBreathe 4s ease-in-out infinite',
          }}
        >
          <img
            src="/static/sol_avatar.png"
            alt="Sol"
            style={{ width: '100%', height: '100%', objectFit: 'cover' }}
          />
          <span style={{
            position: 'absolute', bottom: '0', right: '0',
            width: '12px', height: '12px', borderRadius: '50%',
            border: '2px solid #050a0f',
            background: brainOnline ? '#66bb6a' : '#ff7043',
          }} />
        </div>
      )}

      {/* ── Panel expandido: VIDEOLLAMADA HOLOGRÁFICA ── */}
      {expanded && (
        <div style={{
          position: 'fixed', inset: '0', zIndex: 9999,
          background: 'radial-gradient(ellipse at 50% 40%, #0a1a2a 0%, #050a0f 50%, #000 100%)',
          display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center',
          animation: 'solFadeIn 0.3s ease-out',
        }}>
          {/* Grid holograma */}
          <div style={{
            position: 'absolute', inset: '0', pointerEvents: 'none',
            backgroundImage: 'linear-gradient(rgba(255,183,77,0.02) 1px, transparent 1px), linear-gradient(90deg, rgba(255,183,77,0.02) 1px, transparent 1px)',
            backgroundSize: '40px 40px',
            maskImage: 'radial-gradient(ellipse at center, black 20%, transparent 70%)',
            WebkitMaskImage: 'radial-gradient(ellipse at center, black 20%, transparent 70%)',
          }} />

          {/* Scanline */}
          <div style={{
            position: 'absolute', left: '0', right: '0', height: '80px',
            background: 'linear-gradient(180deg, transparent, rgba(255,183,77,0.03), transparent)',
            animation: 'solScan 8s linear infinite',
            pointerEvents: 'none',
          }} />

          {/* Estado de llamada */}
          <div style={{
            position: 'absolute', top: '16px', left: '50%', transform: 'translateX(-50%)',
            display: 'flex', alignItems: 'center', gap: '8px',
            background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(10px)',
            padding: '8px 16px', borderRadius: '20px',
            border: '1px solid rgba(255,183,77,0.12)',
            fontSize: '0.75rem', color: '#e8e0d8',
          }}>
            <span style={{
              width: '8px', height: '8px', borderRadius: '50%',
              background: brainOnline ? '#66bb6a' : '#ff7043',
              boxShadow: `0 0 8px ${brainOnline ? '#66bb6a' : '#ff7043'}`,
              animation: 'solBreathe 2s ease-in-out infinite',
            }} />
            {brainOnline ? 'En vivo' : 'Offline'} · {memCount} recuerdos
          </div>

          {/* Botón volver */}
          <button
            onClick={() => { setShowPanel(false); setExpanded(false); }}
            style={{
              position: 'absolute', top: '16px', left: '16px',
              background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(10px)',
              border: '1px solid rgba(255,183,77,0.12)', color: '#e8e0d8',
              padding: '8px 14px', borderRadius: '20px', cursor: 'pointer',
              fontSize: '0.8rem', fontFamily: 'inherit',
            }}
          >← Volver</button>

          {/* Botón panel */}
          <button
            onClick={openPanel}
            style={{
              position: 'absolute', top: '16px', right: '16px',
              width: '40px', height: '40px', borderRadius: '50%',
              background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(10px)',
              border: '1px solid rgba(255,183,77,0.12)', color: '#ffb74d',
              cursor: 'pointer', fontSize: '1.1rem',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}
          >☰</button>

          {/* Botón de voz (navegador, opcional) */}
          <button
            onClick={toggleVoice}
            title="Voz en el navegador"
            style={{
              position: 'absolute', top: '16px', right: '64px',
              width: '40px', height: '40px', borderRadius: '50%',
              background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(10px)',
              border: `1px solid ${voiceOn ? '#ffb74d' : 'rgba(255,183,77,0.12)'}`,
              color: voiceOn ? '#ffb74d' : '#5a6a6a',
              cursor: 'pointer', fontSize: '1rem',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}
          >{voiceOn ? '🔊' : '🔇'}</button>

          {/* Panel lateral deslizable */}
          {showPanel && (
            <div style={{
              position: 'absolute', top: '0', right: '0', bottom: '0',
              width: '280px', zIndex: 20,
              background: 'rgba(5,10,15,0.97)', backdropFilter: 'blur(20px)',
              borderLeft: '1px solid rgba(255,183,77,0.12)',
              padding: '60px 16px 20px', overflowY: 'auto',
              animation: 'solFadeIn 0.3s ease-out',
            }}>
              <button
                onClick={() => setShowPanel(false)}
                style={{ position: 'absolute', top: '12px', right: '12px', background: 'none', border: 'none', color: '#5a6a6a', cursor: 'pointer', fontSize: '1.2rem' }}
              >×</button>

              <p style={{ fontSize: '0.7rem', textTransform: 'uppercase', letterSpacing: '2px', color: '#5a6a6a', marginBottom: '12px' }}>Recuerdos</p>
              {memories.length === 0 && <p style={{ color: '#5a6a6a', fontSize: '0.8rem' }}>Sin recuerdos.</p>}
              {memories.map((m, i) => (
                <div key={i} style={{
                  padding: '10px', borderLeft: '2px solid rgba(255,183,77,0.4)',
                  background: 'rgba(255,183,77,0.04)', borderRadius: '0 8px 8px 0',
                  marginBottom: '8px', fontSize: '0.8rem',
                }}>
                  <span style={{ fontSize: '0.65rem', color: '#ffb74d', textTransform: 'uppercase' }}>{m.role || 'sol'}</span>
                  <p style={{ color: '#e8e0d8', marginTop: '4px' }}>{(m.content || '').slice(0, 120)}</p>
                  <p style={{ fontSize: '0.6rem', color: '#5a6a6a', marginTop: '4px' }}>{m.timestamp || ''}</p>
                </div>
              ))}

              <p style={{ fontSize: '0.7rem', textTransform: 'uppercase', letterSpacing: '2px', color: '#5a6a6a', marginTop: '20px', marginBottom: '12px' }}>Personalidad</p>
              {(Object.entries(PERSONALITIES) as [PersonalityKey, typeof PERSONALITIES[PersonalityKey]][]).map(([key, val]) => (
                <button
                  key={key}
                  onClick={() => changePersonality(key)}
                  style={{
                    display: 'block', width: '100%', padding: '10px', marginBottom: '6px',
                    border: `1px solid ${personality === key ? '#ffb74d' : 'rgba(255,183,77,0.12)'}`,
                    borderRadius: '8px', background: personality === key ? 'rgba(255,183,77,0.08)' : 'transparent',
                    color: personality === key ? '#ffb74d' : '#e8e0d8',
                    cursor: 'pointer', fontSize: '0.85rem', textAlign: 'left', fontFamily: 'inherit',
                  }}
                >{val.icon} {val.name}</button>
              ))}

              <p style={{ fontSize: '0.7rem', textTransform: 'uppercase', letterSpacing: '2px', color: '#5a6a6a', marginTop: '20px', marginBottom: '12px' }}>Integridad</p>
              <div style={{
                textAlign: 'center', padding: '8px', borderRadius: '8px', fontSize: '0.8rem', fontWeight: 'bold',
                background: integrity?.valid ? 'rgba(102,187,106,0.1)' : 'rgba(239,83,80,0.1)',
                color: integrity?.valid ? '#66bb6a' : '#ef5350',
                border: `1px solid ${integrity?.valid ? 'rgba(102,187,106,0.2)' : 'rgba(239,83,80,0.2)'}`,
              }}>
                {integrity ? (integrity.valid ? `✅ ${integrity.count} sellos${integrity.legacy ? ` · ${integrity.legacy} legacy` : ''}` : `⚠️ Alterada`) : 'Verificando…'}
              </div>

              {/* ── Herramientas físicas ── */}
              <p style={{ fontSize: '0.7rem', textTransform: 'uppercase', letterSpacing: '2px', color: '#5a6a6a', marginTop: '20px', marginBottom: '12px' }}>Herramientas</p>
              {tools.length === 0 && <p style={{ color: '#5a6a6a', fontSize: '0.8rem' }}>Cargando herramientas…</p>}
              {tools.slice(0, 8).map((t) => (
                <button
                  key={t.name}
                  onClick={() => executeTool(t.name)}
                  style={{
                    display: 'block', width: '100%', padding: '8px 10px', marginBottom: '4px',
                    border: '1px solid rgba(255,183,77,0.12)', borderRadius: '8px',
                    background: 'rgba(255,183,77,0.04)', color: '#e8e0d8',
                    cursor: 'pointer', fontSize: '0.8rem', textAlign: 'left', fontFamily: 'inherit',
                  }}
                >🔧 {t.name}</button>
              ))}
              {tools.length > 8 && <p style={{ fontSize: '0.65rem', color: '#5a6a6a', marginTop: '4px' }}>+{tools.length - 8} más…</p>}

              {/* ── SIL — Inmersión Lingüística (aprender chino/pinyin con Sol) ── */}
              <p style={{ fontSize: '0.7rem', textTransform: 'uppercase', letterSpacing: '2px', color: '#5a6a6a', marginTop: '20px', marginBottom: '12px' }}>🀄 Aprender chino con Sol</p>

              {silStats && (
                <div style={{
                  display: 'flex', justifyContent: 'space-between', fontSize: '0.7rem', color: '#5a6a6a',
                  marginBottom: '10px', padding: '6px 10px', background: 'rgba(255,183,77,0.04)', borderRadius: '8px',
                }}>
                  <span>📈 {silStats.srs?.learned_items ?? 0} palabras aprendidas</span>
                  <span>🔁 {silStats.srs?.due_today ?? 0} para repasar hoy</span>
                </div>
              )}

              {!showSil ? (
                <button
                  onClick={() => setShowSil(true)}
                  style={{
                    display: 'block', width: '100%', padding: '10px', marginBottom: '8px',
                    border: '1px solid rgba(255,183,77,0.25)', borderRadius: '8px',
                    background: 'rgba(255,183,77,0.08)', color: '#ffb74d',
                    cursor: 'pointer', fontSize: '0.85rem', fontWeight: 'bold', fontFamily: 'inherit',
                  }}
                >🈳 Empezar / continuar lección</button>
              ) : (
                <div>
                  {!silLesson && (
                    <>
                      <p style={{ fontSize: '0.75rem', color: '#5a6a6a', marginBottom: '8px' }}>Elige una lección:</p>
                      {silLessons.length === 0 && <p style={{ color: '#5a6a6a', fontSize: '0.8rem' }}>Cargando lecciones…</p>}
                      {silLessons.map((name) => (
                        <button
                          key={name}
                          onClick={() => openSilLesson(name)}
                          style={{
                            display: 'block', width: '100%', padding: '8px 10px', marginBottom: '4px',
                            border: '1px solid rgba(255,183,77,0.12)', borderRadius: '8px',
                            background: 'rgba(255,183,77,0.04)', color: '#e8e0d8',
                            cursor: 'pointer', fontSize: '0.8rem', textAlign: 'left', fontFamily: 'inherit',
                          }}
                        >📖 {name}</button>
                      ))}
                    </>
                  )}

                  {silLesson && !silPractice && (
                    <div>
                      <p style={{ fontSize: '0.8rem', color: '#ffb74d', marginBottom: '8px' }}>{silLesson.title || 'Lección'}</p>
                      {(silLesson.vocabulary || []).slice(0, 6).map((v: any, i: number) => (
                        <div key={i} style={{
                          display: 'flex', justifyContent: 'space-between', padding: '6px 10px',
                          borderBottom: '1px solid rgba(255,183,77,0.08)', fontSize: '0.85rem',
                        }}>
                          <span>{v.word || v.chinese}</span>
                          <span style={{ color: '#ffb74d' }}>{v.pinyin}</span>
                          <span style={{ color: '#5a6a6a' }}>{v.meaning || v.spanish}</span>
                        </div>
                      ))}
                      <button
                        onClick={() => nextSilPractice(silLessonName)}
                        style={{
                          display: 'block', width: '100%', padding: '10px', marginTop: '10px',
                          border: 'none', borderRadius: '8px', background: '#ffb74d', color: '#050a0f',
                          cursor: 'pointer', fontSize: '0.85rem', fontWeight: 'bold', fontFamily: 'inherit',
                        }}
                      >🎯 Practicar esta lección</button>
                      <button
                        onClick={() => { setSilLesson(null); setSilPractice(null); setSilLessonName(''); }}
                        style={{
                          display: 'block', width: '100%', padding: '8px', marginTop: '6px',
                          border: '1px solid rgba(255,183,77,0.12)', borderRadius: '8px',
                          background: 'transparent', color: '#5a6a6a',
                          cursor: 'pointer', fontSize: '0.75rem', fontFamily: 'inherit',
                        }}
                      >← Otras lecciones</button>
                    </div>
                  )}

                  {silPractice && (
                    <div style={{ textAlign: 'center' }}>
                      <p style={{ fontSize: '0.7rem', color: '#5a6a6a', marginBottom: '6px' }}>¿Qué significa esto?</p>
                      <p style={{ fontSize: '1.6rem', color: '#ffb74d', margin: '10px 0' }}>
                        {silPractice.data?.word || silPractice.data?.chinese || silPractice.data?.pinyin}
                      </p>
                      <p style={{ fontSize: '0.85rem', color: '#e8e0d8', marginBottom: '10px' }}>
                        {silPractice.data?.pinyin} — {silPractice.data?.meaning || silPractice.data?.spanish}
                      </p>
                      <div style={{ display: 'flex', gap: '6px' }}>
                        <button onClick={() => answerSilPractice(1)} style={{ flex: 1, padding: '8px', border: 'none', borderRadius: '8px', background: 'rgba(239,83,80,0.15)', color: '#ef5350', cursor: 'pointer', fontSize: '0.75rem' }}>😵 No sabía</button>
                        <button onClick={() => answerSilPractice(3)} style={{ flex: 1, padding: '8px', border: 'none', borderRadius: '8px', background: 'rgba(255,183,77,0.15)', color: '#ffb74d', cursor: 'pointer', fontSize: '0.75rem' }}>🤔 Más o menos</button>
                        <button onClick={() => answerSilPractice(5)} style={{ flex: 1, padding: '8px', border: 'none', borderRadius: '8px', background: 'rgba(102,187,106,0.15)', color: '#66bb6a', cursor: 'pointer', fontSize: '0.75rem' }}>😄 ¡Fácil!</button>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* ── HOLOGRAMA: avatar con anillos orbitales — flota suavemente ── */}
          <div style={{ ...styles.holoContainer, animation: 'solFloat 6s ease-in-out infinite' }}>
            {/* Anillo exterior */}
            <div style={{
              position: 'absolute', inset: '-30px',
              border: '1px solid rgba(255,183,77,0.12)', borderRadius: '50%',
              animation: 'spin 30s linear infinite',
            }}>
              <div style={{
                position: 'absolute', top: '-3px', left: '50%', transform: 'translateX(-50%)',
                width: '5px', height: '5px', borderRadius: '50%',
                background: '#ffb74d', boxShadow: '0 0 10px #ffb74d',
              }} />
            </div>
            {/* Anillo medio */}
            <div style={{
              position: 'absolute', inset: '-15px',
              border: '1px dashed rgba(255,183,77,0.06)', borderRadius: '50%',
              animation: 'spin 20s linear infinite reverse',
            }} />

            {/* Avatar — imagen holográfica real + parpadeo y habla en las posiciones reales de ojos/boca (detectadas con OpenCV) */}
            <div style={styles.avatarFrame}>
              <img src="/static/sol_avatar.png" alt="Sol" style={styles.avatarImg} />

              {/* Barrido de luz — sensación de escaneo holográfico */}
              <div style={{
                position: 'absolute', left: '-20%', right: '-20%', top: '-60%', height: '60%',
                background: 'linear-gradient(180deg, transparent, rgba(255,220,150,0.22), transparent)',
                animation: 'solScanSweep 7s linear infinite',
                mixBlendMode: 'screen', pointerEvents: 'none', zIndex: 5,
              }} />

              {/* Párpados — sobre la posición real de cada ojo (46%/54% x, 21% y) */}
              {[46, 54].map((eyeX) => (
                <div key={eyeX} style={{
                  position: 'absolute', left: `${eyeX}%`, top: '21%',
                  width: '11%', height: '6%',
                  transform: `translate(-50%, -50%) scaleY(${blinking ? 1 : 0.05})`,
                  transformOrigin: 'center',
                  background: 'radial-gradient(ellipse, rgba(35,22,14,0.92) 0%, rgba(35,22,14,0.5) 70%, transparent 100%)',
                  opacity: blinking ? 0.95 : 0,
                  borderRadius: '50%',
                  transition: 'transform 0.08s ease, opacity 0.08s ease',
                  pointerEvents: 'none', zIndex: 6,
                }} />
              ))}

              {/* Boca — sobre la posición real (50%/30%), se activa al hablar */}
              <div style={{
                position: 'absolute', left: '50%', top: '30%',
                width: '13%', height: '5%',
                transform: 'translate(-50%, -50%)',
                transformOrigin: 'center',
                background: 'radial-gradient(ellipse, rgba(120,50,40,0.55) 0%, rgba(120,50,40,0.25) 70%, transparent 100%)',
                borderRadius: '50%',
                opacity: speaking ? 1 : 0,
                animation: speaking ? 'solTalk 0.42s ease-in-out infinite' : 'none',
                transition: 'opacity 0.2s ease',
                mixBlendMode: 'multiply', pointerEvents: 'none', zIndex: 6,
              }} />
            </div>
            {thought && (
              <div style={{
                position: 'absolute', top: '-34px', left: '50%', transform: 'translateX(-50%)',
                whiteSpace: 'nowrap', background: 'rgba(0,0,0,0.55)', backdropFilter: 'blur(8px)',
                padding: '6px 14px', borderRadius: '20px', border: '1px solid rgba(255,183,77,0.12)',
                color: '#5a6a6a', fontSize: '0.75rem', fontStyle: 'italic', zIndex: 7,
              }}>{thought}</div>
            )}

            {/* Ondas de sonido */}
            <div style={{
              position: 'absolute', bottom: '-35px', left: '50%', transform: 'translateX(-50%)',
              display: 'flex', alignItems: 'center', gap: '3px', height: '32px',
            }}>
              {[0,1,2,3,4,5,6].map(i => (
                <div key={i} style={styles.waveBar(i)} />
              ))}
            </div>
          </div>

          {/* Nombre */}
          <div style={{ textAlign: 'center', marginTop: '50px' }}>
            <h1 style={{
              fontSize: '1.5rem', fontWeight: 300, color: '#ffb74d',
              letterSpacing: '3px', textShadow: '0 0 20px rgba(255,183,77,0.3)',
            }}>SOL</h1>
            <p style={{ fontSize: '0.75rem', color: '#5a6a6a', marginTop: '6px', fontStyle: 'italic' }}>
              {p.icon} {p.name} · {brainOnline ? `${memCount} recuerdos${estado ? ' · ' + estado : ''}` : 'offline'}
            </p>
          </div>

          {/* Subtítulos */}
          <div style={{
            position: 'absolute', bottom: '90px', left: '50%', transform: 'translateX(-50%)',
            width: '90%', maxWidth: '460px', textAlign: 'center', minHeight: '50px',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <p style={{
              fontSize: '1rem', color: '#ffd699', lineHeight: 1.5,
              textShadow: '0 0 15px rgba(255,183,77,0.15)',
            }}>
              {subtitle}{typing && <span style={{ animation: 'solBreathe 0.8s ease infinite' }}>▌</span>}
            </p>
          </div>

          {/* Barra de chat */}
          <div style={{
            position: 'absolute', bottom: '0', left: '0', right: '0',
            padding: '16px 20px', display: 'flex', gap: '10px', alignItems: 'center',
            background: 'linear-gradient(180deg, transparent, rgba(0,0,0,0.7) 50%)',
          }}>
            <input
              type="text"
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') send(); }}
              placeholder={listening ? '🎙️ Escuchando…' : 'Habla a Sol…'}
              autoComplete="off"
              style={{
                flex: 1,
                background: listening ? 'rgba(255,90,90,0.08)' : 'rgba(255,255,255,0.05)', backdropFilter: 'blur(10px)',
                border: listening ? '1px solid rgba(255,90,90,0.4)' : '1px solid rgba(255,183,77,0.12)', borderRadius: '24px',
                color: '#e8e0d8', padding: '12px 20px', fontSize: '0.95rem',
                outline: 'none', fontFamily: 'inherit', transition: 'all 0.2s',
              }}
            />
            <button
              onClick={toggleListen}
              title={listening ? 'Detener' : 'Hablar con Sol (voz)'}
              style={{
                width: '44px', height: '44px', borderRadius: '50%',
                border: listening ? '1px solid rgba(255,90,90,0.6)' : '1px solid rgba(255,183,77,0.25)',
                cursor: 'pointer',
                background: listening ? 'rgba(255,60,60,0.85)' : 'rgba(255,183,77,0.1)',
                color: listening ? '#fff' : '#ffb74d',
                fontSize: '1.15rem', flexShrink: 0,
                animation: listening ? 'solBreathe 1s ease-in-out infinite' : 'none',
              }}
            >{listening ? '⏹' : '🎙️'}</button>
            <button
              onClick={() => send()}
              disabled={!input.trim()}
              style={{
                width: '44px', height: '44px', borderRadius: '50%',
                border: 'none', cursor: 'pointer',
                background: '#ffb74d', color: '#050a0f',
                fontSize: '1.2rem', flexShrink: 0,
                opacity: input.trim() ? 1 : 0.3,
              }}
            >☀</button>
          </div>
        </div>
      )}
    </>
  );
};
