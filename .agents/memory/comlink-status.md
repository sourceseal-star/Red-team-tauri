---
name: COM-LINK status semantics
description: Distinguishes the local COM-LINK core from optional physical communication channels.
---

`available` debe representar que el núcleo COM-LINK y sus comandos locales están operativos. La disponibilidad de SMS, Telegram, VoIP, mesh, radio y satélite se expresa por separado con `channels_ready`, `ready_channels` y `ready_count`.

**Why:** En Replit/PC el núcleo puede ejecutar consultas del dispositivo y administrar la cola aunque Termux:API, SIM, credenciales o hardware de radio no estén presentes. Marcar todo COM-LINK como no disponible oculta capacidades funcionales y hace que el dashboard parezca caído.

**How to apply:** Mantener las acciones locales visibles, mostrar los canales físicos como no listos con su razón, y exigir confirmación explícita para cola, ubicación transmitida y cualquier envío. No simular entregas cuando un adaptador/hardware no está configurado.