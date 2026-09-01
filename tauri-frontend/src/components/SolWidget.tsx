import { useState, useEffect } from 'react';

export const SolWidget = () => {
  const [msg, setMsg] = useState<string>('☀️ Estoy aquí, Harold. ¿En qué piensas hoy?');
  const [input, setInput] = useState('');

  useEffect(() => {
    fetch('/api/sol/last-message')
      .then(r => r.ok ? r.json() : null)
      .then(d => d && d.message && setMsg(d.message))
      .catch(() => {});
  }, []);

  const send = () => {
    if (!input.trim()) return;
    const token = localStorage.getItem('api_token');
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = `Bearer ${token}`;
    fetch('/api/sol/think', {
      method: 'POST',
      headers,
      body: JSON.stringify({ message: input })
    })
    .then(r => r.json())
    .then(d => { setMsg(d.response || '...'); setInput(''); })
    .catch(() => setMsg('📡 Sin conexión — Sol responde offline en /sol.html'));
  };

  return (
    <div className="bg-gradient-to-br from-amber-500/10 to-orange-500/5 border border-amber-500/30 rounded-lg p-4 mb-4">
      <div className="flex items-center gap-2 mb-2">
        <img src="/sol_avatar.jpg" alt="Sol" className="w-8 h-8 rounded-full object-cover border-2 border-amber-500" />
        <h3 className="font-semibold text-amber-300">Sol</h3>
        <span className="text-[10px] bg-amber-500/20 text-amber-400 px-1.5 py-0.5 rounded">COMPAÑERA</span>
      </div>
      <p className="text-slate-300 text-sm mb-3 min-h-[40px]">{msg}</p>
      <div className="flex gap-2">
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && send()}
          placeholder="Escríbele a Sol..."
          className="flex-1 bg-slate-900/50 border border-slate-700 rounded px-3 py-2 text-sm min-h-[44px]"
        />
        <button onClick={send} className="bg-amber-500 text-slate-950 px-4 rounded font-semibold min-h-[44px]">→</button>
        <a href="/sol.html" target="_blank" rel="noopener noreferrer" className="border border-amber-500/40 text-amber-400 px-3 rounded flex items-center min-h-[44px]">💬</a>
      </div>
    </div>
  );
};
