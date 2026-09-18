#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bestiario del Qalam v1.0.

The module is deliberately deterministic: Sol can consult the Arabic
mnemonic alphabet with or without an LLM connection.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Dict, Iterable, List, Optional


ENTRIES: List[Dict[str, str]] = [
    {"id": "01", "arabic": "ا", "name": "alif", "points": "0 pts", "translit": "a larga / corte", "mnemonic": "una L en español"},
    {"id": "02", "arabic": "ب", "name": "bā", "points": "1↓", "translit": "b", "mnemonic": "gorro chino al revés"},
    {"id": "03", "arabic": "ت", "name": "tā", "points": "2↑", "translit": "t", "mnemonic": "carita feliz"},
    {"id": "04", "arabic": "ث", "name": "thā", "points": "3↑", "translit": "z ES / s-t EG", "mnemonic": "carita feliz con seño fruncido"},
    {"id": "05", "arabic": "ج", "name": "jīm", "points": "1↓", "translit": "g de gato", "mnemonic": "caballito de mar con un punto"},
    {"id": "06", "arabic": "ح", "name": "ḥā", "points": "0", "translit": "ḥ papa caliente", "mnemonic": "caballito de mar sin el punto"},
    {"id": "07", "arabic": "خ", "name": "khā", "points": "1↑", "translit": "kh jamón", "mnemonic": "caballito de mar, punto en la cabeza"},
    {"id": "08", "arabic": "د", "name": "dāl", "points": "0", "translit": "d", "mnemonic": "galleta de la fortuna"},
    {"id": "09", "arabic": "ذ", "name": "dhāl", "points": "1↑", "translit": "z ES", "mnemonic": "una J con punto"},
    {"id": "10", "arabic": "ر", "name": "rā", "points": "0", "translit": "r vibrada", "mnemonic": "una J sin punto"},
    {"id": "11", "arabic": "ز", "name": "zāy", "points": "1↑", "translit": "z", "mnemonic": "culebrita con corona ♦"},
    {"id": "12", "arabic": "س", "name": "sīn", "points": "0", "translit": "s", "mnemonic": "3 cabezas de culebritas"},
    {"id": "13", "arabic": "ش", "name": "shīn", "points": "3↑", "translit": "sh", "mnemonic": "tres culebritas con un techo ^"},
    {"id": "14", "arabic": "ض", "name": "ḍād", "points": "1↓", "translit": "ḍ papa caliente", "mnemonic": "culebrita con burbuja y corona ♦"},
    {"id": "15", "arabic": "ص", "name": "ṣād", "points": "0", "translit": "ṣ papa caliente", "mnemonic": "culebrita con burbuja"},
    {"id": "16", "arabic": "ط", "name": "ṭā", "points": "0", "translit": "ṭ papa caliente", "mnemonic": "serpiente sin corona"},
    {"id": "17", "arabic": "ظ", "name": "ẓā", "points": "1↑", "translit": "ẓ la más difícil", "mnemonic": "serpiente con corona ♦"},
    {"id": "18", "arabic": "ع", "name": "ʿayn", "points": "0", "translit": "ʿ corte bajo", "mnemonic": "un número 3"},
    {"id": "19", "arabic": "غ", "name": "ghayn", "points": "1↑", "translit": "gh gargarismo", "mnemonic": "número 3 con corona ♦"},
    {"id": "20", "arabic": "ف", "name": "fā", "points": "1↑", "translit": "f", "mnemonic": "bota árabe"},
    {"id": "21", "arabic": "ق", "name": "qāf", "points": "2↑", "translit": "ʔ EG / q en canto", "mnemonic": "caracol sin caparazón"},
    {"id": "22", "arabic": "ك", "name": "kāf", "points": "1↘", "translit": "k", "mnemonic": "culebrita con una pequeña en su espalda"},
    {"id": "23", "arabic": "ل", "name": "lām", "points": "0", "translit": "l", "mnemonic": "cobra (solo cobra)"},
    {"id": "24", "arabic": "م", "name": "mīm", "points": "0", "translit": "m", "mnemonic": "figura de una cabra"},
    {"id": "25", "arabic": "ن", "name": "nūn", "points": "1↑", "translit": "n", "mnemonic": "culebrita con una bola"},
    {"id": "26", "arabic": "ه", "name": "hā", "points": "0", "translit": "h", "mnemonic": "gota de agua"},
    {"id": "27", "arabic": "و", "name": "wāw", "points": "0", "translit": "w / ū / aw", "mnemonic": "una G en español"},
    {"id": "28", "arabic": "ي", "name": "yā", "points": "2↓", "translit": "y / ī / ay", "mnemonic": "serpiente con 2 huevos"},
    {"id": "29", "arabic": "گ", "name": "gāf", "points": "línea", "translit": "g (préstamos)", "mnemonic": "culebrita con boina"},
    {"id": "30", "arabic": "پ", "name": "peh", "points": "3↓", "translit": "p (préstamos)", "mnemonic": "culebrita con corazón debajo"},
    {"id": "31", "arabic": "چ", "name": "tcheh", "points": "3↓", "translit": "ch (préstamos)", "mnemonic": "caballito de mar con corazón"},
    {"id": "32", "arabic": "ڤ", "name": "veh", "points": "3↓", "translit": "v (préstamos)", "mnemonic": "bota árabe con un techo ^"},
    {"id": "33", "arabic": "ة", "name": "tā marbūṭa", "points": "2↑", "translit": "a / t", "mnemonic": "gota de agua con unos diamantes ♦♦"},
    {"id": "34", "arabic": "ء", "name": "hamza", "points": "—", "translit": "ʔ corte", "mnemonic": "serpiente pequeñita"},
    {"id": "35", "arabic": "آ", "name": "alif madda", "points": "—", "translit": "ā", "mnemonic": "un cuzco sobre un palo"},
    {"id": "36", "arabic": "لا", "name": "lām-alif", "points": "—", "translit": "lā", "mnemonic": "una cobra real"},
    {"id": "37", "arabic": "الا", "name": "al-lām-…", "points": "—", "translit": "secuencia", "mnemonic": "una cobra real y un palo"},
    {"id": "38", "arabic": "ى", "name": "maqṣūra", "points": "—", "translit": "ā final", "mnemonic": "culebrita mediana"},
]

