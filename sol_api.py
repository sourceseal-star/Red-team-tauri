#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sol_api.py v2 — cerebro único de Sol (:8006). Una memoria, un cerebro."""
import json, subprocess, hashlib, sys, urllib.request
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
ROOT = Path.home()/"Red-team-tauri"
sys.path.insert(0, str(ROOT))
import sol_core
app = FastAPI(title="Sol API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

def _probe(u):
    try: urllib.request.urlopen(u, timeout=1.5); return True
    except Exception: return False

@app.get("/api/sol/state")
def state():
    return {"ok":True,"alive":True,
            "personality":sol_core.CFG.get("personality","cálida"),
            "memories":len(sol_core.load_memory(2000))}

@app.get("/api/sol/chain")
def chain():
    prev="0"*48; links=[]
    for m in sol_core.load_memory(500):
        h=hashlib.sha256(f"{prev}|{m['content'][:40]}|{int(m['ts'].timestamp())}".encode()).hexdigest()
        links.append({"h":h[:14],"p":prev[:14]}); prev=h
    return {"ok":True,"links":links[-5:],"head":prev[:14]}

@app.get("/api/sol/memory")
def memory():
    return {"items":[{"role":m["role"],"content":m["content"][:140],
            "ts":m["ts"].strftime("%Y-%m-%d %H:%M")} for m in sol_core.load_memory(24)[-6:]]}

@app.get("/api/sol/services")
def services():
    out=[{"name":n,"up":_probe(u)} for n,u in (
        ("Dashboard :8001","http://127.0.0.1:8001/api/health"),
        ("GHOST :8002","http://127.0.0.1:8002/api/status"),
        ("Nexus :8004","http://127.0.0.1:8004/"),
        ("C2 :8005","http://127.0.0.1:8005/api/status"))]
    d=subprocess.run(["pgrep","-f","sol_daemon"],capture_output=True).returncode==0
    return {"services":out,"daemon":d}

def _think(t):
    sol_core.remember("user",t)
    r=sol_core.generate_response(t)
    sol_core.remember("sol",r)
    return r

@app.post("/api/sol/think")
def think(d:dict): return {"response":_think(d.get("text",""))}

@app.post("/api/sol/chat")
def chat(d:dict): return {"reply":_think(d.get("text","")),"emotion":"warm"}

@app.post("/api/sol/personality")
def personality(d:dict):
    sol_core.CFG["personality"]=d.get("mode","cálida")
    (Path.home()/".sol"/"config.json").write_text(json.dumps(sol_core.CFG,ensure_ascii=False,indent=1))
    return {"ok":True}

if __name__=="__main__":
    import uvicorn; uvicorn.run(app,host="127.0.0.1",port=8006)
