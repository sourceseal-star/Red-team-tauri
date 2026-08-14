#!/usr/bin/env python3
"""
Integrity Seal Manager — Protege configuración y reportes JSON contra manipulación.
Genera un hash SHA-256 + firma HMAC de cada archivo crítico al instalar.
Verifica integridad antes de ejecutar cualquier módulo defensivo.
"""
import os
import json
import hashlib
import hmac
import time
import pathlib
from datetime import datetime

class SealManager:
    def __init__(self, root="."):
        self.root = pathlib.Path(root)
        self.seal_file = self.root / "integrity" / "seals.json"
        self.seal_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Archivos críticos que deben sellarse
        self.critical_files = [
            "ztna/gateway.py",
            "xdr/correlator.py",
            "soar/engine.py",
            "ndr/engine.py",
            "rasp/agent.py",
            "deception/mesh.py",
            "tlsproxy/interceptor.py",
            "runner/unified_orchestrator.py",
            "runner/orchestrator.py",
            "tip/platform.py",
            "config/policies.json",
            "config/mitre_mapping.json",
            "config/soar_playbooks.json",
            "tip/platform.py",
        ]
        
        # Clave derivada del dispositivo (no hardcoded)
        self._hmac_key = self._derive_key()
    
    def _derive_key(self):
        """Deriva clave del dispositivo — no se puede copiar a otro lado."""
        import platform
        import getpass
        machine = platform.node() or "unknown"
        user = getpass.getuser() if hasattr(getpass, 'getuser') else "termux"
        # En Termux, usar el ID del dispositivo
        termux_id = os.environ.get("TERMUX_UID", "")
        if not termux_id:
            try:
                termux_id = str(os.stat("/data/data/com.termux").st_uid)
            except:
                termux_id = "fallback"
        raw = f"{machine}:{user}:{termux_id}:sourceseal-integrity-v1"
        return hashlib.sha256(raw.encode()).digest()
    
    def _hash_file(self, filepath):
        """Calcula SHA-256 de un archivo."""
        h = hashlib.sha256()
        try:
            with open(filepath, "rb") as f:
                while True:
                    chunk = f.read(8192)
                    if not chunk:
                        break
                    h.update(chunk)
            return h.hexdigest()
        except FileNotFoundError:
            return None
    
    def _sign(self, data):
        """Firma HMAC-SHA256 de los datos."""
        return hmac.new(self._hmac_key, data.encode(), hashlib.sha256).hexdigest()
    
    def seal_all(self):
        """Sella todos los archivos críticos. Guarda hash + firma + timestamp."""
        seals = {}
        for rel_path in self.critical_files:
            abs_path = self.root / rel_path
            file_hash = self._hash_file(abs_path)
            if file_hash is None:
                # Si el archivo no existe, lo saltamos
                continue
            
            seal_data = f"{rel_path}:{file_hash}"
            signature = self._sign(seal_data)
            
            seals[rel_path] = {
                "sha256": file_hash,
                "hmac": signature,
                "sealed_at": datetime.utcnow().isoformat(),
                "size": os.path.getsize(abs_path) if os.path.exists(abs_path) else 0,
            }
        
        # Guardar con la firma del archivo de sellos completo
        seals_json = json.dumps(seals, indent=2, sort_keys=True)
        file_sig = self._sign(seals_json)
        
        manifest = {
            "seals": seals,
            "manifest_hmac": file_sig,
            "sealed_at": datetime.utcnow().isoformat(),
            "total_files": len(seals),
            "version": "1.0",
        }
        
        with open(self.seal_file, "w") as f:
            json.dump(manifest, f, indent=2, sort_keys=True)
        
        return manifest
    
    def verify_all(self):
        """Verifica que ningún archivo sellado haya sido modificado."""
        if not self.seal_file.exists():
            return {
                "status": "NOT_SEALED",
                "message": "No hay sellos. Ejecuta 'seal' primero.",
                "tampered": [],
                "ok": [],
            }
        
        with open(self.seal_file) as f:
            manifest = json.load(f)
        
        seals = manifest.get("seals", {})
        tampered = []
        ok = []
        
        for rel_path, seal_info in seals.items():
            abs_path = self.root / rel_path
            current_hash = self._hash_file(abs_path)
            
            if current_hash is None:
                tampered.append({
                    "file": rel_path,
                    "reason": "ARCHIVO ELIMINADO",
                })
                continue
            
            if current_hash != seal_info["sha256"]:
                tampered.append({
                    "file": rel_path,
                    "reason": "HASH MODIFICADO",
                    "original_hash": seal_info["sha256"][:16] + "...",
                    "current_hash": current_hash[:16] + "...",
                })
                continue
            
            # Verificar firma HMAC
            seal_data = f"{rel_path}:{current_hash}"
            expected_sig = self._sign(seal_data)
            if not hmac.compare_digest(expected_sig, seal_info["hmac"]):
                tampered.append({
                    "file": rel_path,
                    "reason": "FIRMA HMAC INVÁLIDA — sellos manipulados",
                })
                continue
            
            ok.append(rel_path)
        
        # Verificar firma del manifiesto completo
        seals_json = json.dumps(seals, indent=2, sort_keys=True)
        manifest_ok = hmac.compare_digest(
            self._sign(seals_json),
            manifest.get("manifest_hmac", "")
        )
        
        if not manifest_ok:
            return {
                "status": "MANIFEST_TAMPERED",
                "message": "⚠️  ARCHIVO DE SELLOS MANIPULADO — firma del manifiesto inválida",
                "tampered": tampered,
                "ok": ok,
                "manifest_valid": False,
            }
        
        if tampered:
            return {
                "status": "TAMPERED",
                "message": f"⚠️  {len(tampered)} archivo(s) modificados sin autorización",
                "tampered": tampered,
                "ok": ok,
                "manifest_valid": True,
            }
        
        return {
            "status": "VERIFIED",
            "message": f"✅ {len(ok)} archivos verificados — integridad intacta",
            "tampered": [],
            "ok": ok,
            "manifest_valid": True,
        }
    
    def verify_or_block(self):
        """Verifica integridad. Si hay manipulación, bloquea la ejecución."""
        result = self.verify_all()
        if result["status"] not in ("VERIFIED", "NOT_SEALED"):
            print("\n" + "=" * 60)
            print("🚨 INTEGRIDAD COMPROMETIDA — EJECUCIÓN BLOQUEADA")
            print("=" * 60)
            print(f"\n{result['message']}")
            print("\nArchivos manipulados:")
            for t in result.get("tampered", []):
                print(f"  ❌ {t['file']}: {t['reason']}")
            print("\nPara restaurar: git checkout -- .")
            print("Para re-sellar tras cambios autorizados: python3 -m integrity.seal_manager seal")
            print("=" * 60)
            return False
        return True
