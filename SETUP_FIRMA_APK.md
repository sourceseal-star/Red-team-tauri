# Configuración de firma APK — Instrucciones desde el celular

## ¿Por qué es necesario?
Android identifica apps por su firma digital. Si el APK tiene **siempre la misma firma**,
Android instala la actualización **encima** sin borrar datos ni configuración.
Sin firma consistente = hay que desinstalar cada vez.

---

## Paso 1 — Agregar los 4 secrets a GitHub

Ve a tu repo en GitHub desde el celular:
**Settings → Secrets and variables → Actions → New repository secret**

Agrega estos 4 secrets exactamente con estos nombres y valores:

---

### Secret 1: `KEYSTORE_BASE64`
```
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
```

---

### Secret 2: `KEY_ALIAS`
```
sourceseal
```

---

### Secret 3: `STORE_PASSWORD`
```
SourceSeal2026!
```

---

### Secret 4: `KEY_PASSWORD`
```
SourceSeal2026!
```

---

## Paso 2 — Disparar el primer build

Desde el celular, en GitHub:
**Actions → Build Android APK → Run workflow → Run workflow**

Espera ~15-20 minutos. Al terminar aparece en **Releases**.

---

## Paso 3 — Instalar en el Moto Edge 50 Fusion

1. Ve a **GitHub → Releases** desde el celular
2. Descarga el `.apk` más reciente
3. Abre el archivo desde **Gestión de archivos**
4. Si aparece el aviso de "fuentes desconocidas":
   - Toca **Ajustes** en el diálogo
   - Activa **"Permitir de esta fuente"** para Chrome/tu navegador
   - Regresa y toca **Instalar**
5. ✅ Listo — abre **SourceSeal Console**

---

## Paso 4 — Actualizaciones futuras (sin desinstalar)

Cada vez que hagas un **push** al repo, GitHub Actions compila y publica
un nuevo Release automáticamente. Para actualizar:

1. Descarga el nuevo `.apk` de Releases
2. Instálalo directamente — Android detecta la misma firma y **actualiza sin borrar datos**

---

## ⚠️ Guarda el keystore

El archivo `signing/sourceseal.keystore` está en el workspace.
**No lo pierdas** — si cambias de keystore, Android te obliga a desinstalar
la app antes de instalar la nueva versión.

El archivo `signing/` está en `.gitignore` para no subir la clave privada al repo.
Guarda una copia segura (Google Drive, etc.) del archivo `.keystore`.
