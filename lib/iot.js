const net = require('net');
const dgram = require('dgram');
const http = require('http');

const CAM_PATHS = [
  { p: '/ISAPI/System/deviceInfo', v: 'Hikvision' },
  { p: '/cgi-bin/magicBox.cgi?action=getVendor', v: 'Dahua' },
  { p: '/axis-cgi/com/param.cgi', v: 'Axis' },
  { p: '/onvif/device_service', v: 'ONVIF' },
  { p: '/snapshot.cgi', v: 'cam-IP genérica' },
  { p: '/doc/page/index.asp', v: 'Hikvision (web)' },
];
const IOT_PORTS = [80, 443, 554, 3702, 8080, 8000, 8001, 8088, 37777, 5060];

function tcpProbe(ip, port, timeout = 1800) {
  return new Promise(res => {
    const s = net.createConnection({ host: ip, port });
    let done = false, banner = '';
    const fin = o => { if (done) return; done = true; s.destroy(); res(o); };
    s.setTimeout(timeout);
    s.on('connect', () => { banner = ''; fin({ open: true, banner: '' }); });
    s.on('data', d => { banner += d.toString('latin1'); if (banner.length > 240) fin({ open: true, banner }); });
    s.on('timeout', () => fin({ open: banner.length > 0, banner }));
    s.on('error', () => fin({ open: false, banner }));
  });
}

