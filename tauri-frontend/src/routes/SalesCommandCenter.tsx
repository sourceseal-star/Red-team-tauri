import React, { useState, useEffect, useCallback } from 'react';
import {
  TrendingUp, Users, DollarSign, ShoppingCart, AlertCircle,
  CheckCircle, XCircle, Clock, Search, Filter, RefreshCw,
  Send, CreditCard, ChevronDown, ChevronUp, Activity,
  Mail, MessageSquare, BarChart3, Zap, Shield
} from 'lucide-react';

// ==========================================
// CONFIGURACIÓN
// ==========================================
const API_BASE = import.meta.env.VITE_MOTOR_CIERRE_API_URL || 'http://localhost:8000';
const API_KEY = import.meta.env.VITE_MOTOR_CIERRE_API_KEY || 'tu-clave-super-secreta-para-el-webhook';

const STATUS_CONFIG: Record<string, { label: string; color: string; icon: any }> = {
  new: { label: 'Nuevo', color: 'bg-slate-600', icon: Users },
  qualified: { label: 'Calificado', color: 'bg-cyan-600', icon: CheckCircle },
  objection: { label: 'Objeción', color: 'bg-amber-600', icon: AlertCircle },
  ready_to_buy: { label: 'Listo para comprar', color: 'bg-green-600', icon: Zap },
  checkout_sent: { label: 'Checkout enviado', color: 'bg-purple-600', icon: Send },
  paid: { label: 'Pagado', color: 'bg-emerald-600', icon: DollarSign },
  dropped: { label: 'Descartado', color: 'bg-red-600', icon: XCircle },
  nurturing: { label: 'Nurturing', color: 'bg-blue-600', icon: Clock },
};

// ==========================================
// COMPONENTES AUXILIARES
// ==========================================
const Card = ({ children, className = '' }: { children: React.ReactNode; className?: string }) => (
  <div className={`bg-slate-900/60 border border-slate-800 rounded-xl p-4 ${className}`}>
    {children}
  </div>
);

const Badge = ({ status }: { status: string }) => {
  const cfg = STATUS_CONFIG[status] || STATUS_CONFIG.new;
  const Icon = cfg.icon;
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold text-white ${cfg.color}`}>
      <Icon size={10} /> {cfg.label}
    </span>
  );
};

// ==========================================
// HOOK PERSONALIZADO PARA FETCH
// ==========================================
function useApi() {
  const fetcher = useCallback(async (endpoint: string, options: RequestInit = {}) => {
    const res = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${API_KEY}`,
        ...options.headers,
      },
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Error desconocido' }));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    return res.json();
  }, []);
  return { fetcher };
}

