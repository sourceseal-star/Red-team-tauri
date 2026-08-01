// IoT + Port scanner + Service fingerprinting expandido.
// TCP probe, RTSP, SIP, SSH, FTP, Telnet, DB, HTTP camera, UPnP/SSDP.
const net = require('net');
const dgram = require('dgram');
const http = require('http');
const https = require('https');
const crypto = require('crypto');


// Puertos FAST para escaneo de red rápida — solo CCTV/IoT esenciales
const FAST_PORTS = [
  // Web (para descubrir el panel web de la cámara)
  80, 443, 8080, 8000, 8888, 8443, 8081,
  // RTSP (streaming de video)
  554, 8554,
  // ONVIF
  3702,
  // CCTV específicos
  37777, 34567, 5000, 8001,
  // VoIP
  5060,
];

// Puertos expandidos — cobertura completa de CCTV/IoT/radio
const ALL_PORTS = [
  // Web común
  80, 81, 82, 83, 85, 88, 443, 8080, 8081, 8082, 8083, 8088, 8090,
  8443, 8888, 9000, 9090, 9080, 8000, 8001, 8002, 8003,
  // CCTV — Hikvision
  8000, 8001, 8020, 8200,
  // CCTV — Dahua
  37777, 37778,
  // CCTV — otros vendors
  34567, 34578, 34579, 34580, 34581,  // Xiongmai/Sricam
  5000, 5001, 5002, 5003,  // Vivotek/Amcrest
  7000, 7001, 7002,  // Generic NVR
  10080,  // Hikvision NVR
  // RTSP / video streaming
  554, 8554, 10554, 15554,
  // ONVIF / WS-Discovery
  3702, 5000,
  // VoIP / SIP
  5060, 5061, 5080,
  // Radio IP / streaming
  8000, 8001, 8005, 8006, 8080, 8443,
  // Shell / remote
  22, 23, 3389, 5900, 5901,
  // FTP / mail
  21, 25, 110, 143, 993, 995,
  // DBs
  1433, 3306, 5432, 6379, 27017, 9200, 11211,
  // DNS / SNMP / misc
  53, 161, 162, 123,
  // DVR / NVR adicionales
  9008, 9009, 9010,  // Hikvision DVR
  30001, 30002,  // Generic DVR
  4321, 4322,  // Vivotek
  7777, 7778,  // Generic IP cam
  1080, 1081,  // Generic
  2048, 2049,  // Generic
  8889, 8890,  // Generic
  65535,       // DVR chino
];

const CAM_PATHS = [
  { p: '/ISAPI/System/deviceInfo', v: 'Hikvision' },
  { p: '/cgi-bin/magicBox.cgi?action=getVendor', v: 'Dahua' },
  { p: '/axis-cgi/com/param.cgi', v: 'Axis' },
  { p: '/onvif/device_service', v: 'ONVIF' },
  { p: '/snapshot.cgi', v: 'cam-IP generica' },
  { p: '/doc/page/index.asp', v: 'Hikvision (web)' },
  { p: '/api/ptz/status', v: 'Vivotek' },
  { p: '/cgi-bin/viewer/video.jpg', v: 'Axis (stream)' },
  { p: '/live/cam.html', v: 'cam-IP web' },
  { p: '/video/mjpg.cgi', v: 'Foscam' },
  { p: '/mjpg/video.mjpg', v: 'Axis (MJPEG)' },
];

const md5 = s => crypto.createHash('md5').update(s, 'latin1').digest('hex');

function tcpProbe(ip, port, timeout = 800) {
  return new Promise(res => {
    const s = net.createConnection({ host: ip, port }); let done = false, banner = '';
    const fin = o => { if (done) return; done = true; s.destroy(); res(o); };
    s.setTimeout(timeout);
    s.on('connect', () => fin({ open: true, banner: '' }));
    s.on('data', d => { banner += d.toString('latin1'); if (banner.length > 512) fin({ open: true, banner }); });
    s.on('timeout', () => fin({ open: banner.length > 0, banner }));
    s.on('error', () => fin({ open: false, banner }));
  });
}