function httpGet(ip, port, path, timeout = 2200) {
  return new Promise(res => {
    const req = http.get({ host: ip, port, path, timeout, headers: { 'User-Agent': 'sealctl-iot/1.0' } }, r => {
      let b = ''; r.on('data', d => { b += d; if (b.length > 1200) r.destroy(); });
      const fin = () => res({ status: r.statusCode, headers: r.headers, body: b });
      r.on('end', fin); r.on('close', fin);
    });
    req.on('error', () => res(null)); req.on('timeout', () => { req.destroy(); res(null); });
  });
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

function guessVendor(banner, headers, body) {
  const hay = `${banner} ${JSON.stringify(headers || {})} ${body || ''}`.toLowerCase();
  if (/hikvision|isapi/.test(hay)) return 'Hikvision';
  if (/dahua|magicbox/.test(hay)) return 'Dahua';
  if (/axis|vapix/.test(hay)) return 'Axis';
  if (/gsoap|onvif/.test(hay)) return 'ONVIF';
  if (/uniview|univ/.test(hay)) return 'Uniview';
  if (/asterisk|freeswitch|grandstream|yealink|cisco-sip/.test(hay)) return 'VoIP/SIP';
  if (/icy-|icecast|shoutcast|server:\s*icy/.test(hay)) return 'Radio IP (stream)';
  return null;
}

async function scan(ip) {
  const evidence = []; let type = 'unknown', vendor = null;
  // 1) TCP abierto + banner en puertos IoT
  const tcp = await Promise.all(IOT_PORTS.filter(p => p !== 5060).map(async p => {
    const r = await tcpProbe(ip, p); if (r.open) evidence.push({ port: p, proto: 'tcp', banner: r.banner.trim() }); return { p, r };
  }));
  // 2) RTSP
  const rtsp = await rtspOptions(ip); if (rtsp.ok) { evidence.push({ port: 554, proto: 'rtsp', banner: rtsp.banner }); type = 'camera'; }
  // 3) SIP (radio/voip)
  const sip = await sipOptions(ip); if (sip.ok) { evidence.push({ port: 5060, proto: 'sip/udp', banner: sip.banner }); type = type === 'unknown' ? 'radio/voip' : type; }
  // 4) HTTP paths de cámara + fingerprint
  const httpPort = tcp.find(x => x.r.open && (x.p === 80 || x.p === 8080 || x.p === 8000));
  if (httpPort) {
    for (const c of CAM_PATHS) {
      const r = await httpGet(ip, httpPort.p, c.p);
      if (r && r.status && r.status < 500) {
        evidence.push({ port: httpPort.p, proto: 'http', path: c.p, status: r.status, vendor_hint: c.v });
        const gv = guessVendor('', r.headers, r.body);
        if (gv) { vendor = gv; if (/radio|stream/i.test(gv)) type = 'radio'; else if (/sip|voip/i.test(gv)) type = 'radio/voip'; else type = 'camera'; }
        else if (!vendor) vendor = c.v;
        if (type === 'unknown') type = 'camera';
        break;
      }
    }
    // radio: cabeceras ICY en la raíz
    if (type === 'unknown') {
      const root = await httpGet(ip, httpPort.p, '/');
      const gv = guessVendor('', root && root.headers, root && root.body);
      if (gv) { vendor = gv; type = /radio|stream/i.test(gv) ? 'radio' : 'camera'; evidence.push({ port: httpPort.p, proto: 'http', path: '/', status: root.status, vendor_hint: gv }); }
    }
  }
  // vendor por banner si aún no
  if (!vendor) for (const e of evidence) { const g = guessVendor(e.banner || '', null, null); if (g) { vendor = g; if (type === 'unknown') type = /radio|stream|sip|voip/i.test(g) ? 'radio/voip' : 'camera'; break; } }
  return { ip, type, vendor, ports_open: evidence.map(e => e.port + '/' + e.proto), evidence,
    summary: type === 'unknown' ? 'sin huella de cámara/radio' : `${type}${vendor ? ' · ' + vendor : ''}` };
}

// pool con concurrencia limitada
async function scanMany(ips, conc = 6) {
  const out = []; let i = 0;
  const workers = Array.from({ length: conc }, async () => {
    while (i < ips.length) { const ip = ips[i++]; out.push(await scan(ip)); }
  });
  await Promise.all(workers); return out;
}
module.exports = { scan, scanMany };


// ---- login-audit DEFENSIVO: credenciales TUYAS contra TUS dispositivos ----
// Devuelve si el auth viajó en claro, el deviceInfo si existe, y si acepta defaults.
const DEFAULTS = [['admin','admin'],['admin','12345'],['admin',''],['admin','password'],['root','root'],['admin','888888']];
function httpAuth(ip, port, path, user, pass, scheme='Basic', timeout=3000){
  return new Promise(res=>{
    const hdr={ 'User-Agent':'sealctl-audit/1.0' };
    if(scheme==='Basic') hdr['Authorization']='Basic '+Buffer.from(user+':'+pass).toString('base64');
    const proto = port===443||port===8443 ? require('https') : http;
    const req=proto.get({host:ip,port,path,timeout,headers:hdr,rejectUnauthorized:false},r=>{
      let b='';r.on('data',d=>{b+=d;if(b.length>2000)r.destroy()});
      const fin=()=>res({status:r.statusCode,headers:r.headers,body:b,www:r.headers['www-authenticate']||''});
      r.on('end',fin);r.on('close',fin);
    });
    req.on('error',e=>res({status:0,error:e.message}));req.on('timeout',()=>{req.destroy();res({status:0,error:'timeout'})});
  });
}
async function loginAudit(ip, user, pass, port=80){
  const out={ip,user,tests:[]};
  for(const p of [port, port===80?443:8443]){
    const r=await httpAuth(ip,p,'/ISAPI/System/deviceInfo',user,pass,'Basic');
    const tls=(p===443||p===8443);
    const ok=r.status===200;
    out.tests.push({port:p,tls,scheme:'Basic',status:r.status,cleartext:!tls&&r.status>0,
      deviceInfo: ok? (r.body.match(/<modelName>[^<]*<\/modelName>/i)||[])[0]||null : null,
      www: r.www||null});
    if(ok){out.working={port:p,tls};break}
  }
  out.defaultCreds=null;
  if(!out.working){
    for(const [du,dp] of DEFAULTS){
      const r=await httpAuth(ip,port,'/ISAPI/System/deviceInfo',du,dp,'Basic');
      if(r.status===200){out.defaultCreds={user:du,pass:dp||'(vacia)',cleartext:port!==443};break}
    }
  }
  const clear=out.tests.some(t=>t.cleartext)|| (out.defaultCreds&&out.defaultCreds.cleartext);
  out.verdict = out.defaultCreds ? 'CRITICO: acepta credenciales por defecto'
                : clear ? 'ALTO: autenticacion viaja en claro (HTTP)'
                : out.working ? 'OK: auth sobre TLS'
                : 'sin acceso (credenciales incorrectas o dispositivo sin web/ISAPI)';
  return out;
}
module.exports.loginAudit = loginAudit;