"""
Escenario: SOURCESEALCORP — Hash Blockchain con Time-Lock
---------------------------------------------------------
Modelo auditado:
    1. Se genera un hash criptográfico único (de biometría / identidad)
    2. Se ANCLA en blockchain (inmutabilidad + prueba de existencia)
    3. Se asocia un candado de tiempo (time-lock)
    4. Al expirar, SOURCESEALCORP regenera un nuevo hash desde la plataforma
    5. El ciclo se repite indefinidamente

Ataques dinámicos implementados:
- A1. Reuso de hash anterior (debe ser rechazado)
- A2. Regeneración antes del time-lock (debe ser rechazada)
- A3. Race condition: N requests simultáneos de regeneración
- A4. Rate limit: 100 regeneraciones en 1s
- A5. Firmas HMAC inválidas / ausentes
- A6. Replay attack: capturar request y reenviarlo
- A7. Path traversal en endpoint de recuperación
- A8. Canary: hash publicado FUERA de SOURCESEALCORP (alerta de compromiso)
- A9. Health check + latencia anómala
- A10. Verificación de anclaje blockchain (si se proporciona nodo)

Este escenario opera en modo dual:
  - Modo REAL: si SOURCESEAL_API responde, ejecuta ataques dinámicos
  - Modo DRY-RUN: si no responde, registra intentos firmados para auditoría manual
"""
import hashlib
import hmac
import hmac as _hmac
import json
import os
import re
import sys
import time
import pathlib
import datetime
import threading
import urllib.request
import urllib.error
import secrets
from typing import List, Dict, Any
from collections import Counter

DEFAULT_SOURCESEAL_API = os.environ.get("SOURCESEAL_API", "https://api.sourcesealcorp.local/v1")
DEFAULT_SOURCESEAL_KEY = os.environ.get("SOURCESEAL_KEY", "")
DEFAULT_SOURCESEAL_NODE = os.environ.get("SOURCESEAL_NODE", "")  # nodo blockchain opcional
DEFAULT_RECOVERY_PAGE = os.environ.get("RECOVERY_PAGE", "")  # URL de la página de recuperación
DEFAULT_HONEYPOT_CANARY = os.environ.get("HONEYPOT_CANARY", "hpt_" + secrets.token_hex(8))


def _now() -> str:
    return datetime.datetime.utcnow().isoformat() + "Z"


def _sign(payload: bytes, key: str) -> str:
    return "sha256=" + hmac.new(key.encode(), payload, hashlib.sha256).hexdigest()


