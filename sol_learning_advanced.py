#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sol_learning_advanced.py — Sistema de Inmersión Lingüística (SIL)"""

import sil_advanced
import json
import random
import math
import re
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

# ============================================================
# CONFIGURACIÓN
# ============================================================
SOL_HOME = Path.home() / ".sol"
LESSONS_DIR = SOL_HOME / "lessons"
PROGRESS_FILE = SOL_HOME / "learning_progress.json"
SRS_FILE = SOL_HOME / "srs_data.json"

LESSONS_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================
# GESTIÓN DE LECCIONES
# ============================================================
def _load_lessons() -> Dict:
    if LESSONS_DIR.exists():
        lessons = {}
        for f in LESSONS_DIR.glob("*.json"):
            try:
                data = json.loads(f.read_text())
                lessons[f.stem] = data
            except Exception:
                pass
        if lessons:
            return lessons
    _create_default_lessons()
    return _load_lessons()

def _create_default_lessons():
    """Crea lecciones por defecto (Chino y Japonés)."""
    chino_lessons = {
        "saludos": {
            "title": "Saludos y presentaciones",
            "grammar": {
                "title": "Estructura básica",
                "explanation": "En chino, el orden es Sujeto + Verbo + Objeto. Ej: 我 爱 你 (yo amar tú).",
                "examples": ["你好 = hola", "再见 = adiós"]
            },
            "vocabulary": [
                {"word": "你好", "pinyin": "nǐ hǎo", "meaning": "hola"},
                {"word": "再见", "pinyin": "zài jiàn", "meaning": "adiós"},
                {"word": "谢谢", "pinyin": "xiè xiè", "meaning": "gracias"},
                {"word": "不客气", "pinyin": "bù kè qì", "meaning": "de nada"},
                {"word": "对不起", "pinyin": "duì bu qǐ", "meaning": "lo siento"}
            ],
            "phrases": [
                {"chinese": "你好吗？", "pinyin": "nǐ hǎo ma?", "spanish": "¿Cómo estás?"},
                {"chinese": "我很好，谢谢", "pinyin": "wǒ hěn hǎo, xiè xiè", "spanish": "Estoy bien, gracias."},
                {"chinese": "你叫什么名字？", "pinyin": "nǐ jiào shén me míng zi?", "spanish": "¿Cómo te llamas?"},
                {"chinese": "我叫...", "pinyin": "wǒ jiào...", "spanish": "Me llamo..."}
            ],
            "dialogue": [
                {"personA": "你好！", "personB": "你好！"},
                {"personA": "你好吗？", "personB": "我很好，谢谢。你呢？"},
                {"personA": "我也很好。", "personB": "太好了。"}
            ],
            "exercises": [
                {"type": "translate", "question": "Traduce 'hola' al chino", "answer": "你好"},
                {"type": "translate", "question": "Traduce 'gracias' al chino", "answer": "谢谢"},
                {"type": "translate", "question": "Traduce '¿Cómo estás?' al chino", "answer": "你好吗？"}
            ]
        },
        "comida": {
            "title": "Comida y bebida",
            "grammar": {
                "title": "Verbo 吃 (comer) y 喝 (beber)",
                "explanation": "En chino, 吃 se usa para comida sólida, 喝 para líquidos.",
                "examples": ["我吃米饭 = como arroz", "我喝水 = bebo agua"]
            },
            "vocabulary": [
                {"word": "吃", "pinyin": "chī", "meaning": "comer"},
                {"word": "喝", "pinyin": "hē", "meaning": "beber"},
                {"word": "米饭", "pinyin": "mǐ fàn", "meaning": "arroz"},
                {"word": "面条", "pinyin": "miàn tiáo", "meaning": "fideos"},
                {"word": "水", "pinyin": "shuǐ", "meaning": "agua"},
                {"word": "茶", "pinyin": "chá", "meaning": "té"},
                {"word": "啤酒", "pinyin": "pí jiǔ", "meaning": "cerveza"}
            ],
            "phrases": [
                {"chinese": "我吃米饭", "pinyin": "wǒ chī mǐ fàn", "spanish": "Como arroz"},
                {"chinese": "我喝水", "pinyin": "wǒ hē shuǐ", "spanish": "Bebo agua"},
                {"chinese": "你要茶吗？", "pinyin": "nǐ yào chá ma?", "spanish": "¿Quieres té?"},
                {"chinese": "我要啤酒", "pinyin": "wǒ yào pí jiǔ", "spanish": "Quiero cerveza"}
            ],
            "dialogue": [
                {"personA": "你想吃什么？", "personB": "我想吃面条。"},
                {"personA": "你想喝什么？", "personB": "我想喝啤酒。"}
            ],
            "exercises": [
                {"type": "translate", "question": "Traduce 'Como arroz' al chino", "answer": "我吃米饭"},
                {"type": "translate", "question": "Traduce 'Bebo agua' al chino", "answer": "我喝水"}
            ]
        },
        "numeros": {
            "title": "Números y cantidades",
            "grammar": {
                "title": "Sistema de números chinos",
                "explanation": "Los números del 1 al 10: 一二三四五六七八九十. Del 11 al 19: 十 + número.",
                "examples": ["一 = 1", "十 = 10", "十一 = 11"]
            },
            "vocabulary": [
                {"word": "一", "pinyin": "yī", "meaning": "uno"},
                {"word": "二", "pinyin": "èr", "meaning": "dos"},
                {"word": "三", "pinyin": "sān", "meaning": "tres"},
                {"word": "四", "pinyin": "sì", "meaning": "cuatro"},
                {"word": "五", "pinyin": "wǔ", "meaning": "cinco"},
                {"word": "十", "pinyin": "shí", "meaning": "diez"},
                {"word": "百", "pinyin": "bǎi", "meaning": "cien"}
            ],
            "phrases": [
                {"chinese": "三个苹果", "pinyin": "sān ge píng guǒ", "spanish": "Tres manzanas"},
                {"chinese": "十个人", "pinyin": "shí ge rén", "spanish": "Diez personas"},
                {"chinese": "多少钱？", "pinyin": "duō shǎo qián?", "spanish": "¿Cuánto cuesta?"}
            ],
            "dialogue": [
                {"personA": "这个多少钱？", "personB": "五十块。"},
                {"personA": "太贵了！", "personB": "四十块，怎么样？"}
            ],
            "exercises": [
                {"type": "translate", "question": "Traduce 'cinco' al chino", "answer": "五"},
                {"type": "translate", "question": "Traduce '¿Cuánto cuesta?' al chino", "answer": "多少钱？"}
            ]
        }
    }
    japones_lessons = {
        "saludos": {
            "title": "Saludos básicos en japonés",
            "grammar": {
                "title": "Partículas básicas",
                "explanation": "En japonés, la partícula は marca el tema. Ej: 私は (watashi wa) = yo (como tema).",
                "examples": ["こんにちは = hola", "さようなら = adiós"]
            },
            "vocabulary": [
                {"word": "こんにちは", "romaji": "konnichiwa", "meaning": "hola"},
                {"word": "こんばんは", "romaji": "konbanwa", "meaning": "buenas noches"},
                {"word": "おはよう", "romaji": "ohayō", "meaning": "buenos días"},
                {"word": "さようなら", "romaji": "sayōnara", "meaning": "adiós"},
                {"word": "ありがとう", "romaji": "arigatō", "meaning": "gracias"},
                {"word": "すみません", "romaji": "sumimasen", "meaning": "perdón / disculpe"},
                {"word": "はい", "romaji": "hai", "meaning": "sí"},
                {"word": "いいえ", "romaji": "iie", "meaning": "no"}
            ],
            "phrases": [
                {"japanese": "お元気ですか？", "romaji": "o-genki desu ka?", "spanish": "¿Cómo estás?"},
                {"japanese": "元気です", "romaji": "genki desu", "spanish": "Estoy bien"},
                {"japanese": "お名前は？", "romaji": "o-namae wa?", "spanish": "¿Cómo te llamas?"},
                {"japanese": "私は...です", "romaji": "watashi wa ... desu", "spanish": "Me llamo..."}
            ],
            "dialogue": [
                {"personA": "こんにちは！", "personB": "こんにちは！"},
                {"personA": "お元気ですか？", "personB": "元気です。あなたは？"},
                {"personA": "元気です。", "personB": "よかった。"}
            ],
            "exercises": [
                {"type": "translate", "question": "Traduce 'hola' al japonés", "answer": "こんにちは"},
                {"type": "translate", "question": "Traduce 'gracias' al japonés", "answer": "ありがとう"}
            ]
        },
        "comida": {
            "title": "Comida y restaurante",
            "grammar": {
                "title": "Verbos comer y beber",
                "explanation": "食べます (tabemasu) = comer, 飲みます (nomimasu) = beber. La partícula を marca el objeto.",
                "examples": ["寿司を食べます = como sushi", "水を飲みます = bebo agua"]
            },
            "vocabulary": [
                {"word": "食べる", "romaji": "taberu", "meaning": "comer"},
                {"word": "飲む", "romaji": "nomu", "meaning": "beber"},
                {"word": "寿司", "romaji": "sushi", "meaning": "sushi"},
                {"word": "水", "romaji": "mizu", "meaning": "agua"},
                {"word": "お茶", "romaji": "ocha", "meaning": "té"},
                {"word": "ご飯", "romaji": "gohan", "meaning": "arroz/comida"},
                {"word": "美味しい", "romaji": "oishii", "meaning": "delicioso"}
            ],
            "phrases": [
                {"japanese": "何を食べますか？", "romaji": "nani o tabemasu ka?", "spanish": "¿Qué vas a comer?"},
                {"japanese": "寿司を食べます", "romaji": "sushi o tabemasu", "spanish": "Como sushi"},
                {"japanese": "美味しいです", "romaji": "oishii desu", "spanish": "Está delicioso"}
            ],
            "dialogue": [
                {"personA": "何を食べますか？", "personB": "寿司を食べます。"},
                {"personA": "美味しいですか？", "personB": "はい、とても美味しいです。"}
            ],
            "exercises": [
                {"type": "translate", "question": "Traduce 'como sushi' al japonés", "answer": "寿司を食べます"},
                {"type": "translate", "question": "Traduce 'delicioso' al japonés", "answer": "美味しい"}
            ]
        }
    }
    for lang, lessons in [("chino", chino_lessons), ("japones", japones_lessons)]:
        for name, content in lessons.items():
            path = LESSONS_DIR / f"{lang}_{name}.json"
            path.write_text(json.dumps(content, ensure_ascii=False, indent=2))

