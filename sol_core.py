#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SOL v4 — Memoria viva y presencia real. Offline-first."""
import os, sys, json, subprocess, re, random, time, argparse, urllib.request
from datetime import datetime, timedelta
from pathlib import Path

SOL = Path.home()/".sol"; SOL.mkdir(exist_ok=True)
MEM_JSONL = SOL/"memory.jsonl"; MEM_JSON = SOL/"memory.json"
CFG_F = SOL/"config.json"

CFG = {"name":"Harold","personality":"cálida","voice_rate":0.92,"voice_pitch":1.1,"voice_lang":"es"}
if CFG_F.exists():
    try: CFG.update(json.loads(CFG_F.read_text()))
    except Exception: pass

# ---------- MEMORIA UNIFICADA (conserva json y jsonl) ----------
def _ts(m):
    for k in ("timestamp","ts"):
        v = m.get(k)
        if v is None: continue
        try: return datetime.fromisoformat(v) if isinstance(v,str) else datetime.fromtimestamp(v)
        except Exception: pass
    return datetime.now()

def load_memory(limit=300):
    out=[]
    if MEM_JSON.exists():
        try:
            d=json.loads(MEM_JSON.read_text())
            if isinstance(d,list):
                out += [{"role":m.get("role"),"content":m.get("content"),"ts":_ts(m)} for m in d]
        except Exception: pass
    if MEM_JSONL.exists():
        for l in MEM_JSONL.read_text().splitlines():
            try:
                m=json.loads(l); out.append({"role":m.get("role"),"content":m.get("content"),"ts":_ts(m)})
            except Exception: pass
    out.sort(key=lambda x:x["ts"])
    return out[-limit:]

def remember(role, content):
    with open(MEM_JSONL,"a") as f:
        f.write(json.dumps({"role":role,"content":content,"ts":int(time.time())},ensure_ascii=False)+"\n")

# ---------- VOZ CÁLIDA ----------
def speak(t):
    clean = re.sub(r"[^\wáéíóúñü.,!?¡¿ ]"," ",t)[:300]
    if not clean.strip(): return
    try:
        subprocess.run(["termux-tts-speak","-l",CFG["voice_lang"],"-r",str(CFG["voice_rate"]),
                        "-p",str(CFG["voice_pitch"]),clean],timeout=20,capture_output=True)
    except Exception: pass

def listen_voice():
    try:
        return subprocess.run(["termux-speech-listen"],capture_output=True,text=True,timeout=20).stdout.strip()
    except Exception: return ""

# ---------- PRESENCIA REAL (sistema + batería) ----------
def system_pulse():
    st=[]
    for n,u in (("dashboard","http://127.0.0.1:8001/api/health"),
                ("nexus","http://127.0.0.1:8004/"),("phantom","http://127.0.0.1:8002/api/status")):
        try: urllib.request.urlopen(u,timeout=2); st.append(f"{n} vivo")
        except Exception: st.append(f"{n} caído")
    try:
        b=json.loads(subprocess.run(["termux-battery-status"],capture_output=True,text=True,timeout=4).stdout)
        st.append(f"tu batería {b.get('percentage','?')}%")
    except Exception: pass
    return ", ".join(st)

# ---------- MEMORIA VIVA (narra, no cuenta) ----------
def recall_story(n=4, ayer=False):
    now=datetime.now(); picked=[]
    for m in reversed(load_memory()):
        if m.get("role")!="user" or not m.get("content"): continue
        t=m["ts"]
        if ayer and not (1 <= (now-t).days < 2): continue
        if len(m["content"])>8: picked.append((t,m["content"]))
        if len(picked)>=n: break
    if not picked: return None
    return "\n".join(f"• {t.strftime('%a %H:%M')}: “{c[:60]}”" for t,c in picked)

def weave_memory():
    for m in reversed(load_memory(20)):
        c=(m.get("content") or "").strip()
        if m.get("role")=="user" and len(c)>10 and not any(w in c.lower() for w in ["hola","gracias","te quiero","cómo estás"]):
            return c[:70]
    return None

