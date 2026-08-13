#!/usr/bin/env python3
"""
Descifrador del Manual de Operaciones - AES-256-CBC
Uso:
  python3 acceder_manual_py.py                    (te pide la clave, oculta)
  python3 acceder_manual_py.py TU_CLAVE_AQUI      (clave como argumento, evita problemas de teclado)
"""
import getpass
import subprocess
import sys
import os
import tempfile

ENC_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "manual_operaciones.enc")

def get_safe_tempdir():
    """
    En Termux/Android, /tmp NO es escribible (permission denied).
    Usamos TMPDIR (Termux la define como $PREFIX/tmp) o, si falla,
    el propio directorio del script (que sabemos que es escribible).
    """
    candidatos = [
        os.environ.get("TMPDIR"),
        tempfile.gettempdir(),
        os.path.dirname(os.path.abspath(__file__)),
    ]
    for c in candidatos:
        if c and os.path.isdir(c) and os.access(c, os.W_OK):
            return c
    return "."

TEMP_DIR = get_safe_tempdir()
TEMP_FILE = os.path.join(TEMP_DIR, f".manual_dec_{os.getpid()}.md")

def main():
    if not os.path.exists(ENC_FILE):
        print(f"\nERROR: {ENC_FILE} no existe.")
        sys.exit(1)

    print("\n============================================")
    print("  ACCESO AL MANUAL DE OPERACIONES")
    print("  Cifrado: AES-256-CBC + PBKDF2")
    print("============================================\n")
    print(f"(temporal en: {TEMP_FILE})\n")

    if len(sys.argv) > 1:
        clave = sys.argv[1]
        print(f"Usando clave pasada como argumento (longitud: {len(clave)})")
    else:
        clave = getpass.getpass("Introduce la clave de acceso: ")

    try:
        result = subprocess.run(
            [
                "openssl", "enc", "-d", "-aes-256-cbc",
                "-pbkdf2", "-iter", "100000",
                "-in", ENC_FILE,
                "-out", TEMP_FILE,
                "-pass", f"pass:{clave}"
            ],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            print("\nCLAVE INCORRECTA o error tecnico. Acceso denegado.")
            print(f"(detalle openssl: {result.stderr.strip()})")
            if os.path.exists(TEMP_FILE):
                os.remove(TEMP_FILE)
            sys.exit(1)

        if not os.path.exists(TEMP_FILE) or os.path.getsize(TEMP_FILE) == 0:
            print("\nCLAVE INCORRECTA. Acceso denegado.")
            sys.exit(1)

        with open(TEMP_FILE, "r") as f:
            primeras_lineas = f.read(500)
        if "MANUAL DE OPERACIONES" not in primeras_lineas.upper():
            print("\nCLAVE INCORRECTA. Acceso denegado.")
            os.remove(TEMP_FILE)
            sys.exit(1)

        print("\nClave correcta. Manual descifrado.\n")
        print("Como quieres verlo?")
        print("  1) Mostrar en consola")
        print("  2) Abrir con less (navegable)")
        print("  3) Solo descifrar y salir")
        print()

        opcion = input("Opcion: ").strip()

        if opcion == "1":
            with open(TEMP_FILE, "r") as f:
                print(f.read())
        elif opcion == "2":
            os.system(f"less '{TEMP_FILE}'")
        else:
            print(f"Descifrado en {TEMP_FILE}")
            sys.exit(0)

        os.remove(TEMP_FILE)
        print("\nTemporal borrado. El manual cifrado sigue en manual_operaciones.enc")

    except FileNotFoundError:
        print("\nERROR: openssl no esta instalado.")
        print("Instala con: pkg install openssl-tool")
        sys.exit(1)

if __name__ == "__main__":
    main()
