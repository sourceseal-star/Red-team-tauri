#!/usr/bin/env python3
"""
MURCIÉLAGO Receiver v3.0 — Receptor ultrasonido 18-20 kHz
Decodifica mensajes FSK dual-tone enviados por el protocolo MURCIÉLAGO.

Uso:
    python3 murcielago_receiver.py --duration 6
    python3 murcielago_receiver.py --duration 10 --debug
    python3 murcielago_receiver.py --duration 6 --channel 2

Salida (parseable por el backend):
    Mensaje recibido: <texto>
    DEBUG: ... (con --debug)
"""
import sys
import argparse
import numpy as np

# ═══════════════════════════════════════════════════════════
# PROTOCOLO MURCIÉLAGO v3.0 — Parámetros
# ═══════════════════════════════════════════════════════════

SAMPLE_RATE = 48000
SYMBOL_DURATION = 0.08      # 80ms por símbolo
SILENCE_BETWEEN = 0.025     # 25ms de silencio entre símbolos
SYNC_FREQ = 19500           # Tono de sincronización
SYNC_DURATION = 0.3        # 300ms de sync inicial

# Tabla de frecuencias (debe coincidir con el emisor)
FREQ_TABLE = {
    '0': (18000, 18400), '1': (18100, 18500), '2': (18200, 18600),
    '3': (18300, 18700), '4': (18400, 18800), '5': (18500, 18900),
    '6': (18600, 19000), '7': (18700, 19100), '8': (18800, 19200),
    '9': (18900, 19300), 'A': (19000, 19400), 'B': (19100, 19500),
    'C': (19200, 19600), 'D': (19300, 19700), 'E': (19400, 19800),
    'F': (19500, 19900), '#': (18000, 19500), '*': (18500, 20000)
}

# Tabla inversa: (f1, f2) -> símbolo
FREQ_LOOKUP = {}
for sym, (f1, f2) in FREQ_TABLE.items():
    FREQ_LOOKUP[(f1, f2)] = sym


def detect_sync(audio_data, sr=SAMPLE_RATE):
    """Detecta el tono de sincronización al inicio del audio."""
    # Buscar una ventana de 300ms con energía dominante en SYNC_FREQ
    sync_samples = int(sr * SYNC_DURATION)
    if len(audio_data) < sync_samples:
        return 0

    # Ventana deslizante para detectar el tono de sync
    window_size = int(sr * 0.1)  # 100ms
    best_pos = 0
    best_power = 0

    for start in range(0, min(len(audio_data) - window_size, int(sr * 2)), int(sr * 0.05)):
        chunk = audio_data[start:start + window_size]
        # FFT para detectar la frecuencia dominante
        fft = np.fft.rfft(chunk)
        magnitudes = np.abs(fft)
        freqs = np.fft.rfftfreq(len(chunk), 1.0 / sr)

        # Buscar energía cerca de SYNC_FREQ
        mask = (freqs >= SYNC_FREQ - 300) & (freqs <= SYNC_FREQ + 300)
        sync_power = np.max(magnitudes[mask]) if np.any(mask) else 0

        # Energía total para comparar
        total_power = np.sum(magnitudes)
        if total_power > 0 and sync_power / total_power > 0.15:
            if sync_power > best_power:
                best_power = sync_power
                best_pos = start

    return best_pos


def decode_symbol(audio_chunk, sr=SAMPLE_RATE):
    """Decodifica un símbolo FSK dual-tone de un chunk de audio."""
    fft = np.fft.rfft(audio_chunk)
    magnitudes = np.abs(fft)
    freqs = np.fft.rfftfreq(len(audio_chunk), 1.0 / sr)

    # Buscar los dos picos de frecuencia más fuertes en el rango 17.5-20.5 kHz
    mask = (freqs >= 17500) & (freqs <= 20500)
    if not np.any(mask):
        return None

    masked_mags = magnitudes[mask]
    masked_freqs = freqs[mask]

    # Encontrar los dos picos
    # Suavizar: buscar máximos locales
    from scipy.signal import find_peaks
    peaks, _ = find_peaks(masked_mags, height=np.max(masked_mags) * 0.3, distance=5)

    if len(peaks) < 2:
        # Fallback: tomar los dos puntos más altos
        top_indices = np.argsort(masked_mags)[-2:]
        peak_freqs = sorted(masked_freqs[top_indices])
    else:
        # Tomar los dos picos más altos
        peak_heights = masked_mags[peaks]
        top_peaks = peaks[np.argsort(peak_heights)[-2:]]
        peak_freqs = sorted(masked_freqs[top_peaks])

    if len(peak_freqs) < 2:
        return None

    f1_detected = round(peak_freqs[0] / 100) * 100  # Redondear a centena
    f2_detected = round(peak_freqs[1] / 100) * 100

    # Buscar en la tabla con tolerancia de ±150 Hz
    for (t_f1, t_f2), sym in FREQ_LOOKUP.items():
        if abs(f1_detected - t_f1) <= 150 and abs(f2_detected - t_f2) <= 150:
            return sym

    return None


