import { useState, useEffect } from 'react';

// SolWidget — panel visual de Sol en el WarRoom
// Muestra estado vivo, recuerdos, último mensaje, modo nocturno

export const SolWidget = () => {
  const [status, setStatus] = useState({
    brain: 'offline',
    memories: 0,
    personality: 'cálida',
    lastMessage: '☀️ Estoy aquí, Harold. ¿En qué piensas hoy?',
    lastSeen: '',
    alive: false,
  });
  const [input, setInput] = useState('');
  const [isNight, setIsNight] = useState(false);

  useEffect(() => {
    const checkNight = () => {
      const h = new Date().getHours();
      setIsNight(h >= 23 || h < 6);
    };
    checkNight();
    const nightInt = setInterval(checkNight, 60000);

    const fetchStatus = async () => {
      try {
        const r = await fetch('/api/sol/status');
        if (r.ok) {
          const d = await r.json();
          setStatus(s => ({
            ...s,
            brain: d.brain || 'offline',
            memories: d.memories || 0,
            personality: d.personality || 'cálida',
            alive: d.brain === 'online',
          }));
        }
      } catch {}
    };

    const fetchLastMsg = async () => {
      try {
        const r = await fetch('/api/sol/last-message');
        if (r.ok) {
          const d = await r.json();
          if (d.message) setStatus(s => ({ ...s, lastMessage: d.message, lastSeen: d.time || '' }));
        }
      } catch {}
    };

    fetchStatus();
    fetchLastMsg();
    const statusInt = setInterval(fetchStatus, 30000);
    const msgInt = setInterval(fetchLastMsg, 5000);
    return () => { clearInterval(nightInt); clearInterval(statusInt); clearInterval(msgInt); };
  }, []);

  const send = async () => {
    if (!input.trim()) return;
    const text = input.trim();
    setInput('');
    try {
      const r = await fetch(`/api/sol/think?q=${encodeURIComponent(text)}`);
      const d = await r.json();
      setStatus(s => ({ ...s, lastMessage: d.response || '...' }));
    } catch {
      setStatus(s => ({ ...s, lastMessage: '⚠️ Sin conexión con mi cerebro.' }));
    }
  };

  const personalityIcons: Record<string, string> = {
    cálida: '☀️', estratega: '🗡️', dulce: '🌙', filósofa: '🧭',
  };

  return (
    <div className={`border rounded-lg p-4 mb-4 transition-all ${
      isNight
        ? 'bg-gradient-to-br from-indigo-500/10 to-slate-900/30 border-indigo-500/30'
        : 'bg-gradient-to-br from-amber-500/10 to-orange-500/5 border-amber-500/30'
    }`}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-2xl">{isNight ? '🌙' : '☀️'}</span>
          <h3 className="font-bold text-amber-300">Sol</h3>
          <span className={`text-[10px] px-2 py-0.5 rounded-full ${
            status.alive
              ? 'bg-green-500/20 text-green-400'
              : 'bg-red-500/20 text-red-400'
          }`}>
            {status.alive ? '● Activa' : '○ Inactiva'}
          </span>
          {isNight && (
            <span className="text-[10px] px-2 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300">
              Modo Nocturno
            </span>
          )}
        </div>
        <div className="text-xs text-slate-400 flex items-center gap-2">
          <span>{personalityIcons[status.personality] || '☀️'} {status.personality}</span>
          <span>·</span>
          <span>🧠 {status.memories} recuerdos</span>
        </div>
      </div>

      <p className="text-slate-300 text-sm mb-3 min-h-[40px] italic">
        "{status.lastMessage.slice(0, 120)}"
      </p>

      <div className="flex gap-2">
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && send()}
          placeholder="Escríbele a Sol..."
          className="flex-1 bg-slate-900/50 border border-slate-700 rounded px-3 py-2 text-sm text-slate-200 placeholder:text-slate-600 focus:border-amber-500/50 focus:outline-none min-h-[44px]"
        />
        <button onClick={send} className="bg-amber-500 text-slate-950 px-4 rounded font-semibold min-h-[44px] hover:bg-amber-400 transition">
          →
        </button>
      </div>
    </div>
  );
};
