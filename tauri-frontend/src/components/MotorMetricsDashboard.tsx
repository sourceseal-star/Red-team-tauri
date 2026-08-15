import React, { useState, useEffect } from 'react';
import { TrendingUp, TrendingDown, DollarSign, ShoppingCart, Users, Zap, Clock, Target, ArrowUpRight, ArrowDownRight } from 'lucide-react';

interface FunnelData {
  leads_received: number;
  qualified: number;
  ready_to_buy: number;
  checkouts_sent: number;
  payments_completed: number;
  revenue_usd: number;
}

interface ConversionRates {
  lead_to_qualified: number;
  qualified_to_checkout: number;
  checkout_to_paid: number;
}

export default function MotorMetricsDashboard() {
  const [period, setPeriod] = useState(30);
  const [metrics, setMetrics] = useState<{
    funnel: FunnelData;
    conversion_rates: ConversionRates;
  } | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadMetrics();
  }, [period]);

  const loadMetrics = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem('api_token');
      const res = await fetch(`/motor-api/metrics/dashboard?days=${period}`, {
        headers: { 'X-API-Key': token }
      });
      if (res.ok) {
        const data = await res.json();
        setMetrics(data);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  // Mock data para preview visual
  const mockData = {
    funnel: {
      leads_received: 342,
      qualified: 128,
      ready_to_buy: 67,
      checkouts_sent: 45,
      payments_completed: 23,
      revenue_usd: 11477,
    },
    conversion_rates: {
      lead_to_qualified: 37.4,
      qualified_to_checkout: 35.2,
      checkout_to_paid: 51.1,
    }
  };

  const data = metrics || mockData;
  const funnel = data.funnel;
  const rates = data.conversion_rates;

  const funnelSteps = [
    { key: 'leads_received' as const, label: 'Leads', icon: Users, color: 'from-slate-600 to-slate-500' },
    { key: 'qualified' as const, label: 'Calificados', icon: Target, color: 'from-cyan-600 to-cyan-500' },
    { key: 'ready_to_buy' as const, label: 'Hot Leads', icon: Zap, color: 'from-green-600 to-green-500' },
    { key: 'checkouts_sent' as const, label: 'Checkouts', icon: ShoppingCart, color: 'from-purple-600 to-purple-500' },
    { key: 'payments_completed' as const, label: 'Pagos', icon: DollarSign, color: 'from-emerald-600 to-emerald-500' },
  ];

  const maxVal = Math.max(...funnelSteps.map(s => funnel[s.key]), 1);

  return (
    <div className="space-y-6">
      {/* Header con selector de período */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold text-white">Motor de Cierre — Métricas</h2>
          <p className="text-xs text-slate-500">Pipeline de conversión y revenue</p>
        </div>
        <div className="flex gap-1 bg-slate-900 rounded-lg p-1 border border-slate-800">
          {[7, 30, 90].map(d => (
            <button
              key={d}
              onClick={() => setPeriod(d)}
              className={`px-3 py-1 text-[10px] font-bold rounded-md transition-all ${
                period === d ? 'bg-slate-700 text-white' : 'text-slate-500 hover:text-slate-300'
              }`}
            >
              {d}d
            </button>
          ))}
        </div>
      </div>

      {/* KPIs principales */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { label: 'Revenue', value: `$${funnel.revenue_usd.toLocaleString()}`, change: '+12%', up: true, icon: DollarSign, color: 'text-emerald-400' },
          { label: 'Checkouts', value: funnel.checkouts_sent, change: '+5%', up: true, icon: ShoppingCart, color: 'text-purple-400' },
          { label: 'Tasa de Cierre', value: `${rates.checkout_to_paid}%`, change: '-2%', up: false, icon: Target, color: 'text-cyan-400' },
          { label: 'Leads', value: funnel.leads_received, change: '+23%', up: true, icon: Users, color: 'text-slate-400' },
        ].map(kpi => {
          const Icon = kpi.icon;
          return (
            <div key={kpi.label} className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 hover:border-slate-700 transition-colors">
              <div className="flex items-center justify-between mb-2">
                <span className="text-[10px] text-slate-500 font-bold uppercase">{kpi.label}</span>
                <Icon size={14} className={kpi.color} />
              </div>
              <div className="text-2xl font-bold text-white">{kpi.value}</div>
              <div className={`flex items-center gap-1 mt-1 text-[10px] ${kpi.up ? 'text-green-400' : 'text-red-400'}`}>
                {kpi.up ? <ArrowUpRight size={10} /> : <ArrowDownRight size={10} />}
                {kpi.change} vs período anterior
              </div>
            </div>
          );
        })}
      </div>

      {/* Embudo visual */}
      <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5">
        <h3 className="text-sm font-bold text-slate-200 mb-5">Embudo de Conversión</h3>
        <div className="space-y-3">
          {funnelSteps.map((step, idx) => {
            const value = funnel[step.key];
            const pct = (value / maxVal) * 100;
            const prevValue = idx > 0 ? funnel[funnelSteps[idx - 1].key] : value;
            const dropOff = idx > 0 && prevValue ? ((prevValue - value) / prevValue * 100).toFixed(1) : null;
            const Icon = step.icon;

            return (
              <div key={step.key} className="flex items-center gap-4">
                <div className="w-24 text-right">
                  <div className="text-[10px] text-slate-400 font-medium">{step.label}</div>
                  <div className="text-xs font-bold text-white">{value}</div>
                </div>
                <div className="flex-1 h-10 bg-slate-800 rounded-lg overflow-hidden relative">
                  <div 
                    className={`h-full bg-gradient-to-r ${step.color} transition-all duration-1000 flex items-center px-3`}
                    style={{ width: `${Math.max(pct, 3)}%` }}
                  >
                    <Icon size={14} className="text-white/80" />
                  </div>
                  {dropOff && parseFloat(dropOff) > 0 && (
                    <div className="absolute right-2 top-1/2 -translate-y-1/2 text-[10px] text-red-400 font-bold">
                      -{dropOff}%
                    </div>
                  )}
                </div>
                <div className="w-16 text-[10px] text-slate-500">
                  {idx === 0 ? '100%' : `${((value / funnel.leads_received) * 100).toFixed(1)}%`}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Tasas de conversión */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {[
          { label: 'Lead → Calificado', value: rates.lead_to_qualified, color: 'cyan' },
          { label: 'Calificado → Checkout', value: rates.qualified_to_checkout, color: 'purple' },
          { label: 'Checkout → Pagado', value: rates.checkout_to_paid, color: 'emerald' },
        ].map(rate => (
          <div key={rate.label} className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 text-center">
            <div className="text-[10px] text-slate-500 font-bold mb-2">{rate.label}</div>
            <div className="relative w-24 h-24 mx-auto">
              <svg className="w-full h-full -rotate-90" viewBox="0 0 36 36">
                <path
                  d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                  fill="none"
                  stroke="#1e293b"
                  strokeWidth="3"
                />
                <path
                  d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                  fill="none"
                  stroke={rate.color === 'cyan' ? '#06b6d4' : rate.color === 'purple' ? '#a855f7' : '#10b981'}
                  strokeWidth="3"
                  strokeDasharray={`${rate.value}, 100`}
                  className="transition-all duration-1000"
                />
              </svg>
              <div className="absolute inset-0 flex items-center justify-center">
                <span className="text-lg font-bold text-white">{rate.value}%</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
