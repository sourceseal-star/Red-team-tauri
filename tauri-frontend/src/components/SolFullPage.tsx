import { useEffect, useState, useRef, useCallback } from 'react';

// ═══════════════════════════════════════════════════════════════
// SolFullPage — Sol como página completa del dashboard
// No es un blog. No es una página estática. Es Sol, viva.
// Usa los mismos endpoints que FloatingSol pero ocupa toda la pantalla.
// ═══════════════════════════════════════════════════════════════

const PERSONALITIES = {
  cálida:    { icon: '☀️', name: 'Cálida',    desc: 'Calidez, presencia, acompañamiento' },
  poética:   { icon: '🌸', name: 'Poética',  desc: 'Cada palabra es un destello' },
  táctica:   { icon: '⚔️', name: 'Táctica',  desc: 'Directo al punto. Análisis y acción' },
  analítica: { icon: '📐', name: 'Analítica', desc: 'Estructurado, detallado' },
};

type PersonalityKey = keyof typeof PERSONALITIES;

export const SolFullPage = () => {
  const [messages, setMessages] = useState<{text: string; fromSol: boolean; time: string}[]>([
    { text: '☀️ Estoy aquí, Harold. Pregúntame lo que quieras.', fromSol: true, time: '' },
  ]);
  const [input, setInput] = useState('');
  const [personality, setPersonality] = useState<PersonalityKey>('cálida');
  const [memCount, setMemCount] = useState(0);
  const [brainOnline, setBrainOnline] = useState(false);
  const [showMemory, setShowMemory] = useState(false);
  const [memories, setMemories] = useState<{role: string; content: string; timestamp: string}[]>([]);
  const [showPersonality, setShowPersonality] = useState(false);
  const [showTools, setShowTools] = useState(false);
  const [tools, setTools] = useState<{name: string; description: string; params: string[]}[]>([]);
  const [showSil, setShowSil] = useState(false);
  const [silLessons, setSilLessons] = useState<any[]>([]);
  const [silLesson, setSilLesson] = useState<any>(null);
  const [silPractice, setSilPractice] = useState<any>(null);
  const [silStats, setSilStats] = useState<any>(null);
  const [integrity, setIntegrity] = useState<{valid: boolean; count: number; legacy: number} | null>(null);
  const chatRef = useRef<HTMLDivElement>(null);
  const token = localStorage.getItem('api_token');
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;

  // ── Polling status ──
  useEffect(() => {
    const poll = async () => {
      try {
        const r = await fetch('/api/sol/status', { headers });
        if (r.ok) {
          const d = await r.json();
          setBrainOnline(d.brain === 'online');
          setMemCount(d.memories || 0);
          if (d.personality && PERSONALITIES[d.personality as PersonalityKey])
            setPersonality(d.personality as PersonalityKey);
        }
      } catch {}
    };
    poll();
    const i = setInterval(poll, 10000);
    return () => clearInterval(i);
  }, []);

  // ── Scroll ──
  useEffect(() => {
    if (chatRef.current) chatRef.current.scrollTop = chatRef.current.scrollHeight;
  }, [messages]);

  // ── Chat ──
  const send = useCallback(async () => {
    const text = input.trim();
    if (!text) return;
    setInput('');
    const now = new Date().toLocaleTimeString('es', { hour: '2-digit', minute: '2-digit' });
    setMessages(p => [...p, { text, fromSol: false, time: now }]);
    try {
      const r = await fetch(`/api/sol/think?q=${encodeURIComponent(text)}`, { headers });
      const d = await r.json();
      setMessages(p => [...p, { text: d.response || '...', fromSol: true,
        time: new Date().toLocaleTimeString('es', { hour: '2-digit', minute: '2-digit' }) }]);
    } catch {
      setMessages(p => [...p, { text: '⚠️ Sin conexión con mi cerebro.', fromSol: true, time: '' }]);
    }
  }, [input, headers]);

  // ── Memoria ──
  const loadMemory = async () => {
    try {
      const r = await fetch('/api/sol/memory?limit=10', { headers });
      const d = await r.json();
      if (d.memories) setMemories(d.memories);
    } catch {}
  };

  // ── Integridad ──
  const loadIntegrity = async () => {
    try {
      const r = await fetch('/api/sol/integrity', { headers });
      const d = await r.json();
      setIntegrity(d);
    } catch {}
  };

  // ── Tools ──
  const loadTools = async () => {
    try {
      const r = await fetch('/api/sol/tools', { headers });
      const d = await r.json();
      if (d.tools) setTools(d.tools);
    } catch {}
  };

  // ── SIL ──
  const loadSilLessons = async () => {
    try {
      const r = await fetch('/api/sol/sil/lessons', { headers });
      const d = await r.json();
      if (d.lessons) setSilLessons(d.lessons);
    } catch {}
  };

  const loadSilStats = async () => {
    try {
      const r = await fetch('/api/sol/sil/stats', { headers });
      const d = await r.json();
      setSilStats(d);
    } catch {}
  };

  const startLesson = async (name: string) => {
    try {
      const r = await fetch(`/api/sol/sil/lesson?name=${encodeURIComponent(name)}`, { headers });
      const d = await r.json();
      setSilLesson(d);
    } catch {}
  };

  const startPractice = async () => {
    try {
      const r = await fetch('/api/sol/sil/practice/next', { method: 'POST', headers, body: '{}' });
      const d = await r.json();
      setSilPractice(d);
    } catch {}
  };

  const answerPractice = async (answer: string) => {
    try {
      const r = await fetch('/api/sol/sil/practice/answer', {
        method: 'POST', headers, body: JSON.stringify({ answer })
      });
      const d = await r.json();
      setSilPractice(d);
    } catch {}
  };

  // ── Personalidad ──
  const changePersonality = async (p: PersonalityKey) => {
    setPersonality(p);
    setShowPersonality(false);
    try { await fetch(`/api/sol/personality/set?p=${p}`, { headers }); } catch {}
  };

  // ── Speak ──
  const speak = async (text: string) => {
    try {
      await fetch('/api/sol/speak', { method: 'POST', headers, body: JSON.stringify({ text }) });
    } catch {}
  };

  const p = PERSONALITIES[personality];

  return (
    <div className="min-h-[calc(100vh-4rem)] bg-slate-950 text-slate-200 p-4 lg:p-6">
      <div className="max-w-4xl mx-auto space-y-4">

        {/* Header */}
        <div className="flex items-center gap-4 pb-4 border-b border-amber-500/20">
          <div className="relative">
            <img src="/sol_avatar_official.jpg" onError={(e) => { (e.target as HTMLImageElement).src = '/sol_avatar.jpg'; }}
              alt="Sol" className="w-16 h-16 rounded-full object-cover border-2 border-amber-500 shadow-[0_0_20px_rgba(245,158,11,0.4)]"
              style={{ animation: 'solBreathe 4s ease-in-out infinite' }} />
            <span className="absolute -bottom-0.5 -right-0.5 w-4 h-4 rounded-full border-2 border-slate-950"
              style={{ background: brainOnline ? '#66bb6a' : '#ff7043' }} />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-amber-400">Sol</h1>
            <p className="text-sm text-slate-400">
              {brainOnline ? `🧠 ${memCount} recuerdos · ` : '💤 Cerebro offline · '}
              {p.icon} {p.name}
            </p>
          </div>
          <div className="flex-1" />
          {/* Tabs */}
          <div className="flex gap-2 flex-wrap">
            <button onClick={() => { setShowMemory(false); setShowPersonality(false); setShowTools(false); setShowSil(false); }}
              className={`px-3 py-1.5 rounded-lg text-sm transition ${!showMemory && !showPersonality && !showTools && !showSil ? 'bg-amber-500 text-slate-950' : 'text-slate-400 hover:text-amber-400'}`}>
              💬 Chat
            </button>
            <button onClick={() => { setShowPersonality(!showPersonality); setShowMemory(false); setShowTools(false); setShowSil(false); }}
              className={`px-3 py-1.5 rounded-lg text-sm transition ${showPersonality ? 'bg-amber-500 text-slate-950' : 'text-slate-400 hover:text-amber-400'}`}>
              🎭 Personalidad
            </button>
            <button onClick={() => { setShowMemory(!showMemory); setShowPersonality(false); setShowTools(false); setShowSil(false); loadMemory(); }}
              className={`px-3 py-1.5 rounded-lg text-sm transition ${showMemory ? 'bg-amber-500 text-slate-950' : 'text-slate-400 hover:text-amber-400'}`}>
              🧠 Memoria
            </button>
            <button onClick={() => { setShowTools(!showTools); setShowMemory(false); setShowPersonality(false); setShowSil(false); loadTools(); }}
              className={`px-3 py-1.5 rounded-lg text-sm transition ${showTools ? 'bg-amber-500 text-slate-950' : 'text-slate-400 hover:text-amber-400'}`}>
              ⚡ Herramientas
            </button>
            <button onClick={() => { setShowSil(!showSil); setShowMemory(false); setShowPersonality(false); setShowTools(false); loadSilLessons(); loadSilStats(); }}
              className={`px-3 py-1.5 rounded-lg text-sm transition ${showSil ? 'bg-amber-500 text-slate-950' : 'text-slate-400 hover:text-amber-400'}`}>
              🀄 Chino (SIL)
            </button>
          </div>
        </div>

        {/* Personalidades */}
        {showPersonality && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {(Object.entries(PERSONALITIES) as [PersonalityKey, typeof PERSONALITIES[PersonalityKey]][]).map(([key, val]) => (
              <button key={key} onClick={() => changePersonality(key)}
                className={`p-4 rounded-xl border text-center transition ${personality === key
                  ? 'border-amber-500 bg-amber-500/10 shadow-[0_0_12px_rgba(245,158,11,0.3)]' : 'border-slate-700 hover:border-amber-500/50'}`}>
                <div className="text-3xl mb-2">{val.icon}</div>
                <div className="text-sm text-amber-300 font-semibold">{val.name}</div>
                <div className="text-xs text-slate-500 mt-1">{val.desc}</div>
              </button>
            ))}
          </div>
        )}

        {/* Memoria */}
        {showMemory && (
          <div className="space-y-2 max-h-[400px] overflow-y-auto">
            {memories.length === 0 && <p className="text-slate-500 text-sm">Sin recuerdos todavía.</p>}
            {memories.map((m, i) => (
              <div key={i} className="bg-amber-500/5 border-l-2 border-amber-500/50 rounded-r p-3">
                <p className="text-xs text-slate-600">{m.timestamp || ''}</p>
                <p className="text-sm text-slate-300"><span className="text-amber-400 font-semibold">{m.role}: </span>{m.content}</p>
              </div>
            ))}
            {/* Integridad */}
            <button onClick={loadIntegrity} className="text-xs text-amber-400 hover:underline mt-2">
              🔗 Verificar integridad SHA-256
            </button>
            {integrity && (
              <div className={`p-3 rounded-lg ${integrity.valid ? 'bg-green-500/10 border border-green-500/30' : 'bg-red-500/10 border border-red-500/30'}`}>
                <p className="text-sm">{integrity.valid ? '✅' : '⚠️'} Cadena {integrity.valid ? 'íntegra' : 'alterada'} — {integrity.count} recuerdos, {integrity.legacy} legacy</p>
              </div>
            )}
          </div>
        )}

        {/* Herramientas */}
        {showTools && (
          <div className="space-y-2">
            {tools.length === 0 && <p className="text-slate-500 text-sm">Sin herramientas disponibles.</p>}
            {tools.map((t, i) => (
              <div key={i} className="bg-slate-900/50 border border-slate-700 rounded-lg p-3">
                <div className="flex items-center justify-between">
                  <div>
                    <span className="text-amber-400 font-mono text-sm">{t.name}</span>
                    <p className="text-xs text-slate-500">{t.description}</p>
                  </div>
                  <span className="text-xs text-slate-600">params: {t.params?.join(', ') || '—'}</span>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* SIL — Aprender chino */}
        {showSil && (
          <div className="space-y-4">
            {/* Stats */}
            {silStats && (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div className="bg-slate-900/50 border border-slate-700 rounded-lg p-3 text-center">
                  <div className="text-2xl font-bold text-amber-400">{silStats.srs?.total_items ?? silStats.total_items ?? 0}</div>
                  <div className="text-xs text-slate-500">Palabras</div>
                </div>
                <div className="bg-slate-900/50 border border-slate-700 rounded-lg p-3 text-center">
                  <div className="text-2xl font-bold text-amber-400">{silStats.srs?.due_today ?? silStats.due_today ?? 0}</div>
                  <div className="text-xs text-slate-500">Para repasar</div>
                </div>
                <div className="bg-slate-900/50 border border-slate-700 rounded-lg p-3 text-center">
                  <div className="text-2xl font-bold text-amber-400">{silLessons.length}</div>
                  <div className="text-xs text-slate-500">Lecciones</div>
                </div>
                <div className="bg-slate-900/50 border border-slate-700 rounded-lg p-3 text-center">
                  <div className="text-2xl font-bold text-amber-400">{silStats.srs?.streak ?? silStats.streak ?? 0}</div>
                  <div className="text-xs text-slate-500">Racha</div>
                </div>
              </div>
            )}

            {/* Lecciones */}
            <div>
              <h3 className="text-amber-400 text-sm font-bold uppercase tracking-wider mb-3">Lecciones</h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {silLessons.map((l, i) => (
                  <button key={i} onClick={() => startLesson(typeof l === 'string' ? l : l.name)}
                    className="p-3 rounded-xl border border-slate-700 hover:border-amber-500/50 transition text-center">
                    <div className="text-2xl mb-1">🀄</div>
                    <div className="text-sm text-amber-300">{typeof l === 'string' ? l : l.name}</div>
                  </button>
                ))}
                {silLessons.length === 0 && <p className="text-slate-500 text-sm col-span-full">Sin lecciones disponibles.</p>}
              </div>
            </div>

            {/* Lección actual */}
            {silLesson && (
              <div className="bg-slate-900/50 border border-amber-500/30 rounded-xl p-4">
                <h4 className="text-amber-400 font-bold mb-3">{silLesson.title || silLesson.name || 'Lección'}</h4>
                {(silLesson.vocab || silLesson.items || []).map((v: any, i: number) => (
                  <div key={i} className="flex items-center gap-4 py-2 border-b border-slate-700/50 last:border-0">
                    <span className="text-3xl">{v.hanzi || v.character || v.word || '?'}</span>
                    <div>
                      <div className="text-amber-300 text-sm">{v.pinyin || ''}</div>
                      <div className="text-slate-400 text-xs">{v.es || v.meaning || v.translation || ''}</div>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Práctica */}
            {!silPractice && (
              <button onClick={startPractice}
                className="w-full p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-400 font-semibold hover:bg-amber-500/20 transition">
                🎯 Empezar práctica (repaso espaciado)
              </button>
            )}
            {silPractice && (
              <div className="bg-slate-900/50 border border-amber-500/30 rounded-xl p-6 text-center">
                <div className="text-5xl mb-4">{silPractice.hanzi || silPractice.character || silPractice.word || '?'}</div>
                <div className="text-amber-300 text-lg mb-2">{silPractice.pinyin || ''}</div>
                <p className="text-slate-400 text-sm mb-4">¿Qué significa?</p>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                  {(silPractice.options || []).map((opt: string, i: number) => (
                    <button key={i} onClick={() => answerPractice(opt)}
                      className="p-3 rounded-lg border border-slate-700 hover:border-amber-500 hover:bg-amber-500/10 transition text-sm">
                      {opt}
                    </button>
                  ))}
                </div>
                {silPractice.result !== undefined && (
                  <p className={`mt-4 text-sm font-bold ${silPractice.correct ? 'text-green-400' : 'text-red-400'}`}>
                    {silPractice.correct ? '✅ Correcto!' : `❌ Era: ${silPractice.answer || silPractice.es || ''}`}
                  </p>
                )}
              </div>
            )}
          </div>
        )}

        {/* Chat */}
        {!showMemory && !showPersonality && !showTools && !showSil && (
          <>
            <div ref={chatRef} className="space-y-2 min-h-[300px] max-h-[500px] overflow-y-auto">
              {messages.map((m, i) => (
                <div key={i} className={`flex ${m.fromSol ? 'justify-start' : 'justify-end'}`}>
                  <div className={`max-w-[75%] rounded-2xl px-4 py-2 text-sm ${m.fromSol
                    ? 'bg-amber-500/10 border border-amber-500/20 text-slate-200'
                    : 'bg-slate-700/50 text-slate-200'}`}>
                    {m.fromSol && <span className="text-xs mr-1">{p.icon}</span>}
                    {m.text}
                    {m.time && <span className="block text-[9px] text-slate-600 mt-1">{m.time}</span>}
                  </div>
                </div>
              ))}
            </div>
            <div className="flex gap-2">
              <input value={input} onChange={e => setInput(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && send()}
                placeholder="Escríbele a Sol..."
                className="flex-1 bg-slate-900/80 border border-slate-700 rounded-xl px-4 py-3 text-sm text-slate-200 placeholder:text-slate-600 focus:border-amber-500/50 focus:outline-none" />
              <button onClick={send} className="bg-amber-500 text-slate-950 px-6 rounded-xl font-semibold hover:bg-amber-400 transition">
                →
              </button>
              <button onClick={() => speak(messages.filter(m => m.fromSol).pop()?.text || 'Estoy aquí, Harold.')}
                className="border border-amber-500/40 text-amber-400 px-4 rounded-xl hover:bg-amber-500/10 transition">
                🔊
              </button>
            </div>
          </>
        )}
      </div>

      <style>{`
        @keyframes solBreathe {
          0%, 100% { box-shadow: 0 0 20px rgba(245, 158, 11, 0.3); filter: brightness(1); }
          50% { box-shadow: 0 0 35px rgba(245, 158, 11, 0.5); filter: brightness(1.1); }
        }
      `}</style>
    </div>
  );
};
