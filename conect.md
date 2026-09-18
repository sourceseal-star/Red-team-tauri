# SourceSeal — Plan seguro de conexión y operación

## Propósito

Este documento define cómo conectar proveedores externos y cómo operar los
módulos sensibles sin exponer credenciales ni activar acciones de red por
accidente.

La regla principal es:

> Detectar y validar primero. Ejecutar acciones operativas solo después de una
> confirmación explícita y dentro de un alcance autorizado.

No se deben pegar claves en el frontend, en el chat, en Git, en reportes ni en
logs.

---

## 1. Reglas internas que no se deben romper

- No ejecutar acciones destructivas o que cambien tráfico sin confirmación
  explícita.
- No activar Chaos automáticamente al arrancar el backend ni al detectar una
  clave.
- No tocar ni reemplazar Sol, War Room, AppShell ni componentes críticos.
- Mantener el backend unificado en `redteam/scripts/dashboard_server.py`.
- No modificar la copia antigua `backend/dashboard_server.py`.
- Mantener las credenciales en Secrets administrados o en el mecanismo seguro
  del entorno, nunca en código fuente.
- Respetar el alcance autorizado antes de cualquier escaneo.
- Preferir primero comprobaciones de presencia y validaciones de solo lectura.
- Reiniciar el workflow después de cambios de Secrets cuando el proceso pueda
  haber cacheado una variable al importar un módulo.

---

## 2. Nombres canónicos de Secrets

El código debe leer estos nombres exactos:

| Proveedor | Secret esperado | Requisitos |
|---|---|---|
| Shodan | `SHODAN_API_KEY` | Una API key |
| Hunter.io | `HUNTER_API_KEY` | Una API key |
| AbuseIPDB | `ABUSEIPDB_KEY` | Una API key |
| VirusTotal | `VIRUSTOTAL_API_KEY` | Una API key |
| Censys | `CENSYS_API_ID` | ID |
| Censys | `CENSYS_API_SECRET` | Secret |
| GitHub | `GITHUB_TOKEN` | Token con el alcance mínimo necesario |
| Google CSE | `GOOGLE_API_KEY` | API key |
| Google CSE | `GOOGLE_CSE_ID` | ID del motor de búsqueda |
| Brave | `BRAVE_API_KEY` | Opcional; existe fallback HTML |

### Problema conocido

El entorno puede tener `SHODAN_KEY`, pero los módulos esperan
`SHODAN_API_KEY`. No se deben duplicar claves en archivos. La solución segura es
usar el nombre canónico en Secrets o implementar una normalización controlada
en el backend, sin imprimir el valor.

### Comprobación segura

El estado de inteligencia debe distinguir entre:

1. Secret ausente.
2. Secret presente.
3. Credencial validada.
4. Credencial rechazada, expirada o sin créditos.

El estado “presente” por sí solo no demuestra que una API funcione.

---

## 3. Dónde deben vivir las claves

La fuente preferida es Secrets administrados por el entorno de ejecución.

No se deben guardar claves completas en `ops_config.json`. El endpoint de
configuración operativa puede inyectar variables en memoria, pero persistir
secretos completos en un archivo local aumenta el riesgo de exposición,
copias accidentales y respaldos inseguros.

Si se conserva configuración operativa en disco:

- Guardar solo nombres, estados y metadatos no sensibles.
- Enmascarar valores en cualquier respuesta de configuración.
- No escribir valores en logs.
- No devolver valores al frontend.
- Usar Secrets para el valor real.

Después de modificar un Secret:

1. Reiniciar `SourceSeal Dashboard`.
2. Consultar el estado protegido de inteligencia.
3. Ejecutar una validación mínima de lectura.
4. Confirmar que el proveedor responde sin mostrar la clave.

---

## 4. Uso seguro por proveedor

### Shodan

- Usar `SHODAN_API_KEY`.
- Validar primero con una consulta de información de cuenta o una consulta
  host mínima.
- Las IP privadas no tienen datos de Shodan público; el sistema puede usar
  enriquecimiento local separado.
- No confundir escaneo local con datos indexados por Shodan.

### Hunter.io

- `HUNTER_API_KEY` puede estar configurada aunque el tab actual no la use.
- El análisis local de email debe ser el comportamiento predeterminado:
  formato, MX, SPF, DMARC y proveedor.
- Hunter debe ser una acción opcional y explícita, porque envía información a
  un tercero y consume límites de la cuenta.
- La respuesta debe guardar solo los campos necesarios.
- No registrar emails completos ni respuestas completas en logs.

