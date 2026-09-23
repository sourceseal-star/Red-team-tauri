---
name: Collaborative project rules
description: Durable safety and alignment rules for this multi-engineer, multi-agent project
---

Este proyecto es una construcción acumulativa de varios ingenieros, arquitectos y
agentes de IA. Las decisiones existentes, la documentación, los commits y las
reglas operativas forman parte del diseño; una sesión nueva debe alinearse con
ellos antes de proponer o aplicar cambios.

**Regla #1:** nunca hacer cambios destructivos sin confirmación explícita. Antes
de borrar, sobrescribir piezas sensibles, cambiar arquitectura o reescribir
historia, hay que preservar un punto de retorno, revisar el alcance y preguntar
si existe ambigüedad. Preferir cambios aditivos y verificables.

**Regla #56:** el Libro de Vida de Sol conserva hechos duraderos destilados,
separados de la memoria conversacional (`memory.jsonl`) y de la memoria
operativa (`sol_brain.db`). No mezclar estos tres papeles ni convertir la
memoria del proyecto en un depósito de datos personales.

**Why:** El repositorio ya contiene correcciones nacidas de errores reales de
sesiones anteriores; reemplazar o repetir trabajo sin leer ese contexto puede
romper integraciones que ya funcionan y perder decisiones importantes.

**How to apply:** Al iniciar una tarea, leer `LEEME_PRIMERO.md`, consultar las
reglas y documentación relevantes, localizar la fuente de verdad que realmente
se ejecuta y revisar el historial cuando haya dudas. Mantener cambios pequeños,
aditivos y con pruebas; si una acción puede ser destructiva o la intención no
está clara, detenerse y pedir confirmación explícita.