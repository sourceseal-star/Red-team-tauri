// Geo + DNS + CIDR: geolocalización, resolución DNS, expansión de rangos, distancia Haversine.
const http = require('http');
const https = require('https');
const dns = require('dns').promises;
const cache = new Map();
const TTL = 30 * 60 * 1000;

function isPrivate(ip) {
  return /^(10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.|127\.|0\.0\.0\.0|169\.254\.|100\.(6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.)/.test(ip);
}

// Expandir CIDR a lista de IPs (máx 256 para evitar abuso)
function expandCidr(cidr) {
  const m = cidr.match(/^(\d+)\.(\d+)\.(\d+)\.(\d+)\/(\d+)$/);
  if (!m) return [cidr];
  const prefix = parseInt(m[5]);
  if (prefix < 24) return [cidr]; // /24 minimo
  const base = (parseInt(m[1]) << 24 | parseInt(m[2]) << 16 | parseInt(m[3]) << 8 | parseInt(m[4])) >>> 0;
  const mask = prefix === 32 ? 0xFFFFFFFF : (0xFFFFFFFF << (32 - prefix)) >>> 0;
  const network = (base & mask) >>> 0;
  const count = Math.min(256, 1 << (32 - prefix));
  const ips = [];
  for (let i = 0; i < count; i++) ips.push(int2ip(network + i));
  return ips;
}
function int2ip(n) { return [(n >>> 24) & 255, (n >>> 16) & 255, (n >>> 8) & 255, n & 255].join('.'); }

// DNS forward (hostname -> IPs)
async function resolveHost(host) {
  if (/^\d+\.\d+\.\d+\.\d+$/.test(host)) return [host];
  try { const a = await dns.resolve4(host); return a || []; }
  catch { try { const a = await dns.lookup(host, { family: 4 }); return a ? [a.address] : []; } catch { return []; } }
}

// Reverse DNS (IP -> hostname)
async function reverse(ip) {
  try { const r = await dns.reverse(ip); return r && r[0] ? r[0] : null; }
  catch { return null; }
}

// Distancia Haversine (km)
function haversine(lat1, lon1, lat2, lon2) {
  if (lat1 == null || lon1 == null || lat2 == null || lon2 == null) return null;
  const R = 6371, toRad = d => d * Math.PI / 180;
  const dLat = toRad(lat2 - lat1), dLon = toRad(lon2 - lon1);
  const a = Math.sin(dLat/2)**2 + Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon/2)**2;
  return Math.round(R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a)));
}

// Lookup individual
function lookup(ip) {
  return new Promise(resolve => {
    if (isPrivate(ip)) return resolve({
      ip, private: true, lat: null, lon: null, country: '—', city: '—',
      isp: 'red privada / LAN', as: '—', timezone: null,
      note: 'IP privada: sin geolocalizacion publica (esperado).'
    });
    const c = cache.get(ip);
    if (c && Date.now() - c.t < TTL) return resolve(c.v);
    const req = https.get(
      `https://ipwho.is/${encodeURIComponent(ip)}?fields=success,country,country_code,city,latitude,longitude,connection,flag,timezone`,
      { timeout: 10000 }, res => {
        let b = ''; res.on('data', d => b += d); res.on('end', () => {
          try {
            const j = JSON.parse(b);
            if (!j.success) return resolve({ ip, error: j.message || 'geo fallo', lat: null, lon: null });
            const conn = j.connection || {};
            const v = {
              ip: j.ip || ip,
              country: j.country || '—', country_code: j.country_code || null,
              city: j.city || '—', lat: j.latitude, lon: j.longitude,
              isp: conn.isp || conn.org || '—', as: conn.asn || '—',
              timezone: j.timezone?.id || null, utc_offset: j.timezone?.utc || null,
              proxy: !!(conn.type && /proxy|vpn/i.test(conn.type)),
              hosting: !!(conn.type && /hosting|cloud|datacenter/i.test(conn.type)) ||
                       !!(conn.isp && /digitalocean|amazon|google|microsoft|azure|ovh|hetzner|vultr|linode|cloudflare|contabo|scaleway|upcloud|kamatera|hostinger|godaddy|m247|psychz|leaseweb/i.test(conn.isp)),
              mobile: !!(conn.type && /mobile|cellular/i.test(conn.type))
            };
            cache.set(ip, { t: Date.now(), v }); resolve(v);
          } catch { resolve({ ip, error: 'parse', lat: null, lon: null }); }
        });
      });
    req.on('error', e => resolve({ ip, error: e.message, lat: null, lon: null }));
    req.on('timeout', () => { req.destroy(); resolve({ ip, error: 'timeout', lat: null, lon: null }); });
  });
}

// Bulk lookup con concurrencia limitada
async function lookupMany(ips, conc = 4) {
  const out = []; let i = 0;
  const workers = Array.from({ length: Math.min(conc, ips.length) }, async () => {
    while (i < ips.length) { const ip = ips[i++]; out.push(await lookup(ip)); }
  });
  await Promise.all(workers);
  return out;
}

// Recon geografico completo: DNS + geo + reverse
async function recon(target) {
  const ips = await resolveHost(target);
  if (!ips.length) return { target, error: 'no se pudo resolver el hostname', ips: [] };
  const results = [];
  for (const ip of ips) {
    const [geo, rdns] = await Promise.all([lookup(ip), reverse(ip)]);
    results.push({ ip, rdns, geo });
  }
  return { target, resolved_ips: ips, results };
}

module.exports = { lookup, lookupMany, isPrivate, expandCidr, resolveHost, reverse, haversine, recon };
