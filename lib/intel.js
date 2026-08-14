// Intel expandido: scoring de riesgo con multiples blocklists, WHOIS/RDAP, SSL cert, correlacion de puertos.
const dns = require('dns').promises;
const https = require('https');
const http = require('http');
const tls = require('tls');
const { lookup, reverse } = require('./geo');

// Cache de blocklists
let blAbuse = { set: new Set(), ok: false, at: 0 };
let blSpamhaus = { set: new Set(), ok: false, at: 0 };
let blET = { set: new Set(), ok: false, at: 0 };

function loadList(store, url, parser, ttl = 6 * 3600 * 1000) {
  if (store.ok && Date.now() - store.at < ttl) return Promise.resolve(store);
  return new Promise(resolve => {
    const req = https.get(url, { timeout: 8000 }, res => {
      let b = ''; res.on('data', d => b += d); res.on('end', () => {
        const set = parser(b);
        Object.assign(store, { set, ok: set.size > 0, at: Date.now() });
        resolve(store);
      });
    });
    req.on('error', () => resolve(store));
    req.on('timeout', () => { req.destroy(); resolve(store); });
  });
}

async function loadAllLists() {
  await Promise.all([
    loadList(blAbuse, 'https://feodotracker.abuse.ch/downloads/ipblocklist_recommended.txt',
      b => new Set(b.split(/\r?\n/).map(l => l.trim()).filter(l => l && !l.startsWith('#')))),
    // Spamhaus DROP (lista de redes hijacked)
    loadList(blSpamhaus, 'https://www.spamhaus.org/drop/drop.txt',
      b => new Set(b.split(/\r?\n/).map(l => l.split(';')[0].trim()).filter(l => l && l.includes('/')))),
    // Emerging Threats compromised IPs
    loadList(blET, 'https://rules.emergingthreats.net/blockrules/compromised-ips.txt',
      b => new Set(b.split(/\r?\n/).map(l => l.trim()).filter(l => l && !l.startsWith('#')))),
  ]);
  return { abuse: blAbuse.ok, spamhaus: blSpamhaus.ok, et: blET.ok };
}

const BULLETPROOF = /marosnet|king.?servers|hostkey|firstheberg|neterra|abeloost|m247|psychz|bulletproof|offshore/i;

// Puertos comunes de C2 / servicios comprometidos
const C2_PORTS = {
  4444: 'Metasploit default',
  1337: 'Slager/DevShell',
  9001: 'Cobalt Strike (common)',
  8080: 'HTTP proxy/C2',
  443: 'HTTPS C2',
  8443: 'HTTPS alt C2',
  1234: 'C2 variants',
  9999: 'C2 variants',
  31337: 'Back Orifice / Elite',
  6667: 'IRC botnet C2',
  6660: 'IRC botnet C2',
  6669: 'IRC botnet C2',
};

// SSL cert info (issuer, validity, SANs)
function probeTLS(host, port = 443, timeout = 4000) {
  return new Promise(resolve => {
    const s = tls.connect({ host, port, rejectUnauthorized: true, servername: host }, () => {
      const cert = s.getPeerCertificate();
      resolve({
        present: !!cert,
        subject: cert?.subject?.CN || null,
        issuer: cert?.issuer?.O || cert?.issuer?.CN || null,
        valid_from: cert?.valid_from || null,
        valid_to: cert?.valid_to || null,
        self_signed: cert?.subject?.CN === cert?.issuer?.CN,
        sans: cert?.subjectaltname?.replace(/DNS:|IP Address:/g, '').split(',').map(s => s.trim()).filter(Boolean).slice(0, 10) || [],
        authorized: s.authorized
      });
      s.destroy();
    });
    s.setTimeout(timeout);
    s.on('timeout', () => { s.destroy(); resolve({ present: false, error: 'timeout' }); });
    s.on('error', e => resolve({ present: false, error: e.message }));
  });
}

// WHOIS/RDAP lookup (ip -> org, abuse contact, country)
function rdapLookup(ip, timeout = 6000) {
  return new Promise(resolve => {
    const req = https.get(`https://rdap.org/ip/${ip}`, { timeout, headers: { 'Accept': 'application/rdap+json' } }, res => {
      let b = ''; res.on('data', d => b += d); res.on('end', () => {
        try {
          const j = JSON.parse(b);
          const entities = (j.entities || []).map(e => ({
            role: e.roles?.[0] || null,
            handle: e.handle || null,
            email: (j.entities || []).find(e => e.vcardArray?.[1]?.some(v => v[0] === 'email'))?.vcardArray?.[1]?.find(v => v[0] === 'email')?.[3] || null
          }));
          resolve({
            ok: true,
            network: j.name || null,
            start: j.startAddress || null,
            end: j.endAddress || null,
            country: j.country || null,
            entities
          });
        } catch { resolve({ ok: false, error: 'parse' }); }
      });
    });
    req.on('error', e => resolve({ ok: false, error: e.message }));
    req.on('timeout', () => { req.destroy(); resolve({ ok: false, error: 'timeout' }); });
  });
}

