#!/usr/bin/env python3
"""
SOURCESEAL GLOBAL PROTOCOL — AUDITOR DE SEGURIDAD v3.0
=====================================================
Escanea múltiples repositorios en busca de vulnerabilidades
criptográficas, de validación, inyección y exposición de datos.

Protocolo: SSP-ZKP-2048-L4 | Nivel 4 — Nacional (SM3)

Detecta:
  Vector 1: Claves hardcodeadas (JS/TS)
  Vector 2: Actualizaciones sin firma (JS/TS)
  Vector 3: Falta de SSL Pinning (JS/TS)
  Vector 4: RNG débil (JS/TS)
  Vector 5: Exposición en memoria (JS/TS)
  Vector 6: Bypass validación IP (Python AST)
  Vector 7: Command injection (Python/JS/TS)
  Vector 8: Path traversal (Python/JS/TS)
  Vector 9: Secrets en código (Python/JS/TS)
  Vector 10: CORS wildcard (Python/JS/TS)

Uso:
  python3 source_seal_audit.py                    # escanea ~/Red-team-tauri/*
  python3 source_seal_audit.py /path/to/repos     # escanea directorio custom
  python3 source_seal_audit.py /path/to/repo      # escanea un solo repo
"""

import os
import ast
import sys
import re
import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone

# ═════════════════════════════════════════════════════════════════════════════
#  CONFIGURACIÓN
# ═════════════════════════════════════════════════════════════════════════════

EXCLUDE_DIRS = {
    "node_modules", "dist", ".git", ".next", "build", "coverage",
    ".cache", "__pycache__", "venv", ".venv", "env", ".env",
    "incoming_files", ".agents", "platform-docs",
}

SCAN_EXTENSIONS_PY = {".py"}
SCAN_EXTENSIONS_JS = {".ts", ".tsx", ".js", ".jsx", ".mjs"}
MAX_SNIPPET_LEN = 200
MAX_FILE_SIZE = 2 * 1024 * 1024  # 2MB

# ═════════════════════════════════════════════════════════════════════════════
#  PATRONES — VECTORES 1-5 (JS/TS)
# ═════════════════════════════════════════════════════════════════════════════

VECTOR_1_PATTERNS = [
    (r'(?:const|let|var)\s+\w*(?:SECRET|KEY|IV|SALT|NONCE|PASS(?:WORD)?)\w*\s*[:=]\s*["\']([0-9a-fA-F]{16,})["\']', "CRITICAL", "Clave criptográfica hardcodeada en hex"),
    (r'(?:const|let|var)\s+\w*(?:SECRET|KEY|IV|SALT|NONCE|PASS(?:WORD)?)\w*\s*[:=]\s*["\']([A-Za-z0-9+/=]{24,})["\']', "HIGH", "Posible clave/secret hardcodeado en base64"),
    (r'process\.env\[(["\'])\w+(?:SECRET|KEY|IV)\1\]\s*\?\?\s*["\']([0-9a-fA-F]{16,})["\']', "MEDIUM", "Secret con fallback hardcodeado"),
    (r'(?:const|let|var)\s+\w*IV\w*\s*[:=]\s*Buffer\.from\(["\']([0-9a-fA-F]{16,})', "CRITICAL", "IV hardcodeado en Buffer"),
    (r'create(?:Cipher|Decipher)(?:iv)?\(\s*["\']aes[^"\']+["\']\s*,\s*["\']([0-9a-fA-F]{16,})["\']', "CRITICAL", "Clave AES pasada como string"),
]

VECTOR_2_PATTERNS = [
    (r'createHash\(\s*["\']md5["\']', "HIGH", "MD5 usado para hash — vulnerable a colisiones"),
    (r'createHash\(\s*["\']sha1["\']', "MEDIUM", "SHA-1 para hash — débil para integridad"),
    (r'hash\s*===\s*expectedHash|hash\s*===\s*checksum|hash\s*===\s*fileHash', "MEDIUM", "Verificación solo con hash simétrico (sin firma asimétrica)"),
    (r'rejectUnauthorized\s*:\s*false', "HIGH", "rejectUnauthorized: false — acepta cualquier cert TLS"),
]

