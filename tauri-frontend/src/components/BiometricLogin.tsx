import React, { useState, useEffect } from 'react';
import { Fingerprint, Shield, Eye, EyeOff, AlertCircle, CheckCircle, Key, X } from 'lucide-react';

// ── Helpers base64 ↔ ArrayBuffer para WebAuthn ──
function b64urlToBuffer(b64url: string): ArrayBuffer {
  const pad = '='.repeat((4 - b64url.length % 4) % 4);
  const b64 = (b64url + pad).replace(/-/g, '+').replace(/_/g, '/');
  const raw = atob(b64);
  const buf = new ArrayBuffer(raw.length);
  const arr = new Uint8Array(buf);
  for (let i = 0; i < raw.length; i++) arr[i] = raw.charCodeAt(i);
  return buf;
}
function bufferToB64url(buf: ArrayBuffer | Uint8Array): string {
  const arr = buf instanceof Uint8Array ? buf : new Uint8Array(buf);
  let b64 = '';
  for (let i = 0; i < arr.length; i++) b64 += String.fromCharCode(arr[i]);
  return btoa(b64).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

interface LoginProps {
  onLogin: (token: string) => void;
}

export default function BiometricLogin({ onLogin }: LoginProps) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPass, setShowPass] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [bioAvailable, setBioAvailable] = useState(false);
  const [bioScanning, setBioScanning] = useState(false);
  const [bioSuccess, setBioSuccess] = useState(false);
  const [hasRegisteredFingerprint, setHasRegisteredFingerprint] = useState(false);
  const [showRegisterModal, setShowRegisterModal] = useState(false);
  const [showPasswordModal, setShowPasswordModal] = useState(false);

  useEffect(() => {
    if (window.PublicKeyCredential) {
      setBioAvailable(true);
      checkFingerprintStatus();
    }
  }, []);

  const checkFingerprintStatus = async () => {
    try {
      const res = await fetch('/api/auth/webauthn/status');
      const data = await res.json();
      setHasRegisteredFingerprint(data.registered);
    } catch {}
  };

  const handlePasswordLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Credenciales invalidas');
      localStorage.setItem('api_token', data.token);
      onLogin(data.token);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // ── WebAuthn real: registrar huella ──
  const handleRegisterFingerprint = async () => {
    if (!bioAvailable) {
      setError('WebAuthn no soportado en este navegador');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const beginRes = await fetch('/api/auth/webauthn/register/begin', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });
      if (!beginRes.ok) {
        const d = await beginRes.json();
        throw new Error(d.detail || 'No se pudo iniciar registro');
      }
      const beginData = await beginRes.json();

      const publicKey: PublicKeyCredentialCreationOptions = {
        challenge: b64urlToBuffer(beginData.challenge),
        rp: beginData.rp,
        user: {
          ...beginData.user,
          id: b64urlToBuffer(beginData.user.id),
        },
        pubKeyCredParams: beginData.pubKeyCredParams,
        authenticatorSelection: beginData.authenticatorSelection,
        timeout: beginData.timeout,
      };

      const credential = await navigator.credentials.create({ publicKey }) as PublicKeyCredential;
      if (!credential) throw new Error('No se pudo crear la credencial');

      const credentialId = bufferToB64url(credential.rawId);

      const finishRes = await fetch('/api/auth/webauthn/register/finish', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ challenge: beginData.challenge, credentialId }),
      });
      if (!finishRes.ok) {
        const d = await finishRes.json();
        throw new Error(d.detail || 'Error al guardar huella');
      }

      setHasRegisteredFingerprint(true);
      setShowRegisterModal(false);
      setError('');
      setBioSuccess(true);
      setTimeout(() => setBioSuccess(false), 2000);
    } catch (err: any) {
      setError(err.message || 'Error registrando huella');
    } finally {
      setLoading(false);
    }
  };

  // ── WebAuthn real: login con huella ──
  const handleBiometric = async () => {
    if (!bioAvailable) {
      setError('Biometria no soportada en este dispositivo/navegador');
      return;
    }
    if (!hasRegisteredFingerprint) {
      setShowRegisterModal(true);
      return;
    }
    setBioScanning(true);
    setError('');
    try {
      const beginRes = await fetch('/api/auth/webauthn/auth/begin', { method: 'POST' });
      if (!beginRes.ok) {
        const d = await beginRes.json();
        throw new Error(d.detail || 'No se pudo iniciar autenticacion');
      }
      const beginData = await beginRes.json();

      const publicKey: PublicKeyCredentialRequestOptions = {
        challenge: b64urlToBuffer(beginData.challenge),
        allowCredentials: beginData.credentials.map((c: any) => ({
          type: c.type,
          id: b64urlToBuffer(c.id),
        })),
        timeout: beginData.timeout,
        userVerification: beginData.userVerification,
      };

      const assertion = await navigator.credentials.get({ publicKey }) as PublicKeyCredential;
      if (!assertion) throw new Error('Autenticacion cancelada');

      const credentialId = bufferToB64url(assertion.rawId);

      const finishRes = await fetch('/api/auth/webauthn/auth/finish', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ challenge: beginData.challenge, credentialId }),
      });
      const finishData = await finishRes.json();
      if (!finishRes.ok) throw new Error(finishData.detail || 'Huella no reconocida');

      setBioSuccess(true);
      setTimeout(() => {
        localStorage.setItem('api_token', finishData.token);
        onLogin(finishData.token);
      }, 600);
    } catch (err: any) {
      setError(err.message);
      setBioScanning(false);
    }
  };

  // ── Cambiar contraseña ──
  const handleChangePassword = async (currentPass: string, newPass: string) => {
    const res = await fetch('/api/auth/password', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ current_password: currentPass, new_password: newPass }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Error al cambiar contrasena');
    return data;
  };

  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="w-16 h-16 bg-gradient-to-br from-cyan-500 to-purple-600 rounded-2xl mx-auto mb-4 flex items-center justify-center shadow-lg shadow-cyan-500/20">
            <Shield size={32} className="text-white" />
          </div>
          <h1 className="text-2xl font-bold text-white tracking-tight">RedTeam Dashboard</h1>
          <p className="text-sm text-slate-500 mt-1">Autenticacion requerida</p>
        </div>

        <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-6 shadow-2xl">
          {error && (
            <div className="mb-4 p-3 bg-red-900/20 border border-red-800 rounded-lg flex items-center gap-2 text-xs text-red-400">
              <AlertCircle size={14} /> {error}
            </div>
          )}

          <form onSubmit={handlePasswordLogin} className="space-y-4">
            <div>
              <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Email</label>
              <input
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                required
                className="w-full mt-1 bg-slate-950 border border-slate-700 rounded-lg px-3 py-2.5 text-sm text-slate-200 focus:border-cyan-500 focus:outline-none transition-colors"
                placeholder="admin@redteam.local"
              />
            </div>
            <div>
              <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Contrasena</label>
              <div className="relative mt-1">
                <input
                  type={showPass ? 'text' : 'password'}
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  required
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2.5 text-sm text-slate-200 focus:border-cyan-500 focus:outline-none transition-colors pr-10"
                  placeholder="••••••••"
                />
                <button type="button" onClick={() => setShowPass(!showPass)} className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300">
                  {showPass ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>
            <button type="submit" disabled={loading} className="w-full py-2.5 bg-cyan-600 hover:bg-cyan-500 disabled:bg-slate-700 text-white text-sm font-bold rounded-lg transition-all flex items-center justify-center gap-2">
              {loading ? <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : <><Shield size={14} /> Acceder</>}
            </button>
          </form>

          {/* Separador */}
          <div className="flex items-center gap-3 my-5">
            <div className="flex-1 h-px bg-slate-800" />
            <span className="text-[10px] text-slate-600 font-bold uppercase">O</span>
            <div className="flex-1 h-px bg-slate-800" />
          </div>

          {/* Huella */}
          <button onClick={handleBiometric} disabled={bioScanning || bioSuccess} className={`w-full py-3 rounded-lg border transition-all flex items-center justify-center gap-2 text-sm font-medium ${bioSuccess ? 'bg-green-900/20 border-green-700 text-green-400' : bioScanning ? 'bg-amber-900/20 border-amber-700 text-amber-400 animate-pulse' : 'bg-slate-800 border-slate-700 text-slate-300 hover:border-slate-600 hover:bg-slate-800/80'}`}>
            {bioSuccess ? <><CheckCircle size={16} /> Autenticado</> : bioScanning ? <><Fingerprint size={16} className="animate-bounce" /> Escaneando huella...</> : <><Fingerprint size={16} /> {hasRegisteredFingerprint ? 'Usar huella' : 'Registrar huella'}</>}
          </button>

          {!bioAvailable && <p className="text-[10px] text-slate-600 text-center mt-2">WebAuthn requiere HTTPS o localhost</p>}
          {bioAvailable && !hasRegisteredFingerprint && <p className="text-[10px] text-slate-600 text-center mt-2">Primero ingresa con email/contrasena y registra tu huella</p>}

          {/* Cambiar contraseña */}
          <button onClick={() => setShowPasswordModal(true)} className="w-full mt-4 py-2 text-xs text-slate-500 hover:text-slate-300 flex items-center justify-center gap-1.5 transition-colors">
            <Key size={12} /> Cambiar contrasena
          </button>
        </div>

        <p className="text-center text-[10px] text-slate-600 mt-4">v2.1.0 — WebAuthn + Motor de Cierre</p>
      </div>

      {/* Modal: Registrar huella */}
      {showRegisterModal && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4 z-50" onClick={() => setShowRegisterModal(false)}>
          <div className="bg-slate-900 border border-slate-700 rounded-2xl p-6 max-w-sm w-full" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-bold text-white flex items-center gap-2"><Fingerprint size={18} className="text-cyan-400" /> Registrar huella</h2>
              <button onClick={() => setShowRegisterModal(false)} className="text-slate-500 hover:text-white"><X size={18} /></button>
            </div>
            <p className="text-xs text-slate-400 mb-4">Necesitas ingresar tu email y contrasena actuales para registrar tu huella. Luego podras entrar solo con la huella.</p>
            <div className="space-y-3 mb-4">
              <input type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="admin@redteam.local" className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 focus:border-cyan-500 focus:outline-none" />
              <input type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="Contrasena actual" className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 focus:border-cyan-500 focus:outline-none" />
            </div>
            <button onClick={handleRegisterFingerprint} disabled={loading || !email || !password} className="w-full py-2.5 bg-cyan-600 hover:bg-cyan-500 disabled:bg-slate-700 text-white text-sm font-bold rounded-lg transition-all flex items-center justify-center gap-2">
              {loading ? <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : <><Fingerprint size={14} /> Registrar mi huella</>}
            </button>
          </div>
        </div>
      )}

      {/* Modal: Cambiar contraseña */}
      {showPasswordModal && (
        <PasswordModal
          onClose={() => setShowPasswordModal(false)}
          onChange={handleChangePassword}
        />
      )}
    </div>
  );
}