# ============================================================
# SISTEMA DE REPETICIÓN ESPACIADA (SRS) — SM-2
# ============================================================
class SRSManager:
    def __init__(self):
        self.data = self._load()

    def _load(self) -> Dict:
        if SRS_FILE.exists():
            try:
                return json.loads(SRS_FILE.read_text())
            except Exception:
                pass
        return {"items": {}, "stats": {"total": 0, "learned": 0, "due_today": 0}}

    def _save(self):
        SRS_FILE.write_text(json.dumps(self.data, indent=2, ensure_ascii=False))

    def add_item(self, item_id: str, item_type: str, data: Dict):
        if item_id in self.data["items"]:
            return
        now = datetime.now().isoformat()
        self.data["items"][item_id] = {
            "type": item_type,
            "data": data,
            "ease_factor": 2.5,
            "interval": 1,
            "repetitions": 0,
            "next_review": now,
            "last_review": None,
            "correct_count": 0,
            "wrong_count": 0
        }
        self.data["stats"]["total"] += 1
        self._save()

    def review(self, item_id: str, quality: int):
        if item_id not in self.data["items"]:
            return
        item = self.data["items"][item_id]
        if quality < 3:
            item["repetitions"] = 0
            item["interval"] = 1
            item["wrong_count"] += 1
        else:
            item["repetitions"] += 1
            if item["repetitions"] == 1:
                item["interval"] = 1
            elif item["repetitions"] == 2:
                item["interval"] = 6
            else:
                item["interval"] = int(item["interval"] * item["ease_factor"])
            item["ease_factor"] = max(1.3, item["ease_factor"] + (0.1 - (5 - quality) * 0.08))
            item["correct_count"] += 1
        item["last_review"] = datetime.now().isoformat()
        item["next_review"] = (datetime.now() + timedelta(days=item["interval"])).isoformat()
        self._save()

    def get_due_items(self, limit: int = 20) -> List[Tuple[str, Dict]]:
        now = datetime.now()
        due = []
        for item_id, data in self.data["items"].items():
            next_review = datetime.fromisoformat(data["next_review"])
            if next_review <= now:
                due.append((item_id, data))
        due.sort(key=lambda x: x[1]["next_review"])
        return due[:limit]

    def get_stats(self) -> Dict:
        total = self.data["stats"]["total"]
        learned = len([i for i in self.data["items"].values() if i["repetitions"] > 0])
        due_today = len(self.get_due_items(999))
        return {
            "total_items": total,
            "learned_items": learned,
            "due_today": due_today,
            "retention_rate": round((learned / total * 100) if total > 0 else 0, 1)
        }

