# -*- coding: utf-8 -*-
"""
NEXUS Map Core v10.0 — el mapa de IA de la War Room.

Cada dispositivo descubierto en la red LAN real se proyecta sobre la
posición GPS real del teléfono: el resultado es un mapa físico de la red
que se puede abrir en OsmAnd (offline), exportar como GPX/KML o seguir
con GPS Test. Los dispositivos LAN no tienen GPS propio; el mapa los
sitúa en un racimo determinista alrededor del teléfono (quién es quién
queda claro por IP/nombre, no por metros).

Sin root en ningún punto: termux-location y nada más.
"""

import hashlib
import json
import math
import os
import re
import subprocess
import time

NEXUS_MAP_VERSION = "10.0"

# Desplazamiento máximo del racimo (en metros) alrededor del teléfono.
# Pequeño a propósito: en OsmAnd los dispositivos quedan como puntos
# vecinos a tu posición, como un "mapa de campo" de tu red.
CLUSTER_RADIUS_M = 25.0

ICON_POR_TIPO = {
    "router": "internet",
    "camera": "camera",
    "dvr": "recorder",
    "desktop": "computer",
    "phone": "phone",
    "iot": "sensor",
    "unknown": "flag",
}


def _h(s):
    return int(hashlib.sha256(str(s).encode()).hexdigest()[:12], 16)


