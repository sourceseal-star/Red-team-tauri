---
name: Ghost Radio safety boundary
description: Alcance operativo de Ghost Radio v3 y criterio para habilitar transmisión
---

Ghost Radio v3 debe permanecer en diagnóstico local y probes de streaming dentro
de un alcance confirmado. No debe implementar ni anunciar transmisión AX.25, SDR,
TNC o escritura en puertos serie mientras no exista hardware, driver, protocolo y
prueba controlada verificables.

**Why:** el proyecto ya tenía un script de radio que podía devolver éxito después
de escribir texto directamente en un puerto supuesto; eso no demostraba una
transmisión real y podía dar una falsa sensación de capacidad.

**How to apply:** mantener separados el diagnóstico, el reconocimiento autorizado
y cualquier futura TX. Un cambio de TX debe exigir un adaptador concreto, una
confirmación explícita de alcance y pruebas con un dispositivo propio.