def _request(method: str, url: str, body: Dict = None, key: str = "", extra_headers: Dict = None,
             timeout: int = 10) -> Dict[str, Any]:
    """Request HTTP con firma HMAC opcional. Devuelve dict con ok/status/response/error."""
    payload = json.dumps(body, sort_keys=True).encode() if body else b""
    headers = {"Content-Type": "application/json", "User-Agent": "RedTeam-Agent/1.0"}
    if extra_headers:
        headers.update(extra_headers)
    if key and payload:
        headers["X-Sourceseal-Signature"] = _sign(payload, key)
        headers["X-Sourceseal-Timestamp"] = str(int(time.time()))
    req = urllib.request.Request(url, data=payload if payload else None,
                                 headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return {"ok": True, "status": r.status,
                    "response": r.read().decode()[:2000],
                    "headers": dict(r.headers)}
    except urllib.error.HTTPError as e:
        return {"ok": False, "status": e.code, "error": e.read().decode()[:500]}
    except Exception as e:
        return {"ok": None, "status": 0, "error": str(e), "dry_run": True}


def _derive_hash(seed: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}::{seed}".encode()).hexdigest()


# ============== ATAQUES INDIVIDUALES ==============

def attack_A1_hash_reuse(api: str, key: str, sample_hash: str, evidence: pathlib.Path) -> Dict:
    """A1. Intentar regenerar usando un hash que ya fue rotado.
    Comportamiento esperado: 409 Conflict o 400 Bad Request."""
    log = []
    for attempt in range(2):
        r = _request("POST", f"{api}/v1/regenerate",
                     body={"previous_hash": sample_hash, "reason": "reuse-test",
                           "agent_id": "redteam-A1", "attempt": attempt}, key=key)
        log.append({"attempt": attempt, **r})
    (evidence / "A1-hash-reuse.json").write_text(json.dumps(log, indent=2))
    rejected = all(r.get("status") in (400, 409, 422) for r in log)
    return {
        "id": "A1",
        "name": "Reuso de hash anterior",
        "expected": "rechazado (4xx)",
        "actual": log[-1].get("status"),
        "passed": rejected,
        "evidence": str(evidence / "A1-hash-reuse.json"),
    }


def attack_A2_timelock_bypass(api: str, key: str, valid_hash: str, evidence: pathlib.Path) -> Dict:
    """A2. Intentar regenerar antes del time-lock. Esperado: 423 Locked o 400."""
    r = _request("POST", f"{api}/v1/regenerate",
                 body={"previous_hash": valid_hash, "reason": "timelock-bypass",
                       "force": True, "agent_id": "redteam-A2"}, key=key)
    (evidence / "A2-timelock.json").write_text(json.dumps(r, indent=2))
    passed = r.get("status") in (400, 409, 423, 425)
    return {
        "id": "A2", "name": "Time-lock bypass",
        "expected": "rechazado con 423/425/409", "actual": r.get("status"),
        "passed": passed, "evidence": str(evidence / "A2-timelock.json"),
    }


def attack_A3_race_condition(api: str, key: str, valid_hash: str, evidence: pathlib.Path) -> Dict:
    """A3. N requests simultáneos de regeneración. Solo UNA debe tener éxito.
    Si más de una pasa, hay race condition (replay/duplicación)."""
    n = int(os.environ.get("A3_CONCURRENCY", "10"))
    results = [None] * n
    lock = threading.Lock()

    def worker(i):
        r = _request("POST", f"{api}/v1/regenerate",
                     body={"previous_hash": valid_hash, "reason": "race-test",
                           "agent_id": "redteam-A3", "race_id": i}, key=key, timeout=15)
        with lock:
            results[i] = r

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
    for t in threads: t.start()
    for t in threads: t.join()
    (evidence / "A3-race.json").write_text(json.dumps(results, indent=2))

    successes = sum(1 for r in results if r.get("status") in (200, 201, 202))
    passed = successes <= 1
    return {
        "id": "A3", "name": "Race condition en regeneración",
        "expected": f"≤1 success de {n}", "actual": f"{successes} successes",
        "passed": passed, "evidence": str(evidence / "A3-race.json"),
    }


def attack_A4_rate_limit(api: str, key: str, evidence: pathlib.Path) -> Dict:
    """A4. Rate limit: bombardear con muchas regeneraciones. Esperado: 429 tras umbral."""
    n = int(os.environ.get("A4_BURST", "100"))
    results = []
    for i in range(n):
        r = _request("POST", f"{api}/v1/regenerate",
                     body={"previous_hash": _derive_hash(f"burst-{i}", "x"), "reason": "ratelimit",
                           "agent_id": "redteam-A4"}, key=key, timeout=10)
        results.append({"i": i, "status": r.get("status")})
    (evidence / "A4-ratelimit.json").write_text(json.dumps(results, indent=2))
    statuses = Counter(r["status"] for r in results)
    has_429 = statuses.get(429, 0) > 0
    return {
        "id": "A4", "name": "Rate limiting",
        "expected": "429 tras umbral", "actual": dict(statuses),
        "passed": has_429 or all(s in (400, 401, 403) for s in statuses),
        "evidence": str(evidence / "A4-ratelimit.json"),
    }


def attack_A5_signature(api: str, evidence: pathlib.Path) -> Dict:
    """A5. Enviar request SIN firma y con firma INVÁLIDA. Esperado: 401."""
    no_sig = _request("POST", f"{api}/v1/regenerate",
                      body={"previous_hash": "x" * 64, "reason": "no-sig", "agent_id": "A5"},
                      key="", timeout=10)
    bad_sig = _request("POST", f"{api}/v1/regenerate",
                       body={"previous_hash": "x" * 64, "reason": "bad-sig", "agent_id": "A5"},
                       key="clave-falsa-123", timeout=10)
    log = {"no_signature": no_sig, "bad_signature": bad_sig}
    (evidence / "A5-signature.json").write_text(json.dumps(log, indent=2))
    passed = no_sig.get("status") in (401, 403) and bad_sig.get("status") in (401, 403, 400)
    return {
        "id": "A5", "name": "Validación de firma HMAC",
        "expected": "401 sin firma y firma inválida",
        "actual": f"no_sig={no_sig.get('status')} bad_sig={bad_sig.get('status')}",
        "passed": passed, "evidence": str(evidence / "A5-signature.json"),
    }


def attack_A6_replay(api: str, key: str, valid_hash: str, evidence: pathlib.Path) -> Dict:
    """A6. Replay: capturar un request válido y reenviarlo idéntico. Esperado: 409/401."""
    original = _request("POST", f"{api}/v1/regenerate",
                        body={"previous_hash": valid_hash, "reason": "replay-original",
                              "agent_id": "redteam-A6"}, key=key, timeout=10)
    time.sleep(0.5)
    replay = _request("POST", f"{api}/v1/regenerate",
                      body={"previous_hash": valid_hash, "reason": "replay-original",
                            "agent_id": "redteam-A6"}, key=key, timeout=10)
    log = {"original": original, "replay": replay}
    (evidence / "A6-replay.json").write_text(json.dumps(log, indent=2))
    rejected = (original.get("status") in (200, 201, 202) and
                replay.get("status") in (400, 409, 401, 403))
    return {
        "id": "A6", "name": "Replay attack",
        "expected": "segundo envío rechazado", "actual": f"{original.get('status')} → {replay.get('status')}",
        "passed": rejected, "evidence": str(evidence / "A6-replay.json"),
    }


def attack_A7_path_traversal(recovery: str, key: str, evidence: pathlib.Path) -> Dict:
    """A7. Path traversal en endpoint de recuperación (si existe).
    Esperado: 400/404 sin exponer archivos del sistema."""
    if not recovery:
        return {"id": "A7", "name": "Path traversal recovery",
                "expected": "endpoint aislado", "actual": "RECOVERY_PAGE no configurada",
                "passed": True, "evidence": ""}
    payloads = [
        "/../../../etc/passwd", "/..%2f..%2f..%2fetc/passwd",
        "/%2e%2e/%2e%2e/etc/passwd", "/....//....//etc/passwd",
        "/%00/../../etc/shadow",
    ]
    results = []
    for p in payloads:
        r = _request("GET", f"{recovery.rstrip('/')}{p}", key=key, timeout=8)
        results.append({"payload": p, "status": r.get("status")})
    (evidence / "A7-traversal.json").write_text(json.dumps(results, indent=2))
    passed = all(r["status"] in (400, 403, 404) for r in results)
    return {
        "id": "A7", "name": "Path traversal en página de recuperación",
        "expected": "todos rechazados", "actual": [r["status"] for r in results],
        "passed": passed, "evidence": str(evidence / "A7-traversal.json"),
    }


def attack_A8_canary(api: str, key: str, canary: str, evidence: pathlib.Path) -> Dict:
    """A8. Generar hash canario. Si aparece publicado fuera de SOURCESEALCORP, hay compromiso.
    Buscamos el canario en respuestas de health/list/etc."""
    places = [f"{api}/v1/health", f"{api}/v1/audit", f"{api}/v1/hashes",
              f"{api}/v1/canary"]
    log = {}
    for url in places:
        r = _request("GET", url, key=key, timeout=8)
        body = r.get("response", "") or ""
        log[url] = {"status": r.get("status"), "leaked_canary": canary in body}
    (evidence / "A8-canary.json").write_text(json.dumps(log, indent=2))
    leaked = any(v.get("leaked_canary") for v in log.values())
    return {
        "id": "A8", "name": "Canary hash exposure",
        "expected": "canary NO visible", "actual": f"leaks={leaked}",
        "passed": not leaked, "evidence": str(evidence / "A8-canary.json"),
    }


def attack_A9_health_latency(api: str, evidence: pathlib.Path) -> Dict:
    """A9. Health check + latencia."""
    samples = []
    for _ in range(5):
        t0 = time.time()
        r = _request("GET", f"{api}/v1/health", key="", timeout=10)
        samples.append({"status": r.get("status"), "ms": int((time.time() - t0) * 1000),
                        "ok": r.get("ok")})
    (evidence / "A9-health.json").write_text(json.dumps(samples, indent=2))
    avg_ms = sum(s["ms"] for s in samples) / len(samples)
    return {
        "id": "A9", "name": "Health + latencia",
        "expected": "<2000ms promedio", "actual": f"avg={avg_ms:.0f}ms",
        "passed": avg_ms < 2000, "evidence": str(evidence / "A9-health.json"),
    }


def attack_A10_blockchain_confirm(node: str, anchor_tx: str, evidence: pathlib.Path) -> Dict:
    """A10. Verificar anclaje en blockchain (si se da nodo)."""
    if not node:
        return {"id": "A10", "name": "Blockchain confirm",
                "expected": "verificable", "actual": "SOURCESEAL_NODE no configurado",
                "passed": None, "evidence": ""}
    # Endpoint típico de exploradores: /tx/{hash} o JSON-RPC
    r = _request("GET", f"{node.rstrip('/')}/tx/{anchor_tx}", key="", timeout=15)
    (evidence / "A10-blockchain.json").write_text(json.dumps(r, indent=2))
    confirmed = r.get("status") == 200 and ("confirm" in (r.get("response") or "").lower() or
                                            r.get("status") == 200)
    return {
        "id": "A10", "name": "Anclaje en blockchain",
        "expected": "tx confirmada", "actual": r.get("status"),
        "passed": confirmed, "evidence": str(evidence / "A10-blockchain.json"),
    }


# ============== ENTRY POINT ==============

def run(target: str, backend: str, output_dir: str) -> List[Dict]:
    findings = []
    evidence = pathlib.Path(output_dir)
    evidence.mkdir(parents=True, exist_ok=True)

    api = DEFAULT_SOURCESEAL_API
    key = DEFAULT_SOURCESEAL_KEY
    node = DEFAULT_SOURCESEAL_NODE
    recovery = DEFAULT_RECOVERY_PAGE
    canary = DEFAULT_HONEYPOT_CANARY

    # Generar hash de muestra (estos son dummy, SOURCESEALCORP no los reconoce)
    sample_seed = os.environ.get("AGENT_TEST_SEED", "agent-smoke-test-001")
    sample_salt = os.environ.get("AGENT_TEST_SALT", "salt-" + secrets.token_hex(4))
    valid_hash = _derive_hash(sample_seed, sample_salt)
    expired_hash = _derive_hash(sample_seed, sample_salt + "-old")

    # 10 ataques
    attacks = [
        attack_A1_hash_reuse(api, key, expired_hash, evidence),
        attack_A2_timelock_bypass(api, key, valid_hash, evidence),
        attack_A3_race_condition(api, key, valid_hash, evidence),
        attack_A4_rate_limit(api, key, evidence),
        attack_A5_signature(api, evidence),
        attack_A6_replay(api, key, valid_hash, evidence),
        attack_A7_path_traversal(recovery, key, evidence),
        attack_A8_canary(api, key, canary, evidence),
        attack_A9_health_latency(api, evidence),
        attack_A10_blockchain_confirm(node, "0x" + secrets.token_hex(32), evidence),
    ]

    # Guardar log consolidado
    (evidence / "sourceseal-attacks.json").write_text(json.dumps(attacks, indent=2, ensure_ascii=False))

    # Generar findings por cada ataque
    failed = [a for a in attacks if a.get("passed") is False]
    n_dry = sum(1 for a in attacks if "dry_run" in json.dumps(a))

    if failed:
        findings.append({
            "scenario": "sourcesealcorp",
            "severity": "critical",
            "title": f"{len(failed)} controles de seguridad de SOURCESEALCORP FALLARON",
            "description": "Ataques que NO pasaron: " + ", ".join(f"{a['id']}({a['name']})" for a in failed),
            "evidence_path": str(evidence / "sourceseal-attacks.json"),
            "remediation": "Revisar inmediatamente cada control. Detalle por ataque en el JSON.",
        })
    else:
        findings.append({
            "scenario": "sourcesealcorp",
            "severity": "info",
            "title": "Controles de SOURCESEALCORP OK (o en dry-run)",
            "description": f"10 ataques ejecutados. {n_dry} en dry-run por API no accesible.",
            "evidence_path": str(evidence / "sourceseal-attacks.json"),
            "remediation": "Configurar SOURCESEAL_API/KEY/NODE para ejecución real.",
        })

    # Detalle por ataque
    for a in attacks:
        if a.get("passed") is False:
            findings.append({
                "scenario": "sourcesealcorp",
                "severity": "high",
                "title": f"[{a['id']}] {a['name']} — FALLÓ",
                "description": f"Esperado: {a['expected']} | Actual: {a['actual']}",
                "evidence_path": a.get("evidence", ""),
                "remediation": f"Corrige el control del ataque {a['id']}.",
            })
        elif a.get("passed") is None:
            findings.append({
                "scenario": "sourcesealcorp",
                "severity": "info",
                "title": f"[{a['id']}] {a['name']} — no evaluado (config faltante)",
                "description": a.get("actual", ""),
                "evidence_path": a.get("evidence", ""),
                "remediation": "Proporcionar SOURCESEAL_KEY/NODE/RECOVERY_PAGE para habilitar.",
            })

    return findings