// ==========================================
// PANEL PRINCIPAL
// ==========================================
export default function SalesCommandCenter() {
  const { fetcher } = useApi();
  const [activeTab, setActiveTab] = useState<'pipeline' | 'leads' | 'metrics' | 'tools'>('pipeline');
  const [health, setHealth] = useState<any>(null);
  const [metrics, setMetrics] = useState<any>(null);
  const [leads, setLeads] = useState<any[]>([]);
  const [selectedLead, setSelectedLead] = useState<any>(null);
  const [leadDetail, setLeadDetail] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filterStatus, setFilterStatus] = useState<string>('all');
  const [searchEmail, setSearchEmail] = useState('');

  // Formularios
  const [manualCheckout, setManualCheckout] = useState({ email: '', price: 499, service: 'Auditoría Operativa Express' });
  const [simReply, setSimReply] = useState({ email: '', subject: '', body: '' });

  // Cargar datos iniciales
  const loadHealth = useCallback(async () => {
    try { setHealth(await fetcher('/health')); } catch (e) { setHealth({ status: 'error' }); }
  }, [fetcher]);

  const loadMetrics = useCallback(async () => {
    try { setMetrics(await fetcher('/metrics/dashboard?days=30')); } catch (e) { /* silent */ }
  }, [fetcher]);

  const loadLeads = useCallback(async () => {
    setLoading(true);
    try {
      const qs = filterStatus !== 'all' ? `?status=${filterStatus}&limit=100` : '?limit=100';
      const data = await fetcher(`/leads${qs}`);
      setLeads(data.leads || []);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [fetcher, filterStatus]);

  const loadLeadDetail = async (email: string) => {
    try {
      const data = await fetcher(`/leads/${email}`);
      setLeadDetail(data);
      setSelectedLead(data.lead);
    } catch (e: any) {
      setError(e.message);
    }
  };

  useEffect(() => { loadHealth(); loadMetrics(); }, [loadHealth, loadMetrics]);
  useEffect(() => { loadLeads(); }, [loadLeads]);

  // Acciones
  const handleManualCheckout = async () => {
    try {
      const data = await fetcher('/checkout/manual', {
        method: 'POST',
        body: JSON.stringify({
          lead_email: manualCheckout.email,
          price_usd: parseInt(manualCheckout.price as any),
          service_name: manualCheckout.service,
        }),
      });
      alert(`✅ Checkout generado:
${data.payment_link}`);
      loadLeads();
    } catch (e: any) {
      alert(`❌ Error: ${e.message}`);
    }
  };

  const handleSimulateReply = async () => {
    try {
      const data = await fetcher('/webhook/email-reply', {
        method: 'POST',
        body: JSON.stringify({
          lead_email: simReply.email,
          subject: simReply.subject,
          body_text: simReply.body,
          source: 'manual_test',
        }),
      });
      alert(`🤖 NLP detectó: ${data.intent}
Acción: ${data.action}`);
      loadLeads();
      loadMetrics();
    } catch (e: any) {
      alert(`❌ Error: ${e.message}`);
    }
  };

  const updateLeadStatus = async (email: string, status: string) => {
    try {
      await fetcher(`/leads/${email}`, {
        method: 'PATCH',
        body: JSON.stringify({ status }),
      });
      loadLeads();
      if (selectedLead?.email === email) loadLeadDetail(email);
    } catch (e: any) {
      alert(`❌ Error: ${e.message}`);
    }
  };

  // Filtrado local
  const filteredLeads = leads.filter(l =>
    l.email.toLowerCase().includes(searchEmail.toLowerCase()) ||
    l.company?.toLowerCase().includes(searchEmail.toLowerCase())
  );

  // Funnel visual
  const funnel = metrics?.funnel || {};
  const funnelSteps = [
    { key: 'leads_received', label: 'Leads', color: 'bg-slate-600' },
    { key: 'qualified', label: 'Calificados', color: 'bg-cyan-600' },
    { key: 'ready_to_buy', label: 'Hot Leads', color: 'bg-green-600' },
    { key: 'checkouts_sent', label: 'Checkouts', color: 'bg-purple-600' },
    { key: 'payments_completed', label: 'Pagos', color: 'bg-emerald-600' },
  ];
  const maxFunnel = Math.max(...funnelSteps.map(s => funnel[s.key] || 0), 1);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans">
      {/* Header */}
      <header className="border-b border-slate-800 bg-slate-900/80 backdrop-blur sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-gradient-to-br from-cyan-500 to-purple-600 rounded-lg flex items-center justify-center">
              <TrendingUp size={18} className="text-white" />
            </div>
            <div>
              <h1 className="text-sm font-bold tracking-wide">MOTOR DE CIERRE AUTÓNOMO</h1>
              <p className="text-[10px] text-slate-500 font-mono">v2.0.0 — Pipeline de Conversión</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className={`flex items-center gap-1.5 text-[10px] px-2 py-1 rounded-full border ${
              health?.status === 'ok' ? 'border-green-800 bg-green-900/20 text-green-400' : 'border-red-800 bg-red-900/20 text-red-400'
            }`}>
              <Shield size={10} />
              {health?.status === 'ok' ? 'API Online' : 'API Offline'}
            </div>
            <button onClick={() => { loadHealth(); loadMetrics(); loadLeads(); }}
              className="p-1.5 hover:bg-slate-800 rounded-lg text-slate-400 transition-colors">
              <RefreshCw size={14} />
            </button>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 py-6">
        {/* Tabs */}
        <div className="flex gap-1 bg-slate-900 rounded-xl p-1 mb-6 border border-slate-800 w-fit">
          {([
            { id: 'pipeline', label: 'Pipeline', icon: BarChart3 },
            { id: 'leads', label: 'Leads', icon: Users },
            { id: 'metrics', label: 'Métricas', icon: Activity },
            { id: 'tools', label: 'Herramientas', icon: Zap },
          ] as const).map(tab => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-medium transition-all ${
                  activeTab === tab.id
                    ? 'bg-slate-800 text-white shadow'
                    : 'text-slate-500 hover:text-slate-300'
                }`}
              >
                <Icon size={14} /> {tab.label}
              </button>
            );
          })}
        </div>

        {/* ─── PIPELINE ─── */}
        {activeTab === 'pipeline' && (
          <div className="space-y-6">
            {/* KPIs */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <Card>
                <div className="text-[10px] text-slate-500 font-bold mb-1">INGRESOS (30d)</div>
                <div className="text-2xl font-bold text-emerald-400">${funnel.revenue_usd?.toLocaleString() || 0}</div>
              </Card>
              <Card>
                <div className="text-[10px] text-slate-500 font-bold mb-1">CHECKOUTS ENVIADOS</div>
                <div className="text-2xl font-bold text-purple-400">{funnel.checkouts_sent || 0}</div>
              </Card>
              <Card>
                <div className="text-[10px] text-slate-500 font-bold mb-1">TASA DE CONVERSIÓN</div>
                <div className="text-2xl font-bold text-cyan-400">
                  {metrics?.conversion_rates?.checkout_to_paid || 0}%
                </div>
              </Card>
              <Card>
                <div className="text-[10px] text-slate-500 font-bold mb-1">LEADS ACTIVOS</div>
                <div className="text-2xl font-bold text-white">{leads.filter(l => !l.archived).length}</div>
              </Card>
            </div>

            {/* Funnel Visual */}
            <Card>
              <h3 className="text-sm font-bold text-slate-200 mb-4 flex items-center gap-2">
                <BarChart3 size={14} className="text-cyan-400" />
                Embudo de Conversión
              </h3>
              <div className="space-y-3">
                {funnelSteps.map((step, idx) => {
                  const value = funnel[step.key] || 0;
                  const pct = maxFunnel ? (value / maxFunnel) * 100 : 0;
                  const prevValue = idx > 0 ? funnel[funnelSteps[idx - 1].key] || 0 : value;
                  const dropOff = idx > 0 && prevValue ? ((prevValue - value) / prevValue * 100).toFixed(1) : null;
                  return (
                    <div key={step.key} className="flex items-center gap-3">
                      <div className="w-24 text-[10px] text-slate-400 font-medium text-right">{step.label}</div>
                      <div className="flex-1 h-8 bg-slate-800 rounded-lg overflow-hidden relative">
                        <div
                          className={`h-full ${step.color} transition-all duration-700 flex items-center px-3`}
                          style={{ width: `${Math.max(pct, 5)}%` }}
                        >
                          <span className="text-xs font-bold text-white">{value}</span>
                        </div>
                      </div>
                      {dropOff && parseFloat(dropOff) > 0 && (
                        <div className="text-[10px] text-red-400 w-12">-{dropOff}%</div>
                      )}
                    </div>
                  );
                })}
              </div>
            </Card>

            {/* Leads recientes */}
            <Card>
              <h3 className="text-sm font-bold text-slate-200 mb-3">Últimos Leads</h3>
              <div className="space-y-2">
                {leads.slice(0, 5).map((lead: any) => (
                  <div key={lead.id} className="flex items-center justify-between p-2 bg-slate-800/50 rounded-lg">
                    <div>
                      <div className="text-xs font-mono text-slate-200">{lead.email}</div>
                      <div className="text-[10px] text-slate-500">{lead.company || 'Sin empresa'}</div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge status={lead.status} />
                      {lead.score > 0 && (
                        <span className="text-[10px] text-cyan-400 font-mono">{lead.score}pts</span>
                      )}
                    </div>
                  </div>
                ))}
                {leads.length === 0 && <div className="text-slate-600 text-xs text-center py-4">Sin leads aún.</div>}
              </div>
            </Card>
          </div>
        )}

        {/* ─── LEADS ─── */}
        {activeTab === 'leads' && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            {/* Lista */}
            <div className="lg:col-span-2 space-y-4">
              <Card>
                <div className="flex items-center gap-2 mb-4">
                  <Search size={14} className="text-slate-500" />
                  <input
                    value={searchEmail}
                    onChange={e => setSearchEmail(e.target.value)}
                    placeholder="Buscar por email o empresa..."
                    className="flex-1 bg-transparent text-xs text-slate-200 outline-none placeholder:text-slate-600"
                  />
                  <select
                    value={filterStatus}
                    onChange={e => setFilterStatus(e.target.value)}
                    className="bg-slate-800 border border-slate-700 rounded text-xs text-slate-300 px-2 py-1"
                  >
                    <option value="all">Todos</option>
                    {Object.keys(STATUS_CONFIG).map(s => (
                      <option key={s} value={s}>{STATUS_CONFIG[s].label}</option>
                    ))}
                  </select>
                </div>

                <div className="space-y-2 max-h-[600px] overflow-y-auto">
                  {loading && <div className="text-center text-slate-500 text-xs py-4">Cargando...</div>}
                  {error && <div className="text-center text-red-400 text-xs py-4">{error}</div>}
                  {filteredLeads.map((lead: any) => (
                    <div
                      key={lead.id}
                      onClick={() => loadLeadDetail(lead.email)}
                      className={`p-3 rounded-lg border cursor-pointer transition-all ${
                        selectedLead?.email === lead.email
                          ? 'bg-cyan-900/20 border-cyan-700'
                          : 'bg-slate-800/40 border-slate-700 hover:border-slate-600'
                      }`}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="font-mono text-xs text-slate-200">{lead.email}</span>
                        <Badge status={lead.status} />
                      </div>
                      <div className="flex items-center justify-between text-[10px] text-slate-500">
                        <span>{lead.company || lead.domain || 'Unknown'}</span>
                        <span className="font-mono">${lead.price_offered || 0}</span>
                      </div>
                      {lead.payment_link && (
                        <div className="mt-1 text-[10px] text-purple-400 truncate">{lead.payment_link}</div>
                      )}
                    </div>
                  ))}
                  {!loading && filteredLeads.length === 0 && (
                    <div className="text-center text-slate-600 text-xs py-8">No se encontraron leads.</div>
                  )}
                </div>
              </Card>
            </div>

            {/* Detalle */}
            <div>
              {leadDetail ? (
                <div className="space-y-4 sticky top-20">
                  <Card>
                    <h3 className="text-sm font-bold text-slate-100 mb-3">Detalle del Lead</h3>
                    <div className="space-y-2 text-xs">
                      <div className="flex justify-between"><span className="text-slate-500">Email</span><span className="font-mono text-slate-200">{leadDetail.lead.email}</span></div>
                      <div className="flex justify-between"><span className="text-slate-500">Empresa</span><span className="text-slate-200">{leadDetail.lead.company || '—'}</span></div>
                      <div className="flex justify-between"><span className="text-slate-500">Score</span><span className="text-cyan-400 font-bold">{leadDetail.lead.score}/100</span></div>
                      <div className="flex justify-between"><span className="text-slate-500">Precio</span><span className="text-emerald-400">${leadDetail.lead.price_offered || 0}</span></div>
                      <div className="flex justify-between"><span className="text-slate-500">Estado</span><Badge status={leadDetail.lead.status} /></div>
                      {leadDetail.lead.payment_link && (
                        <div className="pt-2 border-t border-slate-800">
                          <a href={leadDetail.lead.payment_link} target="_blank" rel="noreferrer"
                            className="text-[10px] text-purple-400 hover:text-purple-300 break-all">
                            {leadDetail.lead.payment_link}
                          </a>
                        </div>
                      )}
                    </div>

                    {/* Cambiar estado */}
                    <div className="mt-4 pt-3 border-t border-slate-800">
                      <div className="text-[10px] text-slate-500 font-bold mb-2">CAMBIAR ESTADO</div>
                      <div className="flex flex-wrap gap-1">
                        {Object.keys(STATUS_CONFIG).map(s => (
                          <button
                            key={s}
                            onClick={() => updateLeadStatus(leadDetail.lead.email, s)}
                            className="px-2 py-1 bg-slate-800 hover:bg-slate-700 text-[10px] text-slate-300 rounded transition-colors"
                          >
                            {STATUS_CONFIG[s].label}
                          </button>
                        ))}
                      </div>
                    </div>
                  </Card>

                  {/* Historial de conversaciones */}
                  <Card>
                    <h3 className="text-sm font-bold text-slate-100 mb-3 flex items-center gap-2">
                      <MessageSquare size={14} className="text-cyan-400" />
                      Conversaciones
                    </h3>
                    <div className="space-y-3 max-h-80 overflow-y-auto">
                      {leadDetail.conversation_history?.map((conv: any, i: number) => (
                        <div key={i} className={`p-2 rounded-lg text-[11px] ${
                          conv.direction === 'inbound' ? 'bg-slate-800/60 border-l-2 border-cyan-500' :
                          conv.direction === 'outbound' ? 'bg-purple-900/10 border-l-2 border-purple-500' :
                          'bg-amber-900/10 border-l-2 border-amber-500'
                        }`}>
                          <div className="flex items-center justify-between mb-1">
                            <span className={`font-bold ${
                              conv.direction === 'inbound' ? 'text-cyan-400' :
                              conv.direction === 'outbound' ? 'text-purple-400' : 'text-amber-400'
                            }`}>
                              {conv.direction === 'inbound' ? 'Prospecto' :
                               conv.direction === 'outbound' ? 'Sistema' : 'AI'}
                            </span>
                            <span className="text-[10px] text-slate-600">
                              {new Date(conv.created_at).toLocaleString()}
                            </span>
                          </div>
                          <div className="text-slate-300 whitespace-pre-wrap">{conv.content}</div>
                          {conv.intent_detected && (
                            <div className="mt-1 text-[10px] text-amber-400">Intent: {conv.intent_detected}</div>
                          )}
                        </div>
                      ))}
                      {(!leadDetail.conversation_history || leadDetail.conversation_history.length === 0) && (
                        <div className="text-slate-600 text-xs text-center py-4">Sin conversaciones.</div>
                      )}
                    </div>
                  </Card>
                </div>
              ) : (
                <Card className="sticky top-20">
                  <div className="text-center text-slate-600 text-sm py-8">
                    <Users size={24} className="mx-auto mb-2 opacity-30" />
                    Selecciona un lead para ver detalles
                  </div>
                </Card>
              )}
            </div>
          </div>
        )}

        {/* ─── MÉTRICAS ─── */}
        {activeTab === 'metrics' && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <Card>
                <div className="text-[10px] text-slate-500 font-bold mb-2">LEAD → CALIFICADO</div>
                <div className="text-3xl font-bold text-cyan-400">{metrics?.conversion_rates?.lead_to_qualified || 0}%</div>
                <div className="text-[10px] text-slate-600 mt-1">De todos los leads recibidos</div>
              </Card>
              <Card>
                <div className="text-[10px] text-slate-500 font-bold mb-2">CALIFICADO → CHECKOUT</div>
                <div className="text-3xl font-bold text-purple-400">{metrics?.conversion_rates?.qualified_to_checkout || 0}%</div>
                <div className="text-[10px] text-slate-600 mt-1">Tasa de cierre del bot</div>
              </Card>
              <Card>
                <div className="text-[10px] text-slate-500 font-bold mb-2">CHECKOUT → PAGADO</div>
                <div className="text-3xl font-bold text-emerald-400">{metrics?.conversion_rates?.checkout_to_paid || 0}%</div>
                <div className="text-[10px] text-slate-600 mt-1">Tasa de conversión de pago</div>
              </Card>
            </div>

            <Card>
              <h3 className="text-sm font-bold text-slate-200 mb-4">Distribución de Intenciones (30 días)</h3>
              <div className="grid grid-cols-3 gap-4 text-center">
                <div className="p-4 bg-green-900/20 rounded-lg border border-green-800">
                  <div className="text-2xl font-bold text-green-400">{funnel.ready_to_buy || 0}</div>
                  <div className="text-[10px] text-slate-500 mt-1">Ready to Buy</div>
                </div>
                <div className="p-4 bg-amber-900/20 rounded-lg border border-amber-800">
                  <div className="text-2xl font-bold text-amber-400">{funnel.qualified ? funnel.qualified - (funnel.ready_to_buy || 0) : 0}</div>
                  <div className="text-[10px] text-slate-500 mt-1">Objections / Nurturing</div>
                </div>
                <div className="p-4 bg-red-900/20 rounded-lg border border-red-800">
                  <div className="text-2xl font-bold text-red-400">{funnel.dropped || 0}</div>
                  <div className="text-[10px] text-slate-500 mt-1">Dropped</div>
                </div>
              </div>
            </Card>

            <Card>
              <h3 className="text-sm font-bold text-slate-200 mb-4">Estado de la API</h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
                <div className="p-3 bg-slate-800 rounded-lg">
                  <div className="text-slate-500 mb-1">Stripe</div>
                  <div className={`font-bold ${health?.stripe_configured ? 'text-green-400' : 'text-red-400'}`}>
                    {health?.stripe_configured ? 'Configurado' : 'No configurado'}
                  </div>
                </div>
                <div className="p-3 bg-slate-800 rounded-lg">
                  <div className="text-slate-500 mb-1">OpenAI</div>
                  <div className={`font-bold ${health?.openai_configured ? 'text-green-400' : 'text-red-400'}`}>
                    {health?.openai_configured ? 'Configurado' : 'No configurado'}
                  </div>
                </div>
                <div className="p-3 bg-slate-800 rounded-lg">
                  <div className="text-slate-500 mb-1">Base de Datos</div>
                  <div className="font-bold text-cyan-400">{health?.db_path || '—'}</div>
                </div>
                <div className="p-3 bg-slate-800 rounded-lg">
                  <div className="text-slate-500 mb-1">Versión</div>
                  <div className="font-bold text-slate-200">{health?.version || '—'}</div>
                </div>
              </div>
            </Card>
          </div>
        )}

        {/* ─── HERRAMIENTAS ─── */}
        {activeTab === 'tools' && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {/* Checkout Manual */}
            <Card>
              <h3 className="text-sm font-bold text-slate-100 mb-3 flex items-center gap-2">
                <CreditCard size={14} className="text-purple-400" />
                Generar Checkout Manual
              </h3>
              <div className="space-y-3">
                <div>
                  <label className="text-[10px] text-slate-500 font-bold">EMAIL DEL LEAD</label>
                  <input
                    value={manualCheckout.email}
                    onChange={e => setManualCheckout({ ...manualCheckout, email: e.target.value })}
                    placeholder="cliente@empresa.com"
                    className="w-full mt-1 bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-200 font-mono"
                  />
                </div>
                <div>
                  <label className="text-[10px] text-slate-500 font-bold">SERVICIO</label>
                  <input
                    value={manualCheckout.service}
                    onChange={e => setManualCheckout({ ...manualCheckout, service: e.target.value })}
                    className="w-full mt-1 bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-200"
                  />
                </div>
                <div>
                  <label className="text-[10px] text-slate-500 font-bold">PRECIO (USD)</label>
                  <input
                    type="number"
                    value={manualCheckout.price}
                    onChange={e => setManualCheckout({ ...manualCheckout, price: parseInt(e.target.value) || 0 })}
                    className="w-full mt-1 bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-200 font-mono"
                  />
                </div>
                <button
                  onClick={handleManualCheckout}
                  className="w-full py-2 bg-purple-600 hover:bg-purple-500 text-white text-xs font-bold rounded-lg transition-colors flex items-center justify-center gap-2"
                >
                  <Send size={12} /> Generar y Enviar Link
                </button>
              </div>
            </Card>

            {/* Simular Respuesta */}
            <Card>
              <h3 className="text-sm font-bold text-slate-100 mb-3 flex items-center gap-2">
                <Mail size={14} className="text-cyan-400" />
                Simular Respuesta de Prospecto
              </h3>
              <div className="space-y-3">
                <input
                  value={simReply.email}
                  onChange={e => setSimReply({ ...simReply, email: e.target.value })}
                  placeholder="Email del prospecto"
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-200 font-mono"
                />
                <input
                  value={simReply.subject}
                  onChange={e => setSimReply({ ...simReply, subject: e.target.value })}
                  placeholder="Asunto del correo"
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-200"
                />
                <textarea
                  value={simReply.body}
                  onChange={e => setSimReply({ ...simReply, body: e.target.value })}
                  placeholder="Contenido del correo..."
                  rows={4}
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-200 resize-none"
                />
                <button
                  onClick={handleSimulateReply}
                  className="w-full py-2 bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-bold rounded-lg transition-colors flex items-center justify-center gap-2"
                >
                  <Zap size={12} /> Procesar con NLP
                </button>
              </div>
            </Card>
          </div>
        )}
      </div>
    </div>
  );
}