VECTOR_3_PATTERNS = [
    (r'NODE_TLS_REJECT_UNAUTHORIZED\s*=\s*["\']0["\']', "CRITICAL", "TLS validation deshabilitada globalmente"),
    (r'rejectUnauthorized\s*:\s*false', "HIGH", "Acepta certificados TLS no válidos"),
    (r'NODE_TLS_REJECT_UNAUTHORIZED', "MEDIUM", "Referencia a deshabilitación de TLS validation"),
    (r'https?\.get\s*\(\s*["\']https://', "LOW", "Petición HTTPS sin pinning explícito"),
]

VECTOR_4_PATTERNS = [
    (r'Math\.random\(\).*toString\(36\)|Math\.random\(\).*hex', "CRITICAL", "Math.random() para tokens — no criptográficamente seguro"),
    (r'Math\.random\(\)', "HIGH", "Math.random() — no usar para material criptográfico"),
    (r'Date\.now\(\).*toString\(36\)|new Date\(\)\.getTime\(\).*toString\(36\)', "CRITICAL", "Timestamp como token/nonce — predecible"),
    (r'uuid[/\.]v1\(\)|uuidv1\(\)', "HIGH", "UUID v1 basado en tiempo/MAC — predecible"),
    (r'jwt\.sign\(\s*[^,]+,\s*["\']([^"\']{1,15})["\']', "HIGH", "JWT firmado con secret corto o predecible"),
]

VECTOR_5_PATTERNS = [
    (r'(?:const)\s+\w*(?:SECRET|KEY|TOKEN|PASSWORD)\w*\s*[:=]\s*(?:process\.env\[[^\]]+\]|["\'][^"\']+["\'])', "MEDIUM", "Secret en const string — inmutable en heap"),
    (r'^(?:const|let)\s+\w*(?:SECRET|KEY|TOKEN)\w*\s*[:=]\s*process\.env', "MEDIUM", "Secret leído a nivel de módulo — persiste en memoria"),
    (r'Buffer\.from\(\s*[^,]+(?:secret|key|token|password)[^,]*', "MEDIUM", "Buffer con material sensible — verificar zeroization"),
]

# ═════════════════════════════════════════════════════════════════════════════
#  PATRONES — VECTORES 6-10 (Python + JS/TS)
# ═════════════════════════════════════════════════════════════════════════════

VECTOR_7_PATTERNS_PY = [
    (r'subprocess\.\w+\([^)]*shell\s*=\s*True', "HIGH", "subprocess con shell=True — riesgo de command injection"),
    (r'os\.system\(', "HIGH", "os.system() — sin sanitización de entrada"),
    (r'os\.popen\(', "HIGH", "os.popen() — sin sanitización de entrada"),
    (r'\beval\(', "CRITICAL", "eval() — ejecución arbitraria de código"),
    (r'\bexec\(', "CRITICAL", "exec() — ejecución arbitraria de código"),
]

VECTOR_7_PATTERNS_JS = [
    (r'child_process\.exec\(', "HIGH", "child_process.exec — shell injection risk"),
    (r'\beval\(', "CRITICAL", "eval() — ejecución arbitraria de código"),
    (r'new Function\(', "HIGH", "new Function() — eval dinámico"),
]

VECTOR_8_PATTERNS_PY = [
    (r'open\([^)]*\.\./', "HIGH", "open() con path relativo ../ — path traversal"),
    (r'Path\([^)]*\.\.', "MEDIUM", "Path() con .. — verificar sanitización"),
]

VECTOR_8_PATTERNS_JS = [
    (r'path\.join\([^)]*\.\.', "MEDIUM", "path.join con .. — verificar sanitización"),
    (r'path\.resolve\([^)]*\.\.', "MEDIUM", "path.resolve con .. — verificar sanitización"),
    (r'readFile(?:Sync)?\([^)]*\.\.', "HIGH", "readFile con path traversal"),
    (r'writeFile(?:Sync)?\([^)]*\.\.', "HIGH", "writeFile con path traversal"),
]

