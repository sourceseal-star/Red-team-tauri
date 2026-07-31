const dns = require('dns').promises;
const https = require('https');
const http = require('http');
const { lookup } = require('./geo');

// blocklist caché (abuse.ch / spamhaus DROP). Si falla, score parcial y se avisa.
let bl = { set: new Set(), ok: false, at: 0 };
function loadBlocklist() {
  if (bl.ok && Date.now() - bl.at < 6 * 3600 * 1000) return Promise.resolve(bl);
  return new Promise(resolve => {
    const req = https.get('https://feodotracker.abuse.ch/downloads/ipblocklist_recommended.txt', { timeout: 8000 }, res => {
      let b = ''; res.on('data', d => b += d); res.on('end', () => {
        const set = new Set(b.split(/\r?\n/).map(l => l.trim()).filter(l => l && !l.startsWith('#')));
        bl = { set, ok: set.size > 0, at: Date.now() }; resolve(bl);
      });
    });
    req.on('error', () => resolve(bl)); req.on('timeout', () => { req.destroy(); resolve(bl); });
  });
}

const BULLETPROOF = /marosnet|king servers|hostkey|firstheberg|neterra|abeloost|m247|psychz/i;

async function reverse(ip) {
  try { const r = await dns.reverse(ip); return r && r[0] ? r[0] : null; } catch (e) { return null; }
}

// score 0..100 de RIESGO (más alto = menos confiable). Desglose visible.
async function assess(ip) {
  const g = await lookup(ip);
  const rdns = await reverse(ip);
  const list = await loadBlocklist();
  const breakdown = [];
  let score = 0;
  if (g.private) return { ip, private: true, score: 0, label: 'LAN', rdns, breakdown: [{ f: 'red privada', w: 0 }], flags: g, blocklist: list.ok, note: 'IP interna: confianza N/A (no es un host público).' };
  if (g.hosting) { score += 25; breakdown.push({ f: 'hosting / cloud', w: 25 }); }
  if (g.proxy)   { score += 30; breakdown.push({ f: 'proxy / vpn', w: 30 }); }
  if (g.mobile)  { score -= 10; breakdown.push({ f: 'móvil / CGN (suele residencial)', w: -10 }); }
  if (rdns && /tor|exit|relay/i.test(rdns)) { score += 40; breakdown.push({ f: 'posible nodo tor', w: 40 }); }
  if (list.ok && list.set.has(ip)) { score += 45; breakdown.push({ f: 'en blocklist (abuse.ch)', w: 45 }); }
  if (rdns && BULLETPROOF.test(rdns)) { score += 20; breakdown.push({ f: 'ASN bulletproof', w: 20 }); }
  if (g.as && BULLETPROOF.test(g.as)) { score += 20; breakdown.push({ f: 'AS bulletproof', w: 20 }); }
  score = Math.max(0, Math.min(100, score));
  const label = score <= 20 ? 'ALTA (limpia)' : score <= 50 ? 'MEDIA' : score <= 80 ? 'BAJA' : 'CRÍTICA';
  return { ip, score, label, rdns, breakdown, flags: g, blocklist: list.ok,
    note: list.ok ? 'score completo' : 'score PARCIAL: blocklist no disponible en esta red' };
}
module.exports = { assess };