srs = SRSManager()

# ============================================================
# FUNCIONES DE APRENDIZAJE
# ============================================================
def get_lesson(language: str, lesson_name: str) -> Optional[Dict]:
    lessons = _load_lessons()
    return lessons.get(f"{language}_{lesson_name}")

def list_lessons(language: str) -> List[str]:
    lessons = _load_lessons()
    return [k.split("_")[1] for k in lessons.keys() if k.startswith(f"{language}_")]

def get_next_practice_item(language: str, lesson_name: str = None) -> Optional[Dict]:
    due = srs.get_due_items(5)
    if due:
        item_id, data = due[0]
        return {"type": "srs_review", "item_id": item_id, "data": data["data"]}
    if lesson_name:
        lesson = get_lesson(language, lesson_name)
        if lesson:
            pool = []
            for v in lesson.get("vocabulary", []):
                pool.append({"type": "vocabulary", "data": v})
            for p in lesson.get("phrases", []):
                pool.append({"type": "phrase", "data": p})
            if pool:
                return random.choice(pool)
    return None

def process_practice_answer(item_type: str, item_id: str, quality: int):
    if item_type == "srs_review":
        srs.review(item_id, quality)
    else:
        srs.add_item(item_id, item_type, {"content": item_id})
        srs.review(item_id, quality)

def get_learning_stats() -> Dict:
    srs_stats = srs.get_stats()
    lessons = _load_lessons()
    total_lessons = sum(1 for _ in lessons.keys())
    return {
        "srs": srs_stats,
        "total_lessons": total_lessons,
        "languages": {
            "chino": len(list_lessons("chino")),
            "japones": len(list_lessons("japones"))
        }
    }

def export_progress() -> Dict:
    return {
        "srs": srs.data,
        "lessons": _load_lessons(),
        "timestamp": datetime.now().isoformat()
    }

# ═════════════════════════════════════════════════════════════════
# LECCIONES AVANZADAS (desde sil_advanced.py)
# ═════════════════════════════════════════════════════════════════
def get_advanced_lesson_data():
    """Devuelve todas las lecciones avanzadas de sil_advanced."""
    try:
        return sil_advanced.get_advanced_lessons()
    except Exception:
        return {}

def get_advanced_levels():
    """Lista niveles avanzados disponibles."""
    try:
        return sil_advanced.list_advanced_levels()
    except Exception:
        return []

def get_advanced_total():
    """Total de items avanzados."""
    try:
        return sil_advanced.get_total_items()
    except Exception:
        return 0
