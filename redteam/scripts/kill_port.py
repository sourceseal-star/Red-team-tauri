#!/usr/bin/env python3
"""
Mata cualquier proceso escuchando en un puerto TCP dado, leyendo /proc
directamente (sin depender de fuser/lsof/netstat, que normalmente NO
estan instalados en Termux). Funciona para procesos propios de Termux
(misma UID de la app), que es el caso de dashboard_server.py / vite.

Uso: python3 kill_port.py 8001
"""
import sys
import os
import glob


def _find_inodes_for_port(port: int) -> set:
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
            # state 0A = LISTEN
            if lport.upper() == port_hex and state == "0A":
                inodes.add(parts[9])
    return inodes


def kill_port(port: int) -> list:
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


if __name__ == "__main__":
    p = int(sys.argv[1]) if len(sys.argv) > 1 else 8001
    result = kill_port(p)
    if result:
        print(f"[kill_port] Matados PID(s) en puerto {p}: {', '.join(result)}")
    else:
        print(f"[kill_port] Nada escuchando en puerto {p} (o sin permiso de lectura)")