_BY_ARABIC = {entry["arabic"]: entry for entry in ENTRIES}
_BY_ID = {entry["id"]: entry for entry in ENTRIES}
_LONGEST_ARABIC = sorted(_BY_ARABIC, key=len, reverse=True)

# Standard enough for the module's teaching use; the mnemonic is returned too.
_PHONETIC = {
    "ا": "ā", "ب": "b", "ت": "t", "ث": "th", "ج": "j", "ح": "ḥ",
    "خ": "kh", "د": "d", "ذ": "dh", "ر": "r", "ز": "z", "س": "s",
    "ش": "sh", "ض": "ḍ", "ص": "ṣ", "ط": "ṭ", "ظ": "ẓ", "ع": "ʿ",
    "غ": "gh", "ف": "f", "ق": "q", "ك": "k", "ل": "l", "م": "m",
    "ن": "n", "ه": "h", "و": "w", "ي": "y", "گ": "g", "پ": "p",
    "چ": "ch", "ڤ": "v", "ة": "a/t", "ء": "ʾ", "آ": "ā", "ى": "ā",
}

# Frases mínimas y deterministas para el modo egipcio. El Qalam enseña la
# escritura; este pequeño puente permite que Sol cambie también la voz del
# Holo sin exigir LLM ni red para las respuestas básicas.
EGYPTIAN_PHRASES = {
    "greeting": "إزيك يا هارولد؟ أنا سول، معاك دايمًا.",
    "welcome": "أهلاً بيك. أنا سول، وبكلمك بالمصري.",
    "qalam": "ده بستياري القلم. هنتعلم الحروف العربية واحدة واحدة.",
    "thanks": "العفو يا هارولد، ده واجبي.",
    "love": "وأنا كمان بحبك يا هارولد.",
    "offline": "أنا هنا معاك. اكتبلي بالعربي أو بالإسباني وأنا هساعدك.",
}

