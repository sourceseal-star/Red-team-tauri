# Runbook — Respuesta a Incidentes Enterprise

## Flujo de Respuesta Automática

```
Sensor detecta → XDR correlaciona → SOAR ejecuta playbook → ZTNA aplica acción → TIP propaga IoC
```

---

## Playbook 1: C2 Beaconing + Exfiltración (CRITICAL)

**Trigger:** NDR detecta beaconing + exfiltración low-and-slow desde misma IP
**MITRE:** T1071, T1573, T1041

### Respuesta automática (SOAR):
1. `block_ip` — Bloquear IP en WAF por 24h
2. `isolate_endpoint` — Aislar dispositivo en ZTNA (solo /api/health)
3. `revoke_tokens` — Revocar todos los JWT del usuario afectado

### Respuesta manual (SOC):
1. Verificar si el beaconing es legítimo (API monitoring, health checks)
2. Si confirmado: extender bloqueo a 72h, crear caso en TheHive
3. Revisar logs de exfiltración: ¿qué datos salieron?
4. Notificar al equipo legal si hay datos de clientes

---

## Playbook 2: Evasión de Debugger + Inyección (CRITICAL)

**Trigger:** RASP detecta Frida/Xposed + inyección de proceso
**MITRE:** T1622, T1055, T1027

### Respuesta automática (SOAR):
1. `kill_app_session` — Enviar push de revocación a la app móvil
2. `revoke_tokens` — Revocar JWT del dispositivo
3. `quarantine_device` — Cuarentena completa (block IP 72h + aislamiento)

### Respuesta manual (SOC):
1. Identificar el dispositivo afectado (device_id)
2. Revisar si hay otros dispositivos del mismo usuario comprometidos
3. Forzar re-autenticación con MFA para todos los dispositivos del usuario
4. Documentar evidencia para forense

---

## Playbook 3: Movimiento Lateral vía Deception (CRITICAL)

**Trigger:** Canary token consumido o decoy endpoint accedido
**MITRE:** T1550, T1074, T1005

### Respuesta automática (SOAR):
1. `isolate_endpoint` — Aislar dispositivo que consumió el canary
2. `block_ip` — Bloquear IP por 24h
3. `alert_soc` — Crear caso en TheHive + notificar Slack
4. `revoke_tokens` — Revocar todas las sesiones

### Respuesta manual (SOC):
1. Identificar qué token fue consumido y desde dónde
2. Trazar el camino: ¿cómo llegó el atacante al canary?
3. Revisar accesos recientes desde la misma IP/subred
4. Si hay múltiples canaries consumidos: escalar a incidente mayor

---

## Playbook 4: Credenciales Comprometidas (HIGH)

**Trigger:** Brute force detectado + acceso exitoso posterior
**MITRE:** T1110, T1556, T1550

### Respuesta automática (SOAR):
1. `revoke_tokens` — Revocar todas las sesiones JWT
2. `force_reauth` — Forzar re-autenticación con MFA
3. `block_ip` — Bloquear IP de origen del brute force

### Respuesta manual (SOC):
1. Verificar si el acceso exitoso fue legítimo
2. Revisar actividad de la cuenta comprometida post-acceso
3. Notificar al usuario sobre el evento
4. Si hay acceso administrativo comprometido: escalar a CRITICAL

---

## Playbook 5: DoS / Rate Limit Saturado (HIGH)

**Trigger:** ZTNA reporta >5 denegaciones por rate limit en 30s
**MITRE:** T1499

### Respuesta automática (SOAR):
1. `rate_limit` — Reducir límite a 10 req/min por 1h
2. `block_ip` — Bloquear IP por 24h
3. `alert_soc` — Notificar al SOC

### Respuesta manual (SOC):
1. Verificar si es tráfico legítimo (lanzamiento, campaña)
2. Si es DDoS distribuido: activar Cloudflare/WAF rules adicionales
3. Monitorear recursos del servidor (CPU, memoria, DB connections)

---

## Playbook 6: Reconocimiento + Explotación API (HIGH)

**Trigger:** Escaneo de servicios + intento de exploit en API pública
**MITRE:** T1046, T1595, T1190

### Respuesta automática (SOAR):
1. `block_ip` — Bloquear IP por 24h
2. `rate_limit` — Rate limit agresivo
3. `alert_soc` — Notificar

### Respuesta manual (SOC):
1. Revisar qué endpoints fueron escaneados
2. Verificar si algún exploit tuvo éxito (revisar response codes)
3. Si hay explotación exitosa: escalar a CRITICAL y ejecutar playbook de contención

---

## Matriz de Severidad y SLA

| Severidad | SLA Respuesta | SLA Contención | Notificar a |
|---|---|---|---|
| CRITICAL | < 30 segundos (auto) | < 5 minutos (auto) | SOC + CEO + Legal |
| HIGH | < 1 minuto (auto) | < 15 minutos (auto+manual) | SOC |
| MEDIUM | < 5 minutos (auto) | < 1 hora (manual) | SOC |
| LOW | < 15 minutos | < 4 horas | Log only |

---

## Contactos de Escalación

| Nivel | Rol | Cuándo |
|---|---|---|
| L1 | SOC Analyst | Todos los incidentes HIGH/CRITICAL |
| L2 | Security Engineer | Incidentes CRITICAL no resueltos en 15 min |
| L3 | CISO / CEO | Exfiltración confirmada o compromiso de admin |
| Legal | Equipo Legal | Si hay datos de clientes comprometidos |

---

## Post-Incidente

Después de cada incidente CRITICAL:
1. Recolectar evidencia (logs XDR, reportes NDR, capturas RASP)
2. Generar reporte post-incidente con timeline
3. Actualizar reglas de correlación XDR si es necesario
4. Actualizar blocklist TIP con nuevos IoCs
5. Lessons learned documentado en `/reports/post-incident-{date}.md`