### Censys

- Requiere los dos valores: `CENSYS_API_ID` y `CENSYS_API_SECRET`.
- Solo consultar objetivos públicos compatibles con el proveedor.
- Rechazar de forma clara IPs privadas y no presentar “sin resultados” como
  si fuera un fallo del sistema.

### VirusTotal

- Usar `VIRUSTOTAL_API_KEY`.
- Mostrar el origen real de los datos.
- No subir archivos ni enviar indicadores sensibles sin una acción explícita.

### Google CSE y Brave

- Google requiere `GOOGLE_API_KEY` y `GOOGLE_CSE_ID`.
- Brave puede usar API o fallback de búsqueda pública.
- Los fallbacks no deben presentarse como resultados de una API autenticada.

### GitHub

- Usar `GITHUB_TOKEN` con el mínimo alcance.
- Consultar repositorios y perfiles públicos salvo autorización adicional.
- No guardar tokens, secretos detectados ni contenido sensible innecesario.

---

## 5. Chaos: mantenerlo desactivado por defecto

Hay dos conceptos distintos:

### Black Mirror Chaos local

El módulo actual genera reglas y scripts locales con `iptables` y `netcat`.
Puede modificar tráfico real. Por seguridad:

- No se ejecuta al arrancar.
- No se activa por tener una clave.
- Requiere confirmación explícita del operador.
- Debe mostrar previamente puerto, destino, banner y efecto.
- Debe tener una ruta clara para desactivar o revertir la regla.
- Debe ejecutarse únicamente en una red y un equipo autorizados.

### Chaos externo

Si se trata de ProjectDiscovery Chaos u otro proveedor externo, actualmente no
hay una integración de API activa. Una prueba gratuita no se consume ni se
activa automáticamente. La integración futura debe incluir:

1. Secret separado y con nombre documentado.
2. Validación de cuenta de solo lectura.
3. Límite de consultas y caché.
4. Indicador visible de fuente y estado.
5. Interruptor independiente, apagado por defecto.
6. Confirmación explícita antes de usarlo en una operación.

---

## 6. Auditoría Táctica

Auditoría Táctica es un módulo prioritario y debe conservar este flujo:

1. Confirmar que el operador tiene autorización.
2. Introducir una subred/CIDR concreta siempre que sea posible.
3. Evitar el autodetectado cuando exista riesgo de escanear una red no
   autorizada.
4. Lanzar el trabajo asíncrono.
5. Consultar el estado mediante el `job_id`.
6. Mostrar progreso y errores reales.
7. Generar el informe sellado con SHA-256.
8. Descargar el informe solo desde la ruta protegida.

El motor realiza descubrimiento TCP, identificación de cámaras y pruebas de
credenciales por defecto. Por eso debe utilizarse únicamente en activos
propios o expresamente autorizados.

El panel debe:

- Enviar el token de sesión a carga de diccionarios, puertos, lanzamiento,
  polling y descarga.
- Mostrar 401/403/4xx/5xx como errores claros.
- No quedarse indefinidamente en estado de escaneo si el backend rechaza una
  petición.
- Tratar un resultado vacío como resultado válido, no como error.
- No mostrar credenciales en logs del navegador.
- Mantener la notificación externa opcional y controlada.

---

## 7. Checklist antes de considerar una conexión lista

- [ ] El nombre del Secret coincide exactamente con la tabla.
- [ ] La clave no aparece en código, Git, frontend ni logs.
- [ ] El backend se reinició después del cambio.
- [ ] El estado distingue presencia de validez.
- [ ] Se ejecutó una comprobación de solo lectura.
- [ ] El proveedor y la fuente aparecen en el resultado.
- [ ] El alcance autorizado está confirmado.
- [ ] Chaos sigue apagado.
- [ ] Auditoría Táctica carga sus catálogos sin error.
- [ ] Auditoría Táctica puede iniciar y consultar un job autenticado.
- [ ] Un 401 no deja el panel bloqueado en “Escaneando”.
- [ ] El informe sellado y su hash se pueden descargar.

---

## 8. Prioridad recomendada

1. Mantener Chaos apagado.
2. Corregir el nombre `SHODAN_API_KEY`.
3. Validar presencia y conectividad sin exponer claves.
4. Evitar persistir secretos completos en configuración operativa.
5. Conectar Hunter como acción explícita del flujo de email.
6. Verificar completamente Auditoría Táctica en un alcance autorizado.
7. Evaluar una integración externa de Chaos solo después de lo anterior.
