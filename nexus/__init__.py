# -*- coding: utf-8 -*-
"""
NEXUS — módulo central del mapa de IA de la War Room.

v10.0 (2026-10-02, pedido de Harold): el mapa de IA se separa del motor
OMNI v9.0 y vive aquí, en su propio módulo. map_core.py integra:

  🗺️  Topología real    → dispositivos descubiertos por /api/scan/topology
                          (Regla #44: ARP + ping + SSDP + mDNS + NetBIOS)
  📍  GPS sin root      → termux-location (red/gps) o coordenadas manuales
  🧭  OsmAnd            → enlaces go/geo y exportes GPX/KML (mapa offline)
  🛰️  GPS Test          → entrada manual de satélites/precisión
  🛡️  NetGuard          → parseo de logs exportados (bloqueos por IP)

Regla #63: aditivo — el motor nexus_omni_v9.py (:8004) NO se toca.
"""

from .map_core import (  # noqa: F401
    NEXUS_MAP_VERSION,
    NexusMap,
    parse_netguard_log,
)

__version__ = NEXUS_MAP_VERSION
