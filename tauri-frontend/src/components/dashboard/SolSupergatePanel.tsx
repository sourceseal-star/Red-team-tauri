import { useCallback, useEffect, useRef, useState } from 'react';
import { AlertTriangle, Check, RefreshCw, Save, ShieldCheck } from 'lucide-react';

type SupergateSnapshot = {
  config: Record<string, unknown>;
  version: string;
  mtime_ns: number;
  modified_at: string;
  file: string;
  probe: {
    available: boolean;
    status_code: number | null;
    url: string;
    error?: string;
  };
};

const API_PATH = '/api/ops/sol-supergate';

export default function SolSupergatePanel() {
  const [snapshot, setSnapshot] = useState<SupergateSnapshot | null>(null);
  const [draft, setDraft] = useState('');
  const [dirty, setDirty] = useState(false);
  const [externalChange, setExternalChange] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');
  const dirtyRef = useRef(false);
  const versionRef = useRef('');

  const syncNow = useCallback(async (replaceDraft: boolean) => {
    setLoading(true);
    try {
      const response = await fetch(API_PATH);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const next = await response.json() as SupergateSnapshot;
      const changedWhileEditing =
        dirtyRef.current &&
        !!versionRef.current &&
        next.version !== versionRef.current;

      setSnapshot(next);
      versionRef.current = next.version;
      if (replaceDraft || !dirtyRef.current) {
        setDraft(JSON.stringify(next.config, null, 2));
        dirtyRef.current = false;
        setDirty(false);
        setExternalChange(false);
      } else if (changedWhileEditing) {
        setExternalChange(true);
      }
      setMessage(`Sincronizado ${new Date().toLocaleTimeString()}`);
    } catch (error) {
      setMessage(`No se pudo sincronizar: ${error instanceof Error ? error.message : 'error desconocido'}`);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void syncNow(true);
    const interval = window.setInterval(() => void syncNow(false), 4000);
    return () => window.clearInterval(interval);
  }, [syncNow]);

  const editDraft = (value: string) => {
    dirtyRef.current = true;
    setDirty(true);
    setExternalChange(false);
    setDraft(value);
  };

  const save = async () => {
    let config: Record<string, unknown>;
    try {
      const parsed: unknown = JSON.parse(draft);
      if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
        throw new Error('la raíz debe ser un objeto JSON');
      }
      config = parsed as Record<string, unknown>;
    } catch (error) {
      setMessage(`JSON inválido: ${error instanceof Error ? error.message : 'revisa el formato'}`);
      return;
    }

    setSaving(true);
    try {
      const response = await fetch(API_PATH, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          config,
          expected_version: versionRef.current,
        }),
      });
      if (response.status === 409) {
        setExternalChange(true);
        setMessage('El archivo cambió con nano. Sincroniza antes de guardar.');
        return;
      }
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const next = await response.json() as SupergateSnapshot;
      setSnapshot(next);
      versionRef.current = next.version;
      dirtyRef.current = false;
      setDirty(false);
      setExternalChange(false);
      setDraft(JSON.stringify(next.config, null, 2));
      setMessage('Cambios guardados en el archivo local.');
    } catch (error) {
      setMessage(`No se pudo guardar: ${error instanceof Error ? error.message : 'error desconocido'}`);
    } finally {
      setSaving(false);
    }
  };

  const probe = snapshot?.probe;
  const probeLabel = probe?.available ? 'Portero accesible' : 'Portero no accesible';

  return (
    <div className="p-4 space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-amber-300">
            <ShieldCheck size={16} />
            <h2 className="text-sm font-bold tracking-wide">SOL SUPERGATE</h2>
          </div>
          <p className="mt-1 text-[11px] text-slate-500">
            Configuración local sincronizada con cambios hechos desde Termux.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className={`rounded-full border px-2 py-1 text-[10px] ${
            probe?.available
              ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
              : 'border-slate-700 bg-slate-950/50 text-slate-500'
          }`}>
            <span className="mr-1">●</span>{probeLabel}
          </span>
          <button
            type="button"
            onClick={() => void syncNow(true)}
            disabled={loading}
            className="inline-flex items-center gap-1 rounded-lg border border-slate-700 px-2.5 py-1.5 text-[10px] font-bold text-slate-300 hover:border-slate-500 disabled:opacity-50"
          >
            <RefreshCw size={12} className={loading ? 'animate-spin' : ''} />
            Sincronizar
          </button>
        </div>
      </div>

      {externalChange && (
        <div className="flex items-start gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-[11px] text-amber-200">
          <AlertTriangle size={14} className="mt-0.5 shrink-0" />
          <span>Se detectó una edición externa. Pulsa «Sincronizar» antes de guardar para no sobrescribir lo que cambiaste con nano.</span>
        </div>
      )}

      <textarea
        value={draft}
        onChange={(event) => editDraft(event.target.value)}
        spellCheck={false}
        aria-label="Configuración JSON de sol_supergate"
        className="min-h-56 w-full resize-y rounded-lg border border-slate-800 bg-slate-950/80 p-3 font-mono text-xs leading-5 text-slate-200 outline-none focus:border-amber-500/50"
        placeholder={loading ? 'Cargando configuración…' : '{ }'}
      />

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="text-[10px] text-slate-600">
          <div>Archivo: <span className="text-slate-400">{snapshot?.file ?? 'cargando…'}</span></div>
          <div>
            Última modificación: <span className="text-slate-400">{snapshot?.modified_at ?? '—'}</span>
            {probe?.url ? <> · Puerto: <span className="text-slate-400">{probe.url}</span></> : null}
          </div>
          <div className="mt-1 text-slate-500">También puedes editar este JSON con nano; el panel revisa cambios cada 4 segundos.</div>
        </div>
        <button
          type="button"
          onClick={() => void save()}
          disabled={saving || !dirty || externalChange}
          className="inline-flex items-center gap-2 rounded-lg bg-amber-500 px-3 py-2 text-[11px] font-bold text-slate-950 hover:bg-amber-400 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {saving ? <RefreshCw size={13} className="animate-spin" /> : <Save size={13} />}
          Guardar cambios
        </button>
      </div>

      <div className={`flex items-center gap-2 text-[10px] ${message.startsWith('No se pudo') || message.startsWith('JSON inválido') ? 'text-red-300' : 'text-slate-500'}`}>
        {message && !message.startsWith('No se pudo') && !message.startsWith('JSON inválido') ? <Check size={12} /> : null}
        {message}
      </div>
    </div>
  );
}