VECTOR_9_PATTERNS_PY = [
    (r'(?:SECRET|API_KEY|TOKEN|PASSWORD|PASSPHRASE)\s*=\s*["\']([0-9a-fA-F]{16,})["\']', "CRITICAL", "Secret criptográfico hardcodeado en Python"),
    (r'(?:SECRET|API_KEY|TOKEN|PASSWORD)\s*=\s*["\']([^"\']{12,})["\']', "HIGH", "Posible secret hardcodeado en Python"),
    (r'sk_live_[a-zA-Z0-9]{20,}', "CRITICAL", "Stripe live key hardcodeada"),
    (r'sk_test_[a-zA-Z0-9]{20,}', "MEDIUM", "Stripe test key hardcodeada"),
    (r'AKIA[A-Z0-9]{16}', "CRITICAL", "AWS Access Key ID hardcodeada"),
    (r'ghp_[a-zA-Z0-9]{36}', "CRITICAL", "GitHub Personal Access Token hardcodeada"),
]

VECTOR_10_PATTERNS = [
    (r'allow_origins\s*=\s*\[?\s*"\*"\s*\]?', "HIGH", "CORS wildcard — cualquier origen puede hacer peticiones"),
    (r'Access-Control-Allow-Origin.*\*', "HIGH", "CORS header wildcard en respuesta"),
    (r'origin\s*:\s*["\']\*["\']', "HIGH", "CORS origin wildcard"),
]

# ═════════════════════════════════════════════════════════════════════════════
#  UTILIDADES
# ═════════════════════════════════════════════════════════════════════════════

def should_scan(path: Path, extensions: set) -> bool:
    if any(part in EXCLUDE_DIRS for part in path.parts):
        return False
    if path.suffix not in extensions:
        return False
    try:
        if path.stat().st_size > MAX_FILE_SIZE:
            return False
    except OSError:
        return False
    return True

def get_commit_hash(repo_path: str) -> str:
    git_dir = os.path.join(repo_path, ".git")
    head_file = os.path.join(git_dir, "HEAD")
    try:
        with open(head_file) as f:
            ref = f.read().strip()
        if ref.startswith("ref: "):
            ref_path = os.path.join(git_dir, ref[5:])
            with open(ref_path) as f:
                return f.read().strip()[:12]
        return ref[:12]
    except Exception:
        return "unknown"

def get_recommendation(vector_id: int) -> str:
    return {
        1: "Usar Android Keystore / Windows CNG para derivación de claves basada en hardware.",
        2: "Implementar firma asimétrica (RSA/ECDSA) con verificación de CA raíz.",
        3: "Fijar hash del certificado público del servidor (SSL Pinning).",
        4: "Usar crypto.randomBytes (FIPS 140-2). Renovar tokens cortos con refresh rotativos.",
        5: "Zeroization: sobrescribir Buffers con fill(0) tras uso. Evitar strings inmutables.",
        6: "Usar ipaddress.ip_address() (Python) en vez de split+isdigit+all.",
        7: "Usar argumentos como lista (shell=False) y validar entradas. Nunca eval/exec.",
        8: "Validar path resuelto contra ROOT con resolve(). Rechazar ..",
        9: "Mover secrets a variables de entorno o vault. Nunca hardcodear en código.",
        10: "Especificar orígenes explícitos en CORS. Nunca usar wildcard con credentials.",
    }.get(vector_id, "")

# ═════════════════════════════════════════════════════════════════════════════
#  DETECCIÓN AST — Vector 6: Bypass validación IP (Python)
# ═════════════════════════════════════════════════════════════════════════════