class NexusMap:
    """Estado del mapa de IA: topología + GPS + enriquecimientos."""

    def __init__(self, state_path=None, topology_cache_path=None):
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        data_dir = os.path.join(base, "redteam", "data")
        os.makedirs(data_dir, exist_ok=True)
        self.state_path = state_path or os.path.join(
            data_dir, "nexus_map_state.json")
        self.topology_cache_path = topology_cache_path or os.path.join(
            data_dir, "topology_last.json")
        self.state = self._load_state()

    # ── persistencia (aditiva, tolerante a fallos) ──────────────────────
    def _load_state(self):
        try:
            with open(self.state_path, encoding="utf-8") as f:
                s = json.load(f)
            if isinstance(s, dict):
                return s
        except Exception:
            pass
        return {"gps": None, "netguard": None, "updated": None}

    def _save_state(self):
        try:
            with open(self.state_path, "w", encoding="utf-8") as f:
                json.dump(self.state, f, ensure_ascii=False, indent=1)
        except Exception:
            pass

    # ── topología (fuente: caché de /api/scan/topology, Regla #44) ─────
    def load_topology(self):
        """Lee el último escaneo guardado. NO lanza escaneos por sí solo:
        el escaneo sigue siendo MANUAL desde el mapa."""
        try:
            with open(self.topology_cache_path, encoding="utf-8") as f:
                data = json.load(f)
            hosts = data.get("results") or []
            return {
                "saved_at": data.get("saved_at"),
                "method": data.get("method"),
                "subnet": data.get("subnet"),
                "hosts": hosts,
            }
        except Exception:
            return {"saved_at": None, "method": None,
                    "subnet": None, "hosts": []}

    # ── GPS sin root ────────────────────────────────────────────────────
    def get_gps(self, provider="network", timeout=8):
        """termux-location -p {network|gps} -t N. Requiere Termux:API.
        Devuelve dict o None. No lanza nunca: sin Termux:API simplemente
        no hay GPS automático (queda la entrada manual)."""
        try:
            out = subprocess.run(
                ["termux-location", "-p", provider, "-t", str(timeout)],
                capture_output=True, text=True, timeout=timeout + 4,
            )
            if out.returncode == 0 and out.stdout.strip():
                d = json.loads(out.stdout)
                lat, lon = d.get("latitude"), d.get("longitude")
                if lat is not None and lon is not None:
                    gps = {
                        "lat": float(lat), "lon": float(lon),
                        "accuracy": d.get("accuracy"),
                        "provider": provider,
                        "source": "termux-location",
                        "satellites": self.state.get("gps", {}).get("satellites"),
                        "ts": time.time(),
                    }
                    self.state["gps"] = gps
                    self._save_state()
                    return gps
        except Exception:
            pass
        return None

    def set_gps_manual(self, lat, lon, accuracy=None, satellites=None,
                       note=None):
        """Entrada manual (GPS Test / OsmAnd muestran coords exactas)."""
        gps = {
            "lat": float(lat), "lon": float(lon),
            "accuracy": accuracy, "provider": "manual",
            "source": note or "manual",
            "satellites": satellites,
            "ts": time.time(),
        }
        self.state["gps"] = gps
        self._save_state()
        return gps

    # ── proyección: dispositivos alrededor del teléfono ────────────────
    def project(self, hosts, gps):
        """Asigna lat/lon a cada dispositivo: racimo determinista alrededor
        del GPS real. La misma IP siempre cae en el mismo punto."""
        if not gps:
            return hosts
        lat0, lon0 = gps["lat"], gps["lon"]
        # metros→grados (aprox a esta latitud)
        mdeg_lat = 1.0 / 111_320.0
        mdeg_lon = 1.0 / (111_320.0 * max(0.01, math.cos(math.radians(lat0))))
        for i, h in enumerate(hosts):
            hh = _h(h.get("ip", str(i)))
            ang = (hh % 3600) / 10.0            # 0..360 determinista
            rad = 6.0 + (hh >> 12) % int(CLUSTER_RADIUS_M)  # 6..25 m
            h["lat"] = round(lat0 + rad * math.sin(math.radians(ang)) * mdeg_lat, 7)
            h["lon"] = round(lon0 + rad * math.cos(math.radians(ang)) * mdeg_lon, 7)
            h["distance_m"] = round(rad, 1)
        return hosts

    # ── estado completo del mapa ────────────────────────────────────────
    def snapshot(self):
        topo = self.load_topology()
        gps = self.state.get("gps")
        hosts = self.project(topo["hosts"], gps)
        counts = {}
        for h in hosts:
            counts[h.get("type") or "unknown"] = counts.get(h.get("type") or "unknown", 0) + 1
        return {
            "version": NEXUS_MAP_VERSION,
            "gps": gps,
            "gps_available": gps is not None,
            "topology": {"saved_at": topo["saved_at"], "method": topo["method"],
                         "subnet": topo["subnet"], "hosts_up": len(hosts)},
            "devices": hosts,
            "counts": counts,
            "netguard": self.state.get("netguard"),
            "exports": {"gpx": "/api/nexus/map/gpx", "kml": "/api/nexus/map/kml"},
            "osmand_hint": ("GPS activo: cada dispositivo tiene enlace directo "
                            "a OsmAnd y descarga GPX/KML offline."),
        }

    # ── exportes para OsmAnd ────────────────────────────────────────────
    def to_gpx(self):
        snap = self.snapshot()
        gps = snap["gps"]
        lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<gpx version="1.1" creator="NEXUS Map v10.0" '
            'xmlns="http://www.topografix.com/GPX/1/1">',
            "  <metadata>",
            "    <name>War Room — Mapa de IA</name>",
            f"    <desc>Red de {snap['topology']['hosts_up']} dispositivos · "
            f"método {snap['topology']['method']}</desc>",
            "  </metadata>",
        ]
        if gps:
            lines += [
                '  <wpt lat="%s" lon="%s">' % (gps["lat"], gps["lon"]),
                "    <name>📍 TÚ (War Room)</name>",
                f"    <desc>Posición GPS del teléfono ({gps.get('source')})</desc>",
                "    <sym>Pin, Red</sym>",
                "  </wpt>",
            ]
        for h in snap["devices"]:
            if "lat" not in h:
                continue
            nombre = h.get("hostname") or h.get("vendor") or h.get("ip")
            desc = "%s · %s · riesgo %s · fuentes %s" % (
                h.get("type", "?"), h.get("ip"),
                h.get("risk", "n/a"),
                ",".join(h.get("sources", [])) or "topology")
            if h.get("mac"):
                desc += " · MAC %s" % h["mac"]
            lines += [
                '  <wpt lat="%s" lon="%s">' % (h["lat"], h["lon"]),
                "    <name>%s (%s)</name>" % (_xml(nombre), h.get("type", "?")),
                "    <desc>%s</desc>" % _xml(desc),
                "    <sym>%s</sym>" % ICON_POR_TIPO.get(h.get("type"), "flag"),
                "  </wpt>",
            ]
        lines.append("</gpx>")
        return "\n".join(lines)

    def to_kml(self):
        snap = self.snapshot()
        gps = snap["gps"]
        lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<kml xmlns="http://www.opengis.net/kml/2.2">',
            "  <Document>",
            "    <name>War Room — Mapa de IA (NEXUS 10.0)</name>",
        ]
        if gps:
            lines += [
                "    <Placemark>",
                "      <name>📍 TÚ (War Room)</name>",
                "      <Point><coordinates>%s,%s,0</coordinates></Point>" % (gps["lon"], gps["lat"]),
                "    </Placemark>",
            ]
        for h in snap["devices"]:
            if "lat" not in h:
                continue
            nombre = h.get("hostname") or h.get("vendor") or h.get("ip")
            desc = "%s · %s · riesgo %s" % (h.get("type", "?"), h.get("ip"),
                                            h.get("risk", "n/a"))
            lines += [
                "    <Placemark>",
                "      <name>%s (%s)</name>" % (_xml(nombre), h.get("type", "?")),
                "      <description>%s</description>" % _xml(desc),
                "      <Point><coordinates>%s,%s,0</coordinates></Point>" % (h["lon"], h["lat"]),
                "    </Placemark>",
            ]
        lines += ["  </Document>", "</kml>"]
        return "\n".join(lines)

    # ── enlaces directos ────────────────────────────────────────────────
    @staticmethod
    def links_for(lat, lon, label=""):
        """geo: (abre app de mapas del sistema) y osmand.net/go (abre
        OsmAnd directo si está instalado)."""
        q = ("?q=%s" % label) if label else ""
        return {
            "geo": "geo:%s,%s%s" % (lat, lon, q),
            "osmand": "https://osmand.net/go?lat=%s&lon=%s&z=19" % (lat, lon),
            "osmand_marker": "https://osmand.net/map?pin=%s,%s" % (lat, lon),
        }

    # ── NetGuard ────────────────────────────────────────────────────────
    def set_netguard(self, summary):
        self.state["netguard"] = summary
        self._save_state()
        return summary


def parse_netguard_log(text):
    """Resume un log exportado de NetGuard: bloqueos y tráfico por IP.
    NetGuard exporta texto plano con líneas tipo:
      ... ALLOW/BLOCK protocol tcp uid ... from 192.168.1.20 ...
    Tolerante: solo extrae IPs + decisión por línea."""
    per_ip = {}
    total_allowed = total_blocked = 0
    for line in (text or "").splitlines():
        ipm = re.search(r"from ([0-9.]{7,15})|to ([0-9.]{7,15})", line)
        if not ipm:
            continue
        ip = ipm.group(1) or ipm.group(2)
        if ip.startswith(("0.", "127.", "224.", "239.", "255.")):
            continue
        entry = per_ip.setdefault(ip, {"allowed": 0, "blocked": 0})
        low = line.lower()
        if "block" in low:
            entry["blocked"] += 1
            total_blocked += 1
        else:
            entry["allowed"] += 1
            total_allowed += 1
    summary = {
        "parsed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "ips": sorted(per_ip.items(), key=lambda kv: -(kv[1]["blocked"])),
        "total_allowed": total_allowed,
        "total_blocked": total_blocked,
        "unique_ips": len(per_ip),
    }
    return summary


def _xml(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))
