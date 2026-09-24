---
name: Frontend dist and tactical audit
description: Protección del bundle publicado y de la Auditoría táctica crítica
---

El arranque del frontend debe validar al menos las dependencias críticas además de comprobar si existe `node_modules`; un caché parcialmente instalado puede hacer que el build falle aunque el `package.json` y el lockfile sean correctos.

**Why:** El workflow encontró un `node_modules` presente pero sin la dependencia del mapa de topología, y omitió la reinstalación.

**How to apply:** Para cada dependencia que impida el build, usa un sentinel específico en el script de arranque y reinstala el proyecto correcto cuando falte.

**Nota de entorno:** El instalador genérico de paquetes puede operar sobre el `package.json` raíz; cuando el frontend vive en un subdirectorio, la instalación debe ejecutarse desde el launcher o workflow de ese subproyecto.

**Nota de artefactos:** Un reinicio del workflow mientras Vite está escribiendo
`dist/` puede dejar `index.html` y los chunks hash de builds distintos.

**Why:** La pantalla en blanco apareció porque el HTML pidió dos assets que no
existían; un build limpio volvió a alinear el índice y los chunks.

**How to apply:** Antes de una verificación visual, comprueba que cada
referencia `/assets/*` de `dist/index.html` exista en `dist/assets/`; después
reinicia el workflow una sola vez para cargar el build completo.

La Auditoría táctica (`redteam/modules/tactical_executor.py` y sus rutas del
dashboard) es un módulo crítico. Un republish no puede sustituir el `dist` de
la era actual por un bundle viejo, incompleto o mezclado: aunque el backend
siga presente, la Auditoría puede desaparecer de la interfaz o quedar
desconectada.

**Why:** Un republish anterior dañó la War Room al cambiar el bundle
compilado; el código fuente y el ejecutor táctico seguían intactos, pero la
interfaz publicada ya no representaba el sistema real.

**How to apply:** Tratar `tauri-frontend/dist` como artefacto protegido de la
misma entrega que el código frontend. Tras cada cambio o republish, verificar
la integridad de todos los assets y ejecutar la matriz `/api/readiness`,
confirmando `frontend_dist=ok` y `auditoria_tactica=ok` antes de considerar
válido el resultado.

**Nota de rastreo:** El validador también exige que los nuevos nombres hash de
Vite estén registrados en el índice de Git; un build correcto puede impedir el
arranque si esos artefactos todavía aparecen como no rastreados.

**Why:** El cambio de la pantalla Universe produjo hashes nuevos y el workflow
se detuvo antes de abrir el puerto aunque `npm run build` hubiera terminado bien.

**How to apply:** Después de un build limpio, alinea el índice de Git con el
`dist` completo, vuelve a ejecutar `validate_frontend_dist.py` y solo entonces
reinicia el workflow.

**Nota de sincronización:** Si una rebase del teléfono choca únicamente con
bundles bajo `tauri-frontend/dist/`, la versión publicada de `origin/main` es
la canónica; los conflictos de código nunca deben resolverse automáticamente.

**Why:** Los respaldos locales de `curar.sh` pueden incluir hashes de Vite que
ya fueron reemplazados en GitHub, aunque el código de la aplicación siga siendo
válido.

**How to apply:** Permitir una resolución acotada del `dist` generado y abortar
con restauración completa ante cualquier ruta fuera de ese directorio.