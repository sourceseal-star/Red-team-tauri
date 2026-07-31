// Auto-generated from Red-team report data
// This data is embedded in the app for offline use

import { ScanReport, Playbook, HistoryEntry } from './apiClient';

export const EMBEDDED_REPORT: ScanReport = {
  "started_at": "2026-07-29T11:30:05.477052",
  "finished_at": "2026-07-29T11:30:11.926060",
  "elapsed_seconds": 6.4,
  "total_findings": 24,
  "by_severity": {
    "critical": 2,
    "high": 12,
    "medium": 3,
    "low": 0,
    "info": 7
  },
  "findings": [
    {
      "scenario": "sourcesealcorp",
      "severity": "critical",
      "title": "4 controles de SOURCESEALCORP FALLARON",
      "description": "Ataques fallidos: A1(Reuso de hash anterior), A2(Time-lock bypass), A6(Replay attack), A7(Path traversal en página de recuperación)\n1 ataques en dry-run (backend no accesible).4 fallaron · 5 pasaron · 1 no ejecutados (backend offline)",
      "evidence_path": "/home/runner/workspace/redteam/evidence/scan-20260729-113005/sourceseal-attacks.json",
      "remediation": "Revisar cada control fallido. Detalle por ataque en el JSON.",
      "timestamp": "2026-07-29T11:30:11.325837"
    },
    {
      "scenario": "sourcesealcorp",
      "severity": "high",
      "title": "[A1] Reuso de hash anterior — FALLÓ",
      "description": "Esperado: rechazado (4xx) | Actual: 403\nRazón: backend NO rechazó: recibió 403",
      "evidence_path": "/home/runner/workspace/redteam/evidence/scan-20260729-113005/A1-hash-reuse.json",
      "remediation": "Corrige el control del ataque A1.",
      "timestamp": "2026-07-29T11:30:11.325846"
    },
    {
      "scenario": "sourcesealcorp",
      "severity": "high",
      "title": "[A2] Time-lock bypass — FALLÓ",
      "description": "Esperado: rechazado con 423/425/409 | Actual: 403\nRazón: time-lock NO activo: recibió 403",
      "evidence_path": "/home/runner/workspace/redteam/evidence/scan-20260729-113005/A2-timelock.json",
      "remediation": "Corrige el control del ataque A2.",
      "timestamp": "2026-07-29T11:30:11.325847"
    },
    {
      "scenario": "sourcesealcorp",
      "severity": "high",
      "title": "[A6] Replay attack — FALLÓ",
      "description": "Esperado: segundo envío rechazado | Actual: 403 → 403\nRazón: anti-replay AUSENTE: original=403, replay=403",
      "evidence_path": "/home/runner/workspace/redteam/evidence/scan-20260729-113005/A6-replay.json",
      "remediation": "Corrige el control del ataque A6.",
      "timestamp": "2026-07-29T11:30:11.325847"
    },
    {
      "scenario": "sourcesealcorp",
      "severity": "high",
      "title": "[A7] Path traversal en página de recuperación — FALLÓ",
      "description": "Esperado: todos rechazados | Actual: [200, 200, 200, 200, 200]\nRazón: path traversal posible: algún payload no fue rechazado",
      "evidence_path": "/home/runner/workspace/redteam/evidence/scan-20260729-113005/A7-traversal.json",
      "remediation": "Corrige el control del ataque A7.",
      "timestamp": "2026-07-29T11:30:11.325848"
    },
    {
      "scenario": "sourcesealcorp",
      "severity": "info",
      "title": "[A10] Blockchain confirm — NO EJECUTADO",
      "description": "SOURCESEAL_NODE no configurado",
      "evidence_path": "",
      "remediation": "Configura SOURCESEAL_API y verifica conectividad.",
      "timestamp": "2026-07-29T11:30:11.325849"
    },
    {
      "scenario": "multiplatform",
      "severity": "info",
      "title": "Plataforma detectada: Android",
      "description": "Archivo: dummy.apk, extensión: .apk",
      "evidence_path": "/home/runner/workspace/redteam/evidence/dummy.apk",
      "remediation": "N/A",
      "timestamp": "2026-07-29T11:30:11.603473"
    },
    {
      "scenario": "multiplatform",
      "severity": "high",
      "title": "Sin uso del almacén seguro nativo de Android",
      "description": "Esperado alguno de: AndroidKeyStore",
      "evidence_path": "/home/runner/workspace/redteam/evidence/scan-20260729-113005/multiplatform-strings.txt",
      "remediation": "Usar el mecanismo nativo: AndroidKeyStore. Nunca cifrar claves con contraseña hardcodeada.",
      "timestamp": "2026-07-29T11:30:11.603485"
    },
    {
      "scenario": "multiplatform",
      "severity": "high",
      "title": "Sin uso del CSPRNG nativo de Android",
      "description": "Esperado: SecureRandom|getRandom",
      "evidence_path": "/home/runner/workspace/redteam/evidence/scan-20260729-113005/multiplatform-strings.txt",
      "remediation": "Usar SIEMPRE el CSPRNG del SO. Nunca implementar RNG propio.",
      "timestamp": "2026-07-29T11:30:11.603486"
    },
    {
      "scenario": "multiplatform",
      "severity": "info",
      "title": "Check de servidor backend",
      "description": "Backend actual: https://empli.fi/arabela/?fbclid=IwVERDUATUSKdleHRuA2FlbQIxMABzcnRjBmFwcF9pZAwzNTA2ODU1MzE3MjgAAR7j62fWM4-lxCzG347z5vVDEQ879C3VJd9EKWhZT-VOJWSRJ1AlFYAMvY4A6Q_aem_N84fvIjKvTP42gnFWGI9Rg//v1. Verificar manualmente que el servidor Ubuntu tenga: ufw activo, fail2ban, TLS 1.2+ only, AppArmor/SELinux, logrotate, backups cifrados.",
      "evidence_path": "https://empli.fi/arabela/?fbclid=IwVERDUATUSKdleHRuA2FlbQIxMABzcnRjBmFwcF9pZAwzNTA2ODU1MzE3MjgAAR7j62fWM4-lxCzG347z5vVDEQ879C3VJd9EKWhZT-VOJWSRJ1AlFYAMvY4A6Q_aem_N84fvIjKvTP42gnFWGI9Rg//v1",
      "remediation": "Auditar hardening del servidor con lynis / oscap. Rotar claves SSH. Desactivar login con password.",
      "timestamp": "2026-07-29T11:30:11.603487"
    },
    {
      "scenario": "rng",
      "severity": "info",
      "title": "Entropía del sistema OK",
      "description": "Shannon entropy = 7.956 bits/byte",
      "evidence_path": "/home/runner/workspace/redteam/evidence/scan-20260729-113005/rng-sample.bin",
      "remediation": "N/A",
      "timestamp": "2026-07-29T11:30:11.605908"
    },
    {
      "scenario": "rng",
      "severity": "info",
      "title": "Auditar seeds en el binario",
      "description": "Revisar manualmente el binario/app por uso de time/pid como seed. Detectado uso potencial de time.time(); Detectado uso potencial de os.getpid()",
      "evidence_path": "/home/runner/workspace/redteam/evidence/dummy.apk",
      "remediation": "Usar exclusivamente CSPRNG del SO (SecRandomCopyBytes, getrandom, BCryptGenRandom).",
      "timestamp": "2026-07-29T11:30:11.605960"
    },
    {
      "scenario": "pinning",
      "severity": "info",
      "title": "Cert TLS del backend capturado",
      "description": "Host empli.fi:443 SHA256=7bd70be5c191c4f5...",
      "evidence_path": "/home/runner/workspace/redteam/evidence/scan-20260729-113005/pinning-cert.json",
      "remediation": "Comparar SHA256 contra el pin hardcodeado en la app móvil.",
      "timestamp": "2026-07-29T11:30:11.646635"
    },
    {
      "scenario": "pinning",
      "severity": "high",
      "title": "Sin evidencia de pinning en el APK",
      "description": "No se encontraron marcadores típicos (NetworkSecurityConfig, pin-set, OkHttp CertificatePinner).",
      "evidence_path": "/home/runner/workspace/redteam/evidence/scan-20260729-113005/apk-strings.txt",
      "remediation": "Implementar pinning vía OkHttp CertificatePinner o NSP en res/xml/.",
      "timestamp": "2026-07-29T11:30:11.646641"
    },
    {
      "scenario": "imei",
      "severity": "medium",
      "title": "Sin evidencia de validación Luhn de IMEI",
      "description": "No se encontraron marcadores de algoritmo Luhn. Riesgo: aceptar IMEIs malformados.",
      "evidence_path": "/home/runner/workspace/redteam/evidence/scan-20260729-113005/imei-strings.txt",
      "remediation": "Implementar Luhn check antes de aceptar IMEI. Validar también TAC (primeros 8 dígitos) contra base de GSMA.",
      "timestamp": "2026-07-29T11:30:11.656614"
    },
    {
      "scenario": "imei",
      "severity": "medium",
      "title": "Sin evidencia de consulta a blacklist (IMEI robado/perdido)",
      "description": "No se detectan referencias a GSMA blacklist. Riesgo: vender celular reportado como robado.",
      "evidence_path": "/home/runner/workspace/redteam/evidence/scan-20260729-113005/imei-strings.txt",
      "remediation": "Integrar API de blacklist (GSMA, Stolen Phone Check, etc.) antes de aceptar IMEI.",
      "timestamp": "2026-07-29T11:30:11.656619"
    },
    {
      "scenario": "sidechannel",
      "severity": "info",
      "title": "Sin comparación naive evidente",
      "description": "No se detectaron patrones sospechosos en el análisis estático.",
      "evidence_path": "/home/runner/workspace/redteam/evidence/scan-20260729-113005/sidechannel-strings.txt",
      "remediation": "Validar con microbenchmarks (medir tiempo en comparaciones válidas vs inválidas).",
      "timestamp": "2026-07-29T11:30:11.667023"
    },
    {
      "scenario": "keyhandling",
      "severity": "high",
      "title": "Sin uso detectable de KeyStore/Keychain nativo",
      "description": "No se encontraron marcadores de AndroidKeyStore ni iOS Keychain.",
      "evidence_path": "/home/runner/workspace/redteam/evidence/scan-20260729-113005/keyhandling-strings.txt",
      "remediation": "Migrar claves a KeyStore (Android) o Keychain (iOS) con protección StrongBox/biometric.",
      "timestamp": "2026-07-29T11:30:11.677296"
    },
    {
      "scenario": "payments",
      "severity": "high",
      "title": "Sin evidencia de verificación de firma en webhooks",
      "description": "No se detectaron constructEvent/verifyWebhookSignature/validateWebhook. Riesgo de webhook spoofing → pagos falsos confirmados.",
      "evidence_path": "/home/runner/workspace/redteam/evidence/scan-20260729-113005/payments-strings.txt",
      "remediation": "Implementar verificación criptográfica de TODOS los webhooks antes de marcar como pagado.",
      "timestamp": "2026-07-29T11:30:11.688332"
    },
    {
      "scenario": "recovery_page",
      "severity": "high",
      "title": "Headers de seguridad ausentes en página de recuperación",
      "description": "Faltan: x-frame-options, content-security-policy, x-content-type-options, strict-transport-security, referrer-policy",
      "evidence_path": "/home/runner/workspace/redteam/evidence/scan-20260729-113005/recovery-health.json",
      "remediation": "Añadir headers: X-Frame-Options DENY, CSP frame-ancestors 'none', HSTS 1 año, X-Content-Type-Options nosniff.",
      "timestamp": "2026-07-29T11:30:11.902984"
    },
    {
      "scenario": "recovery_page",
      "severity": "critical",
      "title": "Página de recuperación lista hashes SIN autenticación",
      "description": "GET /api/hashes devolvió 200 con 3000 bytes. Cualquiera con la URL puede listar biometrías.",
      "evidence_path": "/home/runner/workspace/redteam/evidence/scan-20260729-113005/recovery-noauth.json",
      "remediation": "AÑADIR AUTH inmediatamente. Requerir login + 2FA + audit log por acceso.",
      "timestamp": "2026-07-29T11:30:11.902993"
    },
    {
      "scenario": "recovery_page",
      "severity": "high",
      "title": "Endpoint de hash responde sin auth",
      "description": "GET /api/hashes/{id} devolvió 200. Si devuelve datos sin token válido, hay IDOR.",
      "evidence_path": "/home/runner/workspace/redteam/evidence/scan-20260729-113005/recovery-idor.json",
      "remediation": "Validar sesión + ownership antes de servir datos de hash.",
      "timestamp": "2026-07-29T11:30:11.902995"
    },
    {
      "scenario": "recovery_page",
      "severity": "medium",
      "title": "Vulnerable a clickjacking",
      "description": "Sin X-Frame-Options ni CSP frame-ancestors, la página puede ser embebida en iframes maliciosos.",
      "evidence_path": "/home/runner/workspace/redteam/evidence/scan-20260729-113005/recovery-clickjack.json",
      "remediation": "X-Frame-Options: DENY o CSP: frame-ancestors 'none'.",
      "timestamp": "2026-07-29T11:30:11.902996"
    },
    {
      "scenario": "recovery_page",
      "severity": "high",
      "title": "Sin evidencia de 2FA en la página de recuperación",
      "description": "Acciones críticas de rotación de hash sin segundo factor detectable.",
      "evidence_path": "/home/runner/workspace/redteam/evidence/scan-20260729-113005/recovery-2fa.json",
      "remediation": "Implementar TOTP/WebAuthn obligatorio para cualquier acción de recuperación.",
      "timestamp": "2026-07-29T11:30:11.902996"
    }
  ],
  "errors": [],
  "target": "/home/runner/workspace/redteam/evidence/dummy.apk",
  "backend": "https://empli.fi/arabela/?fbclid=IwVERDUATUSKdleHRuA2FlbQIxMABzcnRjBmFwcF9pZAwzNTA2ODU1MzE3MjgAAR7j62fWM4-lxCzG347z5vVDEQ879C3VJd9EKWhZT-VOJWSRJ1AlFYAMvY4A6Q_aem_N84fvIjKvTP42gnFWGI9Rg//v1",
  "scenarios_run": 11
};