// Score 0..100 de RIESGO. Desglose visible.
async function assess(ip, opts = {}) {
  const g = await lookup(ip);
  const rdns = await reverse(ip);
  const lists = await loadAllLists();
  const breakdown = [];
  let score = 0;

  if (g.private) return {
    ip, private: true, score: 0, label: 'LAN', rdns, breakdown, flags: g,
    blocklists: lists, note: 'IP interna: confianza N/A.'
  };

  if (g.hosting) { score += 25; breakdown.push({ f: 'hosting / cloud', w: 25 }); }
  if (g.proxy) { score += 30; breakdown.push({ f: 'proxy / vpn', w: 30 }); }
  if (g.mobile) { score -= 10; breakdown.push({ f: 'movil / CGN (suele residencial)', w: -10 }); }

  if (rdns && /tor|exit|relay/i.test(rdns)) { score += 40; breakdown.push({ f: 'posible nodo tor', w: 40 }); }
  if (rdns && BULLETPROOF.test(rdns)) { score += 20; breakdown.push({ f: 'ASN bulletproof (rDNS)', w: 20 }); }
  if (g.as && BULLETPROOF.test(g.as)) { score += 20; breakdown.push({ f: 'AS bulletproof', w: 20 }); }

  if (blAbuse.ok && blAbuse.set.has(ip)) { score += 45; breakdown.push({ f: 'abuse.ch blocklist', w: 45 }); }
  if (blSpamhaus.ok) {
    for (const net of blSpamhaus.set) {
      if (ipInCidr(ip, net)) { score += 35; breakdown.push({ f: 'Spamhaus DROP', w: 35 }); break; }
    }
  }
  if (blET.ok && blET.set.has(ip)) { score += 30; breakdown.push({ f: 'Emerging Threats', w: 30 }); }

  // Correlacion de puertos abiertos si se pasa opts.ports
  if (opts.ports && Array.isArray(opts.ports)) {
    for (const p of opts.ports) {
      if (C2_PORTS[p]) { score += 15; breakdown.push({ f: `puerto ${p} (${C2_PORTS[p]})`, w: 15 }); }
    }
  }

  // SSL cert check si es host publico
  let tlsInfo = null;
  if (!g.private && opts.tls !== false) {
    tlsInfo = await probeTLS(ip);
    if (tlsInfo.self_signed) { score += 15; breakdown.push({ f: 'certificado autofirmado', w: 15 }); }
    if (tlsInfo.present && tlsInfo.valid_to) {
      const expiry = new Date(tlsInfo.valid_to);
      if (expiry < new Date()) { score += 20; breakdown.push({ f: 'certificado vencido', w: 20 }); }
    }
  }

  // RDAP/WHOIS
  let rdap = null;
  if (opts.rdap !== false && !g.private) {
    rdap = await rdapLookup(ip);
  }

  score = Math.max(0, Math.min(100, score));
  const label = score <= 20 ? 'ALTA (limpia)' : score <= 50 ? 'MEDIA' : score <= 80 ? 'BAJA' : 'CRITICA';

  return {
    ip, score, label, rdns, breakdown, flags: g,
    blocklists: lists,
    tls: tlsInfo,
    rdap: rdap?.ok ? rdap : null,
    note: Object.values(lists).every(v => !v) ? 'score PARCIAL: blocklists no disponibles' : 'score completo'
  };
}

// Verificar si IP esta en CIDR
function ipInCidr(ip, cidr) {
  const m = cidr.match(/^(\d+\.\d+\.\d+\.\d+)\/(\d+)$/);
  if (!m) return false;
  const net = m[1], prefix = parseInt(m[2]);
  const ipInt = ip.split('.').reduce((a, o) => (a << 8) + parseInt(o), 0) >>> 0;
  const netInt = net.split('.').reduce((a, o) => (a << 8) + parseInt(o), 0) >>> 0;
  const mask = prefix === 0 ? 0 : (0xFFFFFFFF << (32 - prefix)) >>> 0;
  return (ipInt & mask) === (netInt & mask);
}

module.exports = { assess, loadAllLists, probeTLS, rdapLookup, ipInCidr };