def is_vulnerable_ip_function(node, source_lines):
    """Detecta el patrón vulnerable: all(x.isdigit() for x in ip.split('.'))
    El bug: si ningún part.isdigit(), all() sobre iterable vacío devuelve True."""
    if not isinstance(node, ast.FunctionDef):
        return False

    try:
        func_code = "\n".join(source_lines[node.lineno - 1: node.end_lineno])
    except (AttributeError, IndexError):
        func_code = source_lines[node.lineno - 1] if source_lines else ""

    has_split = ".split(" in func_code
    has_isdigit = ".isdigit()" in func_code
    has_all = "all(" in func_code
    has_ipaddress = "ip_address" in func_code or "ipaddress" in func_code

    return has_split and has_isdigit and has_all and not has_ipaddress


def scan_python_ast(filepath: str, rel_path: str) -> list:
    """Escanea Python con AST para detectar vulnerabilidades estructurales."""
    findings = []
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
            lines = content.splitlines()
    except Exception:
        return findings

    if not content.strip():
        return findings

    try:
        tree = ast.parse(content, filename=filepath)
    except SyntaxError:
        return findings

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            func_name = node.name.lower()
            if any(k in func_name for k in ("_valid_ip", "validate_ip", "is_valid_ip", "check_ip", "_is_ip")):
                if is_vulnerable_ip_function(node, lines):
                    findings.append({
                        "vectorId": 6,
                        "attackVector": "ip_validation_bypass",
                        "file": rel_path,
                        "line": node.lineno,
                        "severity": "CRITICAL",
                        "title": "Bypass en validacion IP: all() sobre isdigit() sin check de fallo",
                        "codeSnippet": lines[node.lineno - 1].strip()[:MAX_SNIPPET_LEN] if node.lineno <= len(lines) else "",
                        "exploitable": True,
                        "description": f"Funcion {node.name} usa split+isdigit+all() — all() devuelve True si ningun elemento pasa el filtro (bug logico). IP maliciosas bypass la validacion.",
                        "recommendation": get_recommendation(6),
                        "status": "open",
                        "mitigated": False,
                    })

    return findings

# ═════════════════════════════════════════════════════════════════════════════
#  ESCANEO POR ARCHIVO (regex)
# ═════════════════════════════════════════════════════════════════════════════

def scan_file_regex(filepath: str, rel_path: str, patterns, vector_id: int, vector_name: str) -> list:
    findings = []
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except Exception:
        return findings

    for i, line in enumerate(lines, 1):
        for pattern, severity, description in patterns:
            if re.search(pattern, line, re.IGNORECASE):
                snippet = line.strip()[:MAX_SNIPPET_LEN]
                findings.append({
                    "vectorId": vector_id,
                    "attackVector": vector_name,
                    "file": rel_path,
                    "line": i,
                    "severity": severity,
                    "title": description,
                    "codeSnippet": snippet,
                    "exploitable": severity in ("CRITICAL", "HIGH"),
                    "description": f"{description} en {rel_path}:{i}",
                    "recommendation": get_recommendation(vector_id),
                    "status": "open",
                    "mitigated": False,
                })
    return findings

# ═════════════════════════════════════════════════════════════════════════════
#  ESCANEO DE REPOSITORIO
# ═════════════════════════════════════════════════════════════════════════════

