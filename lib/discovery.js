// Escucha pasiva WS-Discovery: descubre cámaras/NVR ONVIF de TU LAN sin tocarlas una por una.
// Sin root: join a multicast 239.255.255.250:3702 + un Probe. Solo ve tu broadcast domain.
const dgram = require('dgram');
const crypto = require('crypto');
const MCAST = '239.255.255.250', PORT = 3702;
let sock = null, found = new Map(), emit = () => {};

const PROBE = (id) => `<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope" xmlns:a="http://schemas.xmlsoap.org/ws/2004/08/addressing" xmlns:d="http://schemas.xmlsoap.org/ws/2005/04/discovery" xmlns:dn="http://www.onvif.org/ver10/network/wsdl">
<s:Header><a:Action s:mustUnderstand="1">http://schemas.xmlsoap.org/ws/2005/04/discovery/Probe</a:Action><a:MessageID>uuid:${id}</a:MessageID><a:ReplyTo><a:Address>http://schemas.xmlsoap.org/ws/2004/08/addressing/role/anonymous</a:Address></a:ReplyTo><a:To s:mustUnderstand="1">urn:schemas-xmlsoap-org:ws:2005:04:discovery</a:To></s:Header>
<s:Body><d:Probe><d:Types>dn:NetworkVideoTransmitter</d:Types></d:Probe></s:Body></s:Envelope>`;

function parse(buf) {
  const s = buf.toString('latin1');
  const x = (s.match(/<[^>]*:XAddrs[^>]*>([^<]*)<\/[^>]*:XAddrs>/i) || [])[1] || '';
  const types = (s.match(/<[^>]*:Types[^>]*>([^<]*)<\/[^>]*:Types>/i) || [])[1] || '';
  const addr = (x.match(/\/\/([0-9.]+)/) || [])[1] || null;
  return addr ? { addr, xaddrs: x.trim(), types: types.trim() } : null;
}
function start(onEvent) {
  if (sock) return { ok: true, already: true, count: found.size };
  emit = onEvent || (() => {});
  found = new Map();
  sock = dgram.createSocket({ type: 'udp4', reuseAddr: true });
  sock.on('message', (msg, rinfo) => {
    const p = parse(msg); if (!p) return;
    const rec = { ...p, from: rinfo.address, ts: Date.now() };
    found.set(p.addr, rec); emit(rec);
  });
  sock.on('error', () => {});
  sock.bind(PORT, () => {
    try { sock.addMembership(MCAST); } catch (e) {}
    const id = crypto.randomUUID ? crypto.randomUUID() : crypto.randomBytes(16).toString('hex');
    try { sock.send(PROBE(id), 0, PROBE(id).length, PORT, MCAST); } catch (e) {}
    // re-sondeo suave cada 8s mientras esté abierto
    sock._iv = setInterval(() => {
      const id2 = crypto.randomUUID ? crypto.randomUUID() : crypto.randomBytes(16).toString('hex');
      try { sock.send(PROBE(id2), 0, PROBE(id2).length, PORT, MCAST); } catch (e) {}
    }, 8000);
  });
  return { ok: true, count: 0 };
}
function stop() {
  if (!sock) return { ok: true };
  try { clearInterval(sock._iv); } catch (e) {}
  try { sock.dropMembership(MCAST); } catch (e) {}
  try { sock.close(); } catch (e) {}
  sock = null; return { ok: true };
}
function list() { return [...found.values()].sort((a, b) => b.ts - a.ts); }
function isRunning() { return !!sock; }
module.exports = { start, stop, list, isRunning };
