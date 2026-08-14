import React, { useState, useEffect, useCallback } from 'react';
import {
  TrendingUp, Users, DollarSign, ShoppingCart, AlertCircle,
  CheckCircle, XCircle, Clock, Search, RefreshCw,
  Send, CreditCard, Activity, Mail, BarChart3, Zap, Shield, Package, Plus, Trash2
} from 'lucide-react';

const API_BASE = import.meta.env.VITE_MOTOR_CIERRE_API_URL || '/motor-api';
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

const Card = ({ children, className = '' }: { children: React.ReactNode; className?: string }) => (
  <div className={`bg-slate-900/60 border border-slate-800 rounded-xl p-4 ${className}`}>{children}</div>
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

function useApi() {
  const fetcher = useCallback(async (endpoint: string, options: RequestInit = {}) => {
    const res = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${API_KEY}`, ...options.headers },
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Error desconocido' }));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    return res.json();
  }, []);
  return { fetcher };
}

export default function SalesCommandCenter() {
  const { fetcher } = useApi();
  const [activeTab, setActiveTab] = useState<'pipeline' | 'leads' | 'metrics' | 'products' | 'tools'>('pipeline');
  const [health, setHealth] = useState<any>(null);
  const [metrics, setMetrics] = useState<any>(null);
  const [leads, setLeads] = useState<any[]>([]);
  const [products, setProducts] = useState<any[]>([]);
  const [selectedProduct, setSelectedProduct] = useState<string>('');
  const [selectedLead, setSelectedLead] = useState<any>(null);
  const [leadDetail, setLeadDetail] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filterStatus, setFilterStatus] = useState<string>('all');
  const [searchEmail, setSearchEmail] = useState('');

  // Forms
  const [manualCheckout, setManualCheckout] = useState({ email: '', productId: '', price: 0, service: '' });
  const [simReply, setSimReply] = useState({ email: '', subject: '', body: '', productId: '' });
  const [newProduct, setNewProduct] = useState({ id: '', name: '', description: '', default_price_usd: 199 });

  const loadHealth = useCallback(async () => {
    try { setHealth(await fetcher('/health')); } catch { setHealth({ status: 'error' }); }
  }, [fetcher]);

  const loadProducts = useCallback(async () => {
    try { const data = await fetcher('/products'); setProducts(data.products || []); } catch { /* silent */ }
  }, [fetcher]);

  const loadMetrics = useCallback(async () => {
    try {
      const qs = selectedProduct ? `?days=30&product_id=${selectedProduct}` : '?days=30';
      setMetrics(await fetcher(`/metrics/dashboard${qs}`));
    } catch { /* silent */ }
  }, [fetcher, selectedProduct]);

  const loadLeads = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ limit: '100' });
      if (filterStatus !== 'all') params.set('status', filterStatus);
      if (selectedProduct) params.set('product_id', selectedProduct);
      const data = await fetcher(`/leads?${params}`);
      setLeads(data.leads || []);
    } catch (e: any) { setError(e.message); } finally { setLoading(false); }
  }, [fetcher, filterStatus, selectedProduct]);

  const loadLeadDetail = async (email: string) => {
    try { const data = await fetcher(`/leads/${email}`); setLeadDetail(data); setSelectedLead(data.lead); }
    catch (e: any) { setError(e.message); }
  };

  useEffect(() => { loadHealth(); loadProducts(); }, [loadHealth, loadProducts]);
  useEffect(() => { loadLeads(); loadMetrics(); }, [loadLeads, loadMetrics]);

  // Actions
  const handleManualCheckout = async () => {
    try {
      const product = products.find(p => p.id === manualCheckout.productId);
      const body: any = { lead_email: manualCheckout.email };
      if (manualCheckout.productId) body.product_id = manualCheckout.productId;
      if (manualCheckout.service) body.service_name = manualCheckout.service;
      else if (product) body.service_name = product.name;
      if (manualCheckout.price) body.price_usd = manualCheckout.price;
      const data = await fetcher('/checkout/manual', { method: 'POST', body: JSON.stringify(body) });
      alert(`✅ Checkout generado:\n${data.payment_link}`);
      loadLeads();
    } catch (e: any) { alert(`❌ Error: ${e.message}`); }
  };

  const handleSimulateReply = async () => {
    try {
      const body: any = { lead_email: simReply.email, subject: simReply.subject, body_text: simReply.body, source: 'manual_test' };
      if (simReply.productId) body.product_id = simReply.productId;
      const data = await fetcher('/webhook/email-reply', { method: 'POST', body: JSON.stringify(body) });
      alert(`🤖 NLP detectó: ${data.intent}\nProducto: ${data.product || 'N/A'}\nAcción: ${data.action}`);
      loadLeads(); loadMetrics();
    } catch (e: any) { alert(`❌ Error: ${e.message}`); }
  };

  const updateLeadStatus = async (email: string, status: string) => {
    try {
      await fetcher(`/leads/${email}`, { method: 'PATCH', body: JSON.stringify({ status }) });
      loadLeads();
      if (selectedLead?.email === email) loadLeadDetail(email);
    } catch (e: any) { alert(`❌ Error: ${e.message}`); }
  };

  const handleCreateProduct = async () => {
    try {
      await fetcher('/products', { method: 'POST', body: JSON.stringify(newProduct) });
      alert(`✅ Producto "${newProduct.name}" creado`);
      setNewProduct({ id: '', name: '', description: '', default_price_usd: 199 });
      loadProducts();
    } catch (e: any) { alert(`❌ Error: ${e.message}`); }
  };

  const handleDeactivateProduct = async (productId: string) => {
    if (!confirm('¿Desactivar este producto?')) return;
    try {
      await fetcher(`/products/${productId}`, { method: 'DELETE' });
      loadProducts();
    } catch (e: any) { alert(`❌ Error: ${e.message}`); }
  };

  // Helpers
  const productName = (pid: string) => products.find(p => p.id === pid)?.name || pid || 'Genérico';
  const filteredLeads = leads.filter(l =>
    l.email.toLowerCase().includes(searchEmail.toLowerCase()) ||
    l.company?.toLowerCase().includes(searchEmail.toLowerCase())
  );
  const funnel = metrics?.funnel || {};
  const funnelSteps = [
    { key: 'leads_received', label: 'Leads', color: 'bg-slate-600' },
    { key: 'qualified', label: 'Calificados', color: 'bg-cyan-600' },
    { key: 'ready_to_buy', label: 'Hot Leads', color: 'bg-green-600' },
    { key: 'checkouts_sent', label: 'Checkouts', color: 'bg-purple-600' },
    { key: 'payments_completed', label: 'Pagos', color: 'bg-emerald-600' },
  ];
  const maxFunnel = Math.max(...funnelSteps.map(s => funnel[s.key] || 0), 1);

  const ProductSelect = ({ value, onChange }: { value: string; onChange: (v: string) => void }) => (
    <select value={value} onChange={e => onChange(e.target.value)}
      className="bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-300 px-2 py-1.5">
      <option value="">Todos los productos</option>
      {products.map(p => <option key={p.id} value={p.id}>{p.name} (${p.default_price_usd})</option>)}
    </select>
  );

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans">
      <header className="border-b border-slate-800 bg-slate-900/80 backdrop-blur sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-gradient-to-br from-cyan-500 to-purple-600 rounded-lg flex items-center justify-center">
              <TrendingUp size={18} className="text-white" />
            </div>
            <div>
              <h1 className="text-sm font-bold tracking-wide">MOTOR DE CIERRE AUTÓNOMO</h1>
              <p className="text-[10px] text-slate-500 font-mono">v2.1.0 — Multi-Producto</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className={`flex items-center gap-1.5 text-[10px] px-2 py-1 rounded-full border ${
              health?.status === 'ok' ? 'border-green-800 bg-green-900/20 text-green-400' : 'border-red-800 bg-red-900/20 text-red-400'}`}>
              <Shield size={10} />
              {health?.status === 'ok' ? `API Online · ${health.active_products || 0} productos` : 'API Offline'}
            </div>
            <button onClick={() => { loadHealth(); loadProducts(); loadMetrics(); loadLeads(); }}
              className="p-1.5 hover:bg-slate-800 rounded-lg text-slate-400 transition-colors">
              <RefreshCw size={14} />
            </button>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 py-6">
        {/* Product selector global */}
        <div className="flex items-center gap-3 mb-4">
          <Package size={14} className="text-slate-500" />
          <span className="text-[10px] text-slate-500 font-bold">PRODUCTO:</span>
          <ProductSelect value={selectedProduct} onChange={setSelectedProduct} />
        </div>

        {/* Tabs */}
        <div className="flex gap-1 bg-slate-900 rounded-xl p-1 mb-6 border border-slate-800 w-fit">
          {([
            { id: 'pipeline', label: 'Pipeline', icon: BarChart3 },
            { id: 'leads', label: 'Leads', icon: Users },
            { id: 'metrics', label: 'Métricas', icon: Activity },
            { id: 'products', label: 'Productos', icon: Package },
            { id: 'tools', label: 'Herramientas', icon: Zap },
          ] as const).map(tab => {
            const Icon = tab.icon;
            return (
              <button key={tab.id} onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-medium transition-all ${
                  activeTab === tab.id ? 'bg-slate-800 text-white shadow' : 'text-slate-500 hover:text-slate-300'}`}>
                <Icon size={14} /> {tab.label}
              </button>
            );
          })}
        </div>

        {/* PIPELINE */}
        {activeTab === 'pipeline' && (
          <div className="space-y-6">
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
                <div className="text-2xl font-bold text-cyan-400">{metrics?.conversion_rates?.checkout_to_paid || 0}%</div>
              </Card>
              <Card>
                <div className="text-[10px] text-slate-500 font-bold mb-1">LEADS ACTIVOS</div>
                <div className="text-2xl font-bold text-white">{leads.filter(l => !l.archived).length}</div>
              </Card>
            </div>

            <Card>
              <h3 className="text-sm font-bold text-slate-200 mb-4 flex items-center gap-2">
                <BarChart3 size={14} className="text-cyan-400" /> Embudo de Conversión
                {selectedProduct && <span className="text-[10px] text-cyan-400">· {productName(selectedProduct)}</span>}
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
                        <div className={`h-full ${step.color} transition-all duration-700 flex items-center px-3`}
                          style={{ width: `${Math.max(pct, 5)}%` }}>
                          <span className="text-xs font-bold text-white">{value}</span>
                        </div>
                      </div>
                      {dropOff && parseFloat(dropOff) > 0 && <div className="text-[10px] text-red-400 w-12">-{dropOff}%</div>}
                    </div>
                  );
                })}
              </div>
            </Card>

            {metrics?.by_product && metrics.by_product.length > 0 && (
              <Card>
                <h3 className="text-sm font-bold text-slate-200 mb-3">Ingresos por Producto</h3>
                <div className="space-y-2">
                  {metrics.by_product.map((p: any) => (
                    <div key={p.product_id || 'default'} className="flex items-center justify-between p-2 bg-slate-800/50 rounded-lg">
                      <div className="text-xs text-slate-200">{productName(p.product_id) || 'Genérico'}</div>
                      <div className="flex items-center gap-4">
                        <span className="text-[10px] text-slate-500">{p.leads || 0} leads</span>
                        <span className="text-xs font-bold text-emerald-400">${p.revenue || 0}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </Card>
            )}

            <Card>
              <h3 className="text-sm font-bold text-slate-200 mb-3">Últimos Leads</h3>
              <div className="space-y-2">
                {leads.slice(0, 5).map((lead: any) => (
                  <div key={lead.id} className="flex items-center justify-between p-2 bg-slate-800/50 rounded-lg">
                    <div>
                      <div className="text-xs font-mono text-slate-200">{lead.email}</div>
                      <div className="text-[10px] text-slate-500">
                        {lead.product_id && <span className="text-cyan-500">{productName(lead.product_id)} · </span>}
                        {lead.company || 'Sin empresa'}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge status={lead.status} />
                      {lead.score > 0 && <span className="text-[10px] text-cyan-400 font-mono">{lead.score}pts</span>}
                    </div>
                  </div>
                ))}
                {leads.length === 0 && <div className="text-slate-600 text-xs text-center py-4">Sin leads aún.</div>}
              </div>
            </Card>
          </div>
        )}

        {/* LEADS */}
        {activeTab === 'leads' && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <div className="lg:col-span-2 space-y-4">
              <Card>
                <div className="flex items-center gap-2 mb-4">
                  <Search size={14} className="text-slate-500" />
                  <input value={searchEmail} onChange={e => setSearchEmail(e.target.value)}
                    placeholder="Buscar por email o empresa..."
                    className="flex-1 bg-transparent text-xs text-slate-200 outline-none placeholder:text-slate-600" />
                  <select value={filterStatus} onChange={e => setFilterStatus(e.target.value)}
                    className="bg-slate-800 border border-slate-700 rounded text-xs text-slate-300 px-2 py-1">
                    <option value="all">Todos</option>
                    {Object.keys(STATUS_CONFIG).map(s => <option key={s} value={s}>{STATUS_CONFIG[s].label}</option>)}
                  </select>
                </div>
                <div className="space-y-2 max-h-[60vh] overflow-y-auto">
                  {filteredLeads.map((lead: any) => (
                    <div key={lead.id} onClick={() => loadLeadDetail(lead.email)}
                      className={`flex items-center justify-between p-2.5 rounded-lg cursor-pointer transition-colors ${
                        selectedLead?.email === lead.email ? 'bg-slate-700/50 border border-slate-600' : 'bg-slate-800/50 hover:bg-slate-800'}`}>
                      <div className="min-w-0">
                        <div className="text-xs font-mono text-slate-200 truncate">{lead.email}</div>
                        <div className="text-[10px] text-slate-500 flex items-center gap-1">
                          {lead.product_id && <span className="text-cyan-500">{productName(lead.product_id)}</span>}
                          {lead.product_id && (lead.company || '') && ' · '}
                          {lead.company || 'Sin empresa'}
                        </div>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        {lead.price_offered && <span className="text-[10px] text-emerald-400 font-mono">${lead.price_offered}</span>}
                        <Badge status={lead.status} />
                        {lead.score > 0 && <span className="text-[10px] text-cyan-400 font-mono">{lead.score}</span>}
                      </div>
                    </div>
                  ))}
                  {filteredLeads.length === 0 && <div className="text-slate-600 text-xs text-center py-8">Sin leads.</div>}
                </div>
              </Card>
            </div>

            <div>
              {leadDetail ? (
                <div className="space-y-3 sticky top-20">
                  <Card>
                    <h3 className="text-sm font-bold text-slate-200 mb-3">{leadDetail.lead?.email}</h3>
                    <div className="space-y-2 text-xs">
                      <div className="flex justify-between"><span className="text-slate-500">Estado</span><Badge status={leadDetail.lead?.status} /></div>
                      <div className="flex justify-between"><span className="text-slate-500">Empresa</span><span>{leadDetail.lead?.company || '—'}</span></div>
                      <div className="flex justify-between"><span className="text-slate-500">Producto</span><span className="text-cyan-400">{productName(leadDetail.lead?.product_id) || 'Genérico'}</span></div>
                      <div className="flex justify-between"><span className="text-slate-500">Score</span><span className="text-cyan-400">{leadDetail.lead?.score || 0}/100</span></div>
                      <div className="flex justify-between"><span className="text-slate-500">Precio</span><span className="text-emerald-400">${leadDetail.lead?.price_offered || '—'}</span></div>
                      <div className="flex justify-between"><span className="text-slate-500">Intent</span><span className="text-amber-400">{leadDetail.lead?.intent || '—'}</span></div>
                      {leadDetail.lead?.payment_link && (
                        <div className="pt-2">
                          <a href={leadDetail.lead.payment_link} target="_blank" rel="noreferrer"
                            className="text-[10px] text-purple-400 hover:text-purple-300 break-all">🔗 {leadDetail.lead.payment_link}</a>
                        </div>
                      )}
                    </div>
                    <div className="mt-3 flex flex-wrap gap-1">
                      {Object.keys(STATUS_CONFIG).map(s => (
                        <button key={s} onClick={() => updateLeadStatus(leadDetail.lead.email, s)}
                          className={`px-2 py-1 rounded text-[10px] font-medium transition-colors ${
                            leadDetail.lead.status === s ? 'bg-slate-700 text-white' : 'bg-slate-800 text-slate-500 hover:bg-slate-700'}`}>
                          {STATUS_CONFIG[s].label}
                        </button>
                      ))}
                    </div>
                  </Card>
                  <Card>
                    <h4 className="text-xs font-bold text-slate-300 mb-2">Historial</h4>
                    <div className="space-y-2 max-h-40 overflow-y-auto">
                      {leadDetail.conversation_history?.map((conv: any, i: number) => (
                        <div key={i} className="text-[10px]">
                          <div className="flex items-center gap-2 mb-0.5">
                            <span className={`font-bold ${conv.direction === 'inbound' ? 'text-cyan-400' : conv.direction === 'outbound' ? 'text-purple-400' : 'text-amber-400'}`}>
                              {conv.direction === 'inbound' ? 'Prospecto' : conv.direction === 'outbound' ? 'Sistema' : 'AI'}
                            </span>
                            <span className="text-slate-600">{new Date(conv.created_at).toLocaleString()}</span>
                          </div>
                          <div className="text-slate-300 whitespace-pre-wrap">{conv.content}</div>
                          {conv.intent_detected && <div className="text-amber-400 mt-0.5">Intent: {conv.intent_detected}</div>}
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

        {/* MÉTRICAS */}
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

            {metrics?.by_product && metrics.by_product.length > 0 && (
              <Card>
                <h3 className="text-sm font-bold text-slate-200 mb-4">Métricas por Producto (30 días)</h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="text-slate-500 border-b border-slate-800">
                        <th className="text-left py-2 px-2">Producto</th>
                        <th className="text-right py-2 px-2">Leads</th>
                        <th className="text-right py-2 px-2">Pagos</th>
                        <th className="text-right py-2 px-2">Ingresos</th>
                      </tr>
                    </thead>
                    <tbody>
                      {metrics.by_product.map((p: any) => (
                        <tr key={p.product_id || 'default'} className="border-b border-slate-800/50">
                          <td className="py-2 px-2 text-slate-200">{productName(p.product_id) || 'Genérico'}</td>
                          <td className="py-2 px-2 text-right text-slate-400">{p.leads || 0}</td>
                          <td className="py-2 px-2 text-right text-emerald-400">{p.paid || 0}</td>
                          <td className="py-2 px-2 text-right text-emerald-400 font-bold">${p.revenue || 0}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>
            )}

            <Card>
              <h3 className="text-sm font-bold text-slate-200 mb-4">Estado de la API</h3>
              <div className="grid grid-cols-2 md:grid-cols-5 gap-3 text-xs">
                <div className="p-3 bg-slate-800 rounded-lg">
                  <div className="text-slate-500 mb-1">Stripe</div>
                  <div className={`font-bold ${health?.stripe_configured ? 'text-green-400' : 'text-red-400'}`}>
                    {health?.stripe_configured ? '✓' : '✗'}
                  </div>
                </div>
                <div className="p-3 bg-slate-800 rounded-lg">
                  <div className="text-slate-500 mb-1">OpenAI</div>
                  <div className={`font-bold ${health?.openai_configured ? 'text-green-400' : 'text-red-400'}`}>
                    {health?.openai_configured ? '✓' : '✗'}
                  </div>
                </div>
                <div className="p-3 bg-slate-800 rounded-lg">
                  <div className="text-slate-500 mb-1">Productos</div>
                  <div className="font-bold text-cyan-400">{health?.active_products || 0}</div>
                </div>
                <div className="p-3 bg-slate-800 rounded-lg">
                  <div className="text-slate-500 mb-1">DB</div>
                  <div className="font-bold text-slate-200 text-[10px] truncate">{health?.db_path || '—'}</div>
                </div>
                <div className="p-3 bg-slate-800 rounded-lg">
                  <div className="text-slate-500 mb-1">Versión</div>
                  <div className="font-bold text-slate-200">{health?.version || '—'}</div>
                </div>
              </div>
            </Card>
          </div>
        )}

        {/* PRODUCTOS */}
        {activeTab === 'products' && (
          <div className="space-y-6">
            <Card>
              <h3 className="text-sm font-bold text-slate-200 mb-4 flex items-center gap-2">
                <Plus size={14} className="text-cyan-400" /> Registrar Nuevo Producto
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                <div>
                  <label className="text-[10px] text-slate-500 font-bold">ID (SLUG)</label>
                  <input value={newProduct.id} onChange={e => setNewProduct({ ...newProduct, id: e.target.value })}
                    placeholder="mi-producto"
                    className="w-full mt-1 bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-200 font-mono" />
                </div>
                <div>
                  <label className="text-[10px] text-slate-500 font-bold">NOMBRE</label>
                  <input value={newProduct.name} onChange={e => setNewProduct({ ...newProduct, name: e.target.value })}
                    placeholder="Nombre del producto"
                    className="w-full mt-1 bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-200" />
                </div>
                <div>
                  <label className="text-[10px] text-slate-500 font-bold">PRECIO (USD)</label>
                  <input type="number" value={newProduct.default_price_usd}
                    onChange={e => setNewProduct({ ...newProduct, default_price_usd: parseInt(e.target.value) || 0 })}
                    className="w-full mt-1 bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-200 font-mono" />
                </div>
                <div>
                  <label className="text-[10px] text-slate-500 font-bold">DESCRIPCIÓN</label>
                  <input value={newProduct.description} onChange={e => setNewProduct({ ...newProduct, description: e.target.value })}
                    placeholder="Opcional"
                    className="w-full mt-1 bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-200" />
                </div>
              </div>
              <button onClick={handleCreateProduct}
                className="mt-3 py-2 px-4 bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-bold rounded-lg transition-colors flex items-center gap-2">
                <Plus size={12} /> Crear Producto
              </button>
            </Card>

            <Card>
              <h3 className="text-sm font-bold text-slate-200 mb-4 flex items-center gap-2">
                <Package size={14} className="text-purple-400" /> Productos Registrados ({products.length})
              </h3>
              <div className="space-y-2">
                {products.map(p => (
                  <div key={p.id} className="flex items-center justify-between p-3 bg-slate-800/50 rounded-lg">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 bg-gradient-to-br from-cyan-500 to-purple-600 rounded-lg flex items-center justify-center shrink-0">
                        <Package size={14} className="text-white" />
                      </div>
                      <div>
                        <div className="text-xs font-bold text-slate-200">{p.name}</div>
                        <div className="text-[10px] text-slate-500 font-mono">{p.id} · ${p.default_price_usd}</div>
                        {p.description && <div className="text-[10px] text-slate-600 mt-0.5">{p.description}</div>}
                      </div>
                    </div>
                    <button onClick={() => handleDeactivateProduct(p.id)}
                      className="p-1.5 text-slate-600 hover:text-red-400 transition-colors">
                      <Trash2 size={14} />
                    </button>
                  </div>
                ))}
                {products.length === 0 && <div className="text-slate-600 text-xs text-center py-4">Sin productos registrados.</div>}
              </div>
            </Card>
          </div>
        )}

        {/* HERRAMIENTAS */}
        {activeTab === 'tools' && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <Card>
              <h3 className="text-sm font-bold text-slate-100 mb-3 flex items-center gap-2">
                <CreditCard size={14} className="text-purple-400" /> Generar Checkout Manual
              </h3>
              <div className="space-y-3">
                <div>
                  <label className="text-[10px] text-slate-500 font-bold">EMAIL DEL LEAD</label>
                  <input value={manualCheckout.email} onChange={e => setManualCheckout({ ...manualCheckout, email: e.target.value })}
                    placeholder="cliente@empresa.com"
                    className="w-full mt-1 bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-200 font-mono" />
                </div>
                <div>
                  <label className="text-[10px] text-slate-500 font-bold">PRODUCTO</label>
                  <select value={manualCheckout.productId} onChange={e => {
                    const p = products.find(pr => pr.id === e.target.value);
                    setManualCheckout({ ...manualCheckout, productId: e.target.value, service: p?.name || '', price: p?.default_price_usd || 0 });
                  }}
                    className="w-full mt-1 bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-200">
                    <option value="">Genérico (${499})</option>
                    {products.map(p => <option key={p.id} value={p.id}>{p.name} (${p.default_price_usd})</option>)}
                  </select>
                </div>
                <div>
                  <label className="text-[10px] text-slate-500 font-bold">SERVICIO (OVERRIDE)</label>
                  <input value={manualCheckout.service} onChange={e => setManualCheckout({ ...manualCheckout, service: e.target.value })}
                    className="w-full mt-1 bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-200" />
                </div>
                <div>
                  <label className="text-[10px] text-slate-500 font-bold">PRECIO (USD)</label>
                  <input type="number" value={manualCheckout.price}
                    onChange={e => setManualCheckout({ ...manualCheckout, price: parseInt(e.target.value) || 0 })}
                    className="w-full mt-1 bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-200 font-mono" />
                </div>
                <button onClick={handleManualCheckout}
                  className="w-full py-2 bg-purple-600 hover:bg-purple-500 text-white text-xs font-bold rounded-lg transition-colors flex items-center justify-center gap-2">
                  <Send size={12} /> Generar y Enviar Link
                </button>
              </div>
            </Card>

            <Card>
              <h3 className="text-sm font-bold text-slate-100 mb-3 flex items-center gap-2">
                <Mail size={14} className="text-cyan-400" /> Simular Respuesta de Prospecto
              </h3>
              <div className="space-y-3">
                <input value={simReply.email} onChange={e => setSimReply({ ...simReply, email: e.target.value })}
                  placeholder="Email del prospecto"
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-200 font-mono" />
                <div>
                  <label className="text-[10px] text-slate-500 font-bold">PRODUCTO</label>
                  <select value={simReply.productId} onChange={e => setSimReply({ ...simReply, productId: e.target.value })}
                    className="w-full mt-1 bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-200">
                    <option value="">Genérico</option>
                    {products.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
                  </select>
                </div>
                <input value={simReply.subject} onChange={e => setSimReply({ ...simReply, subject: e.target.value })}
                  placeholder="Asunto del correo"
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-200" />
                <textarea value={simReply.body} onChange={e => setSimReply({ ...simReply, body: e.target.value })}
                  placeholder="Contenido del correo..."
                  rows={4}
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-200 resize-none" />
                <button onClick={handleSimulateReply}
                  className="w-full py-2 bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-bold rounded-lg transition-colors flex items-center justify-center gap-2">
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