def scan_repository(repo_path: str) -> dict:
    repo = Path(repo_path)
    commit_hash = get_commit_hash(repo_path)
    all_findings = []
    files_scanned = 0
    scan_start = datetime.now(timezone.utc)

    for filepath in repo.rglob("*"):
        if not filepath.is_file():
            continue

        rel_path = str(filepath.relative_to(repo))

        # Python files
        if should_scan(filepath, SCAN_EXTENSIONS_PY):
            files_scanned += 1
            all_findings.extend(scan_python_ast(str(filepath), rel_path))
            all_findings.extend(scan_file_regex(str(filepath), rel_path, VECTOR_7_PATTERNS_PY, 7, "command_injection"))
            all_findings.extend(scan_file_regex(str(filepath), rel_path, VECTOR_8_PATTERNS_PY, 8, "path_traversal"))
            all_findings.extend(scan_file_regex(str(filepath), rel_path, VECTOR_9_PATTERNS_PY, 9, "hardcoded_secrets"))
            all_findings.extend(scan_file_regex(str(filepath), rel_path, VECTOR_10_PATTERNS, 10, "cors_wildcard"))

        # JS/TS files
        if should_scan(filepath, SCAN_EXTENSIONS_JS):
            files_scanned += 1
            all_findings.extend(scan_file_regex(str(filepath), rel_path, VECTOR_1_PATTERNS, 1, "hardcoded_keys"))
            all_findings.extend(scan_file_regex(str(filepath), rel_path, VECTOR_2_PATTERNS, 2, "unsigned_updates"))
            all_findings.extend(scan_file_regex(str(filepath), rel_path, VECTOR_3_PATTERNS, 3, "ssl_pinning"))
            all_findings.extend(scan_file_regex(str(filepath), rel_path, VECTOR_4_PATTERNS, 4, "weak_rng"))
            all_findings.extend(scan_file_regex(str(filepath), rel_path, VECTOR_5_PATTERNS, 5, "memory_exposure"))
            all_findings.extend(scan_file_regex(str(filepath), rel_path, VECTOR_7_PATTERNS_JS, 7, "command_injection"))
            all_findings.extend(scan_file_regex(str(filepath), rel_path, VECTOR_8_PATTERNS_JS, 8, "path_traversal"))
            all_findings.extend(scan_file_regex(str(filepath), rel_path, VECTOR_10_PATTERNS, 10, "cors_wildcard"))

    scan_end = datetime.now(timezone.utc)
    duration = (scan_end - scan_start).total_seconds()

    severity_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    vector_counts = {}
    for f in all_findings:
        sev = f["severity"]
        severity_counts[sev] = severity_counts.get(sev, 0) + 1
        vid = f["vectorId"]
        vector_counts[vid] = vector_counts.get(vid, 0) + 1

    return {
        "scanDate": scan_start.isoformat(),
        "commitHash": commit_hash,
        "filesScanned": files_scanned,
        "findingsCount": len(all_findings),
        "criticalCount": severity_counts["CRITICAL"],
        "highCount": severity_counts["HIGH"],
        "mediumCount": severity_counts["MEDIUM"],
        "lowCount": severity_counts["LOW"],
        "duration": round(duration, 2),
        "status": "completed",
        "findings": all_findings,
        "vectorSummary": vector_counts,
    }

# ═════════════════════════════════════════════════════════════════════════════
#  REPORTE EJECUTIVO
# ═════════════════════════════════════════════════════════════════════════════

def generate_report(repo_name: str, result: dict) -> str:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    total = result["findingsCount"]
    crit = result["criticalCount"]
    high = result["highCount"]
    med = result["mediumCount"]
    low = result["lowCount"]

    status = "VULNERABILIDADES DETECTADAS" if total > 0 else "SEGURO"
    status_icon = "[!]" if total > 0 else "[OK]"

    report = f"""
SOURCESEAL GLOBAL PROTOCOL — REPORTE DE AUDITORIA DE SEGURIDAD
================================================================
Protocolo: SSP-ZKP-2048-L4 | Nivel 4 — Nacional (SM3)
Fecha: {ts}
Estado: {status_icon} {status}

Repositorio: {repo_name}
Commit: {result['commitHash']}
Archivos escaneados: {result['filesScanned']}
Duracion: {result['duration']}s

RESUMEN DE HALLAZGOS:
  CRITICAL: {crit}
  HIGH:     {high}
  MEDIUM:   {med}
  LOW:      {low}
  TOTAL:    {total}

POR VECTOR DE ATAQUE:
"""

    vector_names = {
        1: "Claves hardcodeadas",
        2: "Updates sin firma",
        3: "Falta SSL Pinning",
        4: "RNG debil",
        5: "Exposicion en memoria",
        6: "Bypass validacion IP",
        7: "Command injection",
        8: "Path traversal",
        9: "Secrets en codigo",
        10: "CORS wildcard",
    }

    for vid in sorted(vector_names.keys()):
        count = result.get("vectorSummary", {}).get(vid, 0)
        icon = "[!]" if count > 0 else "[OK]"
        report += f"  Vector {vid:2d}: {icon} {vector_names[vid]:30s} {count:3d} hallazgos\n"

    if total > 0 and crit + high > 0:
        report += f"\nHALLAZGOS CRITICOS Y ALTOS (Top 20):\n"
        report += "-" * 70 + "\n"
        critical_high = [f for f in result["findings"] if f["severity"] in ("CRITICAL", "HIGH")]
        for f in critical_high[:20]:
            report += f"  [{f['severity']:8s}] V{f['vectorId']} {f['file']}:{f['line']}\n"
            report += f"             {f['title']}\n"
            if f.get("codeSnippet"):
                report += f"             > {f['codeSnippet'][:100]}\n"
            report += "\n"

    if total > 0:
        report += "RECOMENDACIONES TECNICAS (Nivel 4 — Nacional):\n"
        affected_vectors = set(f["vectorId"] for f in result["findings"])
        for vid in sorted(affected_vectors):
            report += f"  Vector {vid}: {get_recommendation(vid)}\n"

    return report

