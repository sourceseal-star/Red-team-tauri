---
name: PHANTOM runtime compatibility
description: Compatibilidad del worker distribuido y regla de recuperación de tareas no terminales
---

El Master PHANTOM usa WebSocket de Starlette, mientras que el Node usa el cliente
`websockets`; el worker debe enviar mensajes con `send(json.dumps(...))`, no asumir
`send_json()` del servidor.

**Why:** las versiones modernas de `websockets` entregan `ClientConnection`, que no
expone `send_json`; esa diferencia permite que el nodo reciba tareas pero falle al
reportar estado, resultados o finalización.

**How to apply:** mantener un adaptador de envío JSON en el Node y probar siempre
handshake, asignación y estado terminal con el paquete `websockets` instalado.

Las tareas persistidas en estados no terminales deben volver a `queued` al arrancar
el Master o cuando se desconecta el nodo asignado. Solo las tareas `completed` y
`failed` deben salir de `pending_tasks`.

**Why:** el proceso del nodo puede morir por batería, red o actualización; dejar una
tarea como `assigned` la hace desaparecer de la operación aunque siga en SQLite o
Redis.

**How to apply:** al cambiar la cola o el protocolo de nodos, verificar también
reinicio del Master y desconexión durante una tarea en curso.