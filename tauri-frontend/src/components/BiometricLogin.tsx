import React, { useState, useEffect } from 'react';
import { Fingerprint, Shield, Eye, EyeOff, AlertCircle, CheckCircle } from 'lucide-react';

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

  useEffect(() => {
    // Detectar si WebAuthn está disponible
    if (window.PublicKeyCredential) {
      setBioAvailable(true);
    }
  }, []);

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
      if (!res.ok) throw new Error(data.detail || 'Credenciales inválidas');
      localStorage.setItem('api_token', data.token);
      onLogin(data.token);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleBiometric = async () => {
    if (!bioAvailable) {
      setError('Biometría no soportada en este dispositivo/navegador');
      return;
    }
    setBioScanning(true);
    setError('');
    try {
      // Simulación de WebAuthn — en producción usar navigator.credentials.create/get
      await new Promise(r => setTimeout(r, 1500));

      // Mock: si hay email, "autenticamos" con el backend
      const res = await fetch('/api/auth/biometric', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, challenge: 'mock-challenge-' + Date.now() }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Autenticación biométrica fallida');

      setBioSuccess(true);
      setTimeout(() => {
        localStorage.setItem('api_token', data.token);
        onLogin(data.token);
      }, 800);
    } catch (err: any) {
      setError(err.message);
      setBioScanning(false);
    }
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
          <p className="text-sm text-slate-500 mt-1">Autenticación requerida</p>
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
              <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Contraseña</label>
              <div className="relative mt-1">
                <input
                  type={showPass ? 'text' : 'password'}
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  required
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2.5 text-sm text-slate-200 focus:border-cyan-500 focus:outline-none transition-colors pr-10"
                  placeholder="••••••••"
                />
                <button
                  type="button"
                  onClick={() => setShowPass(!showPass)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300"
                >
                  {showPass ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 bg-cyan-600 hover:bg-cyan-500 disabled:bg-slate-700 text-white text-sm font-bold rounded-lg transition-all flex items-center justify-center gap-2"
            >
              {loading ? (
                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : (
                <>
                  <Shield size={14} /> Acceder
                </>
              )}
            </button>
          </form>

          {/* Separador */}
          <div className="flex items-center gap-3 my-5">
            <div className="flex-1 h-px bg-slate-800" />
            <span className="text-[10px] text-slate-600 font-bold uppercase">O</span>
            <div className="flex-1 h-px bg-slate-800" />
          </div>

          {/* Biometría */}
          <button
            onClick={handleBiometric}
            disabled={bioScanning || bioSuccess}
            className={`w-full py-3 rounded-lg border transition-all flex items-center justify-center gap-2 text-sm font-medium ${
              bioSuccess
                ? 'bg-green-900/20 border-green-700 text-green-400'
                : bioScanning
                ? 'bg-amber-900/20 border-amber-700 text-amber-400 animate-pulse'
                : 'bg-slate-800 border-slate-700 text-slate-300 hover:border-slate-600 hover:bg-slate-800/80'
            }`}
          >
            {bioSuccess ? (
              <><CheckCircle size={16} /> Autenticado</>
            ) : bioScanning ? (
              <><Fingerprint size={16} className="animate-bounce" /> Escaneando huella...</>
            ) : (
              <><Fingerprint size={16} /> {bioAvailable ? 'Usar biometría' : 'Biometría no disponible'}</>
            )}
          </button>

          {!bioAvailable && (
            <p className="text-[10px] text-slate-600 text-center mt-2">
              HTTPS + WebAuthn requeridos para biometría real
            </p>
          )}
        </div>

        <p className="text-center text-[10px] text-slate-600 mt-4">
          v2.0.0 — Motor de Cierre Autónomo
        </p>
      </div>
    </div>
  );
}