// ── Modal de cambio de contrasena ──
function PasswordModal({ onClose, onChange }: { onClose: () => void; onChange: (current: string, newPass: string) => Promise<any> }) {
  const [current, setCurrent] = useState('');
  const [newPass, setNewPass] = useState('');
  const [confirm, setConfirm] = useState('');
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState('');
  const [err, setErr] = useState('');

  const submit = async () => {
    setErr(''); setMsg('');
    if (newPass !== confirm) { setErr('Las contrasenas no coinciden'); return; }
    if (newPass.length < 6) { setErr('Minimo 6 caracteres'); return; }
    setLoading(true);
    try {
      const res = await onChange(current, newPass);
      setMsg(res.message || 'Contrasena actualizada');
      setTimeout(onClose, 1500);
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4 z-50" onClick={onClose}>
      <div className="bg-slate-900 border border-slate-700 rounded-2xl p-6 max-w-sm w-full" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-bold text-white flex items-center gap-2"><Key size={18} className="text-cyan-400" /> Cambiar contrasena</h2>
          <button onClick={onClose} className="text-slate-500 hover:text-white"><X size={18} /></button>
        </div>
        {err && <div className="mb-3 p-2 bg-red-900/20 border border-red-800 rounded text-xs text-red-400">{err}</div>}
        {msg && <div className="mb-3 p-2 bg-green-900/20 border border-green-800 rounded text-xs text-green-400">{msg}</div>}
        <div className="space-y-3">
          <input type="password" value={current} onChange={e => setCurrent(e.target.value)} placeholder="Contrasena actual" className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 focus:border-cyan-500 focus:outline-none" />
          <input type="password" value={newPass} onChange={e => setNewPass(e.target.value)} placeholder="Nueva contrasena" className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 focus:border-cyan-500 focus:outline-none" />
          <input type="password" value={confirm} onChange={e => setConfirm(e.target.value)} placeholder="Confirmar nueva contrasena" className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 focus:border-cyan-500 focus:outline-none" />
        </div>
        <button onClick={submit} disabled={loading || !current || !newPass} className="w-full mt-4 py-2.5 bg-cyan-600 hover:bg-cyan-500 disabled:bg-slate-700 text-white text-sm font-bold rounded-lg transition-all">
          {loading ? 'Guardando...' : 'Cambiar contrasena'}
        </button>
      </div>
    </div>
  );
}
