#!/usr/bin/env python3
"""
Verificador del manual cifrado - diagnostico
Uso: python3 verificar_manual.py
"""
import subprocess
import os
import sys
import hashlib

ENC_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "manual_operaciones.enc")

def main():
    print("\n=== DIAGNOSTICO DEL MANUAL CIFRADO ===\n")

    # 1. Existe el archivo?
    if not os.path.exists(ENC_FILE):
        print(f"ADVERTENCIA: {ENC_FILE} NO EXISTE")
        print("El manual cifrado no forma parte de esta copia; se puede consultar MANUAL_OPERATIVO.md.")
        print("Diagnóstico del manual cifrado omitido.")
        return 0

    # 2. Tamano
    size = os.path.getsize(ENC_FILE)
    print(f"Archivo: {ENC_FILE}")
    print(f"Tamano: {size} bytes")
    if size < 100:
        print("ADVERTENCIA: archivo muy pequeno, podria estar corrupto")

    # 3. MD5
    with open(ENC_FILE, "rb") as f:
        md5 = hashlib.md5(f.read()).hexdigest()
    print(f"MD5: {md5}")

    # 4. Primeros bytes (para ver si es binario valido)
    with open(ENC_FILE, "rb") as f:
        header = f.read(16)
    print(f"Header (hex): {header.hex()}")
    print(f"Header (ascii): {header}")

    # 5. openssl disponible?
    result = subprocess.run(["openssl", "version"], capture_output=True, text=True)
    print(f"OpenSSL: {result.stdout.strip()}")

    # 6. Probar clave
    clave = input("\nIntroduce la clave para probar: ").strip()
    print(f"Clave recibida: '{clave}' (longitud: {len(clave)})")

    result = subprocess.run(
        [
            "openssl", "enc", "-d", "-aes-256-cbc",
            "-pbkdf2", "-iter", "100000",
            "-in", ENC_FILE,
            "-out", "/tmp/verify_manual.md",
            "-pass", f"pass:{clave}"
        ],
        capture_output=True,
        text=True
    )
    print(f"\nExit code: {result.returncode}")
    print(f"Stderr: {result.stderr}")

    if result.returncode == 0 and os.path.exists("/tmp/verify_manual.md"):
        with open("/tmp/verify_manual.md", "r") as f:
            content = f.read()
        if "MANUAL" in content.upper():
            print("\nCLAVE CORRECTA - el manual se descifro bien")
            print(f"Primeras lineas:")
            for line in content.split("\n")[:3]:
                print(f"  {line}")
        else:
            print("\nEl archivo se descifro pero el contenido no es el manual")
        os.remove("/tmp/verify_manual.md")
    else:
        print("\nCLAVE INCORRECTA o error de openssl")

if __name__ == "__main__":
    main()