function httpRaw(ip, port, path, headers, timeout = 2500) {
  return new Promise(res => {
    const proto = (port === 443 || port === 8443) ? https : http;
    const req = proto.get({ host: ip, port, path, timeout, headers: Object.assign({ 'User-Agent': 'sealctl-audit/1.0' }, headers), rejectUnauthorized: false }, r => {
      let b = ''; r.on('data', d => { b += d; if (b.length > 4000) r.destroy(); });
      const fin = () => res({ status: r.statusCode, headers: r.headers, body: b, www: r.headers['www-authenticate'] || '' });
      r.on('end', fin); r.on('close', fin);
    });
    req.on('error', e => res({ status: 0, error: e.message }));
    req.on('timeout', () => { req.destroy(); res({ status: 0, error: 'timeout' }); });
  });
}
function httpGet(ip, port, path, timeout = 1500) { return httpRaw(ip, port, path, {}, timeout); }

// ---- Digest handshake REAL (RFC 2617) ----
function parseChallenge(www) {
  const m = www.replace(/^Digest\s+/i, '');
  const get = k => { const r = new RegExp(k + '="([^"]*)"').exec(m); return r ? r[1] : (new RegExp(k + '=([^,]*)').exec(m) || [])[1]; };
  return { realm: get('realm'), nonce: get('nonce'), qop: get('qop'), opaque: get('opaque') };
}
async function httpAuthDigest(ip, port, path, user, pass, timeout = 3000) {
  const first = await httpRaw(ip, port, path, {});
  if (first.status !== 401 || !/^Digest/i.test(first.www || '')) return first;
  const c = parseChallenge(first.www); if (!c.realm || !c.nonce) return first;
  const nc = '00000001', cnonce = crypto.randomBytes(8).toString('hex');
  const HA1 = md5(`${user}:${c.realm}:${pass}`), HA2 = md5(`GET:${path}`);
  const response = c.qop ? md5(`${HA1}:${c.nonce}:${nc}:${cnonce}:auth:${HA2}`) : md5(`${HA1}:${c.nonce}:${HA2}`);
  let hdr = `Digest username="${user}", realm="${c.realm}", nonce="${c.nonce}", uri="${path}", response="${response}"`;
  if (c.qop) hdr += `, qop=auth, nc=${nc}, cnonce="${cnonce}"`;
  if (c.opaque) hdr += `, opaque="${c.opaque}"`;
  const second = await httpRaw(ip, port, path, { 'Authorization': hdr });
  second.digest = true; return second;
}
async function httpAuthAny(ip, port, path, user, pass) {
  const basic = await httpRaw(ip, port, path, { 'Authorization': 'Basic ' + Buffer.from(user + ':' + pass).toString('base64') });
  if (basic.status === 200) return { ...basic, scheme: 'Basic' };
  if (basic.status === 401 && /^Digest/i.test(basic.www || '')) {
    const d = await httpAuthDigest(ip, port, path, user, pass);
    return { ...d, scheme: d.status === 200 ? 'Digest' : 'Basic' };
  }
  return { ...basic, scheme: 'Basic' };
}

function rtspOptions(ip, port = 554, timeout = 2000) {
  return new Promise(res => {
    const s = net.createConnection({ host: ip, port }); let buf = '', done = false;
    const fin = o => { if (done) return; done = true; s.destroy(); res(o); };
    s.setTimeout(timeout);
    s.on('connect', () => s.write(`OPTIONS rtsp://${ip}:${port}/ RTSP/1.0\r\nCSeq: 1\r\n\r\n`));
    s.on('data', d => { buf += d.toString('latin1'); if (/RTSP\/1\.0 \d+/.test(buf)) fin({ ok: true, banner: buf.slice(0, 240) }); });
    s.on('timeout', () => fin({ ok: /RTSP\/1\.0/.test(buf), banner: buf.slice(0, 240) }));
    s.on('error', () => fin({ ok: false, banner: '' }));
  });
}

function sipOptions(ip, port = 5060, timeout = 2000) {
  return new Promise(res => {
    const s = dgram.createSocket('udp4'); let done = false;
    const fin = o => { if (done) return; done = true; try { s.close(); } catch (e) {} res(o); };
    const msg = `OPTIONS sip:${ip} SIP/2.0\r\nVia: SIP/2.0/UDP 127.0.0.1;branch=z9hG4bK-seal\r\nFrom: <sip:seal@127.0.0.1>;tag=1\r\nTo: <sip:${ip}>\r\nCall-ID: seal@127.0.0.1\r\nCSeq: 1 OPTIONS\r\nMax-Forwards: 70\r\nContent-Length: 0\r\n\r\n`;
    s.send(msg, port, ip, () => {});
    s.on('message', d => fin({ ok: true, banner: d.toString('latin1').slice(0, 240) }));
    s.on('error', () => fin({ ok: false, banner: '' }));
    setTimeout(() => fin({ ok: false, banner: '' }), timeout);
  });
}

