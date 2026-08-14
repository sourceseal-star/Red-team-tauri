#!/usr/bin/env node
/**
 * SealCtl — Console REST API Server v2.0
 * Node.js stdlib only — sin dependencias npm. Termux-compatible.
 * Endpoints: /api/health, /api/geo, /api/intel, /api/iot, /api/full,
 *            /api/scan-batch, /api/stream, /api/scan/network,
 *            /api/scan/network/stream, /api/scan/cameras,
 *            /api/forensics/analyze, /api/forensics/tools, /api/forensics/patterns
 */
const http = require('http');
const https = require('https');
const fs = require('fs');
const path = require('path');
const net = require('net');
const url = require('url');
const crypto = require('crypto');
const { lookup, isPrivate } = require('./lib/geo');
const { assess } = require('./lib/intel');
const { scan, scanMany, tcpProbe, rtspOptions, guessVendor } = require('./lib/iot');

const PORT = process.env.SEALCTL_PORT || 8001;
const PUBLIC_DIR = path.join(__dirname, 'public');
const EVIDENCE_DIR = path.join(__dirname, '..', 'evidence');
const MAX_UPLOAD = 50 * 1024 * 1024;
fs.mkdirSync(EVIDENCE_DIR, { recursive: true });

// ─── helpers ─────────────────────────────────────────────────────────────────
function cors(res){res.setHeader('Access-Control-Allow-Origin','*');res.setHeader('Access-Control-Allow-Methods','GET,POST,OPTIONS');res.setHeader('Access-Control-Allow-Headers','Content-Type,X-Api-Key');}
function json(res,code,data){cors(res);res.writeHead(code,{'Content-Type':'application/json;charset=utf-8'});res.end(JSON.stringify(data,null,2));}
function parseBody(req,maxLen=1e6){return new Promise(r=>{let b='';req.on('data',d=>{b+=d;if(b.length>maxLen)req.destroy();});req.on('end',()=>{try{r(JSON.parse(b||'{}'))}catch{r({})}});req.on('error',()=>r({}));});}
function validateTarget(t){if(!t)return 'target requerido';const m=t.match(/^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})(\/(\d{1,2}))?$/);if(!m)return `'${t}' no es IP/subred valida`;for(let i=1;i<=4;i++)if(parseInt(m[i])>255)return `Octeto ${i} fuera de rango`;if(m[6]&&parseInt(m[6])<16)return 'Minimo /16';return null;}
function getBaseIP(s){return s.replace(/\/\d+$/,'').split('.').slice(0,3).join('.');}

// ─── network scan ────────────────────────────────────────────────────────────
const SCAN_PORTS=[22,23,80,443,554,1883,3389,5060,7547,8000,8080,8081,8443,37777,8554];

async function scanHostQuick(ip){
  const openPorts=[];
  await Promise.all(SCAN_PORTS.map(async p=>{
    const r=await tcpProbe(ip,p,1000);
    if(r.open)openPorts.push({port:p,banner:(r.banner||'').trim()});
  }));
  if(openPorts.length===0)return{ip,status:'down',open_ports:[]};
  const pn=openPorts.map(p=>p.port);
  let type='device',vendor=null;
  if(pn.includes(554))type='camera';
  else if(pn.includes(1883))type='iot';
  else if(pn.includes(5060))type='voip';
  else if(pn.includes(22)&&pn.includes(80))type='router';
  else if(pn.includes(80)||pn.includes(8080))type='web';
  else if(pn.includes(3389))type='windows';
  for(const p of openPorts){const g=guessVendor(p.banner,null,null);if(g){vendor=g;break;}}
  return{ip,status:'up',type,vendor,open_ports:pn,ports_detail:openPorts,hint:vendor?`${type} · ${vendor}`:type};
}

// ─── camera deep scan ────────────────────────────────────────────────────────
async function cameraDeepScan(ip){
  const iotResult=await scan(ip);
  const geo=isPrivate(ip)?{ip,private:true}:await lookup(ip);
  return{ip,timestamp:new Date().toISOString(),type:iotResult.type,vendor:iotResult.vendor,
    ports_open:iotResult.ports_open,evidence:iotResult.evidence,
    rtsp_detected:iotResult.evidence.some(e=>e.proto==='rtsp'),geolocation:geo,summary:iotResult.summary};
}