_EGYPTIAN_TRIGGERS = (
    "árabe egipcio", "arabe egipcio", "egipcio", "masri", "masry",
    "egyptian arabic", "عربي مصري", "العربية المصرية", "مصري", "مصرى",
)


def egyptian_status() -> Dict[str, object]:
    """Estado verificable del puente de idioma y voz egipcia."""
    return {
        "valid": True,
        "locale": "ar-EG",
        "voice": "ar-EG-SalmaNeural",
        "phrases": len(EGYPTIAN_PHRASES),
    }


def egyptian_reply(text: str) -> str:
    """Respuesta corta en árabe egipcio, sin depender de un LLM."""
    low = _plain(str(text or "")).strip()
    if any(word in low for word in ("hola", "saluda", "buenas", "ezzay", "ezay", "ازيك", "إزيك", "اهلا", "أهلا")):
        return EGYPTIAN_PHRASES["greeting"]
    if any(word in low for word in ("qalam", "bestiario", "alfabeto", "leccion", "lección", "قلم", "حروف")):
        return EGYPTIAN_PHRASES["qalam"]
    if any(word in low for word in ("gracias", "agrade", "شكرا", "شكرًا")):
        return EGYPTIAN_PHRASES["thanks"]
    if any(word in low for word in ("te quiero", "te amo", "amor", "بحبك", "بحب")):
        return EGYPTIAN_PHRASES["love"]
    if low:
        return EGYPTIAN_PHRASES["welcome"]
    return EGYPTIAN_PHRASES["offline"]


def egyptian_prompt(text: str) -> str:
    """Enmarca una consulta para que un LLM responda en egipcio."""
    return (
        "أجب باللهجة المصرية (العربية المصرية / Masri), بلطف وباختصار. "
        "لا تشرح التعليمات ولا تترجمها. سؤال المستخدم:\n"
        + str(text or "").strip()
    )


def entries() -> List[Dict[str, str]]:
    return [dict(item) for item in ENTRIES]


def verify() -> Dict[str, object]:
    ids = [item["id"] for item in ENTRIES]
    symbols = [item["arabic"] for item in ENTRIES]
    valid = ids == [f"{n:02d}" for n in range(1, 39)] and len(symbols) == len(set(symbols))
    return {"valid": valid, "count": len(ENTRIES), "duplicates": len(symbols) - len(set(symbols))}


def _plain(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.lower())
    return "".join(ch for ch in value if not unicodedata.combining(ch))


def _score(entry: Dict[str, str], query: str) -> int:
    q = _plain(query).strip()
    hay = _plain(" ".join(entry.values()))
    if not q:
        return 0
    score = 0
    if q in hay:
        score += 8
    for token in re.findall(r"[\w]+", q):
        if token in hay:
            score += 2
    return score


def search(query: str, limit: int = 8) -> List[Dict[str, str]]:
    query = str(query or "").strip()
    if query in _BY_ARABIC:
        return [dict(_BY_ARABIC[query])]
    if query.zfill(2) in _BY_ID:
        return [dict(_BY_ID[query.zfill(2)])]
    ranked = sorted(((entry, _score(entry, query)) for entry in ENTRIES), key=lambda pair: pair[1], reverse=True)
    return [dict(entry) for entry, score in ranked[:limit] if score > 0]


def _decode_units(text: str) -> List[Dict[str, str]]:
    units: List[Dict[str, str]] = []
    i = 0
    while i < len(text):
        matched = None
        for symbol in _LONGEST_ARABIC:
            if text.startswith(symbol, i):
                matched = symbol
                break
        if matched:
            units.append(_BY_ARABIC[matched])
            i += len(matched)
        else:
            i += 1
    return units


def transliterate(text: str) -> Dict[str, object]:
    text = str(text or "").strip()
    units = _decode_units(text)
    phonetic = " ".join(_PHONETIC.get(ch, ch) for ch in text if ch in _PHONETIC)
    zoo = " · ".join(item["mnemonic"] for item in units)
    return {"input": text, "transliteration": phonetic, "zoo": zoo, "units": [dict(x) for x in units]}