# ═════════════════════════════════════════════════════════════════════════════
#  MAIN
# ═════════════════════════════════════════════════════════════════════════════

def find_repos(base_dir: str) -> list:
    base = Path(base_dir)
    repos = []
    if (base / ".git").exists():
        repos.append(base)
    for d in base.iterdir():
        if d.is_dir() and (d / ".git").exists() and d not in repos:
            repos.append(d)
    return repos


def main():
    print("=" * 70)
    print("SOURCESEAL GLOBAL PROTOCOL — AUDITOR DE SEGURIDAD v3.0")
    print("Protocolo: SSP-ZKP-2048-L4 | Nivel 4 — Nacional (SM3)")
    print("=" * 70)

    if len(sys.argv) > 1:
        base_dir = sys.argv[1]
    else:
        base_dir = os.path.expanduser("~/Red-team-tauri")

    repos = find_repos(base_dir)

    if not repos:
        print(f"\n[!] No se encontraron repositorios en {base_dir}")
        print("    Uso: python3 source_seal_audit.py /path/to/repos")
        return

    print(f"\nRepositorios detectados ({len(repos)}):")
    for r in repos:
        print(f"  - {r.name} ({get_commit_hash(str(r))})")

    all_results = {}
    total_findings = 0
    total_critical = 0
    total_high = 0

    for repo in repos:
        print(f"\n--- Escaneando: {repo.name} ---")
        result = scan_repository(str(repo))
        all_results[repo.name] = result
        total_findings += result["findingsCount"]
        total_critical += result["criticalCount"]
        total_high += result["highCount"]
        print(f"    {result['filesScanned']} archivos | {result['findingsCount']} hallazgos "
              f"({result['criticalCount']}C / {result['highCount']}H / {result['mediumCount']}M / {result['lowCount']}L)")

    print("\n" + "=" * 70)
    print("REPORTE CONSOLIDADO")
    print("=" * 70)

    for repo_name, result in all_results.items():
        report = generate_report(repo_name, result)
        print(report)

    output_json = Path(base_dir) / "source_seal_audit_report.json"
    with open(output_json, "w") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False, default=str)
    print(f"\nReporte JSON: {output_json}")

    output_txt = Path(base_dir) / "source_seal_audit_report.log"
    with open(output_txt, "w") as f:
        for repo_name, result in all_results.items():
            f.write(generate_report(repo_name, result))
    print(f"Reporte texto: {output_txt}")

    print(f"\n{'=' * 70}")
    print(f"RESUMEN FINAL: {len(repos)} repos | {total_findings} hallazgos totales")
    print(f"  CRITICAL: {total_critical}")
    print(f"  HIGH:     {total_high}")
    if total_critical + total_high > 0:
        print(f"\n[!] ACCION INMEDIATA: {total_critical + total_high} vulnerabilidades criticas/altas requieren atencion.")
    else:
        print(f"\n[OK] Sin vulnerabilidades criticas o altas detectadas.")

    return all_results


if __name__ == "__main__":
    main()
