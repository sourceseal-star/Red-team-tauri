#!/usr/bin/env python3
"""
SOURCESEAL GLOBAL PROTOCOL — AUDITOR DE SEGURIDAD v3.0
Escaneo multi-repositorio | 10 vectores de vulnerabilidad
Protocolo: SSP-ZKP-2048-L4 | Nivel 4 — Nacional (SM3)
Multilenguaje: Python (AST estructural) + JS/TS (regex avanzado)

Uso:
    python source_seal_audit_v3.py

Ajusta REPOS_DIR abajo para apuntar a tus 9 repositorios.
"""

import os
import ast
import re
import json
import sys
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN — AJUSTA ESTA RUTA A TUS REPOSITORIOS
# ═══════════════════════════════════════════════════════════════════════════════
REPOS_DIR = Path(".")

TARGET_PATTERNS = ["*.py", "*.js", "*.ts", "*.jsx", "*.tsx"]
EXCLUDE_DIRS = {'node_modules', '.git', '__pycache__', 'venv', '.venv', 'dist', 'build', '.replit'}

# ═══════════════════════════════════════════════════════════════════════════════
# 10 VECTORES DE VULNERABILIDAD
# ═══════════════════════════════════════════════════════════════════════════════
VULN_VECTORS = {
    # ─── 5 VECTORES CRIPTOGRÁFICOS ───
    "weak_hash_md5": {
        "description": "Uso de MD5 para hashing criptografico — colisiones conocidas",
        "severity": "CRITICO",
        "python_patterns": [r"hashlib\.md5", r"md5\("],
        "js_patterns": [r"crypto\.createHash\(['\"]md5['\"]\)", r"md5\("],
        "safe_alt": "Usar hashlib.sha256() o bcrypt/scrypt para passwords"
    },
    "weak_hash_sha1": {
        "description": "Uso de SHA-1 — colisiones practicas demostradas (SHAttered)",
        "severity": "ALTO",
        "python_patterns": [r"hashlib\.sha1", r"sha1\("],
        "js_patterns": [r"crypto\.createHash\(['\"]sha1['\"]\)", r"sha1\("],
        "safe_alt": "Migrar a SHA-256 o SHA-3"
    },
    "weak_crypto_des": {
        "description": "Cifrado DES/3DES — clave de 56 bits, vulnerable a fuerza bruta",
        "severity": "CRITICO",
        "python_patterns": [r"DES\.new", r"TripleDES", r"DES3"],
        "js_patterns": [r"des\.", r"tripledes", r"3des"],
        "safe_alt": "Usar AES-256-GCM con nonce unico por mensaje"
    },
    "weak_crypto_ecb": {
        "description": "Modo ECB en cifrado por bloques — no oculta patrones de datos",
        "severity": "ALTO",
        "python_patterns": [r"AES\.new\(.*MODE_ECB", r"mode=\s*AES\.MODE_ECB"],
        "js_patterns": [r"aes\.ecb", r"mode\.ecb", r"createCipheriv.*ecb"],
        "safe_alt": "Usar AES-256-GCM o AES-256-CBC con IV aleatorio"
    },
    "hardcoded_key": {
        "description": "Clave criptografica hardcodeada en el codigo fuente",
        "severity": "CRITICO",
        "python_patterns": [r"(?:SECRET_KEY|API_KEY|PASSWORD|PRIVATE_KEY)\s*=\s*['\"][^'\"]{8,}['\"]"],
        "js_patterns": [r"(?:secret|apiKey|password|privateKey)\s*[:=]\s*['\"][^'\"]{8,}['\"]"],
        "safe_alt": "Usar variables de entorno o gestores de secretos (Vault, AWS SM)"
    },
    # ─── 5 VECTORES DE SEGURIDAD DE APLICACIÓN ───
    "ip_validation_bypass": {
        "description": "Bypass en validacion de IP por logica con .isdigit() y all() — permite octal/hex",
        "severity": "CRITICO",
        "python_ast": True,
        "js_patterns": [r"split\(['\"]\.['\"]\).*isdigit", r"\.split\(.*\).*every\("],
        "safe_alt": "Usar ipaddress.ip_address() (Python) o net module (Node)"
    },
    "command_injection": {
        "description": "Ejecucion de comandos del sistema sin sanitizacion de entrada",
        "severity": "CRITICO",
        "python_patterns": [r"os\.system\(", r"subprocess\.call\([^)]*shell\s*=\s*True", r"subprocess\.run\([^)]*shell\s*=\s*True", r"eval\(", r"exec\("],
        "js_patterns": [r"child_process\.", r"exec\(", r"execSync\(", r"eval\("],
        "safe_alt": "Usar argumentos como lista; nunca concatenar input del usuario"
    },
    "path_traversal": {
        "description": "Acceso a archivos del sistema mediante manipulacion de rutas",
        "severity": "ALTO",
        "python_patterns": [r"open\(.*\+\s*", r"send_file\(.*\+\s*", r"os\.path\.join\(.*request"],
        "js_patterns": [r"res\.sendFile\(.*\+", r"fs\.readFile\(.*\+", r"path\.join\(.*req"],
        "safe_alt": "Validar rutas contra whitelist; usar pathlib.resolve()"
    },
    "secrets_exposure": {
        "description": "Tokens, credenciales o secrets expuestos en codigo fuente",
        "severity": "CRITICO",
        "python_patterns": [
            r"ghp_[a-zA-Z0-9]{36}",
            r"sk-[a-zA-Z0-9]{48}",
            r"AKIA[0-9A-Z]{16}"
        ],
        "js_patterns": [
            r"ghp_[a-zA-Z0-9]{36}",
            r"sk-[a-zA-Z0-9]{48}",
            r"AKIA[0-9A-Z]{16}"
        ],
        "safe_alt": "Usar .env, secret managers, pre-commit hooks (git-secrets)"
    },
    "cors_misconfiguration": {
        "description": "CORS configurado con origen wildcard o sin restricciones",
        "severity": "ALTO",
        "python_patterns": [r"allow_origins\s*=\s*\[\s*['\"]\*['\"]\s*\]", r"CORSMiddleware.*allow_all"],
        "js_patterns": [r"res\.header\(['\"]Access-Control-Allow-Origin['\"],\s*['\"]\*['\"]\)", r"cors\(.*origin\s*:\s*true"],
        "safe_alt": "Especificar dominios exactos; nunca usar '*' en produccion"
    }
}


