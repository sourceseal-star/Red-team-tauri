import { useEffect, useState } from 'react';

type Action = { id: string; label: string; run: () => void };

export default function CommandPalette({ actions }: { actions: Action[] }) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState('');

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') { e.preventDefault(); setOpen(true); }
      if (e.key === 'Escape') setOpen(false);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  const filtered = actions.filter(a => a.label.toLowerCase().includes(q.toLowerCase()));

  if (!open) {
    return (
      <button onClick={() => setOpen(true)}
              className="px-3 py-1.5 border border-[var(--ss-border)] text-gray-400 text-xs hover:border-cyan-400 hover:text-cyan-300 transition">
        ⌘K Comandos
      </button>
    );
  }

  return (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-start justify-center pt-[15vh]"
         onClick={() => setOpen(false)}>
      <div onClick={(e) => e.stopPropagation()}
           className="w-full max-w-md bg-[var(--ss-bg-2)] border border-cyan-500/50 ss-glow">
        <input autoFocus value={q} onChange={(e) => setQ(e.target.value)}
               placeholder="Escribe un comando..."
               className="w-full bg-transparent border-b border-[var(--ss-border)] px-4 py-3 text-sm outline-none text-gray-200" />
        <div className="max-h-80 overflow-y-auto">
          {filtered.map(a => (
            <button key={a.id}
                    onClick={() => { a.run(); setOpen(false); setQ(''); }}
                    className="w-full text-left px-4 py-2.5 text-sm text-gray-300 hover:bg-cyan-500/10 hover:text-cyan-300 border-b border-[var(--ss-border)]">
              → {a.label}
            </button>
          ))}
          {filtered.length === 0 && <div className="p-4 text-gray-500 text-xs">Sin resultados</div>}
        </div>
      </div>
    </div>
  );
}