// ─── forensics ───────────────────────────────────────────────────────────────
const IOC_PATTERNS={
  email:/[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/g,
  url:/https?:\/\/[^\s<>"']+/g,
  ipv4:/\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d{1,2})\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d{1,2})\b/g,
  jwt:/eyJ[a-zA-Z0-9_-]+\.eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+/g,
  aws_key:/AKIA[0-9A-Z]{16}/g,
  github_pat:/gh[pousr]_[A-Za-z0-9]{36}/g,
  openai_key:/sk-[a-zA-Z0-9]{48}/g,
  btc_wallet:/\b(bc1[a-z0-9]{39,59}|[13][a-km-zA-HJ-NP-Z1-9]{25,34})\b/g,
  base64_susp:/[A-Za-z0-9+/]{40,}={0,2}/g,
  win_path:/[A-Z]:\\(?:Users|Windows|Program Files|ProgramData)\\[^\s]+/g
};
function shannonEntropy(data){if(!data||data.length===0)return 0;const f={};for(const b of data)f[b]=(f[b]||0)+1;const t=data.length;let e=0;for(const c of Object.values(f)){const p=c/t;if(p>0)e-=p*Math.log2(p);}return e;}
function extractIOCs(text){const r={};for(const[n,p]of Object.entries(IOC_PATTERNS)){const m=text.match(p);if(m&&m.length>0)r[n]=[...new Set(m)];}return r;}

