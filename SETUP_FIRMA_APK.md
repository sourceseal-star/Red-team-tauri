# Configuración de firma APK — Instrucciones

## ¿Por qué es necesario?
Android identifica apps por su firma digital. Si el APK tiene **siempre la misma firma**,
Android instala la actualización **encima** sin borrar datos ni configuración.
Sin firma consistente = hay que desinstalar cada vez.

---

## Paso 1 — Crear el keystore localmente

En tu computador (no en el repo):

```bash
keytool -genkey -v \
  -keystore sourceseal.keystore \
  -alias sourceseal \
  -keyalg RSA -keysize 2048 \
  -validity 10000 \
  -storepass TU_PASSWORD \
  -keypass TU_PASSWORD
```

Guarda el archivo `.keystore` en un lugar seguro. **NO lo subas a GitHub.**

---

## Paso 2 — Agregar los 4 secrets a GitHub

Ve a tu repo en GitHub:
**Settings → Secrets and variables → Actions → New repository secret**

| Secret | Valor |
|---|---|
| `KEYSTORE_BASE64` | Base64 del archivo .keystore (`base64 sourceseal.keystore`) |
| `KEY_ALIAS` | El alias que usaste al crear el keystore (ej: `sourceseal`) |
| `STORE_PASSWORD` | La contraseña del keystore |
| `KEY_PASSWORD` | La contraseña de la clave |

---

## Paso 3 — Disparar el build

Desde GitHub:
**Actions → Build Android APK → Run workflow → Run workflow**

Espera ~15-20 minutos. Al terminar aparece en **Releases**.

---

## Paso 4 — Instalar en el Moto Edge 50 Fusion

1. Ve a **GitHub → Releases** desde el celular
2. Descarga el `.apk` más reciente
3. Abre el archivo desde **Gestión de archivos**
4. Instala (permitir fuentes desconocidas si pide)
