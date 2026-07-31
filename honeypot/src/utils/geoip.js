/**
 * GeoIP — Geolocalización de IPs atacantes
 * Usa ipapi.co (API gratuita, sin API key necesaria)
 * Fallback a geoip-lite si está instalado
 */

let geoipLite = null;
try {
  geoipLite = require('geoip-lite');
} catch (e) {
  // geoip-lite no instalado — usaremos API
}

const cache = new Map();
const CACHE_TTL = 3600000; // 1 hora

async function lookup(ip) {
  // Skip private/local IPs
  if (!ip || ip === '127.0.0.1' || ip === '::1' || ip.startsWith('192.168.') ||
      ip.startsWith('10.') || ip.startsWith('172.') || ip === 'localhost') {
    return { country: 'Local', city: 'Local', region: 'Local', ll: null };
  }

  // Check cache
  if (cache.has(ip)) {
    const cached = cache.get(ip);
    if (Date.now() - cached.ts < CACHE_TTL) {
      return cached.data;
    }
    cache.delete(ip);
  }

  // Try geoip-lite first (offline, fast)
  if (geoipLite) {
    const geo = geoipLite.lookup(ip);
    if (geo) {
      const data = { country: geo.country || 'Unknown', city: geo.city || 'Unknown', region: geo.region || 'Unknown', ll: geo.ll };
      cache.set(ip, { ts: Date.now(), data });
      return data;
    }
  }

  // Fallback: ipapi.co (online, free, no key)
  try {
    const res = await fetch(`https://ipapi.co/${ip}/json/`, {
      signal: AbortSignal.timeout(5000)
    });
    if (res.ok) {
      const data = await res.json();
      const result = {
        country: data.country_name || data.country || 'Unknown',
        city: data.city || 'Unknown',
        region: data.region || 'Unknown',
        ll: data.latitude && data.longitude ? [data.latitude, data.longitude] : null
      };
      cache.set(ip, { ts: Date.now(), data: result });
      return result;
    }
  } catch (e) {
    // Timeout or error — return Unknown
  }

  return { country: 'Unknown', city: 'Unknown', region: 'Unknown', ll: null };
}

function getCountry(ip) {
  // Synchronous version using geoip-lite only
  if (!geoipLite) return 'Unknown';
  if (!ip || ip.startsWith('192.168.') || ip.startsWith('10.') || ip === '127.0.0.1') return 'Local';
  const geo = geoipLite.lookup(ip);
  return geo ? geo.country : 'Unknown';
}

module.exports = { lookup, getCountry };