// ─── server ──────────────────────────────────────────────────────────────────
const server=http.createServer(async(req,res)=>{
  const u=url.parse(req.url,true);const p=u.pathname;
  if(req.method==='OPTIONS'){cors(res);res.writeHead(204);res.end();return;}

  // static
  if(req.method==='GET'&&(p==='/'||p==='/index.html')){
    const f=path.join(PUBLIC_DIR,'index.html');
    if(fs.existsSync(f)){cors(res);res.writeHead(200,{'Content-Type':'text/html;charset=utf-8'});fs.createReadStream(f).pipe(res);return;}
    json(res,404,{error:'index.html no encontrado'});return;
  }

  // health
  if(req.method==='GET'&&p==='/api/health')return json(res,200,{status:'ok',version:'2.0.0',timestamp:new Date().toISOString(),port:PORT,modules:['geo','intel','iot','network-scan','camera-deep','forensics']});

  // geo
  if(req.method==='GET'&&p==='/api/geo'){const ip=u.query.ip;if(!ip)return json(res,400,{error:'?ip= requerido'});return json(res,200,await lookup(ip));}

  // intel
  if(req.method==='GET'&&p==='/api/intel'){const ip=u.query.ip;if(!ip)return json(res,400,{error:'?ip= requerido'});return json(res,200,await assess(ip));}

  // iot
  if(req.method==='GET'&&p==='/api/iot'){const ip=u.query.ip;if(!ip)return json(res,400,{error:'?ip= requerido'});return json(res,200,await scan(ip));}

  // full
  if(req.method==='GET'&&p==='/api/full'){const ip=u.query.ip;if(!ip)return json(res,400,{error:'?ip= requerido'});const[g,i,t]=await Promise.all([lookup(ip),assess(ip),scan(ip)]);return json(res,200,{ip,geo:g,intel:i,iot:t});}

  // scan-batch
  if(req.method==='POST'&&p==='/api/scan-batch'){const b=await parseBody(req);const ips=Array.isArray(b.ips)?b.ips.filter(x=>typeof x==='string'):[];if(!ips.length)return json(res,400,{error:'{ips:[...]} requerido'});return json(res,200,{total:ips.length,results:await scanMany(ips,b.concurrency||10)});}

  // ═══ NUEVO: scan/network ═══
  if(req.method==='POST'&&p==='/api/scan/network'){const b=await parseBody(req);const s=b.subnet||b.target||'';const err=validateTarget(s);if(err)return json(res,400,{error:err});const fs24=s.includes('/')?s:s.replace(/\.\d+$/,'.0/24');const base=getBaseIP(fs24);const results=[];const promises=[];for(let i=1;i<=254;i++){promises.push(scanHostQuick(`${base}.${i}`));}const all=await Promise.allSettled(promises);for(const r of all)if(r.status==='fulfilled'&&r.value&&r.value.open_ports.length>0)results.push(r.value);return json(res,200,{subnet:fs24,timestamp:new Date().toISOString(),hosts_scanned:254,hosts_up:results.length,hosts:results});}

  // ═══ NUEVO: scan/network/stream (SSE) ═══
  if(req.method==='GET'&&p==='/api/scan/network/stream'){const s=u.query.subnet||u.query.target||'';const err=validateTarget(s);if(err)return json(res,400,{error:err});const fs24=s.includes('/')?s:s.replace(/\.\d+$/,'.0/24');const base=getBaseIP(fs24);cors(res);res.writeHead(200,{'Content-Type':'text/event-stream','Cache-Control':'no-cache','Connection':'keep-alive'});const send=(ev,d)=>{res.write(`event: ${ev}\n`);res.write(`data: ${JSON.stringify(d)}\n\n`);};send('start',{subnet:fs24,total:254,timestamp:new Date().toISOString()});let found=0,scanned=0;const BATCH=20;for(let batch=0;batch<254;batch+=BATCH){const ps=[];for(let i=batch+1;i<=Math.min(batch+BATCH,254);i++){const ip=`${base}.${i}`;ps.push(scanHostQuick(ip).then(r=>{scanned++;if(r.open_ports.length>0){found++;send('host',r);}if(scanned%10===0)send('progress',{scanned,total:254,found});}));}await Promise.all(ps);}send('done',{subnet:fs24,scanned:254,found,timestamp:new Date().toISOString()});res.end();return;}

  // ═══ NUEVO: scan/cameras ═══
  if(req.method==='GET'&&p==='/api/scan/cameras'){const ip=u.query.ip;if(!ip)return json(res,400,{error:'?ip= requerido'});const err=validateTarget(ip);if(err)return json(res,400,{error:err});return json(res,200,await cameraDeepScan(ip));}

  // ═══ NUEVO: forensics/analyze ═══
  if(req.method==='POST'&&p==='/api/forensics/analyze'){
    const ct=req.headers['content-type']||'';if(!ct.includes('multipart/form-data'))return json(res,400,{error:'multipart/form-data requerido'});
    const boundary=ct.split('boundary=')[1];if(!boundary)return json(res,400,{error:'boundary no encontrado'});
    const chunks=[];let total=0;const tooBig=await new Promise(r=>{req.on('data',c=>{total+=c.length;if(total>MAX_UPLOAD){r(true);req.destroy();}chunks.push(c);});req.on('end',()=>r(false));req.on('error',()=>r(false));});
    if(tooBig)return json(res,413,{error:`Max ${MAX_UPLOAD/1024/1024}MB`});
    const buf=Buffer.concat(chunks);const bBuf=Buffer.from(`--${boundary}`);let start=0;let fileData=null,filename='upload';
    while(true){const bs=buf.indexOf(bBuf,start);if(bs===-1)break;const ns=buf.indexOf(bBuf,bs+bBuf.length);if(ns===-1)break;const part=buf.slice(bs+bBuf.length+2,ns-2);const ps=part.toString('latin1');const he=ps.indexOf('\r\n\r\n');if(he===-1){start=ns;continue;}const hdrs=ps.slice(0,he);const data=part.slice(he+4);const fm=hdrs.match(/filename="([^"]*)"/);if(fm&&fm[1]){filename=path.basename(fm[1]);fileData=data;break;}start=ns;}
    if(!fileData||fileData.length===0)return json(res,400,{error:'No se encontro archivo'});
    const id=`${Date.now()}-${Math.floor(Math.random()*9000+1000)}`;
    const sha256=crypto.createHash('sha256').update(fileData).digest('hex');
    const md5=crypto.createHash('md5').update(fileData).digest('hex');
    const entVals=[];for(let i=0;i<fileData.length;i+=65536){entVals.push(shannonEntropy(fileData.slice(i,i+65536)));}
    const avgE=entVals.reduce((a,b)=>a+b,0)/(entVals.length||1);const maxE=Math.max(...entVals,0);
    const gauge=avgE<4?'verde':avgE<7?'amarillo':'rojo';
    const txt=fileData.toString('utf-8');const iocs=extractIOCs(txt);const iocCount=Object.values(iocs).reduce((s,a)=>s+a.length,0);
    const result={analysis_id:id,filename,timestamp:new Date().toISOString(),file_size:fileData.length,hashes:{sha256,md5},entropy:{average:Math.round(avgE*1000)/1000,max:Math.round(maxE*1000)/1000,gauge,chunks:entVals.slice(0,20).map(e=>Math.round(e*100)/100)},iocs,ioc_count:iocCount,chain_of_custody:{analysis_id:id,filename,timestamp:new Date().toISOString(),protocol:'SSP-ZKP-2048-L4',sha256,file_size:fileData.length,collected_by:'sealctl-forensics-v2'}};
    fs.writeFileSync(path.join(EVIDENCE_DIR,`forensic_${id}.json`),JSON.stringify(result,null,2));
    return json(res,200,result);
  }

  if(req.method==='GET'&&p==='/api/forensics/tools')return json(res,200,{tools:{ioc_patterns:Object.keys(IOC_PATTERNS).length,entropy:'Shannon 0-8',hash:'SHA-256+MD5',chain_of_custody:'SSP-ZKP-2048-L4'},note:'Node.js stdlib — sin dependencias'});

  if(req.method==='GET'&&p==='/api/forensics/patterns'){const d={email:'Correos',url:'URLs HTTP/HTTPS',ipv4:'IPv4',jwt:'JWT',aws_key:'AWS Keys (AKIA...)',github_pat:'GitHub PATs (ghp_...)',openai_key:'OpenAI Keys (sk-...)',btc_wallet:'Bitcoin wallets',base64_susp:'Base64 sospechoso',win_path:'Rutas Windows'};return json(res,200,{patterns:Object.keys(IOC_PATTERNS).map(k=>({name:k,description:d[k]||k})),total:Object.keys(IOC_PATTERNS).length});}

  // stream (SSE single IP)
  if(req.method==='GET'&&p==='/api/stream'){const ip=u.query.ip;if(!ip)return json(res,400,{error:'?ip= requerido'});cors(res);res.writeHead(200,{'Content-Type':'text/event-stream','Cache-Control':'no-cache','Connection':'keep-alive'});const send=(ev,d)=>{res.write(`event: ${ev}\n`);res.write(`data: ${JSON.stringify(d)}\n\n`);};send('start',{ip,ts:Date.now()});send('geo',await lookup(ip));send('intel',await assess(ip));send('iot',await scan(ip));send('done',{ip,ts:Date.now()});res.end();return;}

  json(res,404,{error:`ruta no encontrada: ${p}`,routes:['GET /api/health','GET /api/geo?ip=X','GET /api/intel?ip=X','GET /api/iot?ip=X','GET /api/full?ip=X','POST /api/scan-batch','POST /api/scan/network','GET /api/scan/network/stream?subnet=X','GET /api/scan/cameras?ip=X','POST /api/forensics/analyze','GET /api/forensics/tools','GET /api/stream?ip=X']});
});

server.listen(PORT,'0.0.0.0',()=>{
  console.log('');
  console.log('  ╔══════════════════════════════════════════════╗');
  console.log('  ║  SealCtl Console v2.0 — puerto '+PORT+'          ║');
  console.log('  ║  http://localhost:'+PORT+'                        ║');
  console.log('  ╠══════════════════════════════════════════════╣');
  console.log('  ║  Modulos: geo · intel · iot · network-scan   ║');
  console.log('  ║          camera-deep · forensics             ║');
  console.log('  ╠══════════════════════════════════════════════╣');
  console.log('  ║  En tu celular abre:                         ║');
  console.log('  ║  http://TU_IP_LOCAL:'+PORT+'                  ║');
  console.log('  ╚══════════════════════════════════════════════╝');
  console.log('');
});
