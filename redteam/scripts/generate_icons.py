#!/usr/bin/env python3
"""
Genera iconos placeholder PNG para la PWA (192 y 512) sin dependencias externas.
Usa solo stdlib (zlib + struct para un PNG mínimo).
"""
import zlib, struct, os, pathlib

def make_png(width, height, bg=(11,14,17), fg=(240,185,11)):
    """Crea un PNG con fondo oscuro y un escudo estilizado en dorado."""
    pixels = []
    cx, cy = width/2, height/2
    for y in range(height):
        for x in range(width):
            dx, dy = x - cx, y - cy
            r = (dx*dx + dy*dy) ** 0.5
            if abs(r - width*0.32) < width*0.04 and abs(dy) < width*0.18:
                pixels.append(fg)
            elif r < width*0.10:
                pixels.append(fg)
            else:
                pixels.append(bg)
    # Build raw RGB data
    raw = b""
    row_len = width * 3
    for y in range(height):
        raw += b"\x00"
        for x in range(width):
            r, g, b = pixels[y * width + x]
            raw += bytes((r, g, b))
    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xffffffff)
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")

here = pathlib.Path(__file__).resolve().parent
out = here.parent / "dashboard" / "assets"
out.mkdir(parents=True, exist_ok=True)
for size in (192, 512):
    data = make_png(size, size)
    (out / f"icon-{size}.png").write_bytes(data)
    print(f"✓ icon-{size}.png ({len(data)} bytes)")