// ---- NUEVO: SSH banner grabbing ----
function sshBanner(ip, port = 22, timeout = 2500) {
  return new Promise(res => {
    const s = net.createConnection({ host: ip, port }); let buf = '', done = false;
    const fin = o => { if (done) return; done = true; s.destroy(); res(o); };
    s.setTimeout(timeout);
    s.on('connect', () => { /* SSH server envia banner primero */ });
    s.on('data', d => { buf += d.toString('latin1'); if (/SSH-/.test(buf)) fin({ ok: true, banner: buf.trim().slice(0, 120) }); });
    s.on('timeout', () => fin({ ok: /SSH-/.test(buf), banner: buf.trim().slice(0, 120) }));
    s.on('error', () => fin({ ok: false, banner: '' }));
  });
}

// ---- NUEVO: FTP banner grabbing ----
function ftpBanner(ip, port = 21, timeout = 2500) {
  return new Promise(res => {
    const s = net.createConnection({ host: ip, port }); let buf = '', done = false;
    const fin = o => { if (done) return; done = true; s.destroy(); res(o); };
    s.setTimeout(timeout);
    s.on('data', d => { buf += d.toString('latin1'); if (/220|421/.test(buf)) fin({ ok: true, banner: buf.trim().slice(0, 200) }); });
    s.on('timeout', () => fin({ ok: buf.length > 0, banner: buf.trim().slice(0, 200) }));
    s.on('error', () => fin({ ok: false, banner: '' }));
  });
}

// ---- NUEVO: Telnet banner ----
function telnetBanner(ip, port = 23, timeout = 2500) {
  return new Promise(res => {
    const s = net.createConnection({ host: ip, port }); let buf = '', done = false;
    const fin = o => { if (done) return; done = true; s.destroy(); res(o); };
    s.setTimeout(timeout);
    s.on('data', d => { buf += d.toString('latin1'); if (buf.length > 20) fin({ ok: true, banner: buf.replace(/\xff[\xfb-\xfe]./g, '').trim().slice(0, 200) }); });
    s.on('timeout', () => fin({ ok: buf.length > 0, banner: buf.replace(/\xff[\xfb-\xfe]./g, '').trim().slice(0, 200) }));
    s.on('error', () => fin({ ok: false, banner: '' }));
  });
}

// ---- NUEVO: UPnP/SSDP discovery (UDP multicast) ----
function ssdpDiscover(timeout = 3000) {
  return new Promise(res => {
    const s = dgram.createSocket('udp4'); const devices = []; let done = false;
    const fin = () => { if (done) return; done = true; try { s.close(); } catch {} res(devices); };
    const msg = 'M-SEARCH * HTTP/1.1\r\nHOST: 239.255.255.250:1900\r\nMAN: "ssdp:discover"\r\nMX: 2\r\nST: ssdp:all\r\n\r\n';
    s.bind(0, () => {
      s.setBroadcast(true);
      s.send(msg, 1900, '239.255.255.250', () => {});
    });
    s.on('message', (d, r) => {
      const text = d.toString('latin1');
      const loc = /LOCATION: (.+)/i.exec(text);
      const st = /ST: (.+)/i.exec(text);
      const server = /SERVER: (.+)/i.exec(text);
      devices.push({ ip: r.address, location: loc?.[1]?.trim() || null, st: st?.[1]?.trim() || null, server: server?.[1]?.trim() || null });
    });
    s.on('error', () => fin());
    setTimeout(fin, timeout);
  });
}

// ---- Service detection por puerto + banner ----
function detectService(port, banner) {
  const h = (banner || '').toLowerCase();
  if (port === 22 || /ssh-/.test(h)) return 'SSH';
  if (port === 21 || /ftp|vsftpd|proftpd|filezilla/.test(h)) return 'FTP';
  if (port === 23) return 'Telnet';
  if (port === 25 || /smtp|postfix|exim|sendmail/.test(h)) return 'SMTP';
  if (port === 53) return 'DNS';
  if (port === 80 || port === 8080 || port === 8000 || port === 8888 || port === 9000) return 'HTTP';
  if (port === 443 || port === 8443) return 'HTTPS';
  if (port === 110 || /pop3|dovecot/.test(h)) return 'POP3';
  if (port === 143 || /imap|dovecot/.test(h)) return 'IMAP';
  if (port === 161 || port === 162) return 'SNMP';
  if (port === 389) return 'LDAP';
  if (port === 443 || port === 8443) return 'HTTPS';
  if (port === 5060 || port === 5061) return 'SIP';
  if (port === 554) return 'RTSP';
  if (port === 1433 || /mssql|sql.?server/.test(h)) return 'MSSQL';
  if (port === 3306 || /mysql|mariadb/.test(h)) return 'MySQL';
  if (port === 5432 || /postgres/.test(h)) return 'PostgreSQL';
  if (port === 6379 || /redis/.test(h)) return 'Redis';
  if (port === 27017 || /mongodb/.test(h)) return 'MongoDB';
  if (port === 9200 || /elasticsearch/.test(h)) return 'Elasticsearch';
  if (port === 11211 || /memcached/.test(h)) return 'Memcached';
  if (port === 3389) return 'RDP';
  if (port === 37777) return 'Dahua DVR';
  if (port === 3702) return 'ONVIF/WS-Discovery';
  return 'unknown';
}

