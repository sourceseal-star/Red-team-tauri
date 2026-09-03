#!/usr/bin/env python3
"""Recuperación de acceso — resetea la contraseña de admin del RedTeam Dashboard.

No necesita la contraseña anterior (por eso es "recuperación", no "cambio").
Reescribe .auth/password.json (fuente de verdad que usa el login primero)
Y sincroniza ADMIN_PASSWORD en .env (fallback), para que ambos coincidan
siempre y no vuelvas a quedar fuera por un desincronismo entre los dos.

No imprime la contraseña en ningún lado — la escribes tú como argumento
en tu propia terminal, y este script solo confirma que se guardó.

Uso:
  python3 scripts/reset_admin_password.py "TuNuevaContraseñaSegura123"

Requisitos: mínimo 6 caracteres (igual que exige el endpoint /api/auth/password).
"""
import sys
import os
import json
import hashlib
import time

def main() -> int:
    if len(sys.argv) != 2:
        print("Uso: python3 scripts/reset_admin_password.py \"TuNuevaContraseña\"")
        return 1

    new_pass = sys.argv[1]
    if len(new_pass) < 6:
        print("❌ La contraseña debe tener al menos 6 caracteres.")
        return 1

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    auth_dir = os.path.join(root, "redteam", "scripts", ".auth")
    os.makedirs(auth_dir, exist_ok=True)
    pass_file = os.path.join(auth_dir, "password.json")

    salt = os.urandom(16)
    iterations = 310000
    password_hash = hashlib.pbkdf2_hmac(
        "sha256", new_pass.encode("utf-8"), salt, iterations
    ).hex()

    with open(pass_file, "w", encoding="utf-8") as f:
        json.dump({
            "algorithm": "pbkdf2-sha256",
            "iterations": iterations,
            "salt": salt.hex(),
            "password_hash": password_hash,
            "changed": time.time(),
        }, f)
    try:
        os.chmod(pass_file, 0o600)
    except OSError:
        pass

    # Sincronizar ADMIN_PASSWORD en .env (fallback si password.json llegara a
    # dañarse de nuevo) usando el mismo escritor seguro que usa el resto del
    # proyecto — nunca imprime valores, preserva todas las demás líneas.
    sys.path.insert(0, root)
    try:
        from nexus_credentials import update_project_env
        update_project_env({"ADMIN_PASSWORD": new_pass})
        env_synced = True
    except Exception as exc:
        env_synced = False
        print(f"⚠️  No se pudo sincronizar .env automáticamente: {exc}")
        print("    (password.json SÍ quedó actualizado — el login funcionará igual)")

    print("✅ Contraseña de administrador actualizada.")
    print(f"   Email: admin@redteam.local")
    if env_synced:
        print("   .env sincronizado (ADMIN_PASSWORD).")
    print("")
    print("Reinicia el dashboard para que tome el cambio:")
    print("   bash omni.sh start")
    print("Luego entra a localhost:8001 con tu nueva contraseña.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
