import { useState, useEffect } from 'react';
import { DollarSign, Users, ShoppingCart, Target, ArrowUpRight, ArrowDownRight, Send, CreditCard } from 'lucide-react';

const API_KEY = 'tu-clave-secreta-123';
const API_BASE = '/motor-api';

export default function MotorPanel() {
  const [metrics, setMetrics] = useState<any>(null);
  const [leads, setLeads] = useState<any[]>([]);
  const [period, setPeriod] = useState(30);
  const [checkoutForm, setCheckoutForm] = useState({ email: '', price: 499, service: 'Auditoría Operativa Express' });

  const headers = { 'Authorization': `Bearer ${API_KEY}`, 'Content-Type': 'application/json' };

  const loadMetrics = async () => {
    try {
      const res = await fetch(`${API_BASE}/metrics/dashboard?days=${period}`, { headers });
      if (res.ok) setMetrics(await res.json());
    } catch (e) { console.error(e); }
  };

  const loadLeads = async () => {
    try {
      const res = await fetch(`${API_BASE}/leads?limit=20`, { headers });
      if (res.ok) setLeads((await res.json()).leads || []);
    } catch (e) { console.error(e); }
  };

  const createCheckout = async () => {
    try {
      const res = await fetch(`${API_BASE}/checkout/manual`, {
        method: 'POST', headers, body: JSON.stringify({
          lead_email: checkoutForm.email, price_usd: checkoutForm.price, service_name: checkoutForm.service
        })
      });
      const data = await res.json();
      if (res.ok) alert(`Link generado:\n${data.payment_link}`);
      else alert(`Error: ${data.detail}`);
      loadLeads();
    } catch (e: any) { alert(e.message); }
  };

  const simulateReply = async () => {
    const email = prompt('Email del prospecto:');
    const body = prompt('Contenido del correo:');
    if (!email || !body) return;
    try {
      const res = await fetch(`${API_BASE}/webhook/email-reply`, {
        method: 'POST', headers, body: JSON.stringify({ lead_email: email, subject: 'Test', body_text: body, source: 'manual' })
      });
      const data = await res.json();
      alert(`Resultado: ${data.intent || data.status}\nAcción: ${data.action}`);
      loadLeads(); loadMetrics();
    } catch (e: any) { alert(e.message); }
  };

  useEffect(() => { loadMetrics(); loadLeads(); }, [period]);

  const funnel = metrics?.funnel || {};
  const rates = metrics?.conversion_rates || {};

  return (
    <div className="space-y-4">
      {/* KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { label: 'Revenue', value: `$${funnel.revenue_usd?.toLocaleString() || 0}`, change: '+12%', up: true, color: 'text-emerald-400' },
          { label: 'Checkouts', value: funnel.checkouts_sent || 0, change: '+5%', up: true, color: 'text-purple-400' },
          { label: 'Conversión', value: `${rates.checkout_to_paid || 0}%`, change: '-2%', up: false, color: 'text-cyan-400' },
          { label: 'Leads', value: funnel.leads_received || 0, change: '+23%', up: true, color: 'text-white' },
        ].map(kpi => (
          <div key={kpi.label} className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
            <div className="text-[10px] text-slate-500 font-bold uppercase">{kpi.label}</div>
            <div className={`text-2xl font-bold ${kpi.color}`}>{kpi.value}</div>
          </div>
        ))}
      </div>

      {/* Embudo */}
      <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-bold text-white">Embudo de Conversión</h3>
          <div className="flex gap-1">
            {[7, 30, 90].map(d => (
              <button key={d} onClick={() => setPeriod(d)} className={`px-2 py-1 text-[10px] rounded ${period === d ? 'bg-slate-700 text-white' : 'text-slate-500'}`}>{d}d</button>
            ))}
          </div>
        </div>
        {[
          { key: 'leads_received', label: 'Leads', color: 'bg-slate-600' },
          { key: 'qualified', label: 'Calificados', color: 'bg-cyan-600' },
          { key: 'ready_to_buy', label: 'Hot', color: 'bg-green-600' },
          { key: 'checkouts_sent', label: 'Checkouts', color: 'bg-purple-600' },
          { key: 'payments_completed', label: 'Pagos', color: 'bg-emerald-600' },
        ].map((step, i) => {
          const val = funnel[step.key] || 0;
          const max = Math.max(funnel.leads_received || 1, 1);
          return (
            <div key={step.key} className="flex items-center gap-3 mb-2">
              <div className="w-20 text-right text-[10px] text-slate-400">{step.label}</div>
              <div className="flex-1 h-8 bg-slate-800 rounded-lg overflow-hidden relative">
                <div className={`h-full ${step.color} flex items-center px-3 transition-all`} style={{ width: `${Math.max((val/max)*100, 3)}%` }}>
                  <span className="text-xs font-bold text-white">{val}</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Acciones rápidas */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
          <h4 className="text-xs font-bold text-white mb-3 flex items-center gap-2"><CreditCard size={12} className="text-purple-400" /> Checkout Manual</h4>
          <div className="space-y-2">
            <input value={checkoutForm.email} onChange={e => setCheckoutForm({...checkoutForm, email: e.target.value})} placeholder="cliente@empresa.com" className="w-full bg-slate-950 border border-slate-700 rounded px-3 py-2 text-xs text-slate-200" />
            <div className="flex gap-2">
              <input type="number" value={checkoutForm.price} onChange={e => setCheckoutForm({...checkoutForm, price: parseInt(e.target.value)||0})} className="w-24 bg-slate-950 border border-slate-700 rounded px-3 py-2 text-xs text-slate-200" />
              <button onClick={createCheckout} className="flex-1 bg-purple-600 hover:bg-purple-500 text-white text-xs font-bold rounded py-2 flex items-center justify-center gap-1"><Send size={10} /> Generar</button>
            </div>
          </div>
        </div>
        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
          <h4 className="text-xs font-bold text-white mb-3 flex items-center gap-2"><Target size={12} className="text-cyan-400" /> Simular Respuesta</h4>
          <button onClick={simulateReply} className="w-full bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-bold rounded py-2">Procesar con NLP</button>
        </div>
      </div>

      {/* Lista de leads */}
      <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
        <h4 className="text-xs font-bold text-white mb-3">Últimos Leads</h4>
        <div className="space-y-2 max-h-64 overflow-y-auto">
          {leads.map((l: any) => (
            <div key={l.id} className="flex items-center justify-between p-2 bg-slate-800/50 rounded-lg">
              <div>
                <div className="text-xs font-mono text-slate-200">{l.email}</div>
                <div className="text-[10px] text-slate-500">{l.status} | score: {l.score}</div>
              </div>
              {l.payment_link && <span className="text-[10px] text-purple-400 truncate max-w-[150px]">{l.payment_link}</span>}
            </div>
          ))}
          {leads.length === 0 && <div className="text-slate-600 text-xs text-center py-4">Sin leads. Simula una respuesta para crear uno.</div>}
        </div>
      </div>
    </div>
  );
}