function guessVendor(banner, headers, body) {
  const hay = `${banner} ${JSON.stringify(headers || {})} ${body || ''}`.toLowerCase();
  if (/hikvision|isapi/.test(hay)) return 'Hikvision';
  if (/dahua|magicbox/.test(hay)) return 'Dahua';
  if (/axis|vapix/.test(hay)) return 'Axis';
  if (/gsoap|onvif/.test(hay)) return 'ONVIF';
  if (/uniview|univ/.test(hay)) return 'Uniview';
  if (/vivotek/.test(hay)) return 'Vivotek';
  if (/foscam/.test(hay)) return 'Foscam';
  if (/asterisk|freeswitch|grandstream|yealink|cisco-sip/.test(hay)) return 'VoIP/SIP';
  if (/icy-|icecast|shoutcast|server:\s*icy/.test(hay)) return 'Radio IP (stream)';
  if (/openssh|dropbear/.test(hay)) return 'SSH server';
  if (/vsftpd|proftpd|pure-ftpd|filezilla/.test(hay)) return 'FTP server';
  if (/nginx|apache|lighttpd|iis|caddy/.test(hay)) return 'Web server';
  return null;
}

// ---- Scan completo de un IP ----
async function scan(ip, opts = {}) {
  const ports = opts.ports || (opts.fast ? FAST_PORTS : ALL_PORTS);
  const evidence = [];
  let type = 'unknown', vendor = null;

  // TCP port scan en paralelo
  const tcp = await Promise.all(ports.map(async p => {
    const r = await tcpProbe(ip, p);
    return { p, r };
  }));

  for (const { p, r } of tcp) {
    if (r.open) {
      const svc = detectService(p, r.banner);
      evidence.push({ port: p, proto: 'tcp', service: svc, banner: r.banner.trim().slice(0, 256) });
    }
  }

  // RTSP
  const rtsp = await rtspOptions(ip);
  if (rtsp.ok) { evidence.push({ port: 554, proto: 'rtsp', banner: rtsp.banner.slice(0, 200) }); type = 'camera'; }

  // SIP
  const sip = await sipOptions(ip);
  if (sip.ok) { evidence.push({ port: 5060, proto: 'sip/udp', banner: sip.banner.slice(0, 200) }); if (type === 'unknown') type = 'radio/voip'; }

  // SSH banner grabbing en puertos abiertos
  for (const e of evidence) {
    if (e.port === 22 || e.service === 'SSH') {
      const ssh = await sshBanner(ip, e.port);
      if (ssh.ok) { e.banner = ssh.banner; e.detail = ssh.banner; }
    }
    if (e.port === 21 || e.service === 'FTP') {
      const ftp = await ftpBanner(ip, e.port);
      if (ftp.ok) { e.banner = ftp.banner; e.detail = ftp.banner; }
    }
    if (e.port === 23 || e.service === 'Telnet') {
      const tel = await telnetBanner(ip, e.port);
      if (tel.ok) { e.banner = tel.banner; e.detail = tel.banner; }
    }
  }

  // HTTP camera fingerprinting
  const httpPort = tcp.find(x => x.r.open && [80, 8080, 8000, 8001, 8088, 8888].includes(x.p));
  if (httpPort) {
    for (const c of CAM_PATHS) {
      const r = await httpGet(ip, httpPort.p, c.p);
      if (r && r.status && r.status < 500) {
        evidence.push({ port: httpPort.p, proto: 'http', path: c.p, status: r.status, vendor_hint: c.v, service: 'HTTP' });
        const gv = guessVendor('', r.headers, r.body);
        if (gv) { vendor = gv; type = /radio|stream/i.test(gv) ? 'radio' : /sip|voip/i.test(gv) ? 'radio/voip' : 'camera'; }
        else if (!vendor) vendor = c.v;
        if (type === 'unknown') type = 'camera';
        break;
      }
    }
    if (type === 'unknown') {
      const root = await httpGet(ip, httpPort.p, '/');
      const gv = guessVendor('', root && root.headers, root && root.body);
      if (gv) { vendor = gv; type = /radio|stream/i.test(gv) ? 'radio' : 'camera'; evidence.push({ port: httpPort.p, proto: 'http', path: '/', status: root?.status, vendor_hint: gv, service: 'HTTP' }); }
      // Server header fingerprinting
      if (root?.headers?.server) {
        evidence.push({ port: httpPort.p, proto: 'http', path: '/', detail: `Server: ${root.headers.server}`, service: 'HTTP' });
        const sv = guessVendor('', { server: root.headers.server }, '');
        if (sv && !vendor) vendor = sv;
      }
    }
  }

  // HTTPS fingerprinting
  const httpsPort = tcp.find(x => x.r.open && [443, 8443].includes(x.p));
  if (httpsPort) {
    const r = await httpGet(ip, httpsPort.p, '/');
    if (r && r.status) {
      evidence.push({ port: httpsPort.p, proto: 'https', status: r.status, service: 'HTTPS', detail: r.headers?.server ? `Server: ${r.headers.server}` : null });
    }
  }

  if (!vendor) for (const e of evidence) {
    const g = guessVendor(e.banner || '', null, null);
    if (g) { vendor = g; if (type === 'unknown') type = /radio|stream|sip|voip/i.test(g) ? 'radio/voip' : 'camera'; break; }
  }

  const ports_open = evidence.map(e => `${e.port}/${e.proto}`);
  const services = [...new Set(evidence.map(e => e.service).filter(Boolean))];

  return {
    ip, type, vendor, ports_open, services,
    evidence,
    summary: type === 'unknown'
      ? `host con ${evidence.length} puerto(s) abierto(s): ${services.join(', ') || 'sin identificar'}`
      : `${type}${vendor ? ' · ' + vendor : ''} · ${services.join(', ')}`
  };
}