export const EMBEDDED_PLAYBOOKS: Playbook[] = [
  {
    "name": "playbook_c2_beaconing",
    "description": "Response to C2 beaconing detected by NDR. Sinkhole the domain, block IPs at WAF, revoke ZTNA sessions for beaconing hosts, and alert SOC.",
    "mitre_techniques": [
      "T1071",
      "T1071.001"
    ],
    "severity": "HIGH",
    "steps": [
      {
        "id": "step_1",
        "name": "DNS Sinkhole C2 Domain",
        "handler": "dns_sinkhole",
        "params": {
          "sinkhole_ip": "127.0.0.1",
          "reason": "C2 beaconing domain"
        },
        "depends_on": [],
        "timeout_seconds": 20,
        "mitre_technique": "T1071"
      },
      {
        "id": "step_2",
        "name": "Block C2 IPs at WAF",
        "handler": "block_ip_waf",
        "params": {
          "waf_provider": "cloudflare",
          "block_reason": "C2 beaconing IP"
        },
        "depends_on": [
          "step_1"
        ],
        "timeout_seconds": 30,
        "rollback_handler": "unblock_ip_waf",
        "mitre_technique": "T1071"
      },
      {
        "id": "step_3",
        "name": "Revoke ZTNA Sessions",
        "handler": "revoke_ztna_session",
        "params": {
          "reason": "C2 beaconing containment"
        },
        "depends_on": [
          "step_2"
        ],
        "timeout_seconds": 30,
        "mitre_technique": "T1071"
      },
      {
        "id": "step_4",
        "name": "Alert SOC",
        "handler": "slack_alert",
        "params": {
          "alert_title": "C2 Beaconing Detected & Contained",
          "alert_message": "Domain sinkholed, IPs blocked at WAF, ZTNA sessions revoked. Investigate affected hosts.",
          "severity": "HIGH"
        },
        "depends_on": [
          "step_3"
        ],
        "timeout_seconds": 15,
        "mitre_technique": "T1071"
      }
    ],
    "status": "idle"
  },
  {
    "name": "playbook_credential_stuffing",
    "description": "Response to credential stuffing / brute force attack. Block source IPs at WAF (parallel with disabling accounts), then alert affected users.",
    "mitre_techniques": [
      "T1110",
      "T1110.004"
    ],
    "severity": "MEDIUM",
    "steps": [
      {
        "id": "step_1",
        "name": "Block Source IPs at WAF",
        "handler": "block_ip_waf",
        "params": {
          "waf_provider": "cloudflare",
          "block_reason": "Credential stuffing source IP",
          "rate_limit_threshold": 100
        },
        "depends_on": [],
        "timeout_seconds": 30,
        "rollback_handler": "unblock_ip_waf",
        "mitre_technique": "T1110"
      },
      {
        "id": "step_2",
        "name": "Disable Locked Accounts",
        "handler": "disable_user_auth",
        "params": {
          "auth_provider": "auth0",
          "reason": "Account locked after credential stuffing detection"
        },
        "depends_on": [],
        "timeout_seconds": 30,
        "mitre_technique": "T1110"
      },
      {
        "id": "step_3",
        "name": "Alert Users and SOC",
        "handler": "slack_alert",
        "params": {
          "alert_title": "Credential Stuffing Attack Mitigated",
          "alert_message": "Source IPs blocked, affected accounts temporarily disabled. Users should reset passwords and re-enable MFA.",
          "severity": "MEDIUM"
        },
        "depends_on": [
          "step_1",
          "step_2"
        ],
        "timeout_seconds": 15,
        "mitre_technique": "T1110"
      }
    ],
    "status": "idle"
  },
  {
    "name": "playbook_data_exfiltration",
    "description": "Critical response to data exfiltration. Block egress IPs at WAF, alert DPO per GDPR Art. 33 (parallel), then disable accounts involved in exfiltration.",
    "mitre_techniques": [
      "T1041",
      "T1048",
      "T1567"
    ],
    "severity": "CRITICAL",
    "steps": [
      {
        "id": "step_1",
        "name": "Block Egress IPs at WAF",
        "handler": "block_ip_waf",
        "params": {
          "waf_provider": "cloudflare",
          "block_reason": "Data exfiltration egress IP — CRITICAL"
        },
        "depends_on": [],
        "timeout_seconds": 30,
        "rollback_handler": "unblock_ip_waf",
        "mitre_technique": "T1041"
      },
      {
        "id": "step_2",
        "name": "Alert DPO — GDPR Article 33",
        "handler": "slack_alert",
        "params": {
          "alert_title": "🚨 DATA BREACH — GDPR Art. 33 Notification Required",
          "alert_message": "Data exfiltration detected. DPO must assess GDPR Art. 33 reporting obligation (72h window). Evidence capture in progress.",
          "severity": "CRITICAL"
        },
        "depends_on": [],
        "timeout_seconds": 15,
        "mitre_technique": "T1041"
      },
      {
        "id": "step_3",
        "name": "Freeze Implicated Accounts",
        "handler": "disable_user_auth",
        "params": {
          "auth_provider": "auth0",
          "reason": "Account frozen — data exfiltration investigation"
        },
        "depends_on": [
          "step_1",
          "step_2"
        ],
        "timeout_seconds": 30,
        "mitre_technique": "T1041"
      }
    ],
    "status": "idle"
  },
  {
    "name": "playbook_lateral_movement",
    "description": "Response to lateral movement detected within the network. Revoke ZTNA sessions and block pivot IPs (parallel), then alert SOC for manual investigation.",
    "mitre_techniques": [
      "T1021",
      "T1021.002",
      "T1550"
    ],
    "severity": "HIGH",
    "steps": [
      {
        "id": "step_1",
        "name": "Revoke ZTNA Sessions for Affected Hosts",
        "handler": "revoke_ztna_session",
        "params": {
          "reason": "Lateral movement detected — isolating affected hosts"
        },
        "depends_on": [],
        "timeout_seconds": 30,
        "mitre_technique": "T1021"
      },
      {
        "id": "step_2",
        "name": "Block Lateral Movement IPs at WAF",
        "handler": "block_ip_waf",
        "params": {
          "waf_provider": "cloudflare",
          "block_reason": "Lateral movement pivot IP"
        },
        "depends_on": [],
        "timeout_seconds": 30,
        "rollback_handler": "unblock_ip_waf",
        "mitre_technique": "T1021"
      },
      {
        "id": "step_3",
        "name": "Alert SOC",
        "handler": "slack_alert",
        "params": {
          "alert_title": "Lateral Movement Detected — Hosts Isolated",
          "alert_message": "ZTNA sessions revoked, pivot IPs blocked. Investigate affected hosts for credential theft and persistence mechanisms.",
          "severity": "HIGH"
        },
        "depends_on": [
          "step_1",
          "step_2"
        ],
        "timeout_seconds": 15,
        "mitre_technique": "T1021"
      }
    ],
    "status": "idle"
  },
  {
    "name": "playbook_phishing",
    "description": "Automated response to phishing attack. Quarantines email, disables compromised user if link was clicked, blocks sender IP at WAF, and alerts SOC.",
    "mitre_techniques": [
      "T1566",
      "T1566.001",
      "T1566.002"
    ],
    "severity": "HIGH",
    "steps": [
      {
        "id": "step_1",
        "name": "Quarantine Email",
        "handler": "quarantine_email",
        "params": {
          "email_provider": "o365",
          "action": "move_to_quarantine"
        },
        "depends_on": [],
        "timeout_seconds": 30,
        "rollback_handler": "restore_email",
        "mitre_technique": "T1566"
      },
      {
        "id": "step_2",
        "name": "Disable Compromised User",
        "handler": "disable_user_auth",
        "params": {
          "auth_provider": "auth0",
          "reason": "Phishing link clicked — account disabled pending investigation"
        },
        "depends_on": [
          "step_1"
        ],
        "timeout_seconds": 30,
        "continue_on_failure": false,
        "mitre_technique": "T1566"
      },
      {
        "id": "step_3",
        "name": "Block Sender IP at WAF",
        "handler": "block_ip_waf",
        "params": {
          "waf_provider": "cloudflare",
          "block_reason": "Phishing sender IP"
        },
        "depends_on": [
          "step_1"
        ],
        "timeout_seconds": 30,
        "rollback_handler": "unblock_ip_waf",
        "mitre_technique": "T1566.001"
      },
      {
        "id": "step_4",
        "name": "Alert SOC",
        "handler": "slack_alert",
        "params": {
          "alert_title": "Phishing Attack Detected & Contained",
          "alert_message": "Email quarantined, user disabled, sender IP blocked. Manual review required.",
          "severity": "HIGH"
        },
        "depends_on": [
          "step_2",
          "step_3"
        ],
        "timeout_seconds": 15,
        "mitre_technique": "T1566"
      }
    ],
    "status": "idle"
  },
  {
    "name": "playbook_ransomware",
    "description": "Critical response to ransomware incident. Sinkhole C2 domain and block C2 IPs in parallel, then revoke ZTNA sessions for affected hosts, and send executive alert.",
    "mitre_techniques": [
      "T1486",
      "T1071",
      "T1041"
    ],
    "severity": "CRITICAL",
    "steps": [
      {
        "id": "step_1",
        "name": "DNS Sinkhole C2 Domain",
        "handler": "dns_sinkhole",
        "params": {
          "sinkhole_ip": "127.0.0.1",
          "reason": "Ransomware C2 domain"
        },
        "depends_on": [],
        "timeout_seconds": 20,
        "mitre_technique": "T1071"
      },
      {
        "id": "step_2",
        "name": "Block C2 IPs at WAF",
        "handler": "block_ip_waf",
        "params": {
          "waf_provider": "cloudflare",
          "block_reason": "Ransomware C2 IP"
        },
        "depends_on": [],
        "timeout_seconds": 30,
        "rollback_handler": "unblock_ip_waf",
        "mitre_technique": "T1071"
      },
      {
        "id": "step_3",
        "name": "Revoke ZTNA Sessions for Affected Hosts",
        "handler": "revoke_ztna_session",
        "params": {
          "reason": "Ransomware containment — all sessions revoked"
        },
        "depends_on": [
          "step_1",
          "step_2"
        ],
        "timeout_seconds": 30,
        "mitre_technique": "T1486"
      },
      {
        "id": "step_4",
        "name": "Executive Alert",
        "handler": "slack_alert",
        "params": {
          "alert_title": "🚨 CRITICAL: Ransomware Detected — Immediate Action Taken",
          "alert_message": "C2 domains sinkholed, IPs blocked, ZTNA sessions revoked. Verify backups immediately. Incident response team notified.",
          "severity": "CRITICAL"
        },
        "depends_on": [
          "step_3"
        ],
        "timeout_seconds": 15,
        "mitre_technique": "T1486"
      }
    ],
    "status": "idle"
  }
];

