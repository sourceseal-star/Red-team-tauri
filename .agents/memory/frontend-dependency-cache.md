---
name: Frontend dependency cache
description: Entorno donde el caché de node_modules puede existir aunque falten paquetes declarados por el frontend
---

El arranque del frontend debe validar al menos las dependencias críticas además de comprobar si existe `node_modules`; un caché parcialmente instalado puede hacer que el build falle aunque el `package.json` y el lockfile sean correctos.

**Why:** El workflow encontró un `node_modules` presente pero sin la dependencia del mapa de topología, y omitió la reinstalación.

**How to apply:** Para cada dependencia que impida el build, usa un sentinel específico en el script de arranque y reinstala el proyecto correcto cuando falte.

**Nota de entorno:** El instalador genérico de paquetes puede operar sobre el `package.json` raíz; cuando el frontend vive en un subdirectorio, la instalación debe ejecutarse desde el launcher o workflow de ese subproyecto.