async function scanMany(ips, conc = 12, opts = {}) {
  const out = []; let i = 0;
  const workers = Array.from({ length: conc }, async () => { while (i < ips.length) { const ip = ips[i++]; out.push(await scan(ip, opts)); } });
  await Promise.all(workers); return out;
}

// ---- login-audit DEFENSIVO con Basic + Digest reales ----
const DEFAULTS = [['admin', 'admin'], ['admin', '12345']];
async function loginAudit(ip, user, pass, port = 80) {
  const out = { ip, user, tests: [] };
  for (const p of [port, port === 80 ? 443 : 8443]) {
    const r = await httpAuthAny(ip, p, '/ISAPI/System/deviceInfo', user, pass);
    const tls = (p === 443 || p === 8443);
    out.tests.push({ port: p, tls, scheme: r.scheme, status: r.status,
      cleartext: !tls && r.status > 0,
      deviceInfo: r.status === 200 ? (r.body.match(/<modelName>[^<]*<\/modelName>/i) || [])[0] || null : null,
      www: r.www || null });
    if (r.status === 200) { out.working = { port: p, tls, scheme: r.scheme }; break; }
  }
  out.defaultCreds = null;
  if (!out.working) {
    for (const [du, dp] of DEFAULTS) {
      const r = await httpAuthAny(ip, port, '/ISAPI/System/deviceInfo', du, dp);
      if (r.status === 200) { out.defaultCreds = { user: du, pass: dp || '(vacia)', scheme: r.scheme, cleartext: port !== 443 }; break; }
    }
  }
  const clear = out.tests.some(t => t.cleartext) || (out.defaultCreds && out.defaultCreds.cleartext);
  out.verdict = out.defaultCreds ? `CRITICO: acepta credenciales por defecto (${out.defaultCreds.scheme})`
    : clear ? 'ALTO: autenticacion viaja en claro (HTTP)'
    : out.working ? `OK: auth sobre ${out.working.tls ? 'TLS' : 'HTTP'} via ${out.working.scheme}`
    : 'sin acceso (credenciales incorrectas, o el dispositivo no expone ISAPI/web)';
  return out;
}

module.exports = { scan, scanMany, loginAudit, sshBanner, ftpBanner, telnetBanner, ssdpDiscover, detectService };
