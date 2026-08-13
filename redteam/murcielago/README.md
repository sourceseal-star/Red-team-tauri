# 🦇 Protocolo MURCIÉLAGO v2.0

Comunicación por ultrasonidos (18-20 kHz) — sin internet, WiFi, Bluetooth, SMS ni satélite.

## Principio

Usa el altavoz y micrófono del dispositivo para transmitir datos en frecuencias 
prácticamente inaudibles (18-20 kHz). Los codecs de voz recortan este rango, 
por lo que las grabaciones ambientales no capturan la señal.

## Instalación (Termux)

```bash
pkg update && pkg upgrade
pkg install python ffmpeg termux-microphone-record
pip install numpy
```

Dar permisos de micrófono a Termux en Android.

## Uso

### Emisor
```bash
python murcielago_sender.py "SOS 192.168.1.10"
python murcielago_sender.py "TORRE 3: 04:30" --farol  # Modo Farol (3 repeticiones)
```

### Receptor
```bash
python murcielago_receiver.py
python murcielago_receiver.py --duration 20  # Grabar 20 segundos
```

## Protocolo

1. Texto → bytes UTF-8 → hex + checksum (suma mod 256)
2. Cada símbolo hex (0-9, A-F, *, #) → dos tonos simultáneos (18-20 kHz)
3. Sync: tono fijo de 19.5 kHz al inicio y final
4. Receptor: FFT → detectar picos → decodificar hex → verificar checksum → texto

## Configuración

| Parámetro | Default | Descripción |
|-----------|---------|-------------|
| `DURATION_SYMBOL` | 0.08s | Duración de cada símbolo |
| `SILENCE_BETWEEN` | 0.025s | Silencio entre símbolos |
| `SAMPLE_RATE` | 48000 Hz | Frecuencia de muestreo |
| `FFT_WINDOW` | 50 ms | Ventana de análisis FFT |

### Larga distancia (hasta 15m)
Aumentar `DURATION_SYMBOL` a 0.15 y `FFT_WINDOW` a 100 ms.

### 100% inaudible (>20 kHz)
Sumar +2000 Hz a todas las frecuencias. Cuidado: algunos teléfonos recortan >20 kHz.

## API del Backend

```
POST /api/murcielago/send    {"message": "texto"}       → genera y reproduce WAV
GET  /api/murcielago/receive?duration=12                 → graba y decodifica
GET  /api/murcielago/generate-wav?message=texto          → devuelve WAV sin reproducir
```

## Ventajas

- Cero huellas de red (sin logs, sin metadatos, sin conexiones)
- Resistente a grabaciones ambientales (codecs recortan 18-20 kHz)
- Checksum criptográfico simple (detección de manipulación)
- Modo Farol (repeticiones para entornos ruidosos)
- 100% offline y auto-contenido
