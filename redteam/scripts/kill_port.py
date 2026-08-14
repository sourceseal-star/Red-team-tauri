#!/usr/bin/env python3
"""
Libera un puerto TCP en Termux/Android de forma fiable.

Por que no usar /proc/net/tcp:
  Desde Android 10 (Q), el kernel bloquea la lectura de /proc/net/tcp y
  /proc/net/tcp6 para apps normales (Termux incluida) por politica SELinux.
  Esto NO es un problema de permisos de archivo que se pueda arreglar --
  es una restriccion del sistema operativo. El metodo viejo (leer
  /proc/net/tcp para hallar el inodo del socket y luego el PID dueno
  via /proc/<pid>/fd) SIEMPRE falla en Android 10+ y siempre imprime
  "Nada escuchando (o sin permiso de lectura)" aunque el puerto este
  ocupado -- por eso el watchdog reintentaba en loop sin nunca liberar
  realmente el puerto.

Por que no usar pkill:
  pkill NO viene instalado por defecto en Termux (hay que instalar
  el paquete 'procps'). Depender de un binario externo que puede no
  estar presente es fragil. En su lugar, este script mata procesos
  leyendo /proc/<pid>/cmdline directamente en Python puro.

Estrategia nueva (100% Python, sin binarios externos):
  1. Si se pasa un patron de proceso (ej "dashboard_server.py"), buscar
     todos los PIDs en /proc/*/cmdline que coincidan y mandarles SIGKILL.
     /proc/<pid>/cmdline SI es legible para procesos propios de Termux
     (misma UID), a diferencia de /proc/net/tcp.
  2. Como red de seguridad, tambien se intenta el metodo viejo via
     /proc/net/tcp (funciona en Android <10 o dispositivos rooteados).
  3. Se hace bind-test: intentar abrir un socket real en el puerto.
     Esto es 100% fiable para saber si el puerto quedo libre o no (no
     depende de ningun /proc). Se reintenta con backoff corto hasta
     un timeout.

Uso:
  python3 kill_port.py <puerto> [patron_proceso] [timeout_seg]

  python3 kill_port.py 8001 dashboard_server.py 5
  python3 kill_port.py 5173 vite 5
"""
import sys
import os
import glob
import socket
import time


def port_is_free(port: int, host: str = "0.0.0.0") -> bool:
    """Bind-test real: unica forma fiable de saber si un puerto esta libre
    en Termux, sin depender de /proc/net/tcp (bloqueado en Android 10+)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.bind((host, port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def kill_by_pattern(pattern: str) -> list:
    """Mata procesos leyendo /proc/<pid>/cmdline en Python puro.
    No depende de pkill ni ningun binario externo.
    /proc/<pid>/cmdline SI es legible para procesos propios de Termux
    (misma UID), a diferencia de /proc/net/tcp que esta bloqueado."""
    if not pattern:
        return []
    killed = []
    for pid_dir in glob.glob("/proc/[0-9]*"):
        pid = os.path.basename(pid_dir)
        cmdline_path = f"{pid_dir}/cmdline"
        try:
            with open(cmdline_path, "r") as f:
                cmdline = f.read().replace("\x00", " ").strip()
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
        if not cmdline:
            continue
        # Coincidencia flexible: el patron puede estar en cualquier parte
        # de la linea de comandos (ej "dashboard_server.py" matchea
        # "python3 /path/to/dashboard_server.py")
        if pattern in cmdline:
            try:
                os.kill(int(pid), 9)
                killed.append(pid)
            except (ProcessLookupError, PermissionError):
                pass
    return killed


def _find_inodes_for_port(port: int) -> set:
    """Metodo legacy via /proc/net/tcp. Solo funciona en Android <10 o
    dispositivos rooteados -- se mantiene como bonus, nunca como unica via."""
    port_hex = format(port, "04X")
    inodes = set()
    for tcp_file in ("/proc/net/tcp", "/proc/net/tcp6"):
        try:
            with open(tcp_file) as f:
                lines = f.readlines()[1:]
        except (FileNotFoundError, PermissionError):
            continue
        for line in lines:
            parts = line.split()
            if len(parts) < 10:
                continue
            local_addr = parts[1]
            state = parts[3]
            try:
                _, lport = local_addr.split(":")
            except ValueError:
                continue
            if lport.upper() == port_hex and state == "0A":
                inodes.add(parts[9])
    return inodes


def kill_via_proc(port: int) -> list:
    """Metodo legacy: busca el inodo del socket en /proc/net/tcp y mata
    el PID dueno. Solo funciona si /proc/net/tcp es legible (Android <10)."""
    inodes = _find_inodes_for_port(port)
    if not inodes:
        return []
    killed = []
    for pid_dir in glob.glob("/proc/[0-9]*"):
        pid = os.path.basename(pid_dir)
        fd_dir = f"{pid_dir}/fd"
        try:
            fds = os.listdir(fd_dir)
        except (FileNotFoundError, PermissionError, NotADirectoryError):
            continue
        for fd in fds:
            try:
                link = os.readlink(f"{fd_dir}/{fd}")
            except OSError:
                continue
            if link.startswith("socket:["):
                inode = link[8:-1]
                if inode in inodes:
                    try:
                        os.kill(int(pid), 9)
                        killed.append(pid)
                    except (ProcessLookupError, PermissionError):
                        pass
                    break
    return killed


def free_port(port: int, pattern: str = None, timeout: float = 5.0) -> bool:
    """Intenta liberar el puerto por todos los medios disponibles y
    confirma con bind-test real. Devuelve True si el puerto quedo libre."""
    if port_is_free(port):
        return True

    pattern_killed = []
    if pattern:
        pattern_killed = kill_by_pattern(pattern)

    proc_killed = kill_via_proc(port)

    # Esperar a que el kernel libere el socket (TIME_WAIT / SO_REUSEADDR)
    deadline = time.time() + timeout
    while time.time() < deadline:
        if port_is_free(port):
            return True
        time.sleep(0.3)
    return port_is_free(port)


if __name__ == "__main__":
    p = int(sys.argv[1]) if len(sys.argv) > 1 else 8001
    pat = sys.argv[2] if len(sys.argv) > 2 else None
    tmo = float(sys.argv[3]) if len(sys.argv) > 3 else 5.0

    if port_is_free(p):
        print(f"[kill_port] Puerto {p} ya estaba libre.")
        sys.exit(0)

    ok = free_port(p, pat, tmo)
    if ok:
        method = ""
        if pat:
            method = f" (patron '{pat}')"
        print(f"[kill_port] Puerto {p} liberado{method}.")
        sys.exit(0)
    else:
        print(f"[kill_port] ADVERTENCIA: puerto {p} sigue ocupado tras {tmo}s.")
        if pat:
            print(f"[kill_port]   Se intento matar por patron '{pat}' pero el")
            print(f"[kill_port]   proceso no murio o el kernel tarda en liberar el socket.")
        print(f"[kill_port]   Cierra Termux completamente y vuelve a abrirlo.")
        sys.exit(1)
