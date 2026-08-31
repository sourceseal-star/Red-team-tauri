---
name: Nexus Omni access
description: Replit access constraint and credential boundary for the Nexus Omni service
---

En Replit, el puerto interno de Nexus Omni no debe ser el único camino de
acceso del usuario. El dashboard unificado en :8001 es la superficie estable:
debe iniciar Nexus y proxyficar su UI y sus llamadas API.

**Why:** El navegador del usuario accede al dominio proxificado del dashboard,
no al `localhost:8004` del proceso. Una UI que conserve rutas absolutas de Nexus
puede verse, pero queda sin estado ni acciones.

**How to apply:** Mantener la autenticación Basic entre el dashboard y Nexus,
usar `.env` protegido o variables del entorno para las credenciales y hacer que
la UI proxificada use rutas relativas bajo `/api/nexus`.