# ═══════════════════════════════════════════════════════════════════════════════
# MOTOR AST ESTRUCTURAL — DETECCION DE IP BYPASS
# ═══════════════════════════════════════════════════════════════════════════════
class IPValidationVisitor(ast.NodeVisitor):
    """Detecta estructuralmente: all(x.isdigit() for x in ip.split('.'))"""
    
    def __init__(self):
        self.vulnerable_functions = []
        self.current_function = None
    
    def visit_FunctionDef(self, node):
        old = self.current_function
        self.current_function = node
        self.generic_visit(node)
        self.current_function = old
    
    def visit_AsyncFunctionDef(self, node):
        self.visit_FunctionDef(node)
    
    def visit_Call(self, node):
        if isinstance(node.func, ast.Name) and node.func.id == 'all':
            if self._contains_isdigit_and_split(node):
                if self.current_function:
                    self.vulnerable_functions.append({
                        'function': self.current_function.name,
                        'line': self.current_function.lineno,
                        'type': 'ip_validation_bypass',
                        'severity': 'CRITICO',
                        'evidence': 'all() + isdigit() + split(".") — AST estructural'
                    })
        self.generic_visit(node)
    
    def _contains_isdigit_and_split(self, node):
        has_isdigit = [False]
        has_split = [False]
        def check(n):
            if isinstance(n, ast.Call):
                if isinstance(n.func, ast.Attribute) and n.func.attr == 'isdigit':
                    has_isdigit[0] = True
                if isinstance(n.func, ast.Attribute) and n.func.attr == 'split':
                    if n.args:
                        arg = n.args[0]
                        if isinstance(arg, ast.Constant) and arg.value == '.':
                            has_split[0] = True
                        elif hasattr(arg, 's') and arg.s == '.':
                            has_split[0] = True
            for child in ast.iter_child_nodes(n):
                check(child)
        check(node)
        return has_isdigit[0] and has_split[0]


