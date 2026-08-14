#!/data/data/com.termux/files/usr/bin/python3
"""
MURCIÉLAGO RECEIVER v2.0 — Escucha ultrasonidos y decodifica
Uso: python murcielago_receiver.py [--duration 12]

Protocolo: WAV ← micrófono → FFT → detectar tonos duales 18-20 kHz → hex → texto
Sin internet. Solo micrófono + numpy.
"""

import os
import sys
import time
import struct
import tempfile
import subprocess
import numpy as np

# Tabla inversa de frecuencias
FREQ_TABLE_INV = {
    (18000, 18400): '0', (18100, 18500): '1', (18200, 18600): '2',
    (18300, 18700): '3', (18400, 18800): '4', (18500, 18900): '5',
    (18600, 19000): '6', (18700, 19100): '7', (18800, 19200): '8',
    (18900, 19300): '9', (19000, 19400): 'A', (19100, 19500): 'B',
    (19200, 19600): 'C', (19300, 19700): 'D', (19400, 19800): 'E',
    (19500, 19900): 'F', (18000, 19500): '#', (18500, 20000): '*'
}

SYNC_FREQ = 19500
SAMPLE_RATE = 48000
DURATION_SYMBOL = 0.08
SILENCE_BETWEEN = 0.025
FFT_WINDOW = int(SAMPLE_RATE * 0.05)  # 50 ms


def record_audio(duration=12):
    """Graba desde el micrófono y guarda WAV temporal."""
    temp_wav = tempfile.NamedTemporaryFile(suffix='.wav', delete=False).name
    try:
        subprocess.run(['termux-microphone-record', 'start'], timeout=1, check=False)
        print(f"🎤 Grabando {duration} segundos...")
        time.sleep(duration)
        subprocess.run(['termux-microphone-record', 'stop'], timeout=1, check=False)
        src = os.path.expanduser('~/storage/downloads/recording.wav')
        if os.path.exists(src):
            os.rename(src, temp_wav)
        else:
            raise Exception("Archivo no creado por termux-microphone-record")
    except Exception:
        # Fallback: ffmpeg con ALSA o arecord
        try:
            subprocess.run(
                ['ffmpeg', '-f', 'alsa', '-i', 'default', '-t', str(duration),
                 '-ar', str(SAMPLE_RATE), '-ac', '1', temp_wav],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False, timeout=duration + 5
            )
        except Exception:
            try:
                subprocess.run(
                    ['arecord', '-d', str(duration), '-r', str(SAMPLE_RATE), '-c', '1', '-f', 'S16_LE', temp_wav],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False, timeout=duration + 5
                )
            except Exception:
                print("⚠️  No se pudo grabar. Instala: pkg install ffmpeg termux-microphone-record")
                return None
    return temp_wav


def detect_frequencies(audio_path, step_ms=50):
    """Detecta pares de frecuencias en el audio usando FFT."""
    with open(audio_path, 'rb') as f:
        f.seek(44)  # Saltar cabecera WAV
        data = f.read()
    samples = np.frombuffer(data, dtype=np.int16)

    if len(samples) == 0:
        return []

    step = int(SAMPLE_RATE * (step_ms / 1000.0))
    detected_symbols = []

    # Buscar sincronización
    sync_start = -1
    for i in range(0, len(samples) - FFT_WINDOW, step):
        window = samples[i:i+FFT_WINDOW].astype(np.float64)
        fft_vals = np.abs(np.fft.rfft(window))
        freqs = np.fft.rfftfreq(len(window), 1/SAMPLE_RATE)
        idx = np.argmin(np.abs(freqs - SYNC_FREQ))
        if fft_vals[idx] > 2000:
            sync_start = i
            break

    if sync_start == -1:
        return []

    print(f"🔍 Sincronización encontrada en {sync_start/SAMPLE_RATE:.2f}s")

    pos = sync_start + int(SAMPLE_RATE * 0.35)

    while pos < len(samples) - FFT_WINDOW:
        window = samples[pos:pos+FFT_WINDOW].astype(np.float64)
        fft_vals = np.abs(np.fft.rfft(window))
        freqs = np.fft.rfftfreq(len(window), 1/SAMPLE_RATE)

        # Buscar picos en 18-20 kHz
        valid_indices = []
        for idx, f in enumerate(freqs):
            if 17800 <= f <= 20100 and fft_vals[idx] > 1000:
                valid_indices.append((idx, fft_vals[idx], f))
        valid_indices.sort(key=lambda x: x[1], reverse=True)

        if len(valid_indices) >= 2:
            f1 = valid_indices[0][2]
            f2 = valid_indices[1][2]
            best_match = None
            best_dist = float('inf')
            for (a, b) in FREQ_TABLE_INV.keys():
                dist = abs(a - f1) + abs(b - f2)
                if dist < best_dist:
                    best_dist = dist
                    best_match = (a, b)
            if best_match and best_dist < 150:
                sym = FREQ_TABLE_INV.get(best_match, '?')
                detected_symbols.append(sym)
                print(f"  ✅ Símbolo: {sym} (f1={f1:.0f}, f2={f2:.0f})")
            else:
                detected_symbols.append('?')
        else:
            detected_symbols.append(' ')

        pos += int(SAMPLE_RATE * (DURATION_SYMBOL + SILENCE_BETWEEN))

    return detected_symbols


def decode_message(symbols):
    """Interpreta símbolos: HEX → ASCII con verificación de checksum."""
    raw = ''.join(symbols)
    if '*' in raw:
        parts = raw.split('*')
        if len(parts) >= 2:
            hex_data = parts[0]
            checksum_hex = parts[1][:2]
            if all(c in '0123456789ABCDEF' for c in hex_data) and len(hex_data) % 2 == 0:
                try:
                    byte_data = bytes.fromhex(hex_data)
                    calc_checksum = sum(byte_data) % 256
                    if calc_checksum == int(checksum_hex, 16):
                        return byte_data.decode('utf-8', errors='ignore')
                    else:
                        return f"⚠️ Checksum incorrecto (esperado {checksum_hex}, calculado {calc_checksum:02X})"
                except Exception:
                    return "❌ Error al decodificar hex"
    return "❌ No se pudo decodificar el mensaje"


def receive_message(duration=12):
    """Escucha y decodifica un mensaje. Devuelve el texto decodificado."""
    print("🦇 MURCIÉLAGO RECEIVER — Escuchando...")
    audio_file = record_audio(duration=duration)
    if not audio_file or not os.path.exists(audio_file):
        return "❌ No se pudo grabar audio"

    print("📡 Procesando señal...")
    symbols = detect_frequencies(audio_file)
    if audio_file and os.path.exists(audio_file):
        os.unlink(audio_file)

    if symbols:
        raw = ''.join(symbols)
        print(f"📥 Símbolos crudos: {raw}")
        return decode_message(symbols)
    else:
        return "❌ No se detectó señal."


if __name__ == "__main__":
    duration = 12
    if '--duration' in sys.argv:
        idx = sys.argv.index('--duration')
        if idx + 1 < len(sys.argv):
            duration = int(sys.argv[idx + 1])

    result = receive_message(duration=duration)
    print(f"📨 Mensaje recibido: {result}")
