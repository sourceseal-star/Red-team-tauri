#!/usr/bin/env python3
"""
Descifrador del Manual de Operaciones - AES-256-CBC
Uso: python3 acceder_manual_py.sh
"""
import getpass
import subprocess
import sys
import os

ENC_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "manual_operaciones.enc")
TEMP_FILE = "/tmp/manual_operaciones_dec.md"

def main():
    if not os.path.exists(ENC_FILE):
        print(f"\nERROR: {ENC_FILE} no existe.")
        sys.exit(1)

    print("\n============================================")
    print("  ACCESO AL MANUAL DE OPERACIONES")
    print("  Cifrado: AES-256-CBC + PBKDF2")
    print("============================================\n")

    clave = getpass.getpass("Introduce la clave de acceso: ")

    # Descifrar con openssl
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
            print("\nCLAVE INCORRECTA. Acceso denegado.")
            if os.path.exists(TEMP_FILE):
                os.remove(TEMP_FILE)
            sys.exit(1)

        if not os.path.exists(TEMP_FILE) or os.path.getsize(TEMP_FILE) == 0:
            print("\nCLAVE INCORRECTA. Acceso denegado.")
            sys.exit(1)

        # Verificar que el descifrado tiene sentido
        with open(TEMP_FILE, "r") as f:
            primera_linea = f.readline()
        if "MANUAL" not in primera_linea.upper():
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
            os.system(f"less {TEMP_FILE}")
        else:
            print(f"Descifrado en {TEMP_FILE}")

        # Borrar temporal
        os.remove(TEMP_FILE)
        print("\nTemporal borrado. El manual cifrado sigue en manual_operaciones.enc")

    except FileNotFoundError:
        print("\nERROR: openssl no esta instalado.")
        print("Instala con: pkg install openssl-tool")
        sys.exit(1)

if __name__ == "__main__":
    main()