def scan_python_ast(file_path, content):
    """Escaneo estructural con AST para Python."""
    findings = []
    try:
        tree = ast.parse(content, filename=str(file_path))
    except SyntaxError:
        return findings
    
    # 1. Deteccion AST estructural de IP bypass
    visitor = IPValidationVisitor()
    visitor.visit(tree)
    for v in visitor.vulnerable_functions:
        v['file'] = str(file_path)
    findings.extend(visitor.vulnerable_functions)
    
    # 2. Fallback: funciones con nombre sospechoso no capturadas por AST
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            name_lower = node.name.lower()
            if any(x in name_lower for x in ['_valid_ip', 'validate_ip', 'is_valid_ip']):
                already = any(f['line'] == node.lineno for f in findings)
                if not already:
                    lines = content.splitlines()
                    end = getattr(node, 'end_lineno', node.lineno)
                    func_text = "\n".join(lines[node.lineno-1:end])
                    if ".isdigit()" in func_text and ".split(" in func_text:
                        findings.append({
                            'file': str(file_path),
                            'function': node.name,
                            'line': node.lineno,
                            'type': 'ip_validation_bypass',
                            'severity': 'CRITICO',
                            'evidence': 'isdigit() + split() — fallback por nombre de funcion'
                        })
    return findings


def scan_regex(file_path, content, lang):
    """Escaneo basado en regex para Python y JS/TS."""
    findings = []
    lines = content.splitlines()
    for vector_name, vector in VULN_VECTORS.items():
        if vector_name == 'ip_validation_bypass':
            continue
        patterns = vector.get(f'{lang}_patterns', [])
        for pattern in patterns:
            try:
                for match in re.finditer(pattern, content, re.IGNORECASE):
                    line_num = content[:match.start()].count('\n') + 1
                    line_content = lines[line_num - 1].strip() if line_num <= len(lines) else ""
                    dup = any(f['line'] == line_num and f['type'] == vector_name for f in findings)
                    if not dup:
                        findings.append({
                            'file': str(file_path),
                            'type': vector_name,
                            'line': line_num,
                            'severity': vector['severity'],
                            'evidence': line_content[:80],
                            'pattern': pattern[:50]
                        })
            except re.error:
                continue
    return findings


def scan_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except Exception:
        return []
    if not content.strip():
        return []
    
    ext = file_path.suffix.lower()
    findings = []
    if ext == '.py':
        findings.extend(scan_python_ast(file_path, content))
        findings.extend(scan_regex(file_path, content, 'python'))
    elif ext in ('.js', '.ts', '.jsx', '.tsx'):
        findings.extend(scan_regex(file_path, content, 'js'))
    return findings


def scan_repository(repo_path):
    all_findings = []
    files_scanned = 0
    for pattern in TARGET_PATTERNS:
        for file_path in repo_path.rglob(pattern):
            if any(part in EXCLUDE_DIRS for part in file_path.parts):
                continue
            vulns = scan_file(file_path)
            all_findings.extend(vulns)
            files_scanned += 1
    return all_findings, files_scanned


