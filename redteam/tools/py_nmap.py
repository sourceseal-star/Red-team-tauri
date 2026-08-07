#!/usr/bin/env python3
"""
PyNmap — Port scanner & service detector in pure Python.
Authorized pentesting use only. Uses only stdlib.
"""
import socket, sys, json, time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

TOP_PORTS = [
    80, 443, 8080, 8443, 8000, 8888, 3000, 5000, 9000,
    22, 23, 2222, 21, 2121, 25, 465, 587, 53,
    3306, 5432, 1433, 1521, 27017, 6379, 9200, 11211,
    110, 995, 143, 993, 111, 2049, 139, 445, 3389,
    161, 162, 514, 515, 873, 1080, 1194, 3128, 4444, 5555, 6443,
    8081, 8082, 8444, 9090, 9091,
]

def scan_port(host, port, timeout=2):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        result = s.connect_ex((host, port))
        if result == 0:
            banner = ""
            try:
                s.settimeout(1.5)
                if port in (80, 8080, 8000, 8888, 3000, 5000, 9000):
                    s.sendall(b"GET / HTTP/1.1\r\nHost: " + host.encode() + b"\r\n\r\n")
                else:
                    s.sendall(b"\r\n")
                banner = s.recv(1024).decode('utf-8', errors='replace').strip()[:200]
            except:
                pass
            s.close()
            return {"port": port, "state": "open", "banner": banner}
        else:
            s.close()
            return {"port": port, "state": "closed"}
    except socket.timeout:
        return {"port": port, "state": "filtered"}
    except Exception as e:
        return {"port": port, "state": "error", "error": str(e)}

def scan_host(host, ports=None, timeout=2, threads=50):
    if ports is None:
        ports = TOP_PORTS
    try:
        ip = socket.gethostbyname(host)
    except socket.gaierror:
        return {"host": host, "error": "DNS resolution failed"}
    
    print(f"\n{'='*60}")
    print(f"  Host: {host} ({ip})")
    print(f"  Scan started: {datetime.now().isoformat()}")
    print(f"  Ports: {len(ports)} | Threads: {threads} | Timeout: {timeout}s")
    print(f"{'='*60}")
    
    start = time.time()
    results = []
    with ThreadPoolExecutor(max_workers=threads) as executor:
        futures = {executor.submit(scan_port, ip, p, timeout): p for p in ports}
        for future in as_completed(futures):
            r = future.result()
            results.append(r)
            if r["state"] == "open":
                bp = r.get("banner", "")[:60]
                print(f"  PORT {r['port']:<6} OPEN    {bp}")
    
    elapsed = time.time() - start
    open_ports = [r for r in results if r["state"] == "open"]
    closed = [r for r in results if r["state"] == "closed"]
    filtered = [r for r in results if r["state"] == "filtered"]
    
    print(f"\n{'─'*60}")
    print(f"  Done in {elapsed:.2f}s | Open: {len(open_ports)} | Closed: {len(closed)} | Filtered: {len(filtered)}")
    print(f"{'='*60}\n")
    
    return {
        "host": host, "ip": ip, "scan_time": datetime.now().isoformat(),
        "elapsed_seconds": round(elapsed, 2),
        "open_ports": open_ports, "closed_count": len(closed), "filtered_count": len(filtered),
    }

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 py_nmap.py <host> [host2 ...]")
        sys.exit(1)
    all_results = []
    for h in sys.argv[1:]:
        all_results.append(scan_host(h))
    print(json.dumps(all_results, indent=2))