export const EMBEDDED_HISTORY: HistoryEntry[] = [
  {
    "finished_at": "2026-07-22T09:41:26.400646",
    "total_findings": 23,
    "by_severity": {
      "critical": 2,
      "high": 10,
      "medium": 2,
      "low": 0,
      "info": 9
    }
  },
  {
    "finished_at": "2026-07-24T06:19:21.373262",
    "total_findings": 22,
    "by_severity": {
      "critical": 2,
      "high": 11,
      "medium": 3,
      "low": 0,
      "info": 6
    }
  },
  {
    "finished_at": "2026-07-27T14:22:28.086573",
    "total_findings": 24,
    "by_severity": {
      "critical": 2,
      "high": 13,
      "medium": 3,
      "low": 0,
      "info": 6
    }
  },
  {
    "finished_at": "2026-07-27T14:22:31.573355",
    "total_findings": 24,
    "by_severity": {
      "critical": 2,
      "high": 13,
      "medium": 3,
      "low": 0,
      "info": 6
    }
  },
  {
    "finished_at": "2026-07-27T14:26:32.442956",
    "total_findings": 24,
    "by_severity": {
      "critical": 2,
      "high": 13,
      "medium": 3,
      "low": 0,
      "info": 6
    }
  },
  {
    "finished_at": "2026-07-27T14:26:40.284275",
    "total_findings": 24,
    "by_severity": {
      "critical": 2,
      "high": 13,
      "medium": 3,
      "low": 0,
      "info": 6
    }
  },
  {
    "finished_at": "2026-07-27T14:27:59.321860",
    "total_findings": 24,
    "by_severity": {
      "critical": 2,
      "high": 13,
      "medium": 3,
      "low": 0,
      "info": 6
    }
  },
  {
    "finished_at": "2026-07-29T11:30:11.926060",
    "total_findings": 24,
    "by_severity": {
      "critical": 2,
      "high": 12,
      "medium": 3,
      "low": 0,
      "info": 7
    }
  }
];