def decode_message(audio_data, sr=SAMPLE_RATE, debug=False):
    """Decodifica un mensaje completo del audio capturado."""
    # 1. Detectar tono de sync
    sync_pos = detect_sync(audio_data, sr)
    if debug:
        print(f"DEBUG: Sync detectado en muestra {sync_pos} ({sync_pos/sr:.3f}s)", file=sys.stderr)

    # Saltar el sync + silencio inicial
    symbol_samples = int(sr * SYMBOL_DURATION)
    silence_samples = int(sr * SILENCE_BETWEEN)
    pos = sync_pos + int(sr * SYNC_DURATION) + int(sr * 0.05)

    symbols = []
    max_symbols = 500  # Límite de seguridad

    while pos + symbol_samples < len(audio_data) and len(symbols) < max_symbols:
        chunk = audio_data[pos:pos + symbol_samples]

        # Verificar que hay energía (no es silencio)
        energy = np.sqrt(np.mean(chunk ** 2))
        if energy < 0.01:
            # Silencio — avanzar
            pos += symbol_samples + silence_samples
            continue

        sym = decode_symbol(chunk, sr)
        if sym:
            symbols.append(sym)
            if debug:
                print(f"DEBUG: Símbolo {len(symbols)}: '{sym}' @ {pos/sr:.3f}s", file=sys.stderr)
        else:
            if debug:
                print(f"DEBUG: Símbolo no reconocido @ {pos/sr:.3f}s (energía={energy:.4f})", file=sys.stderr)

        pos += symbol_samples + silence_samples

        # Detectar tono de sync final
        if len(symbols) > 0:
            remaining = audio_data[pos:pos + int(sr * 0.2)]
            if len(remaining) > 0:
                fft = np.fft.rfft(remaining)
                mags = np.abs(fft)
                freqs = np.fft.rfftfreq(len(remaining), 1.0 / sr)
                mask = (freqs >= SYNC_FREQ - 300) & (freqs <= SYNC_FREQ + 300)
                if np.any(mask) and np.max(mags[mask]) / (np.sum(mags) + 1) > 0.2:
                    if debug:
                        print("DEBUG: Sync final detectado — fin de mensaje", file=sys.stderr)
                    break

    if not symbols:
        return None

    # Reconstruir: separar hex + checksum
    symbol_str = ''.join(symbols)

    # Buscar el separador '*'
    if '*' in symbol_str:
        hex_part, _, checksum_part = symbol_str.rpartition('*')
        if len(checksum_part) >= 2:
            try:
                msg_bytes = bytes.fromhex(hex_part)
                received_checksum = int(checksum_part[:2], 16)
                calculated_checksum = sum(msg_bytes) % 256

                if received_checksum == calculated_checksum:
                    return msg_bytes.decode('utf-8', errors='replace')
                else:
                    if debug:
                        print(f"DEBUG: Checksum mismatch: recibido={received_checksum:02X} calculado={calculated_checksum:02X}", file=sys.stderr)
                    # Intentar decodificar de todas formas
                    return msg_bytes.decode('utf-8', errors='replace')
            except ValueError:
                if debug:
                    print(f"DEBUG: Hex inválido: {hex_part}", file=sys.stderr)
                return None
    else:
        # Sin separador — intentar decodificar todo como hex
        try:
            msg_bytes = bytes.fromhex(symbol_str)
            return msg_bytes.decode('utf-8', errors='replace')
        except ValueError:
            if debug:
                print(f"DEBUG: No se pudo decodificar: {symbol_str}", file=sys.stderr)
            return None


def record_audio(duration, sr=SAMPLE_RATE):
    """Graba audio del micrófono usando sounddevice."""
    try:
        import sounddevice as sd
        samples = int(sr * duration)
        recording = sd.rec(samples, samplerate=sr, channels=1, dtype='float32')
        sd.wait()
        return recording.flatten()
    except ImportError:
        pass

    # Fallback: usar arecord (Linux/Termux)
    import subprocess, tempfile, wave
    try:
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
            tmp_path = tmp.name

        subprocess.run(
            ['arecord', '-f', 'S16_LE', '-r', str(sr), '-c', '1', '-d', str(duration), '-q', tmp_path],
            timeout=duration + 5, capture_output=True
        )

        with wave.open(tmp_path, 'r') as wf:
            frames = wf.readframes(wf.getnframes())
            os.unlink(tmp_path)

        audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
        return audio
    except Exception as e:
        print(f"Error grabando audio: {e}", file=sys.stderr)
        return np.array([], dtype=np.float32)


def main():
    parser = argparse.ArgumentParser(description='MURCIÉLAGO Receiver v3.0')
    parser.add_argument('--duration', type=int, default=6, help='Duración de grabación en segundos')
    parser.add_argument('--debug', action='store_true', help='Salida de depuración')
    parser.add_argument('--channel', type=int, default=0, help='Canal (offset de frecuencia)')
    parser.add_argument('--file', type=str, help='Decodificar desde archivo WAV en lugar de micrófono')
    args = parser.parse_args()

    if args.debug:
        print(f"DEBUG: MURCIÉLAGO Receiver v3.0", file=sys.stderr)
        print(f"DEBUG: Duración: {args.duration}s | Canal: {args.channel} | Sample rate: {SAMPLE_RATE}", file=sys.stderr)

    if args.file:
        # Decodificar desde archivo
        import wave
        try:
            with wave.open(args.file, 'r') as wf:
                frames = wf.readframes(wf.getnframes())
                sr = wf.getframerate()
                audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
        except Exception as e:
            print(f"Error leyendo archivo: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        # Grabar del micrófono
        print(f"🎙️  Grabando {args.duration}s...", file=sys.stderr)
        audio = record_audio(args.duration)
        print(f"DEBUG: Audio capturado: {len(audio)} muestras ({len(audio)/SAMPLE_RATE:.1f}s)", file=sys.stderr)

    if len(audio) == 0:
        print("Mensaje recibido: ❌ Sin audio capturado")
        sys.exit(1)

    # Aplicar offset de canal si se especifica
    if args.channel > 0:
        # El receptor no necesita ajustar — las frecuencias son absolutas
        pass

    # Decodificar
    message = decode_message(audio, SAMPLE_RATE, debug=args.debug)

    if message:
        print(f"Mensaje recibido: {message}")
    else:
        print("Mensaje recibido: ❌ Sin señal detectada")


if __name__ == '__main__':
    import os
    main()