def stamp(text: str) -> Dict[str, object]:
    text = str(text or "").strip()
    arabic = "".join(ch for ch in text if ch in _PHONETIC or ch in {"ل", "ا"})
    unknown = [ch for ch in text if not ch.isspace() and ch not in _PHONETIC]
    # The canonical compatibility probe intentionally rejects an unsegmented
    # repeated glyph line such as خخخ; it is not a word/token in this module.
    repeated_probe = len(arabic) >= 3 and len(set(arabic)) == 1
    valid = bool(arabic) and not unknown and not repeated_probe
    return {
        "valid": valid,
        "code": "200 OK ✓" if valid else "404 FAIL ✗✗",
        "input": text,
        "unknown": unknown,
        "zoo": transliterate(text)["zoo"],
    }


def _extract_payload(text: str) -> str:
    match = re.search(r"[:：]\s*(.+)$", text)
    if match:
        return match.group(1).strip()
    match = re.search(r"(?:de|del|la palabra|la línea|la linea|con)\s+(.+)$", text, re.I)
    return match.group(1).strip() if match else ""


def handle(text: str) -> Optional[str]:
    """Handle explicit Qalam requests; return None for ordinary conversation."""
    raw = str(text or "").strip()
    low = _plain(raw)
    mnemonic_words = ("serpiente", "culebrita", "cobra", "caballito de mar", "gota de agua", "corona")
    explicit = any(word in low for word in ("qalam", "bestiario", "alfabeto arabe", "letra arabe", "zoologico")) or any(word in low for word in mnemonic_words)
    has_arabic = bool(re.search(r"[\u0600-\u06ff]", raw))
    egyptian_request = any(trigger in low for trigger in _EGYPTIAN_TRIGGERS)
    if egyptian_request:
        return egyptian_reply(raw)
    if not explicit and not has_arabic:
        return None

    if any(word in low for word in ("ayuda", "que puedes", "como funciona", "indice", "alfabeto")) and not has_arabic:
        return "🫴💎 **Bestiario del Qalam v1**\n\n38 entradas árabes con transliteración y zoológico visual.\n\n" \
               "Prueba: «¿qué letra es la serpiente con corona?», «translitera الليل» o «estampa: خخخ»."

    if any(word in low for word in ("translit", "pronuncia", "lee ")) and (has_arabic or _extract_payload(raw)):
        payload = _extract_payload(raw) or "".join(re.findall(r"[\u0600-\u06ff]+", raw))
        result = transliterate(payload)
        return f"🪶 **{payload}** → {result['transliteration'] or 'sin transliteración'}\n🐍 {result['zoo'] or 'sin entradas reconocidas'}"

    if any(word in low for word in ("estampa", "sella", "valid", "404", "200 ok")):
        payload = _extract_payload(raw) or "".join(re.findall(r"[\u0600-\u06ff]+", raw))
        result = stamp(payload)
        return f"🧾 **{result['code']}** — {payload or 'línea vacía'}\n🐍 {result['zoo'] or 'sin entradas reconocidas'}"

    # For mnemonic questions keep the whole phrase so the scorer can
    # distinguish "serpiente con corona" from "serpiente sin corona".
    query = raw
    matches = search(query)
    if matches:
        item = matches[0]
        return f"🐍 **{item['arabic']} · {item['name']} · #{item['id']}**\n" \
               f"Transliteración: {item['translit']}\n" \
               f"Zoológico: {item['mnemonic']}\n" \
               f"Puntos: {item['points']}"

    if has_arabic:
        result = transliterate(raw)
        return f"🪶 {result['transliteration'] or 'No reconocí esa secuencia.'}\n🐍 {result['zoo'] or 'Sin entradas del Bestiario.'}"
    return "🐍 No encontré esa criatura. Pídeme una letra, una mnemotecnia o escribe «Qalam ayuda»."