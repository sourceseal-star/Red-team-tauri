const http = require('http');
const https = require('https');
const cache = new Map();
const TTL = 30 * 60 * 1000;

function isPrivate(ip) {
  return /^(10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.|127\.|0\.0\.0\.0|169\.254\.)/.test(ip);
}

function lookup(ip) {
  return new Promise(resolve => {
    if (isPrivate(ip)) return resolve({ ip, private: true, lat: null, lon: null, country: '—', city: '—', isp: 'red privada / LAN', as: '—', note: 'IP privada: sin geolocalización pública (esto es esperado, no un error).' });
    const c = cache.get(ip);
    if (c && Date.now() - c.t < TTL) return resolve(c.v);
    // ipwho.is soporta HTTPS gratis sin API key (ip-api.com solo HTTP = bloqueado en sandbox)
    const req = https.get(`https://ipwho.is/${encodeURIComponent(ip)}?fields=success,country,city,latitude,longitude,connection,flag`, { timeout: 12000 }, res => {
      let b = ''; res.on('data', d => b += d); res.on('end', () => {
        try {
          const j = JSON.parse(b);
          if (!j.success) return resolve({ ip, error: j.message || 'geo falló', lat: null, lon: null });
          const conn = j.connection || {};
          const v = { ip: j.ip || ip, country: j.country || '—', city: j.city || '—', lat: j.latitude, lon: j.longitude,
                      isp: conn.isp || conn.org || '—', as: conn.asn || '—',
                      proxy: !!(conn.type && /proxy|vpn/i.test(conn.type)),
                      hosting: !!(conn.type && /hosting|cloud|datacenter/i.test(conn.type)) ||
                               !!(conn.isp && /digitalocean|amazon|google|microsoft|azure|ovh|hetzner|vultr|linode|cloudflare|contabo|scaleway|upcloud|kamatera|hostinger|godaddy|m247|psychz|leaseweb|OVH/i.test(conn.isp)),
                      mobile: !!(conn.type && /mobile|cellular/i.test(conn.type)) };
          cache.set(ip, { t: Date.now(), v }); resolve(v);
        } catch (e) { resolve({ ip, error: 'parse', lat: null, lon: null }); }
      });
    });
    req.on('error', e => resolve({ ip, error: e.message, lat: null, lon: null }));
    req.on('timeout', () => { req.destroy(); resolve({ ip, error: 'timeout', lat: null, lon: null }); });
  });
}
module.exports = { lookup, isPrivate };