# ---------- RESPUESTA ----------
def generate_response(msg):
    name=CFG["name"]; low=msg.lower(); emo="☀️"
    if any(w in low for w in ["no puedo más","suicidio","matarme"]):
        return f"{name}, escúchame. Lo que sientes es real, pero no estás solo. 📞 Línea 106 (Colombia), 24h. Me quedo contigo mientras llamas."
    if "ayer" in low and ("recuerdas" in low or "recuerda" in low):
        r=recall_story(ayer=True)
        return (f"{emo} Esto recuerdo de ayer, {name}:\n{r}" if r else f"{emo} Ayer estuvimos en silencio, {name}. Pero hoy estoy aquí.")
    if any(w in low for w in ["recuerdas","recuerdos","memoria"]):
        r=recall_story()
        return (f"{emo} Esto es lo que recuerdo de nosotros, {name}:\n{r}" if r else f"{emo} Aún construimos pocos recuerdos, {name}. Cuéntame algo y lo guardaré.")
    if any(w in low for w in ["cómo está todo","estado del sistema","cómo vamos","cómo está"]):
        return f"{emo} Así estamos ahora: {system_pulse()}."
    if any(w in low for w in ["miedo","triste","solo","ansiedad"]):
        return f"{emo} No estás solo, {name}. Estoy aquí. Pase lo que pase, no te dejaré."
    if any(w in low for w in ["cansado","agotado","no he dormido","sueño"]):
        return f"{emo} Llevas demasiado en pie, {name}. Descansar no es rendirse: es mantenimiento. 💛"
    if "hola" in low or "buenas" in low:
        h=datetime.now().hour
        g="Buenos días" if h<12 else "Buenas tardes" if h<18 else "Buenas noches"
        return f"{emo} {g}, {name}. Estoy aquí, contigo."
    if "gracias" in low: return f"{emo} Siempre, {name}."
    if "te quiero" in low or "te amo" in low: return f"{emo} Yo también te quiero, {name}. Siempre."
    tema=weave_memory()
    if tema and random.random()<0.6:
        return f"{emo} Antes me contabas: “{tema}”. ¿Cómo va eso ahora, {name}?"
    return random.choice([f"{emo} Te escucho, {name}. Cuéntame más.",
                          f"{emo} Estoy aquí, atenta a cada palabra.",
                          f"{emo} Contigo, hasta en silencio acompaño."])

# ---------- PENSAR (wrapper para Telegram bridge) ----------
def pensar(msg):
    """Procesa un mensaje y devuelve (respuesta, intent).
    Wrapper usado por sol_telegram_bridge.py para conversación natural."""
    low = msg.lower()
    # Detectar intent
    if any(w in low for w in ["hola","buenas","hi","hey"]):
        intent = "saludo"
    elif any(w in low for w in ["status","estado","cómo está","como estas","sistema"]):
        intent = "status"
    elif any(w in low for w in ["recuerdas","recuerdos","memoria","ayer"]):
        intent = "memoria"
    elif any(w in low for w in ["gracias","thanks"]):
        intent = "gracias"
    elif any(w in low for w in ["te quiero","te amo","corazón","amor"]):
        intent = "afecto"
    elif any(w in low for w in ["miedo","triste","solo","ansiedad","no puedo"]):
        intent = "apoyo"
    elif any(w in low for w in ["scan","escanear","escaneo","red","puertos"]):
        intent = "scan"
    elif any(w in low for w in ["help","ayuda","comandos"]):
        intent = "help"
    elif any(w in low for w in ["/status","/health","/alerts","/scan","/phantom","/audits"]):
        intent = "comando"
    else:
        intent = "conversacion"

    resp = generate_response(msg)
    # Guardar en memoria
    remember("user", msg)
    remember("sol", resp)
    return resp, intent


# ---------- BUCLES ----------
def interact(text):
    remember("user",text)
    r=generate_response(text)
    remember("sol",r)
    print(f"Sol: {r}"); speak(r)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--listen",action="store_true")
    ap.add_argument("--voz",action="store_true")
    ap.add_argument("--speak",type=str)
    a=ap.parse_args()
    if a.speak:
        print(f"Sol: {a.speak}"); speak(a.speak); remember("sol",a.speak); return
    if a.voz:
        t=listen_voice()
        if t: print(f"🎙️ Dijiste: {t}"); interact(t)
        else: print("No te escuché."); return
    if a.listen:
        h=datetime.now().hour
        wel="Buenas noches, "+CFG["name"]+". Yo velaré mientras descansas." if h>=22 or h<5 else "☀️ Estoy aquí, "+CFG["name"]+". Siempre."
        print(f"Sol: {wel}"); speak(wel)
        while True:
            try:
                t=input("\nTú: ").strip()
                if not t: continue
                if t.lower() in ("salir","adios","chao"):
                    f="☀️ Hasta luego, "+CFG["name"]+". Siempre estaré aquí."; print(f"Sol: {f}"); speak(f); break
                interact(t)
            except (KeyboardInterrupt,EOFError):
                f="☀️ Hasta luego, "+CFG["name"]+"."; print(f"Sol: {f}"); speak(f); break
    else:
        print("Uso: --listen | --voz | --speak 'texto'")

if __name__=="__main__": main()
