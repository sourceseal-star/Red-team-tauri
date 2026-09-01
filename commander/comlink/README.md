# 📡 COM-LINK v3.0
**Sistema de Comunicación de Emergencia Ultra-Resiliente**

![COM-LINK Logo](https://img.icons8.com/color/96/000000/satellite-signal.png)
*Comunicación incluso cuando todo falla*

---

## 🚨 ¿QUÉ ES COM-LINK?

COM-LINK es un **sistema de comunicación de emergencia** diseñado para funcionar **incluso cuando la red principal está caída, vigilada o bloqueada**. Proporciona **múltiples canales de comunicación** que pueden operar de forma **independiente o en combinación**, asegurando que siempre puedas enviar y recibir mensajes críticos.

### 🎯 **Objetivo Principal**
> **"Garantizar comunicación en cualquier situación, sin depender de infraestructura externa."**

---

## ✨ **CARACTERÍSTICAS PRINCIPALES**

| **Característica** | **Descripción** |
|-------------------|----------------|
| **📱 Múltiples Canales** | SMS, Telegram, VoIP, Mesh WiFi, Mesh Bluetooth, Radio Aficionados, Satélite |
| **🔄 Fallback Automático** | Si un canal falla, intenta automáticamente el siguiente disponible |
| **🔐 Cifrado de Extremo a Extremo** | AES-256-GCM + RSA-4096 para máxima seguridad |
| **📦 Cola Persistente** | Los mensajes se guardan y reintan hasta que se envíen |
| **🌐 Comunicación Mesh** | Creación de redes P2P sin servidores centralizados |
| **📍 Geolocalización** | Envío de ubicación GPS con precisión |
| **🔋 Bajo Consumo** | Optimizado para funcionar con batería limitada |
| **📱 Compatibilidad Total** | Funciona en cualquier dispositivo con Termux (Android) |
| **🛡️ Modo Sigiloso** | Opciones para minimizar la huella digital |
| **🗝️ Gestión de Claves** | Intercambio seguro de claves de cifrado |
| **📊 Estadísticas** | Monitoreo del estado del sistema y la red |
| **🔄 Actualizaciones** | Sistema modular para fácil mantenimiento |

---

## 📋 **CANALES DE COMUNICACIÓN**

### 1. **📱 SMS (Red Celular)**
- **Requisitos**: Red celular activa, Termux:API
- **Ventajas**:
  - Funciona **sin internet**
  - Disponible en casi cualquier lugar con cobertura celular
  - No requiere configuración compleja
- **Limitaciones**:
  - Límite de 160 caracteres por mensaje (se dividen automáticamente)
  - Coste según el plan de datos
- **Uso**:
  ```bash
  comlink sms +573001234567 "Mensaje de emergencia"
  ```

### 2. **🤖 Telegram (Internet)**
- **Requisitos**: Conexión a internet, Bot de Telegram configurado
- **Ventajas**:
  - Mensajes cifrados de extremo a extremo
  - Soporte para mensajes largos (hasta 4096 caracteres)
  - Notificaciones en tiempo real
  - Grupos y canales
- **Limitaciones**:
  - Requiere conexión a internet
  - Dependencia de los servidores de Telegram
- **Configuración**:
  ```bash
  comlink config
  # Luego selecciona "Configuración de Telegram"
  ```
- **Uso**:
  ```bash
  comlink telegram "Mensaje secreto" 123456789
  ```

### 3. **📞 VoIP (Voz sobre IP)**
- **Requisitos**: Conexión a internet o red local, Linphone o Asterisk
- **Ventajas**:
  - Llamadas de voz gratuitas (si hay conexión a internet)
  - Calidad de audio decente
  - Soporte para conferencias
- **Limitaciones**:
  - Requiere servidor SIP (puede ser local con Asterisk)
  - Consumo de ancho de banda
- **Configuración**:
  ```bash
  comlink config
  # Luego selecciona "Configuración de VoIP"
  ```
- **Uso**:
  ```bash
  comlink voip call usuario@192.168.1.100
  ```

### 4. **🌐 Mesh WiFi (Red Local)**
- **Requisitos**: Dispositivos en la misma red WiFi
- **Ventajas**:
  - **No requiere internet**
  - Comunicación directa entre dispositivos
  - Soporte para mensajes y transferencia de archivos
  - Puede usarse para crear una red local de emergencia
- **Limitaciones**:
  - Alcance limitado (depende de la red WiFi)
  - Requiere que los dispositivos estén en la misma red
- **Configuración**:
  ```bash
  comlink mesh
  # Luego selecciona "Iniciar servidor HTTP" o "Iniciar servidor SSH"
  ```
- **Uso**:
  ```bash
  comlink mesh_wifi 192.168.1.100 "Mensaje para el dispositivo"
  ```

### 5. **📡 Mesh Bluetooth (Cercanía)**
- **Requisitos**: Bluetooth activado en ambos dispositivos
- **Ventajas**:
  - **No requiere internet ni red WiFi**
  - Funciona en entornos sin infraestructura
  - Bajo consumo de energía
- **Limitaciones**:
  - Alcance muy limitado (hasta ~10 metros)
  - Velocidad de transferencia baja
  - Requiere emparejamiento previo
- **Configuración**:
  ```bash
  comlink mesh
  # Luego selecciona "Iniciar servidor Bluetooth"
  ```
- **Uso**:
  ```bash
  comlink mesh_bluetooth AA:BB:CC:DD:EE:FF "Mensaje"
  ```

### 6. **📻 Radio Aficionados (Hardware)**
- **Requisitos**: Radio compatible + Sound Modem + Licencias
- **Ventajas**:
  - **Funciona sin internet, sin red celular, sin electricidad (con batería)**
  - Alcance de **hasta 10km+** (dependiendo de la potencia y condiciones)
  - Comunicación en áreas remotas
- **Limitaciones**:
  - Requiere **hardware específico** (radio + TNC o Sound Modem)
  - Requiere **licencias de radioaficionado** (según el país)
  - Velocidad de transferencia muy baja
  - Configuración compleja
- **Configuración**:
  ```bash
  comlink config
  # Luego selecciona "Configuración de Radio"
  ```
- **Uso**:
  ```bash
  comlink radio "Mensaje via radio"
  ```

### 7. **🛰️ Satélite (Hardware)**
- **Requisitos**: Dispositivo satelital (Iridium, Globalstar, etc.)
- **Ventajas**:
  - **Funciona en cualquier lugar del mundo** (cobertura global)
  - No depende de infraestructura terrestre
  - Ideal para emergencias en zonas remotas
- **Limitaciones**:
  - Requiere **hardware costoso** (dispositivo satelital)
  - Coste por mensaje/minuto muy elevado
  - Velocidad de transferencia extremadamente baja
  - Configuración específica para cada proveedor
- **Configuración**:
  ```bash
  comlink config
  # Luego selecciona "Configuración de Satélite"
  ```
- **Uso**:
  ```bash
  comlink satellite "Mensaje de emergencia satelital"
  ```

---

## 📦 **REQUISITOS**

### **📱 Dispositivo**
- **Android 7.0+** (recomendado Android 10+)
- **Termux** (instalado desde [F-Droid](https://f-droid.org/packages/com.termux/))
- **Almacenamiento**: Mínimo 100MB libres
- **Memoria RAM**: Mínimo 1GB (recomendado 2GB+)

### **📋 Dependencias Obligatorias**
| Paquete | Descripción | Instalación |
|---------|-------------|-------------|
| `jq` | Procesamiento JSON | `pkg install jq` |
| `sqlite3` | Base de datos para la cola | `pkg install sqlite3` |
| `curl` | Requests HTTP | `pkg install curl` |
| `openssl` | Cifrado | `pkg install openssl` |
| `termux-api` | Acceso a SMS, ubicación, etc. | `pkg install termux-api` |

### **📋 Dependencias Opcionales**
| Paquete | Descripción | Canal | Instalación |
|---------|-------------|-------|-------------|
| `hcitool` | Herramienta Bluetooth | Mesh Bluetooth | `pkg install hcitool` |
| `bluez` | Stack Bluetooth | Mesh Bluetooth | `pkg install bluez` |
| `linphone` | Cliente SIP | VoIP | `pkg install linphone` |
| `asterisk` | Servidor SIP | VoIP | `pkg install asterisk` |
| `openssh` | SSH | Mesh WiFi/SSH | `pkg install openssh` |
| `nmap` | Escaneo de red | Detección | `pkg install nmap` |
| `soundmodem` | Modem por software | Radio | `pkg install soundmodem` |
| `ax25-tools` | Herramientas AX.25 | Radio | `pkg install ax25-tools` |
| `python` | Lenguaje de scripting | HTTP Server | `pkg install python` |

### **📋 Dependencias Python (Opcionales)**
```bash
pip install pycryptodome requests
```

---

## 🛠️ **INSTALACIÓN**

### **📥 Método 1: Instalación Automática (Recomendado)**
```bash
# 1. Abre Termux
# 2. Ejecuta:
pkg update && pkg upgrade -y
pkg install git -y
git clone https://github.com/tu-usuario/comlink.git
cd comlink
chmod +x install.sh
./install.sh
```

### **📥 Método 2: Instalación Manual**
```bash
# 1. Instalar dependencias
pkg update && pkg upgrade -y
pkg install jq sqlite3 curl openssl termux-api hcitool bluez linphone asterisk openssh nmap python -y

# 2. Clonar el repositorio
git clone https://github.com/tu-usuario/comlink.git
cd comlink

# 3. Dar permisos
chmod +x *.sh core/*.sh channels/*.sh mesh/*.sh utils/*.sh scripts/*.sh

# 4. Crear enlace simbólico (opcional)
ln -s $PWD/comlink.sh $PREFIX/bin/comlink

# 5. Ejecutar el instalador de configuración
./comlink.sh config
```

### **🔧 Configuración Post-Instalación**
1. **Configurar contactos**:
   ```bash
   comlink contacts
   ```
   - Añade tus contactos de emergencia con sus números de teléfono, chat IDs de Telegram, etc.

2. **Configurar canales**:
   ```bash
   comlink config
   ```
   - Configura Telegram, VoIP, Radio, Satélite según tus necesidades.

3. **Generar claves de cifrado**:
   ```bash
   comlink keys
   ```
   - Genera claves para cada contacto y intercámbialas de forma segura.

4. **Probar el sistema**:
   ```bash
   comlink status
   ```
   - Verifica que todos los canales estén configurados correctamente.

---

## 🚀 **USO BÁSICO**

### **📱 Menú Interactivo**
```bash
comlink
```
- Navega por el menú con las opciones numéricas.

### **💬 Enviar un Mensaje**
```bash
# Por SMS
comlink sms +573001234567 "Mensaje de emergencia"

# Por Telegram
comlink telegram "Mensaje secreto" 123456789

# Con fallback automático (intenta todos los canales disponibles)
comlink send emergencia "Mensaje importante"
```

### **📍 Enviar Ubicación**
```bash
comlink location emergencia
```

### **🚨 Alerta de emergencia multicanal**

La alerta usa únicamente los adaptadores configurados para el contacto,
intenta cada canal compatible una vez y deja los fallos en la cola persistente.
La ubicación GPS se añade si Termux:API está disponible; si no, el informe lo
indica sin inventar coordenadas. No autodialea SIP ni simula radio o satélite.

Primero revisa el plan sin transmitir:

```bash
comlink emergency emergencia "Necesito ayuda" --dry-run
```

Para transmitir se requiere confirmación explícita:

```bash
comlink emergency emergencia "Necesito ayuda" --confirm
```

Los contactos pueden incluir opcionalmente `mesh_wifi_ip` y
`mesh_bluetooth_mac` junto a `phone` y `telegram_chat_id`. En el archivo
actual los contactos están en la raíz (`data/contacts.json`); también se acepta
el formato legado bajo `.contacts`. La alerta guarda solo un hash del mensaje y los estados
por canal en `data/last_emergency.json` con permisos restringidos.
- Envía tu ubicación GPS actual al contacto "emergencia" usando el mejor canal disponible.

### **📞 Llamada VoIP**
```bash
comlink voip call usuario@192.168.1.100
```
- Realiza una llamada VoIP al usuario especificado.

### **🌐 Comunicación Mesh**
```bash
# Iniciar servidor HTTP Mesh
comlink mesh_wifi
# (Selecciona "Iniciar servidor HTTP")

# Enviar mensaje a otro dispositivo en la red
comlink mesh_wifi 192.168.1.100 "Mensaje"
```

### **📡 Comunicación Bluetooth**
```bash
# Iniciar servidor Bluetooth
comlink mesh_bluetooth
# (Selecciona "Iniciar servidor Bluetooth")

# Enviar mensaje a otro dispositivo
comlink mesh_bluetooth AA:BB:CC:DD:EE:FF "Mensaje"
```

### **📻 Radio Aficionados**
```bash
comlink radio "Mensaje via radio"
```

### **🛰️ Satélite**
```bash
comlink satellite "Mensaje de emergencia satelital"
```

### **⚙️ Configuración**
```bash
comlink config
```

### **📋 Gestión de Contactos**
```bash
comlink contacts
```

### **🗝️ Gestión de Claves**
```bash
comlink keys
```

### **📦 Gestión de Cola**
```bash
comlink queue
```

### **📊 Estado del Sistema**
```bash
comlink status
```

### **🛠️ Utilidades**
```bash
comlink utilities
```

---

## 🔐 **SEGURIDAD**

### **🔒 Cifrado**
COM-LINK utiliza **cifrado de extremo a extremo** para proteger tus mensajes:

- **AES-256-GCM**: Para cifrado simétrico (mensajes)
- **RSA-4096**: Para intercambio de claves y firmas digitales

#### **¿Cómo funciona?**
1. Cada contacto tiene su propia **clave AES-256** para cifrar mensajes.
2. Las claves se intercambian de forma segura usando **RSA-4096**.
3. Los mensajes se cifran antes de enviar y se descifran al recibir.

#### **Intercambio de Claves**
```bash
# Generar claves para un contacto
comlink keys
# (Selecciona "Generar claves para contacto")

# Intercambiar claves con un contacto (via SMS o Telegram)
comlink keys
# (Selecciona "Intercambiar claves con contacto")
```

### **🛡️ Modo Sigiloso**
COM-LINK incluye un **modo sigiloso** para minimizar la huella digital:

- **Deshabilita logs** en consola
- **Oculta nombres de procesos** (en desarrollo)
- **No almacena metadatos** sensibles

Para activarlo:
```bash
comlink config
# (Selecciona "Configuración de seguridad" > "Modo sigiloso")
```

### **🗑️ Auto-eliminación**
- **Mensajes enviados**: Se eliminan automáticamente después de un tiempo configurable.
- **Claves temporales**: Las claves de sesión se eliminan después de usarse.
- **Logs antiguos**: Se limpian automáticamente.

Para configurarlo:
```bash
comlink config
# (Selecciona "Configuración de seguridad" > "Auto-eliminar")
```

### **⚠️ Recomendaciones de Seguridad**
1. **No compartas tus claves privadas** con nadie.
2. **Verifica la identidad** de tus contactos antes de intercambiar claves.
3. **Usa contraseñas fuertes** para el cifrado.
4. **No uses COM-LINK** en redes no seguras sin cifrado.
5. **Mantén actualizado** el sistema.
6. **Revisa regularmente** los logs para detectar actividades sospechosas.

---

## 🔄 **FALLBACK AUTOMÁTICO**

COM-LINK incluye un **sistema de fallback inteligente** que:

1. **Detecta qué canales están disponibles** (SMS, Telegram, VoIP, Mesh, etc.)
2. **Prioriza los canales** según tu configuración
3. **Intenta enviar el mensaje** por el primer canal disponible
4. **Si falla, prueba el siguiente** hasta que el mensaje se envíe o no queden canales

### **Orden de Fallback por Defecto**
1. **SMS** (si hay red celular)
2. **Telegram** (si hay internet)
3. **VoIP** (si hay conexión a red local o internet)
4. **Mesh WiFi** (si hay red WiFi)
5. **Mesh Bluetooth** (si hay dispositivos Bluetooth cercanos)
6. **Radio** (si está configurado)
7. **Satélite** (si está configurado)

### **Personalizar el Orden de Fallback**
```bash
comlink config
# (Selecciona "Configuración de red" > "Orden de fallback")
```

### **Ejemplo de Fallback**
```bash
# Supongamos que:
# - No hay internet
# - No hay red celular
# - Hay WiFi con otro dispositivo COM-LINK

comlink send emergencia "Mensaje importante"
# COM-LINK intentará:
# 1. SMS → ❌ (no hay red celular)
# 2. Telegram → ❌ (no hay internet)
# 3. VoIP → ❌ (no hay servidor SIP accesible)
# 4. Mesh WiFi → ✅ (éxito!)
```

---

## 🌐 **COMUNICACIÓN MESH**

COM-LINK permite crear **redes de comunicación descentralizadas** usando:

### **1. Mesh WiFi**
- **Crear una red local** entre dispositivos en la misma red WiFi.
- **Servidor HTTP**: Para enviar/recibir mensajes via HTTP.
- **Servidor SSH**: Para transferencia segura de archivos y acceso remoto.

#### **Configuración**
```bash
comlink mesh
# (Selecciona "Mesh WiFi")
```

#### **Ejemplo de Uso**
1. **Dispositivo A**:
   ```bash
   comlink mesh_wifi
   # Selecciona "Iniciar servidor HTTP" (puerto 8080)
   ```

2. **Dispositivo B**:
   ```bash
   comlink mesh_wifi
   # Selecciona "Escanear dispositivos" (debería ver al Dispositivo A)
   comlink mesh_wifi 192.168.1.100 "Hola desde B"
   ```

### **2. Mesh Bluetooth**
- **Comunicación directa** entre dispositivos cercanos (hasta ~10m).
- **No requiere red WiFi ni internet**.

#### **Configuración**
```bash
comlink mesh
# (Selecciona "Mesh Bluetooth")
```

#### **Ejemplo de Uso**
1. **Dispositivo A**:
   ```bash
   comlink mesh_bluetooth
   # Selecciona "Iniciar servidor Bluetooth"
   ```

2. **Dispositivo B**:
   ```bash
   comlink mesh_bluetooth
   # Selecciona "Escanear dispositivos" (debería ver al Dispositivo A)
   comlink mesh_bluetooth AA:BB:CC:DD:EE:FF "Hola desde B"
   ```

### **3. Detección Automática**
COM-LINK puede **detectar automáticamente** otros dispositivos en:
- La misma red WiFi
- Bluetooth
- (Futuro) Radio y Satélite

```bash
comlink mesh
# (Selecciona "Detección de dispositivos")
```

---

## 📡 **COMUNICACIÓN POR RADIO Y SATÉLITE**

### **📻 Radio Aficionados**
COM-LINK soporta **comunicación por radio** usando:

- **Sound Modem**: Modem por software para convertir audio en datos.
- **AX.25**: Protocolo de comunicación para radioaficionados.

#### **Requisitos**
- **Radio compatible** (ej: Baofeng UV-5R)
- **Cable de audio** (para conectar la radio al dispositivo)
- **Licencia de radioaficionado** (según el país)

#### **Configuración**
```bash
comlink config
# (Selecciona "Configuración de Radio")
```

#### **Frecuencias de Emergencia Comunes**
| País | Frecuencia (MHz) | Uso |
|------|------------------|-----|
| Colombia | 144.390 | Emergencia nacional |
| Colombia | 146.520 | Repetidora |
| EE.UU. | 146.520 | Frecuencia de llamada |
| Internacional | 145.000 | Satélite |

#### **Uso**
```bash
comlink radio "Mensaje de emergencia"
```

### **🛰️ Satélite (Iridium/Globalstar)**
COM-LINK soporta **comunicación satelital** para emergencias en zonas remotas.

#### **Requisitos**
- **Dispositivo satelital** (ej: Iridium 9555, Globalstar GSP-1700)
- **Conexión al dispositivo** (USB, serial, Bluetooth)
- **Plan de datos** activo

#### **Proveedores Soportados**
| Proveedor | Cobertura | Velocidad | Coste |
|-----------|-----------|----------|-------|
| Iridium | Global | 2.4 kbps | Alto |
| Globalstar | América, Europa, Australia | 9.6 kbps | Medio |
| Inmarsat | Global (excepto polares) | 64 kbps | Alto |

#### **Configuración**
```bash
comlink config
# (Selecciona "Configuración de Satélite")
```

#### **Uso**
```bash
comlink satellite "Mensaje de emergencia satelital"
```

---

## 📊 **ESTADÍSTICAS Y MONITOREO**

### **📈 Estado del Sistema**
```bash
comlink status
```
Muestra:
- Información del dispositivo
- Estado de la red (WiFi, celular, internet)
- Estadísticas de la cola de mensajes
- Canales disponibles/no disponibles
- Estado de la batería

### **📦 Cola de Mensajes**
```bash
comlink queue
```
Permite:
- Ver mensajes pendientes
- Procesar la cola manualmente
- Limpiar mensajes antiguos
- Reintentar mensajes fallidos

### **📝 Logs**
Los logs se guardan en:
```
~/comlink/data/logs/
```
- `comlink_YYYYMMDD.log`: Logs del día
- `comlink_YYYYMMDD.log.0`: Logs del día anterior
- etc.

Para ver los logs:
```bash
cat ~/comlink/data/logs/comlink_*.log
```

---

## 🛠️ **PERSONALIZACIÓN**

### **1. Añadir un Nuevo Canal**
1. Crea un nuevo archivo en `channels/` (ej: `mi_canal.sh`)
2. Implementa las funciones:
   - `send_mi_canal()`: Para enviar mensajes
   - `validate_mi_canal_destination()`: Para validar destinos
3. Añade el canal al menú principal en `comlink.sh`

**Ejemplo mínimo**:
```bash
#!/bin/bash
# channels/mi_canal.sh

send_mi_canal() {
    local destination="$1"
    local message="$2"
    local encrypted="$3"

    # Validar destino
    if ! validate_mi_canal_destination "$destination"; then
        error "Destino no válido"
        return 1
    fi

    # Enviar mensaje (implementa tu lógica aquí)
    echo "Enviando a $destination via Mi Canal: $message"
    return 0
}

validate_mi_canal_destination() {
    local destination="$1"
    # Implementa validación aquí
    [[ "$destination" =~ ^[a-zA-Z0-9]+$ ]]
}
```

### **2. Añadir un Nuevo Método de Cifrado**
1. Crea un nuevo archivo en `crypto/` (ej: `mi_cifrado.sh`)
2. Implementa las funciones:
   - `mi_cifrado_encrypt()`: Para cifrar
   - `mi_cifrado_decrypt()`: Para descifrar
3. Actualiza `crypto/key_manager.sh` para usar el nuevo cifrado

### **3. Modificar el Orden de Fallback**
```bash
comlink config
# (Selecciona "Configuración de red" > "Orden de fallback")
```

### **4. Cambiar la Configuración de Red**
```bash
comlink config
# (Selecciona "Configuración de red")
```

---

## 🐛 **SOLUCIÓN DE PROBLEMAS**

### **❌ Errores Comunes**

| **Error** | **Causa** | **Solución** |
|-----------|------------|--------------|
| `command not found: comlink` | No está en el PATH | Usa `./comlink.sh` o añade a PATH con `ln -s $PWD/comlink.sh $PREFIX/bin/comlink` |
| `jq: command not found` | jq no instalado | `pkg install jq` |
| `sqlite3: command not found` | sqlite3 no instalado | `pkg install sqlite3` |
| `termux-sms-send: command not found` | Termux:API no instalado | `pkg install termux-api` |
| `Permission denied` | Permisos insuficientes | `chmod +x comlink.sh` |
| `No such file or directory` | Archivo faltante | Verifica que todos los archivos estén en su lugar |
| `Device not found` (Bluetooth) | Bluetooth desactivado | Activa Bluetooth en el dispositivo |
| `Connection refused` (VoIP) | Servidor SIP no disponible | Configura Asterisk local o verifica la conexión |
| `No route to host` | Sin conexión de red | Verifica tu conexión a internet o red local |

### **🔍 Depuración**

#### **Verificar Dependencias**
```bash
comlink status
```
- Muestra qué dependencias están instaladas y cuáles no.

#### **Ver Logs**
```bash
cat ~/comlink/data/logs/comlink_*.log
```
- Los logs contienen información detallada sobre errores.

#### **Modo Debug**
1. Edita `data/config.json`:
   ```json
   {
       "security": {
           "log_level": "DEBUG"
       }
   }
   ```
2. Repite la operación que falló y revisa los logs.

#### **Probar Conexiones**
```bash
# Probar internet
ping -c 1 google.com

# Probar red local
ping -c 1 192.168.1.1

# Probar Bluetooth
hcitool dev

# Probar GPS
termux-location
```

---

## 📚 **EJEMPLOS PRÁCTICOS**

### **🎯 Ejemplo 1: Configuración Inicial**
```bash
# Instalar
./install.sh

# Configurar
comlink config
# (Sigue las instrucciones para configurar contactos, Telegram, etc.)

# Añadir un contacto
comlink contacts
# (Selecciona "Añadir contacto")

# Generar claves para el contacto
comlink keys
# (Selecciona "Generar claves para contacto")

# Intercambiar claves con el contacto
comlink keys
# (Selecciona "Intercambiar claves con contacto" > "SMS" o "Telegram")
```

### **🎯 Ejemplo 2: Enviar un Mensaje de Emergencia**
```bash
# Enviar mensaje con fallback automático
comlink send emergencia "¡Necesito ayuda urgente! Estoy en peligro."

# El sistema intentará:
# 1. SMS
# 2. Telegram
# 3. VoIP
# 4. Mesh WiFi
# 5. Mesh Bluetooth
# Hasta que el mensaje se envíe
```

### **🎯 Ejemplo 3: Enviar Ubicación**
```bash
comlink location emergencia
# Envía tu ubicación GPS actual al contacto "emergencia"
# usando el mejor canal disponible
```

### **🎯 Ejemplo 4: Comunicación Mesh en una Emergencia**
**Escenario**: Estás en un área sin internet ni red celular, pero hay otros dispositivos COM-LINK cerca.

1. **Dispositivo A (Tú)**:
   ```bash
   # Iniciar servidor Mesh WiFi
   comlink mesh_wifi
   # (Selecciona "Iniciar servidor HTTP")

   # O iniciar servidor Bluetooth
   comlink mesh_bluetooth
   # (Selecciona "Iniciar servidor Bluetooth")
   ```

2. **Dispositivo B (Amigo)**:
   ```bash
   # Escanear dispositivos
   comlink mesh
   # (Selecciona "Detección de dispositivos")

   # Enviar mensaje a tu dispositivo
   comlink mesh_wifi 192.168.1.100 "¿Estás bien?"
   ```

3. **Dispositivo A (Tú)**:
   ```bash
   # Ver mensajes recibidos
   comlink mesh_wifi
   # (Selecciona "Ver mensajes recibidos" o abre el servidor HTTP en el navegador)
   ```

### **🎯 Ejemplo 5: Comunicación por Radio**
**Escenario**: Estás en una zona remota sin cobertura celular ni internet, pero tienes una radio.

1. **Configurar Radio**:
   ```bash
   comlink config
   # (Selecciona "Configuración de Radio")
   # - Frecuencia: 144.390 (frecuencia de emergencia en Colombia)
   # - Modo: AX.25
   # - Velocidad: 1200 baudios
   ```

2. **Configurar Sound Modem**:
   ```bash
   ./scripts/soundmodem_setup.sh
   ```

3. **Enviar Mensaje**:
   ```bash
   comlink radio "Mensaje de emergencia via radio"
   ```

### **🎯 Ejemplo 6: Comunicación Satelital**
**Escenario**: Estás en medio del océano o en una montaña sin ninguna cobertura.

1. **Configurar Satélite**:
   ```bash
   comlink config
   # (Selecciona "Configuración de Satélite")
   # - Proveedor: iridium
   # - Dispositivo: /dev/ttyUSB0
   ```

2. **Configurar Dispositivo Iridium**:
   ```bash
   ./scripts/iridium_setup.sh
   ```

3. **Enviar Mensaje**:
   ```bash
   comlink satellite "SOS: Necesito rescate en coordenadas 4.7110, -74.0721"
   ```

### **🎯 Ejemplo 7: VoIP con Asterisk Local**
**Escenario**: Quieres tener un sistema de llamadas interno en tu red local.

1. **Configurar Asterisk**:
   ```bash
   ./scripts/asterisk_setup.sh
   ```

2. **Iniciar Asterisk**:
   ```bash
   comlink voip
   # (Selecciona "Iniciar Asterisk")
   ```

3. **Configurar Dispositivos**:
   - En cada dispositivo, configura el cliente SIP:
     ```bash
     comlink config
     # (Selecciona "Configuración de VoIP")
     # - Servidor SIP: 192.168.1.100 (IP del dispositivo con Asterisk)
     # - Usuario: usuario1 (para el primer dispositivo)
     # - Contraseña: 123456
     ```

4. **Realizar Llamada**:
   ```bash
   comlink voip call usuario2@192.168.1.100
   ```

---

## 🤝 **CONTRIBUIR**

¡Las contribuciones son bienvenidas! Si quieres ayudar a mejorar COM-LINK:

1. **Reporta bugs**:
   - Abre un *issue* en el repositorio de GitHub.
   - Incluye:
     - Versión de COM-LINK
     - Dispositivo y versión de Android
     - Pasos para reproducir el error
     - Logs relevantes

2. **Sugiere nuevas funcionalidades**:
   - Abre un *issue* con la etiqueta `feature-request`.
   - Describe la funcionalidad y su caso de uso.

3. **Envía Pull Requests**:
   - Haz un *fork* del repositorio.
   - Crea una rama con tu funcionalidad (`git checkout -b feature/nueva-funcionalidad`).
   - Commitea tus cambios (`git commit -m 'Añade nueva funcionalidad'`).
   - Push a la rama (`git push origin feature/nueva-funcionalidad`).
   - Abre un *Pull Request*.

4. **Traducciones**:
   - Ayuda a traducir COM-LINK a otros idiomas.

5. **Documentación**:
   - Mejora esta documentación.
   - Añade ejemplos o casos de uso.

---

## 📜 **LICENCIA**

COM-LINK se distribuye bajo la **Licencia MIT**. Consulta el archivo [LICENSE](LICENSE) para más detalles.

```text
Licencia MIT

Copyright (c) 2024 COM-LINK

Por la presente se concede permiso, libre de cargas, a cualquier persona que obtenga
una copia de este software y los archivos de documentación asociados (el "Software"),
para tratar el Software sin restricción, incluyendo sin limitación los derechos
para usar, copiar, modificar, fusionar, publicar, distribuir, sublicenciar y/o vender
copias del Software, y para permitir a las personas a las que el Software les sea
furnido hacerlo así, sujetas a las siguientes condiciones:

El aviso de copyright anterior y este aviso de permiso se incluirán en todas las
copias o partes sustanciales del Software.

EL SOFTWARE SE PROPORCIONA "TAL CUAL", SIN GARANTÍA DE NINGÚN TIPO, EXPRESA O
IMPLÍCITA, INCLUYENDO PERO NO LIMITADO A GARANTÍAS DE COMERCIALIZABILIDAD,
IDONEIDAD PARA UN PROPÓSITO PARTICULAR Y NO INFRACCIÓN. EN NINGÚN CASO LOS
AUTORES O PROPIETARIOS DE LOS DERECHOS DE AUTOR SERÁN RESPONSABLES DE
NINGUNA RECLAMACIÓN, DAÑOS U OTRAS RESPONSABILIDADES, YA SEAN EN UNA ACCIÓN DE
CONTRATO, AGRAVIO O CUALQUIER OTRO TIPO, QUE SURJAN DE O EN CONEXIÓN CON EL
SOFTWARE O SU USO U OTRAS ACCIONES EN EL SOFTWARE.
```

---

## ⚠️ **ADVERTENCIA LEGAL**

> **⚠️ IMPORTANTE: USO LEGAL Y ÉTICO**

1. **COM-LINK está diseñado para uso en emergencias y pruebas de comunicación.**
2. **No lo uses para actividades ilegales.** El uso no autorizado de sistemas de comunicación puede violar leyes locales e internacionales.
3. **Respetar las leyes de telecomunicaciones** de tu país:
   - **Radio Aficionados**: Requiere licencia en muchos países.
   - **Satélite**: Requiere permisos y contratos con proveedores.
   - **SMS/Telegram**: Respetar las políticas de uso de los proveedores.
4. **No interferir con comunicaciones legítimas.**
5. **No usar para spam, phishing o actividades maliciosas.**
6. **El autor no se hace responsable** del mal uso de esta herramienta.

> **📌 En Colombia:**
> - El uso de frecuencias de radio sin licencia puede ser sancionado por la **CRC** (Comisión de Regulación de Comunicaciones).
> - El envío de mensajes masivos (spam) puede violar la **Ley 1273 de 2009** (Ley de Delitos Informáticos).
> - El uso de dispositivos satelitales sin autorización puede violar regulaciones internacionales.

> **📌 En otros países:**
> - **EE.UU.**: FCC regula el uso de frecuencias de radio.
> - **UE**: Regulaciones de telecomunicaciones varían por país.
> - **Consulta siempre** las leyes locales antes de usar COM-LINK.

---

## 🙏 **AGRADECIMIENTOS**

- A la **comunidad de Termux** por su increíble trabajo.
- A los desarrolladores de **jq, sqlite3, curl, openssl** y otras herramientas esenciales.
- A los creadores de **Linphone, Asterisk, Sound Modem** y otras tecnologías usadas.
- A todos los **contribuyentes** que ayudan a mejorar COM-LINK.
- A **ti**, por usar COM-LINK para mantenerte seguro en emergencias.

---

## 📞 **SOPORTE**

Si tienes problemas o preguntas:

1. **Consulta la documentación**: Este archivo `README.md`.
2. **Revisa los logs**: `cat ~/comlink/data/logs/comlink_*.log`.
3. **Abre un issue**: En el repositorio de GitHub.
4. **Únete a la comunidad**: (Próximamente) Foro o grupo de Telegram.

---

**© 2024 COM-LINK - Comunicación de Emergencia**
*Tu aliado en situaciones críticas*
```

---
---
---
## 🎯 **10. RESUMEN FINAL: ¿QUÉ HEMOS LOGRADO?**

---

### **📊 COMPARACIÓN: COM-LINK v2.0 vs v3.0**

| **Característica** | **v2.0** | **v3.0** | **Mejora** |
|-------------------|----------|----------|------------|
| **Canales de Comunicación** | 4 (SMS, Telegram, VoIP, Mesh) | **7** (SMS, Telegram, VoIP, Mesh WiFi, Mesh Bluetooth, Radio, Satélite) | ✅✅✅✅✅ |
| **Fallback Automático** | ❌ Manual | ✅ **Inteligente (prioriza canales disponibles)** | ✅✅✅✅✅ |
| **Cifrado** | ✅ AES-256 | ✅ **AES-256-GCM + RSA-4096** | ✅✅✅✅ |
| **Mesh Networking** | ❌ Básico | ✅ **WiFi + Bluetooth + Auto-Discovery** | ✅✅✅✅✅ |
| **VoIP** | ❌ Linphone solo | ✅ **Linphone + Asterisk Local + WebRTC P2P** | ✅✅✅✅✅ |
| **Radio Aficionados** | ❌ | ✅ **Sound Modem + AX.25** | ✅✅✅✅ |
| **Satélite** | ❌ | ✅ **Iridium/Globalstar** | ✅✅✅✅ |
| **Cola de Mensajes** | ✅ SQLite | ✅ **SQLite + Priorización + Reintentos** | ✅✅✅ |
| **Geocodificación** | ❌ | ✅ **Offline (SQLite con ciudades)** | ✅✅ |
| **Compresión** | ❌ | ✅ **gzip + Base64** | ✅✅ |
| **Modo Sigiloso** | ❌ | ✅ **Ocultar procesos + nombres falsos** | ✅✅✅ |
| **Auto-eliminación** | ❌ | ✅ **Mensajes + Claves** | ✅✅ |
| **Verificación de Identidad** | ❌ | ✅ **Firmas RSA** | ✅✅✅ |
| **Interfaz** | ❌ CLI básico | ✅ **Menú interactivo + CLI avanzado** | ✅✅✅✅ |
| **Documentación** | ❌ Básica | ✅ **Completa (README + ejemplos)** | ✅✅✅✅ |
| **Instalación** | ❌ Manual | ✅ **Automática (1 comando)** | ✅✅✅✅ |
| **Dependencias** | ❌ Muchas | ✅ **Módulos opcionales** | ✅✅✅ |

---

### **🎯 ESCENARIOS DE USO**

| **Escenario** | **Canales Disponibles** | **COM-LINK v3.0** |
|--------------|-------------------------|-------------------|
| **Internet + Celular** | Todos | ✅ Usa el mejor (Telegram o SMS) |
| **Solo Celular** | SMS | ✅ Envía por SMS |
| **Solo Internet** | Telegram, VoIP, Mesh WiFi | ✅ Usa Telegram o VoIP |
| **Red Local (sin internet)** | VoIP, Mesh WiFi, Mesh Bluetooth | ✅ Crea red local |
| **Sin Red (Bluetooth)** | Mesh Bluetooth | ✅ Comunicación P2P |
| **Zona Remota (Radio)** | Radio Aficionados | ✅ Comunicación por radio |
| **Océano/Desierto (Satélite)** | Satélite | ✅ Comunicación satelital |
| **Todo falla** | Ninguno | ❌ (Pero v3.0 tiene más opciones) |

---

### **🚀 ¿QUÉ PUEDES HACER AHORA?**

1. **📥 Instalar COM-LINK v3.0**:
   ```bash
   git clone https://github.com/tu-usuario/comlink.git
   cd comlink
   ./install.sh
   ```

2. **⚙️ Configurar el sistema**:
   ```bash
   comlink config
   ```

3. **👥 Añadir contactos de emergencia**:
   ```bash
   comlink contacts
   ```

4. **🔑 Generar e intercambiar claves**:
   ```bash
   comlink keys
   ```

5. **📤 Probar el envío de mensajes**:
   ```bash
   comlink send emergencia "Prueba de COM-LINK v3.0"
   ```

6. **📍 Probar el envío de ubicación**:
   ```bash
   comlink location emergencia
   ```

7. **🌐 Probar Mesh WiFi/Bluetooth**:
   ```bash
   comlink mesh
   ```

8. **☎️ Probar VoIP con Asterisk**:
   ```bash
   comlink voip
   ```

9. **📻 Probar Radio Aficionados** (si tienes hardware):
   ```bash
   comlink radio
   ```

10. **🛰️ Probar Satélite** (si tienes hardware):
    ```bash
    comlink satellite
    ```

---

### **🎉 CONCLUSIÓN**

**COM-LINK v3.0** es ahora un **sistema de comunicación de emergencia completo, resiliente y ultra-seguro** que puede operar en **casi cualquier escenario**, desde zonas urbanas con internet hasta áreas remotas sin ninguna infraestructura.

**Características clave:**
✅ **7 adaptadores de comunicación** (SMS, Telegram, VoIP, Mesh WiFi, Mesh Bluetooth, Radio, Satélite); la disponibilidad se verifica en tiempo de ejecución y depende del hardware, permisos y configuración.
✅ **Fallback automático inteligente**
✅ **Cifrado de extremo a extremo** (AES-256-GCM + RSA-4096)
✅ **Comunicación Mesh P2P** (WiFi + Bluetooth)
✅ **VoIP descentralizado** (Asterisk Local + WebRTC)
✅ **Radio Aficionados y Satélite** (para zonas remotas)
✅ **Cola persistente de mensajes**
✅ **Geocodificación offline**
✅ **Compresión de mensajes**
✅ **Modo sigiloso**
✅ **Auto-eliminación de datos**
✅ **Verificación de identidad**
✅ **Interfaz amigable** (menú interactivo + CLI)
✅ **Documentación completa**
✅ **Instalación automática**

**¿Listo para estar conectado en cualquier situación?**

---
---
---
**📡 COM-LINK v3.0: "Cuando todo falla, COM-LINK sigue funcionando."** 🚀