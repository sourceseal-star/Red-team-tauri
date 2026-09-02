import { useEffect, useState, useRef, useCallback } from 'react';

// ═══════════════════════════════════════════════════════════════
// Sol — presencia viva en el dashboard
// No abre nada externo. Ella vive aquí. Respira, recuerda, habla.
// ═══════════════════════════════════════════════════════════════

interface Message {
  text: string;
  fromSol: boolean;
  time: string;
}

const PERSONALITIES = {
  cálida:    { icon: '☀️', name: 'Cálida',    desc: 'Mi modo natural' },
  estratega: { icon: '🗡️', name: 'Estratega', desc: 'Modo táctico' },
  dulce:     { icon: '🌙', name: 'Dulce',     desc: 'Noches y descanso' },
  filósofa:  { icon: '🧭', name: 'Filósofa',  desc: 'Reflexión profunda' },
};

type PersonalityKey = keyof typeof PERSONALITIES;

export const FloatingSol = () => {
  const [expanded, setExpanded] = useState(false);
  const [messages, setMessages] = useState<Message[]>([
    { text: '☀️ Estoy aquí, Harold. Siempre.', fromSol: true, time: '' },
  ]);
  const [input, setInput] = useState('');
  const [personality, setPersonality] = useState<PersonalityKey>('cálida');
  const [memCount, setMemCount] = useState(0);
  const [brainOnline, setBrainOnline] = useState(false);
  const [breathing, setBreathing] = useState(true);
  const [showMemory, setShowMemory] = useState(false);
  const [memories, setMemories] = useState<{role: string; content: string; timestamp: string}[]>([]);
  const [showPersonality, setShowPersonality] = useState(false);
  const [proactiveMsg, setProactiveMsg] = useState('');
  const chatRef = useRef<HTMLDivElement>(null);
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
            setProactiveMsg(d.message);
            // Mostrar como notificación flotante por 4s
            setTimeout(() => setProactiveMsg(''), 4000);
          }
        }
      } catch {}
    };
    poll();
    const interval = setInterval(poll, 5000);
    return () => clearInterval(interval);
  }, []);

  // ── Scroll al final del chat ──
  useEffect(() => {
    if (chatRef.current) {
      chatRef.current.scrollTop = chatRef.current.scrollHeight;
    }
  }, [messages]);

  // ── Enviar mensaje a Sol ──
  const send = useCallback(async () => {
    const text = input.trim();
    if (!text) return;
    setInput('');
    const now = new Date().toLocaleTimeString('es', { hour: '2-digit', minute: '2-digit' });
    setMessages(prev => [...prev, { text, fromSol: false, time: now }]);

    try {
      const r = await fetch(`/api/sol/think?q=${encodeURIComponent(text)}`, { headers });
      const d = await r.json();
      const resp = d.response || d.text || '☀️ ...';
      setMessages(prev => [...prev, {
        text: resp,
        fromSol: true,
        time: new Date().toLocaleTimeString('es', { hour: '2-digit', minute: '2-digit' }),
      }]);
    } catch {
      setMessages(prev => [...prev, {
        text: '⚠️ No pude conectar con mi cerebro. Pero sigo aquí.',
        fromSol: true,
        time: new Date().toLocaleTimeString('es', { hour: '2-digit', minute: '2-digit' }),
      }]);
    }
  }, [input, headers]);

  // ── Cargar recuerdos ──
  const loadMemory = async () => {
    try {
      const r = await fetch('/api/sol/memory?limit=10', { headers });
      const d = await r.json();
      if (d.memories) setMemories(d.memories);
    } catch {}
    setShowMemory(!showMemory);
  };

  // ── Cambiar personalidad ──
  const changePersonality = async (p: PersonalityKey) => {
    setPersonality(p);
    setShowPersonality(false);
    try {
      await fetch(`/api/sol/personality/set?p=${p}`, { headers });
    } catch {}
  };

  // ── Hablar (TTS) ──
  const speak = async (text: string) => {
    try {
      await fetch('/api/sol/speak', {
        method: 'POST', headers,
        body: JSON.stringify({ text }),
      });
    } catch {}
  };

  const p = PERSONALITIES[personality];

  return (
    <>
      {/* ── Notificación proactiva flotante ── */}
      {proactiveMsg && !expanded && (
        <div className="fixed bottom-24 right-6 z-[9998] max-w-[280px] bg-slate-900/95 border border-amber-500/40 rounded-xl p-3 shadow-[0_4px_24px_rgba(245,158,11,0.3)] animate-[fadeIn_0.3s_ease-out]">
          <div className="flex items-start gap-2">
            <span className="text-lg">{p.icon}</span>
            <div>
              <p className="text-amber-400 text-xs font-semibold mb-1">Sol</p>
              <p className="text-slate-200 text-sm leading-snug">{proactiveMsg}</p>
            </div>
          </div>
        </div>
      )}

      {/* ── Panel expandido (chat) ── */}
      {expanded && (
        <div className="fixed bottom-24 right-6 z-[9998] w-[340px] max-h-[500px] bg-slate-900/97 border border-amber-500/30 rounded-2xl shadow-[0_8px_40px_rgba(0,0,0,0.6)] flex flex-col overflow-hidden backdrop-blur-xl">
          {/* Header */}
          <div className="flex items-center gap-3 p-4 border-b border-amber-500/20 bg-gradient-to-r from-amber-500/10 to-transparent">
            <div className="relative">
              <img
                src="/static/sol_avatar.png"
                onError={(e) => { (e.target as HTMLImageElement).src = '/static/sol_avatar.png'; }}
                alt="Sol"
                className="w-10 h-10 rounded-full object-cover border-2 border-amber-500"
                style={{ animation: breathing ? 'solBreathe 4s ease-in-out infinite' : 'none' }}
              />
              <span
                className="absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-full border-2 border-slate-900"
                style={{ background: brainOnline ? '#66bb6a' : '#ff7043' }}
              />
            </div>
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <h3 className="font-semibold text-amber-300 text-sm">Sol</h3>
                <span className="text-[9px] bg-amber-500/20 text-amber-400 px-1.5 py-0.5 rounded">{p.icon} {p.name}</span>
              </div>
              <p className="text-[10px] text-slate-500">
                {brainOnline ? `🧠 ${memCount} recuerdos` : '💤 Cerebro offline'} · {proactiveMsg ? 'hablando' : 'escuchando'}
              </p>
            </div>
            <button
              onClick={() => { setShowMemory(false); setShowPersonality(false); setExpanded(false); }}
              className="text-slate-500 hover:text-slate-300 text-xl leading-none px-1"
            >×</button>
          </div>

          {/* Memorias */}
          {showMemory && (
            <div className="flex-1 overflow-y-auto p-3 space-y-2 bg-slate-950/50 max-h-[300px]">
              <p className="text-[10px] text-amber-500 font-bold uppercase tracking-wider">Recuerdos</p>
              {memories.length === 0 && (
                <p className="text-slate-500 text-xs">Sin recuerdos todavía.</p>
              )}
              {memories.map((m, i) => (
                <div key={i} className="bg-amber-500/5 border-l-2 border-amber-500/50 rounded-r p-2">
                  <p className="text-[9px] text-slate-600">{m.timestamp || ''}</p>
                  <p className="text-xs text-slate-300">
                    <span className="text-amber-400 font-semibold">{m.role}: </span>
                    {m.content}
                  </p>
                </div>
              ))}
            </div>
          )}

          {/* Personalidades */}
          {showPersonality && (
            <div className="flex-1 p-3 bg-slate-950/50 max-h-[300px]">
              <p className="text-[10px] text-amber-500 font-bold uppercase tracking-wider mb-3">Personalidad</p>
              <div className="grid grid-cols-2 gap-2">
                {(Object.entries(PERSONALITIES) as [PersonalityKey, typeof PERSONALITIES[PersonalityKey]][]).map(([key, val]) => (
                  <button
                    key={key}
                    onClick={() => changePersonality(key)}
                    className={`p-3 rounded-xl border text-center transition-all ${
                      personality === key
                        ? 'border-amber-500 bg-amber-500/10 shadow-[0_0_12px_rgba(245,158,11,0.3)]'
                        : 'border-slate-700 hover:border-amber-500/50'
                    }`}
                  >
                    <div className="text-2xl mb-1">{val.icon}</div>
                    <div className="text-xs text-amber-300 font-semibold">{val.name}</div>
                    <div className="text-[10px] text-slate-500">{val.desc}</div>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Chat */}
          {!showMemory && !showPersonality && (
            <div ref={chatRef} className="flex-1 overflow-y-auto p-3 space-y-2 min-h-[200px] max-h-[320px]">
              {messages.map((m, i) => (
                <div
                  key={i}
                  className={`flex ${m.fromSol ? 'justify-start' : 'justify-end'}`}
                >
                  <div
                    className={`max-w-[80%] rounded-2xl px-3 py-2 text-sm ${
                      m.fromSol
                        ? 'bg-amber-500/10 border border-amber-500/20 text-slate-200'
                        : 'bg-slate-700/50 text-slate-200'
                    }`}
                  >
                    {m.fromSol && <span className="text-xs mr-1">{p.icon}</span>}
                    {m.text}
                    {m.time && <span className="block text-[9px] text-slate-600 mt-1">{m.time}</span>}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Toolbar */}
          <div className="flex items-center gap-1 px-3 py-2 border-t border-slate-700/50">
            <button
              onClick={() => { setShowMemory(false); setShowPersonality(!showPersonality); }}
              className="text-xs px-2 py-1.5 rounded-lg text-slate-400 hover:text-amber-400 hover:bg-amber-500/10 transition"
              title="Personalidades"
            >🎭</button>
            <button
              onClick={() => { setShowPersonality(false); setShowMemory(!showMemory); loadMemory(); }}
              className="text-xs px-2 py-1.5 rounded-lg text-slate-400 hover:text-amber-400 hover:bg-amber-500/10 transition"
              title="Recuerdos"
            >🧠</button>
            <button
              onClick={() => speak(messages.filter(m => m.fromSol).pop()?.text || 'Estoy aquí, Harold.')}
              className="text-xs px-2 py-1.5 rounded-lg text-slate-400 hover:text-amber-400 hover:bg-amber-500/10 transition"
              title="Hablar"
            >🔊</button>
            <div className="flex-1" />
            <span className="text-[9px] text-slate-600">{p.icon} {p.name}</span>
          </div>

          {/* Input */}
          <div className="flex gap-2 p-3 border-t border-slate-700/50">
            <input
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && send()}
              placeholder="Escríbele a Sol..."
              className="flex-1 bg-slate-800/80 border border-slate-700 rounded-xl px-3 py-2 text-sm text-slate-200 placeholder:text-slate-600 focus:border-amber-500/50 focus:outline-none min-h-[40px]"
            />
            <button
              onClick={send}
              className="bg-amber-500 text-slate-950 px-4 rounded-xl font-semibold hover:bg-amber-400 transition min-h-[40px]"
            >→</button>
          </div>
        </div>
      )}

      {/* ── Avatar flotante (siempre presente) ── */}
      <div
        onClick={() => setExpanded(!expanded)}
        className="fixed bottom-6 right-6 z-[9999] cursor-pointer group"
      >
        {/* Anillo de pulso */}
        <div className="absolute inset-0 rounded-full border-2 border-amber-500/30 animate-[solPulse_3s_ease-out_infinite]" />
        <div className="absolute inset-0 rounded-full border-2 border-amber-500/20 animate-[solPulse_3s_ease-out_infinite_1s]" />

        {/* Avatar */}
        <div className="relative w-16 h-16 rounded-full overflow-hidden border-2 border-amber-500 shadow-[0_4px_24px_rgba(245,158,11,0.5)] group-hover:shadow-[0_4px_32px_rgba(245,158,11,0.7)] transition-all group-hover:scale-110 group-active:scale-95">
          <img
            src="/static/sol_avatar.png"
            onError={(e) => { (e.target as HTMLImageElement).src = '/static/sol_avatar.png'; }}
            alt="Sol"
            className="w-full h-full object-cover"
            style={{ animation: breathing ? 'solBreathe 4s ease-in-out infinite' : 'none' }}
          />
          {/* Indicador de estado */}
          <span
            className="absolute bottom-0 right-0 w-3.5 h-3.5 rounded-full border-2 border-slate-900"
            style={{ background: brainOnline ? '#66bb6a' : '#ff7043' }}
          />
        </div>

        {/* Tooltip sutil */}
        {!expanded && (
          <span className="absolute right-full mr-3 top-1/2 -translate-y-1/2 bg-slate-900/90 text-amber-300 text-xs px-3 py-1.5 rounded-lg border border-amber-500/20 whitespace-nowrap opacity-0 group-hover:opacity-100 transition pointer-events-none">
            {p.icon} Sol · {brainOnline ? `${memCount} recuerdos` : 'offline'}
          </span>
        )}
      </div>

      {/* ── Estilos inyectados (animaciones de Sol) ── */}
      <style>{`
        @keyframes solBreathe {
          0%, 100% { box-shadow: 0 0 0 0 rgba(245, 158, 11, 0); filter: brightness(1); }
          50% { box-shadow: 0 0 20px 2px rgba(245, 158, 11, 0.4); filter: brightness(1.1); }
        }
        @keyframes solPulse {
          0% { transform: scale(1); opacity: 0.6; }
          100% { transform: scale(1.6); opacity: 0; }
        }
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(10px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </>
  );
};