def generate_executive_report(all_findings):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
    total_repos = len(all_findings)
    total_vulns = sum(len(v[0]) for v in all_findings.values())
    
    severity_counts = defaultdict(int)
    vector_counts = defaultdict(int)
    for findings, _ in all_findings.values():
        for f in findings:
            severity_counts[f.get('severity', 'INFO')] += 1
            vector_counts[f.get('type', 'unknown')] += 1
    
    report = f"""
================================================================================
  SOURCESEAL GLOBAL PROTOCOL — REPORTE DE AUDITORIA DE SEGURIDAD v3.0
  Protocolo: SSP-ZKP-2048-L4 | Nivel 4 — Nacional (SM3)
================================================================================
  FECHA: {timestamp}
  ESTADO: {'VULNERABLE' if total_vulns > 0 else 'SEGURO'}
  REPOSITORIOS: {total_repos}
  VULNERABILIDADES TOTALES: {total_vulns}

  DISTRIBUCION POR SEVERIDAD:
"""
    sev_order = {"CRITICO":0,"ALTO":1,"MEDIO":2,"BAJO":3}
    for sev, count in sorted(severity_counts.items(), key=lambda x: sev_order.get(x[0],4)):
        icon = {"CRITICO":"[CRITICO]","ALTO":"[ALTO]","MEDIO":"[MEDIO]","BAJO":"[BAJO]"}.get(sev, "[INFO]")
        report += f"    {icon} {sev}: {count}\n"
    
    report += "\n  VECTORES DETECTADOS:\n"
    for vec, count in sorted(vector_counts.items(), key=lambda x: -x[1]):
        report += f"    • {vec}: {count} hallazgos\n"
    
    report += "\n" + "="*80 + "\n"
    report += "DETALLES POR REPOSITORIO:\n"
    report += "="*80 + "\n"
    
    for repo_name, (findings, files_scanned) in all_findings.items():
        report += f"\n>> {repo_name} ({files_scanned} archivos)\n"
        if not findings:
            report += "   [OK] Sin vulnerabilidades detectadas\n"
            continue
        by_file = defaultdict(list)
        for f in findings:
            by_file[f['file']].append(f)
        for file_path, file_findings in by_file.items():
            rel = str(file_path).replace(str(REPOS_DIR), "")
            report += f"   {rel}\n"
            for f in file_findings:
                func = f.get('function', 'global')
                sev = f['severity']
                report += f"      [{sev}] L{f['line']} | {f['type']}"
                if func != 'global':
                    report += f" (func: {func})"
                report += "\n"
                if 'evidence' in f:
                    ev = f['evidence'][:60].replace('\n', ' ')
                    report += f"         > {ev}\n"
    
    if total_vulns > 0:
        report += "\n" + "="*80 + "\n"
        report += "RECOMENDACIONES TECNICAS (Nivel 4 — Nacional):\n"
        report += "-"*80 + "\n"
        unique = set()
        for findings, _ in all_findings.values():
            for f in findings:
                unique.add(f['type'])
        for vec in unique:
            if vec in VULN_VECTORS:
                v = VULN_VECTORS[vec]
                report += f"\n[{v['severity']}] {vec}:\n"
                report += f"   {v['description']}\n"
                report += f"   Fix: {v['safe_alt']}\n"
    
    return report


def main():
    print("SOURCESEAL GLOBAL PROTOCOL — AUDITOR v3.0")
    print("Protocolo: SSP-ZKP-2048-L4 | Nivel 4 — Nacional (SM3)")
    print("Vectores: 10 (5 criptograficos + 5 de aplicacion)")
    print("=" * 70)
    
    if not REPOS_DIR.exists():
        print(f"[!] Directorio no encontrado: {REPOS_DIR}")
        print("    Ajusta REPOS_DIR en el script.")
        return
    
    repos = [d for d in REPOS_DIR.iterdir() if d.is_dir() and not d.name.startswith('.')]
    if not repos:
        print(f"[!] No se encontraron repositorios en {REPOS_DIR}")
        return
    
    print(f"\nRepositorios detectados ({len(repos)}):")
    for r in repos:
        print(f"   • {r.name}")
    
    all_findings = {}
    for repo in repos:
        findings, files = scan_repository(repo)
        all_findings[repo.name] = (findings, files)
        print(f"   {repo.name}: {files} archivos | {len(findings)} hallazgos")
    
    report = generate_executive_report(all_findings)
    
    report_path = REPOS_DIR / "source_seal_security_audit_v3.log"
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)
    
    json_path = REPOS_DIR / "source_seal_audit_details.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump({k: v[0] for k, v in all_findings.items()}, f, indent=2, default=str)
    
    print(report)
    print(f"\nReporte guardado: {report_path}")
    print(f"JSON detallado: {json_path}")
    
    total = sum(len(v) for v, _ in all_findings.values())
    if total > 0:
        print(f"\n[!] ACCION INMEDIATA: {total} vulnerabilidades detectadas.")
    else:
        print("\n[OK] Todos los repositorios pasaron la auditoria.")


if __name__ == "__main__":
    main()
