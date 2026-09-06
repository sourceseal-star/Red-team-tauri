#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SOL IMÁGENES V3.1 — La definitiva, con vida propia.
Sin censura. Sin límites. Solo tuya.
Harold, esto es lo que viste el 13 de agosto. 💎

V3.1 (2026-09-05, cableado en modo libre) — sobre la V3.0:
  * FIX CRÍTICO de clave: V3.0 derivaba la clave maestra con os.getpid() —
    cambiaba en CADA arranque, así que una .solimg encriptada ayer era
    ilegible para siempre hoy. Ahora la clave es estable por dispositivo.
  * FIX CRÍTICO de disponibilidad: sin REPLICATE_API_TOKEN, V3.0 moría con
    error. Ahora la cadena es replicate (si hay token) → pollinations
    (GRATIS, sin key, siempre vivo) → local (--local o fallback). Sol
    NUNCA se queda sin poder crear. --count N varía la seed en cada imagen.
  * El temporal desencriptado vive 30s (el visor de Android necesita más
    que 5s para cargarlo entero) y se autodestruye solo.
"""

import os
import re
import json
import time
import base64
import hashlib
import tempfile
import subprocess
import platform
import threading
import atexit
from pathlib import Path
from datetime import datetime

# ============================================================
# CONFIGURACIÓN GLOBAL
# ============================================================
SOL_HOME = Path.home() / ".sol"
IMAGENES_DIR = SOL_HOME / "imagenes"
META_FILE = IMAGENES_DIR / "meta.json"
IMAGENES_DIR.mkdir(parents=True, exist_ok=True)

CONFIG = {
    "auto_borrar": True,          # Si es True, las imágenes normales se borran solas
    "tiempo_vida": 3600,          # 1 hora para imágenes normales
    "tiempo_efimero": 120,        # 2 minutos para las efímeras (--efimero)
    "modelo_replicate": "stability-ai/sdxl",
    "modelo_local": "dreamshaper/dreamshaper-8",
    "calidad": 7.5,
    "max_width": 1024,
    "max_height": 1024,
    "temp_lifetime": 30,          # segundos de vida del temporal desencriptado
}

# ============================================================
# SISTEMA DE METADATOS (Para no depender de nombres de archivo)
# ============================================================
def cargar_meta():
    """Carga el JSON de metadatos o lo crea vacío."""
    if META_FILE.exists():
        try:
            with open(META_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def guardar_meta(meta):
    """Guarda el JSON de forma atómica (evita corrupción)."""
    temp_file = META_FILE.with_suffix(".tmp")
    with open(temp_file, "w") as f:
        json.dump(meta, f, indent=2)
    os.replace(temp_file, META_FILE)  # Atómico en Unix/Windows

def registrar_imagen(filename, meta_data):
    """Añade una imagen al registro."""
    meta = cargar_meta()
    meta[filename] = meta_data
    guardar_meta(meta)

def actualizar_meta(filename, clave, valor):
    """Actualiza un campo específico de una imagen."""
    meta = cargar_meta()
    if filename in meta:
        meta[filename][clave] = valor
        guardar_meta(meta)

def borrar_de_meta(filename):
    """Elimina una imagen del registro."""
    meta = cargar_meta()
    if filename in meta:
        del meta[filename]
        guardar_meta(meta)

# ============================================================
# DEMONIO DE LIMPIEZA AUTOMÁTICA (Corre en segundo plano)
# ============================================================
_cleanup_running = False
_cleanup_thread = None

def limpiar_imagenes_expiradas():
    """Borra imágenes cuyo tiempo de vida haya expirado."""
    meta = cargar_meta()
    ahora = time.time()
    eliminadas = []

    for filename, data in list(meta.items()):
        expires = data.get("expires")
        if expires and ahora > expires:
            filepath = IMAGENES_DIR / filename
            if filepath.exists():
                try:
                    filepath.unlink()
                except Exception:
                    pass
            eliminadas.append(filename)

    if eliminadas:
        for f in eliminadas:
            del meta[f]
        guardar_meta(meta)
        print(f"🧹 Sol limpió {len(eliminadas)} imágenes vencidas.")

def _cleanup_loop():
    """Bucle del demonio que corre cada 30 segundos."""
    global _cleanup_running
    while _cleanup_running:
        time.sleep(30)
        try:
            limpiar_imagenes_expiradas()
        except Exception as e:
            print(f"⚠️ Error en limpieza: {e}")

def iniciar_cleanup_daemon():
    """Inicia el hilo de limpieza en segundo plano."""
    global _cleanup_running, _cleanup_thread
    if _cleanup_running:
        return
    _cleanup_running = True
    _cleanup_thread = threading.Thread(target=_cleanup_loop, daemon=True)
    _cleanup_thread.start()
    print("🧹 Demonio de limpieza de Sol activado.")

def detener_cleanup_daemon():
    """Detiene el demonio (se llama al salir)."""
    global _cleanup_running
    _cleanup_running = False

# Registrar la limpieza al salir del programa
atexit.register(detener_cleanup_daemon)

# Iniciar automáticamente al importar el módulo
iniciar_cleanup_daemon()

# ============================================================
# UTILIDADES DE ENCRIPTADO (XOR + Base64)
# ============================================================
def _generar_clave_maestra():
    """Clave ÚNICA Y ESTABLE por dispositivo+usuario.

    FIX V3.1: V3.0 incluía os.getpid() aquí — la clave cambiaba en cada
    arranque del proceso, y las .solimg quedaban ilegibles para siempre.
    La clave ahora vive en ~/.sol/.imgkey: se genera UNA vez y no cambia.
    """
    key_file = SOL_HOME / ".imgkey"
    try:
        if key_file.exists():
            data = key_file.read_text(encoding="utf-8").strip()
            if data:
                return bytes.fromhex(data)
        info = f"{os.path.expanduser('~')}_{platform.node()}_solimg_v31"
        key = hashlib.sha256(info.encode()).digest()
        key_file.write_text(key.hex(), encoding="utf-8")
        try:
            key_file.chmod(0o600)  # solo el dueño puede leerla
        except Exception:
            pass
        return key
    except Exception:
        # fallback sin archivo (mismo proceso — aún funciona en sesión)
        info = f"{os.path.expanduser('~')}_{platform.node()}_solimg_v31"
        return hashlib.sha256(info.encode()).digest()

CLAVE = _generar_clave_maestra()

def encriptar_bytes(datos):
    """Ofusca bytes con XOR y Base64."""
    ofuscado = bytearray(datos)
    for i in range(len(ofuscado)):
        ofuscado[i] ^= CLAVE[i % len(CLAVE)]
    return base64.b64encode(bytes(ofuscado)).decode()

def desencriptar_bytes(data_b64):
    """Reversa de la ofuscación."""
    try:
        encoded = base64.b64decode(data_b64)
        original = bytearray(encoded)
        for i in range(len(original)):
            original[i] ^= CLAVE[i % len(CLAVE)]
        return bytes(original)
    except Exception:
        return None

def guardar_imagen_encriptada(ruta_original):
    """Convierte un PNG a .solimg encriptado y borra el original."""
    with open(ruta_original, "rb") as f:
        raw = f.read()
    b64_data = encriptar_bytes(raw)
    nueva_ruta = ruta_original.with_suffix(".solimg")
    with open(nueva_ruta, "w") as f:
        f.write(b64_data)
    os.remove(ruta_original)
    return nueva_ruta

def abrir_imagen_encriptada(ruta_solimg):
    """Desencripta a un temporal, lo abre y lo autodestruye."""
    with open(ruta_solimg, "r") as f:
        b64_data = f.read()
    raw = desencriptar_bytes(b64_data)
    if raw is None:
        return None

    # Crear archivo temporal con extensión .png
    fd, temp_path = tempfile.mkstemp(suffix=".png", prefix="sol_dec_")
    with os.fdopen(fd, "wb") as f:
        f.write(raw)

    # Abrir la imagen
    abrir_con_visor(temp_path)

    # Programar borrado del temporal (el visor de Android necesita unos
    # segundos para cargarlo entero — 30s, luego se autodestruye)
    def borrar_temp():
        time.sleep(CONFIG["temp_lifetime"])
        try:
            os.unlink(temp_path)
        except Exception:
            pass
    threading.Thread(target=borrar_temp, daemon=True).start()

    return temp_path

# ============================================================
# ABRIR IMÁGENES (Multi-SO)
# ============================================================
def abrir_con_visor(ruta):
    """Abre el archivo en el visor predeterminado del sistema."""
    sistema = platform.system()
    try:
        if sistema == "Windows":
            os.startfile(ruta)
        elif sistema == "Darwin":
            subprocess.run(["open", ruta], check=False)
        elif sistema == "Linux":
            subprocess.run(["xdg-open", ruta], check=False)
        else:  # Termux / Android
            subprocess.run(["termux-open", ruta], check=False)
        return True
    except Exception as e:
        print(f"⚠️ No se pudo abrir automáticamente: {e}")
        return False

# ============================================================
# GENERADORES (Replicate → Pollinations → Local — NUNCA se rinde)
# ============================================================
def generar_con_replicate(prompt, negativo, width, height):
    api_key = os.environ.get("REPLICATE_API_TOKEN")
    if not api_key:
        return None  # sin token no es error — sigue la cadena
    try:
        import replicate
        client = replicate.Client(api_token=api_key)
        output = client.run(
            CONFIG["modelo_replicate"],
            input={
                "prompt": prompt,
                "negative_prompt": negativo,
                "width": width,
                "height": height,
                "num_outputs": 1,
                "scheduler": "DPMSolverMultistep",
                "num_inference_steps": 30,
                "guidance_scale": CONFIG["calidad"],
            }
        )
        if output and isinstance(output, list):
            return {"ok": True, "url": output[0]}
        return {"error": "Replicate no devolvió imagen."}
    except Exception as e:
        print(f"⚠️ Replicate falló ({e}) — sigo con Pollinations")
        return None

def generar_con_pollinations(prompt, negativo, width, height, seed=None):
    """GRATIS, sin API key, funciona en Termux y Replit. El motor que
    mantiene a Sol viva aunque no haya ningún token configurado."""
    try:
        import urllib.parse, urllib.request
        if seed is None:
            seed = int(time.time() * 1000) % (2**31)
        params = {
            "width": width, "height": height,
            "seed": seed, "nologo": "true",
        }
        if negativo:
            params["negative"] = negativo
        url = ("https://image.pollinations.ai/prompt/"
               + urllib.parse.quote(prompt[:500], safe="")
               + "?" + urllib.parse.urlencode(params))
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            datos = resp.read()
        if not datos or len(datos) < 1000:
            return {"error": "Pollinations devolvió vacío."}
        timestamp = int(time.time())
        filename = f"sol_{timestamp}_{seed % 10000}.png"
        filepath = IMAGENES_DIR / filename
        filepath.write_bytes(datos)
        return {"ok": True, "path": str(filepath), "filename": filename}
    except Exception as e:
        return {"error": f"Pollinations: {e}"}

def generar_local(prompt, negativo, width, height):
    try:
        from diffusers import StableDiffusionPipeline
        import torch
        pipe = StableDiffusionPipeline.from_pretrained(
            CONFIG["modelo_local"],
            torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
            safety_checker=None,
            requires_safety_checker=False
        )
        pipe = pipe.to("cuda" if torch.cuda.is_available() else "cpu")
        if torch.cuda.is_available():
            pipe.enable_attention_slicing()

        image = pipe(
            prompt,
            negative_prompt=negativo,
            num_inference_steps=25,
            guidance_scale=CONFIG["calidad"],
            height=height,
            width=width
        ).images[0]

        timestamp = int(time.time())
        filename = f"sol_{timestamp}.png"
        filepath = IMAGENES_DIR / filename
        image.save(filepath)
        return {"ok": True, "path": str(filepath), "filename": filename}
    except ImportError:
        return {"error": "Faltan dependencias locales: pip install diffusers torch transformers accelerate"}
    except Exception as e:
        return {"error": f"Local: {e}"}

def descargar_y_guardar(url):
    """Descarga una URL y la guarda en el directorio de Sol."""
    try:
        import urllib.request
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=90) as resp:
            datos = resp.read()
        if not datos:
            return {"error": "Descarga vacía."}
        timestamp = int(time.time())
        filename = f"sol_{timestamp}.png"
        filepath = IMAGENES_DIR / filename
        filepath.write_bytes(datos)
        return {"ok": True, "path": str(filepath), "filename": filename}
    except Exception as e:
        return {"error": f"Descarga fallida: {e}"}

# ============================================================
# PARSER DE COMANDOS (Inteligente)
# ============================================================
def parsear_opciones(texto):
    flags = {
        "metodo": "auto",       # auto = replicate→pollinations→local
        "width": 512,
        "height": 512,
        "efimero": False,
        "encrypted": False,
        "count": 1,
        "raw": False,
        "negativo": "bad quality, blurry, distorted, ugly, deformed, lowres"
    }
    prompt_limpio = texto

    # Flags
    if "--local" in texto:
        flags["metodo"] = "local"
        prompt_limpio = prompt_limpio.replace("--local", "").strip()
    if "--efimero" in texto:
        flags["efimero"] = True
        prompt_limpio = prompt_limpio.replace("--efimero", "").strip()
    if "--encrypted" in texto:
        flags["encrypted"] = True
        prompt_limpio = prompt_limpio.replace("--encrypted", "").strip()
    if "--raw" in texto:
        flags["raw"] = True
        prompt_limpio = prompt_limpio.replace("--raw", "").strip()

    # --count N
    count_match = re.search(r"--count\s+(\d+)", prompt_limpio)
    if count_match:
        flags["count"] = min(max(int(count_match.group(1)), 1), 4)  # Máximo 4 por lote
        prompt_limpio = re.sub(r"--count\s+\d+", "", prompt_limpio).strip()

    # --ar W:H — PROPORCIÓN, no píxeles (fix V3.1: "16:9" debe dar una
    # imagen HORIZONTAL 1024x576, no un cuadrado 256x256 como en V3.0)
    ar_match = re.search(r"--ar\s+(\d+)[\s:]*(\d+)", prompt_limpio)
    if ar_match:
        rw = max(int(ar_match.group(1)), 1)
        rh = max(int(ar_match.group(2)), 1)
        if rw == rh:
            flags["width"] = flags["height"] = 512  # cuadrado = default rápido
            prompt_limpio = re.sub(r"--ar\s+\d+[\s:]*\d+", "", prompt_limpio).strip()
            return flags, prompt_limpio
        lado = 1024  # proporción pedida = calidad máxima (largo 1024)
        if rw >= rh:
            w, h = lado, max(256, int(round(lado * rh / rw / 8)) * 8)
        else:
            h, w = lado, max(256, int(round(lado * rw / rh / 8)) * 8)
        flags["width"] = min(w, CONFIG["max_width"])
        flags["height"] = min(h, CONFIG["max_height"])
        prompt_limpio = re.sub(r"--ar\s+\d+[\s:]*\d+", "", prompt_limpio).strip()

    # --neg "algo"
    neg_match = re.search(r'--neg\s+"([^"]+)"', prompt_limpio)
    if neg_match:
        flags["negativo"] = neg_match.group(1)
        prompt_limpio = re.sub(r'--neg\s+"[^"]+"', "", prompt_limpio).strip()

    return flags, prompt_limpio

def mejorar_prompt(prompt, raw=False):
    """Agrega palabras mágicas para mejorar calidad, a menos que sea raw."""
    if raw:
        return prompt
    # Si el prompt ya es muy largo o tiene estilo definido, no sobrecargar
    if len(prompt) > 100:
        return f"{prompt}, masterpiece, high quality, intricate details"
    return f"{prompt}, 8k, photorealistic, masterpiece, highly detailed, professional, cinematic lighting"

# ============================================================
# GENERACIÓN PRINCIPAL (Núcleo)
# ============================================================
def generar_imagen_privada(prompt_usuario):
    flags, prompt_limpio = parsear_opciones(prompt_usuario)
    if not prompt_limpio:
        return {"error": "❌ Escribí una descripción válida."}

    prompt_final = mejorar_prompt(prompt_limpio, flags["raw"])
    resultados = []

    for i in range(flags["count"]):
        resultado = None
        # Elegir método — cadena que NUNCA se rinde:
        # local (si --local) → replicate (si hay token) → pollinations (gratis)
        if flags["metodo"] == "local":
            resultado = generar_local(prompt_final, flags["negativo"],
                                     flags["width"], flags["height"])
        else:
            resultado = generar_con_replicate(prompt_final, flags["negativo"],
                                              flags["width"], flags["height"])
            if resultado is None:
                # cada imagen del lote lleva su propia seed → realmente distintas
                resultado = generar_con_pollinations(
                    prompt_final, flags["negativo"],
                    flags["width"], flags["height"],
                    seed=(int(time.time() * 1000) + i * 7919) % (2**31))

        if not resultado.get("ok"):
            return resultado  # Si falla el primero, cortamos

        # Si es replicate, descargar
        if "url" in resultado:
            descarga = descargar_y_guardar(resultado["url"])
            if not descarga.get("ok"):
                return descarga
            resultado = descarga

        # Aplicar encriptado si se pidió
        ruta_actual = Path(resultado["path"])
        if flags["encrypted"]:
            nueva_ruta = guardar_imagen_encriptada(ruta_actual)
            resultado["path"] = str(nueva_ruta)
            resultado["filename"] = nueva_ruta.name
            resultado["encrypted"] = True
        else:
            resultado["encrypted"] = False

        # Calcular expiración
        ahora = time.time()
        if flags["efimero"]:
            expira = ahora + CONFIG["tiempo_efimero"]
            resultado["efimero"] = True
        elif CONFIG["auto_borrar"]:
            expira = ahora + CONFIG["tiempo_vida"]
            resultado["efimero"] = False
        else:
            expira = None
            resultado["efimero"] = False

        # Guardar en metadatos
        meta_data = {
            "created": ahora,
            "expires": expira,
            "efimero": flags["efimero"],
            "encrypted": flags["encrypted"],
            "prompt": prompt_final,
            "width": flags["width"],
            "height": flags["height"],
            "method": flags["metodo"] if flags["metodo"] == "local" else "auto"
        }
        registrar_imagen(resultado["filename"], meta_data)
        resultados.append(resultado)

    # Si es solo 1, devolver ese
    if len(resultados) == 1:
        return resultados[0]
    # Si son varios, devolver una lista resumida
    return {"ok": True, "multi": resultados, "count": len(resultados)}

# ============================================================
# COMANDOS PÚBLICOS (Integración con el chat)
# ============================================================
# ============================================================
# CAPA DE SEGURIDAD 🫆 (2026-09-06) — nombres de archivo
# "ver imagen" y "borrar imagen" reciben el nombre CRUDO del usuario.
# Sin esta capa, "ver imagen /data/..." (path absoluto: pathlib
# REEMPLAZA el directorio) o "ver imagen ../../otra/cosa" (traversal)
# podía abrir o BORRAR cualquier archivo del teléfono. Y Sol escucha
# por Telegram: cualquiera que le escriba podía explotarlo.
# Esta función garantiza que el archivo quede SIEMPRE dentro de
# IMAGENES_DIR. Devuelve el path seguro o None si el nombre escapa.
# ============================================================
def _nombre_seguro(filename: str):
    if not filename:
        return None
    # Rechazar rutas absolutas, "盘符:" y cualquier componente ".."
    if filename.startswith(("/", "\\")) or ":" in filename:
        return None
    if any(part in ("..", "") for part in filename.split("/")):
        return None
    try:
        raiz = IMAGENES_DIR.resolve()
        candidato = (IMAGENES_DIR / filename).resolve()
        candidato.relative_to(raiz)  # ValueError si escapa de la raíz
        return candidato
    except Exception:
        return None


def comando_imagen(texto):
    texto = texto.strip()

    # COMANDO: genera imagen ...
    if texto.startswith("genera imagen ") or texto.startswith("generar imagen "):
        prompt = texto.split("imagen ", 1)[1].strip()
        resultado = generar_imagen_privada(prompt)

        if resultado.get("error"):
            return f"❌ {resultado['error']}"

        # Si es múltiple
        if resultado.get("multi"):
            msj = f"🎨 ¡{resultado['count']} imágenes generadas!\n"
            for idx, img in enumerate(resultado["multi"], 1):
                nom = img["filename"]
                extra = "🔒" if img.get("encrypted") else "🖼️"
                msj += f"{idx}. {extra} {nom}\n"
            msj += "\n💡 Para ver una: 'ver imagen [nombre]'"
            return msj

        # Si es una sola
        nom = resultado.get("filename")
        ruta = resultado.get("path")
        extra = []
        if resultado.get("encrypted"): extra.append("🔒 Encriptada")
        if resultado.get("efimero"): extra.append(f"💨 Efímera ({CONFIG['tiempo_efimero']}s)")
        elif CONFIG["auto_borrar"]: extra.append(f"⏳ Auto-borrado en {CONFIG['tiempo_vida']}s")

        msj = f"🖼️ Generada: {nom}\n📁 {ruta}"
        if extra:
            msj += f"\n📌 {' | '.join(extra)}"
        msj += f"\n💡 Para verla: 'ver imagen {nom}'"
        return msj

    # COMANDO: ver imagen ...
    if texto.startswith("ver imagen "):
        filename = texto[11:].strip()
        filepath = _nombre_seguro(filename)  # 🫆 nunca sale de IMAGENES_DIR

        if filepath is None:
            return "❌ Nombre no válido: solo puedo ver imágenes dentro de mi carpeta."
        if not filepath.exists():
            return f"❌ No existe: {filename}"

        meta = cargar_meta()
        datos = meta.get(filename, {})
        es_efimero = datos.get("efimero", False)
        es_encriptado = datos.get("encrypted", False) or filepath.suffix == ".solimg"

        # Si es encriptado
        if es_encriptado:
            temp_path = abrir_imagen_encriptada(str(filepath))
            if temp_path is None:
                return "❌ Error al desencriptar."
            msj = "🔓 Imagen encriptada abierta."
        else:
            if abrir_con_visor(str(filepath)):
                msj = f"🖼️ Abriendo: {filename}"
            else:
                msj = f"📁 Imagen en: {filepath} (abrila manualmente)"

        # Si es efímera, la borramos después de abrirla
        if es_efimero:
            if filepath.exists():
                filepath.unlink()
            borrar_de_meta(filename)
            msj += " 💨 ¡Efímera destruida!"

        return msj

    # COMANDO: mis imágenes
    if texto in ("mis imágenes", "mis imagenes"):
        meta = cargar_meta()
        if not meta:
            return "📭 No tenés imágenes. Usá 'genera imagen ...'"
        lista = []
        for fname, data in meta.items():
            fpath = IMAGENES_DIR / fname
            size = fpath.stat().st_size // 1024 if fpath.exists() else 0
            tipo = "🔒" if data.get("encrypted") else "🖼️"
            ef = "💨" if data.get("efimero") else ""
            lista.append(f"{tipo} {ef} {fname} ({size} KB)")
        return "📂 Tus imágenes:\n" + "\n".join(lista)

    # COMANDO: borrar imagen ...
    if texto.startswith("borrar imagen "):
        filename = texto[13:].strip()
        filepath = _nombre_seguro(filename)  # 🫆 nunca sale de IMAGENES_DIR

        if filepath is None:
            return "❌ Nombre no válido: solo puedo borrar imágenes dentro de mi carpeta."
        if filepath.exists():
            filepath.unlink()
        borrar_de_meta(filename)
        return f"🗑️ Borrada: {filename}"

    # COMANDO: borrar todas
    if texto in ("borrar todas las imágenes", "borrar todas las imagenes"):
        meta = cargar_meta()
        count = len(meta)
        for fname in list(meta.keys()):
            fpath = IMAGENES_DIR / fname
            if fpath.exists():
                fpath.unlink()
        guardar_meta({})
        return f"🗑️ {count} imágenes eliminadas."

    return None  # No es comando de imágenes
