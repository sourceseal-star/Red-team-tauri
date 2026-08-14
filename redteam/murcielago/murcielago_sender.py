#!/data/data/com.termux/files/usr/bin/python3
"""
MURCIÉLAGO SENDER v2.0 — Transmite texto por ultrasonidos (18-20 kHz)
Uso: python murcielago_sender.py "mensaje"
Ejemplo: python murcielago_sender.py "SOS 192.168.1.10"

Protocolo: texto → hex → tonos duales (18-20 kHz) → WAV → ffplay
Sin internet, WiFi, Bluetooth, SMS ni satélite. Solo altavoz.
"""

import sys
import math
import struct
import tempfile
import subprocess
import os

# Frecuencias base (todas > 18 kHz) — punto dulce: inaudible pero reproducible
FREQ_TABLE = {
    '0': (18000, 18400), '1': (18100, 18500), '2': (18200, 18600),
    '3': (18300, 18700), '4': (18400, 18800), '5': (18500, 18900),
    '6': (18600, 19000), '7': (18700, 19100), '8': (18800, 19200),
    '9': (18900, 19300), 'A': (19000, 19400), 'B': (19100, 19500),
    'C': (19200, 19600), 'D': (19300, 19700), 'E': (19400, 19800),
    'F': (19500, 19900), '#': (18000, 19500), '*': (18500, 20000)
}

SYNC_FREQ = 19500
SAMPLE_RATE = 48000
DURATION_SYMBOL = 0.08   # 80 ms por símbolo
SILENCE_BETWEEN = 0.025  # 25 ms entre símbolos


def generate_tone(freq, duration, sample_rate=48000):
    n = int(sample_rate * duration)
    samples = []
    for i in range(n):
        t = i / sample_rate
        val = math.sin(2 * math.pi * freq * t)
        samples.append(int(val * 32767))
    return struct.pack(f'<{n}h', *samples)


def generate_silence(duration, sample_rate=48000):
    n = int(sample_rate * duration)
    return struct.pack(f'<{n}h', *[0] * n)


def encode_message_to_symbols(message):
    """Convierte texto a secuencia de símbolos (ASCII hex + checksum)"""
    msg_bytes = message.encode('utf-8')
    checksum = sum(msg_bytes) % 256
    hex_str = msg_bytes.hex().upper()
    check_hex = f"{checksum:02X}"
    return list(hex_str + '*' + check_hex)


def build_wav_packet(symbols, repeat=1):
    """Construye el audio completo: sync + datos + sync de cierre. repeat para modo Farol."""
    full = b''

    for _ in range(repeat):
        # Tono de sincronización — 0.3 s
        full += generate_tone(SYNC_FREQ, 0.3)
        full += generate_silence(0.05)

        for sym in symbols:
            if sym in FREQ_TABLE:
                f1, f2 = FREQ_TABLE[sym]
                n = int(SAMPLE_RATE * DURATION_SYMBOL)
                pcm = []
                for i in range(n):
                    t = i / SAMPLE_RATE
                    val = 0.5 * math.sin(2 * math.pi * f1 * t) + 0.5 * math.sin(2 * math.pi * f2 * t)
                    pcm.append(int(val * 20000))
                full += struct.pack(f'<{n}h', *pcm)
            else:
                full += generate_silence(DURATION_SYMBOL)
            full += generate_silence(SILENCE_BETWEEN)

        full += generate_tone(SYNC_FREQ, 0.2)
        full += generate_silence(0.1)

    # Cabecera WAV
    temp_file = tempfile.NamedTemporaryFile(suffix='.wav', delete=False).name
    data_len = len(full)
    header = struct.pack('<4sI4s4s4sIHHIIHH',
        b'RIFF', data_len + 36, b'WAVE', b'fmt ', b'fmt ',
        16, 1, 1, SAMPLE_RATE, SAMPLE_RATE * 2, 2, 16)
    # Fix: cabecera WAV correcta
    header = b'RIFF' + struct.pack('<I', data_len + 36) + b'WAVE'
    header += b'fmt ' + struct.pack('<IHHIIHH', 16, 1, 1, SAMPLE_RATE, SAMPLE_RATE * 2, 2, 16)
    header += b'data' + struct.pack('<I', data_len)
    with open(temp_file, 'wb') as f:
        f.write(header)
        f.write(full)
    return temp_file


def send_message(message, repeat=1, volume=80):
    """Envía un mensaje por ultrasonidos. Devuelve la ruta del WAV temporal."""
    symbols = encode_message_to_symbols(message)
    print(f"🦇 Enviando: {message}")
    print(f"🔊 Símbolos: {''.join(symbols)}")
    wav_file = build_wav_packet(symbols, repeat=repeat)

    # Intentar ffplay, fallback a aplay
    print("📢 Emitiendo... (coloca el altavoz cerca del receptor)")
    try:
        subprocess.run(
            ['ffplay', '-nodisp', '-autoexit', '-volume', str(volume), wav_file],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        try:
            subprocess.run(
                ['aplay', '-q', wav_file],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30
            )
        except FileNotFoundError:
            print("⚠️  No se encontró ffplay ni aplay. El WAV se guardó en:")
            print(f"   {wav_file}")
            return wav_file

    os.unlink(wav_file)
    print("✅ Transmisión completada.")
    return None


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("🦇 MURCIÉLAGO SENDER v2.0")
        print("Uso: python murcielago_sender.py 'texto'")
        print("Ejemplo: python murcielago_sender.py 'SOS 192.168.1.10'")
        sys.exit(1)

    repeat = 1
    if '--farol' in sys.argv:
        repeat = 3
        sys.argv.remove('--farol')

    msg = sys.argv[1]
    send_message(msg, repeat=repeat)
