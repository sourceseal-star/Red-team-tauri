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
    # FIX 2026-09-03: antes era todo-o-nada (si ya había AL MENOS un
    # archivo, nunca se creaban los defaults faltantes) — ahora siempre
    # rellena las lecciones default que aún no existan, sin tocar las
    # que Harold ya tiene, y luego lee TODO del disco.
    _create_default_lessons()
    lessons = {}
    for f in LESSONS_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text())
            lessons[f.stem] = data
        except Exception:
            pass
    _merge_defaults_into(lessons)
    return lessons

def _default_lessons():
    """Construye (sin escribir) el set completo de lecciones default.
    Separado de _create_default_lessons para que _merge_defaults_into
    pueda usarlo como fuente de verdad sin tocar disco."""
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
                {"word": "对不起", "pinyin": "duì bu qǐ", "meaning": "lo siento"},
                {"word": "早上好", "pinyin": "zǎo shàng hǎo", "meaning": "buenos días"},
                {"word": "晚上好", "pinyin": "wǎn shàng hǎo", "meaning": "buenas noches (al llegar)"},
                {"word": "没关系", "pinyin": "méi guān xi", "meaning": "no hay problema"}
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
                {"word": "啤酒", "pinyin": "pí jiǔ", "meaning": "cerveza"},
                {"word": "咖啡", "pinyin": "kā fēi", "meaning": "café"},
                {"word": "鸡蛋", "pinyin": "jī dàn", "meaning": "huevo"},
                {"word": "肉", "pinyin": "ròu", "meaning": "carne"},
                {"word": "鱼", "pinyin": "yú", "meaning": "pescado"}
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
                {"word": "六", "pinyin": "liù", "meaning": "seis"},
                {"word": "七", "pinyin": "qī", "meaning": "siete"},
                {"word": "八", "pinyin": "bā", "meaning": "ocho"},
                {"word": "九", "pinyin": "jiǔ", "meaning": "nueve"},
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
    # ── Categorías nuevas (2026-09-03) — vocabulario cotidiano y técnico,
    #    tomado del set completo que Harold armó, personalizado con su
    #    nombre en los ejemplos como en las 3 lecciones originales.
    chino_lessons["familia"] = {
        "title": "Familia",
        "grammar": {
            "title": "Posesivo 的 (de) con familia",
            "explanation": "我的 (wǒ de) = mi/mío. Con familia cercana a veces se omite: 我爸爸 en vez de 我的爸爸.",
            "examples": ["我爸爸 = mi papá", "我妈妈 = mi mamá"]
        },
        "vocabulary": [
            {"word": "爸爸", "pinyin": "bà ba", "meaning": "papá"},
            {"word": "妈妈", "pinyin": "mā ma", "meaning": "mamá"},
            {"word": "哥哥", "pinyin": "gē ge", "meaning": "hermano mayor"},
            {"word": "姐姐", "pinyin": "jiě jie", "meaning": "hermana mayor"},
            {"word": "弟弟", "pinyin": "dì di", "meaning": "hermano menor"},
            {"word": "妹妹", "pinyin": "mèi mei", "meaning": "hermana menor"}
        ],
        "phrases": [
            {"chinese": "我爸爸是工程师", "pinyin": "wǒ bà ba shì gōng chéng shī", "spanish": "Mi papá es ingeniero."},
            {"chinese": "Harold有一个哥哥", "pinyin": "Harold yǒu yí ge gē ge", "spanish": "Harold tiene un hermano mayor."}
        ],
        "dialogue": [
            {"personA": "你家有几个人？", "personB": "我家有四个人：爸爸，妈妈，哥哥和我。"}
        ],
        "exercises": [
            {"type": "translate", "question": "Traduce 'mamá' al chino", "answer": "妈妈"},
            {"type": "translate", "question": "Traduce 'hermano mayor' al chino", "answer": "哥哥"}
        ]
    }
    chino_lessons["tecnologia"] = {
        "title": "Tecnología (para Harold, dev)",
        "grammar": {
            "title": "Sustantivos compuestos técnicos",
            "explanation": "Muchas palabras técnicas son compuestos lógicos: 数据 (datos) + 库 (almacén) = 数据库 (base de datos).",
            "examples": ["电脑 = computadora (电 electricidad + 脑 cerebro)", "数据库 = base de datos"]
        },
        "vocabulary": [
            {"word": "电脑", "pinyin": "diàn nǎo", "meaning": "computadora"},
            {"word": "手机", "pinyin": "shǒu jī", "meaning": "teléfono móvil"},
            {"word": "网络", "pinyin": "wǎng luò", "meaning": "red/internet"},
            {"word": "软件", "pinyin": "ruǎn jiàn", "meaning": "software"},
            {"word": "程序", "pinyin": "chéng xù", "meaning": "programa"},
            {"word": "代码", "pinyin": "dài mǎ", "meaning": "código"},
            {"word": "服务器", "pinyin": "fú wù qì", "meaning": "servidor"},
            {"word": "数据库", "pinyin": "shù jù kù", "meaning": "base de datos"},
            {"word": "加密", "pinyin": "jiā mì", "meaning": "encriptar"},
            {"word": "安全", "pinyin": "ān quán", "meaning": "seguridad"}
        ],
        "phrases": [
            {"chinese": "Harold在写代码", "pinyin": "Harold zài xiě dài mǎ", "spanish": "Harold está escribiendo código."},
            {"chinese": "数据库很大", "pinyin": "shù jù kù hěn dà", "spanish": "La base de datos es grande."},
            {"chinese": "网络安全很重要", "pinyin": "wǎng luò ān quán hěn zhòng yào", "spanish": "La seguridad de red es importante."}
        ],
        "dialogue": [
            {"personA": "你在做什么？", "personB": "我在写代码，做一个安全系统。"}
        ],
        "exercises": [
            {"type": "translate", "question": "Traduce 'código' al chino", "answer": "代码"},
            {"type": "translate", "question": "Traduce 'seguridad' al chino", "answer": "安全"}
        ]
    }
    chino_lessons["emociones"] = {
        "title": "Emociones",
        "grammar": {
            "title": "Adjetivos de emoción con 很 (muy)",
            "explanation": "很 (hěn) antes de un adjetivo/emoción suaviza el énfasis: 我很高兴 = estoy (bastante) feliz.",
            "examples": ["我很高兴 = estoy feliz", "我很累 = estoy cansado"]
        },
        "vocabulary": [
            {"word": "高兴", "pinyin": "gāo xìng", "meaning": "feliz"},
            {"word": "累", "pinyin": "lèi", "meaning": "cansado"},
            {"word": "饿", "pinyin": "è", "meaning": "hambriento"},
            {"word": "冷", "pinyin": "lěng", "meaning": "frío"},
            {"word": "热", "pinyin": "rè", "meaning": "caliente"},
            {"word": "担心", "pinyin": "dān xīn", "meaning": "preocupado"},
            {"word": "渴", "pinyin": "kě", "meaning": "sediento"},
            {"word": "生气", "pinyin": "shēng qì", "meaning": "enojado"}
        ],
        "phrases": [
            {"chinese": "Harold今天很高兴", "pinyin": "Harold jīn tiān hěn gāo xìng", "spanish": "Harold está feliz hoy."},
            {"chinese": "别担心，没事的", "pinyin": "bié dān xīn, méi shì de", "spanish": "No te preocupes, no pasa nada."}
        ],
        "dialogue": [
            {"personA": "你今天怎么样？", "personB": "我有点累，但是很高兴。"}
        ],
        "exercises": [
            {"type": "translate", "question": "Traduce 'feliz' al chino", "answer": "高兴"},
            {"type": "translate", "question": "Traduce 'preocupado' al chino", "answer": "担心"}
        ]
    }
    chino_lessons["acciones"] = {
        "title": "Acciones cotidianas",
        "grammar": {
            "title": "Verbo + 在 para progresivo",
            "explanation": "在 (zài) antes del verbo indica acción en curso: 我在学习 = estoy estudiando.",
            "examples": ["我在工作 = estoy trabajando", "我在学习中文 = estoy estudiando chino"]
        },
        "vocabulary": [
            {"word": "看", "pinyin": "kàn", "meaning": "ver/mirar"},
            {"word": "听", "pinyin": "tīng", "meaning": "escuchar"},
            {"word": "说", "pinyin": "shuō", "meaning": "hablar/decir"},
            {"word": "写", "pinyin": "xiě", "meaning": "escribir"},
            {"word": "学习", "pinyin": "xué xí", "meaning": "estudiar"},
            {"word": "工作", "pinyin": "gōng zuò", "meaning": "trabajar"},
            {"word": "睡觉", "pinyin": "shuì jiào", "meaning": "dormir"},
            {"word": "吃", "pinyin": "chī", "meaning": "comer"},
            {"word": "喝", "pinyin": "hē", "meaning": "beber"},
            {"word": "读", "pinyin": "dú", "meaning": "leer"}
        ],
        "phrases": [
            {"chinese": "Harold在家里工作", "pinyin": "Harold zài jiā lǐ gōng zuò", "spanish": "Harold trabaja desde casa."},
            {"chinese": "我在学习中文", "pinyin": "wǒ zài xué xí zhōng wén", "spanish": "Estoy estudiando chino."}
        ],
        "dialogue": [
            {"personA": "你在做什么？", "personB": "我在写代码。你呢？"}
        ],
        "exercises": [
            {"type": "translate", "question": "Traduce 'estudiar' al chino", "answer": "学习"},
            {"type": "translate", "question": "Traduce 'trabajar' al chino", "answer": "工作"}
        ]
    }
    chino_lessons["tiempo"] = {
        "title": "Tiempo (hoy, ayer, mañana)",
        "grammar": {
            "title": "Palabras de tiempo van antes del verbo",
            "explanation": "En chino las expresiones de tiempo se ponen antes del verbo, no después como en español: 今天 (hoy) 我 (yo) 工作 (trabajo).",
            "examples": ["今天我工作 = hoy trabajo", "明天见 = nos vemos mañana"]
        },
        "vocabulary": [
            {"word": "今天", "pinyin": "jīn tiān", "meaning": "hoy"},
            {"word": "明天", "pinyin": "míng tiān", "meaning": "mañana"},
            {"word": "昨天", "pinyin": "zuó tiān", "meaning": "ayer"},
            {"word": "现在", "pinyin": "xiàn zài", "meaning": "ahora"},
            {"word": "早上", "pinyin": "zǎo shàng", "meaning": "mañana (AM)"},
            {"word": "下午", "pinyin": "xià wǔ", "meaning": "tarde"},
            {"word": "晚上", "pinyin": "wǎn shàng", "meaning": "noche"}
        ],
        "phrases": [
            {"chinese": "Harold现在在工作", "pinyin": "Harold xiàn zài zài gōng zuò", "spanish": "Harold está trabajando ahora."},
            {"chinese": "明天见！", "pinyin": "míng tiān jiàn!", "spanish": "¡Nos vemos mañana!"}
        ],
        "dialogue": [
            {"personA": "你现在几点睡觉？", "personB": "晚上十一点。"}
        ],
        "exercises": [
            {"type": "translate", "question": "Traduce 'ahora' al chino", "answer": "现在"},
            {"type": "translate", "question": "Traduce 'mañana' (día siguiente) al chino", "answer": "明天"}
        ]
    }
    chino_lessons["lugares"] = {
        "title": "Lugares",
        "grammar": {
            "title": "en + lugar = 在 + lugar",
            "explanation": "在 (zài) antes de un lugar significa 'en'/'está en': 我在家 = estoy en casa.",
            "examples": ["我在家 = estoy en casa", "我在公司工作 = trabajo en la empresa"]
        },
        "vocabulary": [
            {"word": "家", "pinyin": "jiā", "meaning": "casa"},
            {"word": "学校", "pinyin": "xué xiào", "meaning": "escuela"},
            {"word": "公司", "pinyin": "gōng sī", "meaning": "empresa"},
            {"word": "商店", "pinyin": "shāng diàn", "meaning": "tienda"},
            {"word": "餐厅", "pinyin": "cān tīng", "meaning": "restaurante"},
            {"word": "医院", "pinyin": "yī yuàn", "meaning": "hospital"}
        ],
        "phrases": [
            {"chinese": "Harold在家工作", "pinyin": "Harold zài jiā gōng zuò", "spanish": "Harold trabaja en casa."},
            {"chinese": "我们在餐厅吃饭", "pinyin": "wǒ men zài cān tīng chī fàn", "spanish": "Comemos en el restaurante."}
        ],
        "dialogue": [
            {"personA": "你在哪里？", "personB": "我在家，正在写代码。"}
        ],
        "exercises": [
            {"type": "translate", "question": "Traduce 'casa' al chino", "answer": "家"},
            {"type": "translate", "question": "Traduce 'empresa' al chino", "answer": "公司"}
        ]
    }

    # -*- coding: utf-8 -*-
    """Expansión 2026-09-03: convierte el set básico de 77 palabras en un
    área de aprendizaje real. 10 lecciones nuevas + enriquecimiento de las
    9 existentes. Se inserta al final de _default_lessons(), antes del return."""

    # ── ENRIQUECER las 9 existentes (solo palabras que NO están ya) ──
    for _name, _extra_vocab, _extra_phrases in [
        ("saludos",
         [{"word": "请问", "pinyin": "qǐng wèn", "meaning": "disculpe (para preguntar)"},
          {"word": "欢迎", "pinyin": "huān yíng", "meaning": "bienvenido"},
          {"word": "好久不见", "pinyin": "hǎo jiǔ bù jiàn", "meaning": "cuánto tiempo sin verte"},
          {"word": "我是哥伦比亚人", "pinyin": "wǒ shì Gē lún bǐ yà rén", "meaning": "soy colombiano"},
          {"word": "贵姓", "pinyin": "guì xìng", "meaning": "¿cuál es su apellido? (formal)"}],
         [{"chinese": "很高兴认识你", "pinyin": "hěn gāo xìng rèn shi nǐ", "spanish": "Mucho gusto en conocerte."},
          {"chinese": "你是哪国人？", "pinyin": "nǐ shì nǎ guó rén?", "spanish": "¿De qué país eres?"},
          {"chinese": "好久不见！最近怎么样？", "pinyin": "hǎo jiǔ bù jiàn! zuì jìn zěn me yàng?", "spanish": "¡Cuánto tiempo! ¿Cómo te ha ido?"}]),
        ("comida",
         [{"word": "米饭", "pinyin": "mǐ fàn", "meaning": "arroz cocido"},
          {"word": "面条", "pinyin": "miàn tiáo", "meaning": "fideos"},
          {"word": "鸡肉", "pinyin": "jī ròu", "meaning": "pollo"},
          {"word": "牛肉", "pinyin": "niú ròu", "meaning": "carne de res"},
          {"word": "鱼", "pinyin": "yú", "meaning": "pescado"},
          {"word": "蔬菜", "pinyin": "shū cài", "meaning": "verduras"},
          {"word": "水果", "pinyin": "shuǐ guǒ", "meaning": "fruta"},
          {"word": "辣椒", "pinyin": "là jiāo", "meaning": "chile (¡como en casa!)"},
          {"word": "好吃", "pinyin": "hǎo chī", "meaning": "delicioso"},
          {"word": "饿了", "pinyin": "è le", "meaning": "tener hambre"}],
         [{"chinese": "我想吃饭", "pinyin": "wǒ xiǎng chī fàn", "spanish": "Quiero comer."},
          {"chinese": "这个菜很辣", "pinyin": "zhè ge cài hěn là", "spanish": "Este plato es muy picante."},
          {"chinese": "服务员，买单！", "pinyin": "fú wù yuán, mǎi dān!", "spanish": "¡Camarero, la cuenta!"}]),
        ("numeros",
         [{"word": "百", "pinyin": "bǎi", "meaning": "cien"},
          {"word": "千", "pinyin": "qiān", "meaning": "mil"},
          {"word": "万", "pinyin": "wàn", "meaning": "diez mil"},
          {"word": "第一", "pinyin": "dì yī", "meaning": "primero"},
          {"word": "一半", "pinyin": "yī bàn", "meaning": "la mitad"}],
         [{"chinese": "一百二十三", "pinyin": "yī bǎi èr shí sān", "spanish": "ciento veintitrés"},
          {"chinese": "多少钱？", "pinyin": "duō shǎo qián?", "spanish": "¿Cuánto cuesta?"}]),
        ("familia",
         [{"word": "爷爷", "pinyin": "yé ye", "meaning": "abuelo"},
          {"word": "奶奶", "pinyin": "nǎi nai", "meaning": "abuela"},
          {"word": "哥哥", "pinyin": "gē ge", "meaning": "hermano mayor"},
          {"word": "姐姐", "pinyin": "jiě jie", "meaning": "hermana mayor"},
          {"word": "孩子", "pinyin": "hái zi", "meaning": "niño/hijo"},
          {"word": "丈夫", "pinyin": "zhàng fu", "meaning": "esposo"},
          {"word": "妻子", "pinyin": "qī zi", "meaning": "esposa"}],
         [{"chinese": "我爱我的家人", "pinyin": "wǒ ài wǒ de jiā rén", "spanish": "Amo a mi familia."},
          {"chinese": "我有一个姐姐", "pinyin": "wǒ yǒu yī gè jiě jie", "spanish": "Tengo una hermana mayor."}]),
        ("emociones",
         [{"word": "生气", "pinyin": "shēng qì", "meaning": "enojado"},
          {"word": "害怕", "pinyin": "hài pà", "meaning": "tener miedo"},
          {"word": "惊讶", "pinyin": "jīng yà", "meaning": "sorprendido"},
          {"word": "累", "pinyin": "lèi", "meaning": "cansado"},
          {"word": "无聊", "pinyin": "wú liáo", "meaning": "aburrido"},
          {"word": "紧张", "pinyin": "jǐn zhāng", "meaning": "nervioso"}],
         [{"chinese": "别担心", "pinyin": "bié dān xīn", "spanish": "No te preocupes."},
          {"chinese": "我今天很累", "pinyin": "wǒ jīn tiān hěn lèi", "spanish": "Hoy estoy muy cansado."}]),
        ("acciones",
         [{"word": "学习", "pinyin": "xué xí", "meaning": "estudiar"},
          {"word": "写", "pinyin": "xiě", "meaning": "escribir"},
          {"word": "读", "pinyin": "dú", "meaning": "leer"},
          {"word": "买", "pinyin": "mǎi", "meaning": "comprar"},
          {"word": "卖", "pinyin": "mài", "meaning": "vender"},
          {"word": "起床", "pinyin": "qǐ chuáng", "meaning": "levantarse (de la cama)"},
          {"word": "睡觉", "pinyin": "shuì jiào", "meaning": "dormir"}],
         [{"chinese": "我在学中文", "pinyin": "wǒ zài xué zhōng wén", "spanish": "Estoy aprendiendo chino."},
          {"chinese": "我想睡觉", "pinyin": "wǒ xiǎng shuì jiào", "spanish": "Quiero dormir."}]),
        ("lugares",
         [{"word": "学校", "pinyin": "xué xiào", "meaning": "escuela"},
          {"word": "超市", "pinyin": "chāo shì", "meaning": "supermercado"},
          {"word": "银行", "pinyin": "yín háng", "meaning": "banco"},
          {"word": "公园", "pinyin": "gōng yuán", "meaning": "parque"},
          {"word": "医院", "pinyin": "yī yuàn", "meaning": "hospital"},
          {"word": "机场", "pinyin": "jī chǎng", "meaning": "aeropuerto"}],
         [{"chinese": "我在家", "pinyin": "wǒ zài jiā", "spanish": "Estoy en casa."},
          {"chinese": "我去超市", "pinyin": "wǒ qù chāo shì", "spanish": "Voy al supermercado."}]),
    ]:
        _les = chino_lessons.get(_name)
        if isinstance(_les, dict):
            _words = {v.get("word") for v in _les.get("vocabulary", [])}
            for _v in _extra_vocab:
                if _v["word"] not in _words:
                    _les.setdefault("vocabulary", []).append(_v)
            _phr = {p.get("chinese") for p in _les.get("phrases", [])}
            for _p in _extra_phrases:
                if _p["chinese"] not in _phr:
                    _les.setdefault("phrases", []).append(_p)

    # ── 10 LECCIONES NUEVAS ──
    chino_lessons["verbos"] = {
        "title": "Verbos esenciales",
        "grammar": {
            "title": "El verbo 不 (bù) — negación simple",
            "explanation": "Para negar, pon 不 delante del verbo: 我不去 = no voy. El chino no conjuga verbos: no hay -ar/-er/-ir, el tiempo lo marcan palabras como 了, 过, 在.",
            "examples": ["我不吃 = no como", "他不是 = él no es"]
        },
        "vocabulary": [
            {"word": "是", "pinyin": "shì", "meaning": "ser"},
            {"word": "有", "pinyin": "yǒu", "meaning": "tener/haber"},
            {"word": "去", "pinyin": "qù", "meaning": "ir"},
            {"word": "来", "pinyin": "lái", "meaning": "venir"},
            {"word": "看", "pinyin": "kàn", "meaning": "ver/mirar"},
            {"word": "听", "pinyin": "tīng", "meaning": "escuchar"},
            {"word": "说", "pinyin": "shuō", "meaning": "hablar"},
            {"word": "做", "pinyin": "zuò", "meaning": "hacer"},
            {"word": "给", "pinyin": "gěi", "meaning": "dar"},
            {"word": "知道", "pinyin": "zhī dào", "meaning": "saber"},
            {"word": "想", "pinyin": "xiǎng", "meaning": "querer/pensar"},
            {"word": "能", "pinyin": "néng", "meaning": "poder"}
        ],
        "phrases": [
            {"chinese": "我会说一点中文", "pinyin": "wǒ huì shuō yī diǎn zhōng wén", "spanish": "Hablo un poco de chino."},
            {"chinese": "我不知道", "pinyin": "wǒ bù zhī dào", "spanish": "No lo sé."},
            {"chinese": "你能帮我吗？", "pinyin": "nǐ néng bāng wǒ ma?", "spanish": "¿Puedes ayudarme?"},
            {"chinese": "我想去中国", "pinyin": "wǒ xiǎng qù Zhōng guó", "spanish": "Quiero ir a China."}
        ],
        "dialogue": [
            {"personA": "你会说中文吗？", "personB": "会一点。"},
            {"personA": "你在做什么？", "personB": "我在学习。"}
        ],
        "exercises": [
            {"type": "translate", "question": "Traduce 'no lo sé' al chino", "answer": "我不知道"},
            {"type": "translate", "question": "Traduce '¿Puedes ayudarme?' al chino", "answer": "你能帮我吗？"},
            {"type": "translate", "question": "Traduce 'querer' al chino", "answer": "想"}
        ]
    }
    chino_lessons["adjetivos"] = {
        "title": "Adjetivos",
        "grammar": {
            "title": "很 como conector",
            "explanation": "Entre sujeto y adjetivo se usa 很 (hěn): 我很好 = estoy bien. Sin 很, la frase suena comparativa (yo soy EL bueno).",
            "examples": ["她很漂亮 = ella es bonita", "今天很热 = hoy hace calor"]
        },
        "vocabulary": [
            {"word": "大", "pinyin": "dà", "meaning": "grande"},
            {"word": "小", "pinyin": "xiǎo", "meaning": "pequeño"},
            {"word": "好", "pinyin": "hǎo", "meaning": "bueno"},
            {"word": "坏", "pinyin": "huài", "meaning": "malo"},
            {"word": "新", "pinyin": "xīn", "meaning": "nuevo"},
            {"word": "旧", "pinyin": "jiù", "meaning": "viejo (cosas)"},
            {"word": "热", "pinyin": "rè", "meaning": "caliente/calor"},
            {"word": "冷", "pinyin": "lěng", "meaning": "frío"},
            {"word": "快", "pinyin": "kuài", "meaning": "rápido"},
            {"word": "慢", "pinyin": "màn", "meaning": "lento"},
            {"word": "漂亮", "pinyin": "piào liang", "meaning": "bonito/a"},
            {"word": "容易", "pinyin": "róng yì", "meaning": "fácil"},
            {"word": "难", "pinyin": "nán", "meaning": "difícil"}
        ],
        "phrases": [
            {"chinese": "中文很难但是很有意思", "pinyin": "zhōng wén hěn nán dàn shì hěn yǒu yì si", "spanish": "El chino es difícil pero muy interesante."},
            {"chinese": "今天的天气很好", "pinyin": "jīn tiān de tiān qì hěn hǎo", "spanish": "Hoy el clima está muy bueno."},
            {"chinese": "这个手机很快", "pinyin": "zhè ge shǒu jī hěn kuài", "spanish": "Este teléfono es muy rápido."}
        ],
        "dialogue": [
            {"personA": "这本书容易吗？", "personB": "不难，很容易。"}
        ],
        "exercises": [
            {"type": "translate", "question": "Traduce 'grande' al chino", "answer": "大"},
            {"type": "translate", "question": "Traduce 'El chino es difícil' al chino", "answer": "中文很难"}
        ]
    }
    chino_lessons["preguntas"] = {
        "title": "Preguntas y partículas",
        "grammar": {
            "title": "吗 (ma) y 呢 (ne)",
            "explanation": "吗 al final convierte cualquier frase en pregunta sí/no. 呢 devuelve la pregunta ('¿y tú?'). Las preguntas con palabra interrogativa no llevan 吗.",
            "examples": ["你好吗？= ¿estás bien?", "我很好，你呢？= bien, ¿y tú?"]
        },
        "vocabulary": [
            {"word": "什么", "pinyin": "shén me", "meaning": "qué"},
            {"word": "谁", "pinyin": "shéi", "meaning": "quién"},
            {"word": "哪里", "pinyin": "nǎ lǐ", "meaning": "dónde"},
            {"word": "什么时候", "pinyin": "shén me shí hou", "meaning": "cuándo"},
            {"word": "为什么", "pinyin": "wèi shén me", "meaning": "por qué"},
            {"word": "怎么", "pinyin": "zěn me", "meaning": "cómo"},
            {"word": "多少", "pinyin": "duō shǎo", "meaning": "cuánto"},
            {"word": "几", "pinyin": "jǐ", "meaning": "cuántos (números pequeños)"}
        ],
        "phrases": [
            {"chinese": "这是什么的？", "pinyin": "zhè shì shén me de?", "spanish": "¿De qué es esto?"},
            {"chinese": "你是谁？", "pinyin": "nǐ shì shéi?", "spanish": "¿Quién eres?"},
            {"chinese": "为什么学中文？", "pinyin": "wèi shén me xué zhōng wén?", "spanish": "¿Por qué aprendes chino?"},
            {"chinese": "怎么办？", "pinyin": "zěn me bàn?", "spanish": "¿Qué hacemos?"}
        ],
        "dialogue": [
            {"personA": "你在哪里？", "personB": "我在家。"},
            {"personA": "几点了？", "personB": "现在三点。"}
        ],
        "exercises": [
            {"type": "translate", "question": "Traduce '¿Por qué?' al chino", "answer": "为什么"},
            {"type": "translate", "question": "Traduce '¿Dónde estás?' al chino", "answer": "你在哪里？"}
        ]
    }
    chino_lessons["transporte"] = {
        "title": "Transporte y direcciones",
        "grammar": {
            "title": "往 ... 走 (wǎng ... zǒu)",
            "explanation": "Para dar direcciones: 往 (hacia) + dirección + 走 (caminar): 往左走 = camina hacia la izquierda.",
            "examples": ["往右拐 = gira a la derecha", "直走 = sigue recto"]
        },
        "vocabulary": [
            {"word": "出租车", "pinyin": "chū zū chē", "meaning": "taxi"},
            {"word": "公交车", "pinyin": "gōng jiāo chē", "meaning": "bus"},
            {"word": "地铁", "pinyin": "dì tiě", "meaning": "metro"},
            {"word": "火车", "pinyin": "huǒ chē", "meaning": "tren"},
            {"word": "飞机", "pinyin": "fēi jī", "meaning": "avión"},
            {"word": "左", "pinyin": "zuǒ", "meaning": "izquierda"},
            {"word": "右", "pinyin": "yòu", "meaning": "derecha"},
            {"word": "前面", "pinyin": "qián miàn", "meaning": "delante"},
            {"word": "后面", "pinyin": "hòu miàn", "meaning": "detrás"},
            {"word": "站", "pinyin": "zhàn", "meaning": "estación/parada"},
            {"word": "路", "pinyin": "lù", "meaning": "camino/calle"}
        ],
        "phrases": [
            {"chinese": "地铁站在哪里？", "pinyin": "dì tiě zhàn zài nǎ lǐ?", "spanish": "¿Dónde está la estación de metro?"},
            {"chinese": "往左走然后往右拐", "pinyin": "wǎng zuǒ zǒu rán hòu wǎng yòu guǎi", "spanish": "Ve a la izquierda y luego gira a la derecha."},
            {"chinese": "我要去机场", "pinyin": "wǒ yào qù jī chǎng", "spanish": "Voy al aeropuerto."}
        ],
        "dialogue": [
            {"personA": "这路公交车去市中心吗？", "personB": "去，第三站下。"}
        ],
        "exercises": [
            {"type": "translate", "question": "Traduce 'metro' al chino", "answer": "地铁"},
            {"type": "translate", "question": "Traduce 'Ve a la izquierda' al chino", "answer": "往左走"}
        ]
    }
    chino_lessons["compras"] = {
        "title": "Compras y dinero",
        "grammar": {
            "title": "太 ... 了 (tài ... le)",
            "explanation": "太 + adjetivo + 了 = demasiado/muy: 太贵了 = es muy caro. El 了 aquí marca exclamación, no pasado.",
            "examples": ["太便宜了 = ¡qué barato!", "太好了 = ¡qué bueno!"]
        },
        "vocabulary": [
            {"word": "钱", "pinyin": "qián", "meaning": "dinero"},
            {"word": "买", "pinyin": "mǎi", "meaning": "comprar"},
            {"word": "贵", "pinyin": "guì", "meaning": "caro"},
            {"word": "便宜", "pinyin": "pián yi", "meaning": "barato"},
            {"word": "商店", "pinyin": "shāng diàn", "meaning": "tienda"},
            {"word": "衣服", "pinyin": "yī fu", "meaning": "ropa"},
            {"word": "鞋", "pinyin": "xié", "meaning": "zapatos"},
            {"word": "手机", "pinyin": "shǒu jī", "meaning": "celular"},
            {"word": "块钱", "pinyin": "kuài qián", "meaning": "yuan/pesos (colloquial)"},
            {"word": "打折", "pinyin": "dǎ zhé", "meaning": "descuento"}
        ],
        "phrases": [
            {"chinese": "太贵了！便宜一点吧", "pinyin": "tài guì le! pián yi yī diǎn ba", "spanish": "¡Muy caro! Un descuento, por favor."},
            {"chinese": "我可以看看那个手机吗？", "pinyin": "wǒ kě yǐ kàn kan nà ge shǒu jī ma?", "spanish": "¿Puedo ver ese teléfono?"},
            {"chinese": "这个多少钱？", "pinyin": "zhè ge duō shǎo qián?", "spanish": "¿Cuánto cuesta este?"}
        ],
        "dialogue": [
            {"personA": "这个手机多少钱？", "personB": "三千块。"},
            {"personA": "太贵了！", "personB": "今天打折，两千八。"}
        ],
        "exercises": [
            {"type": "translate", "question": "Traduce '¿Cuánto cuesta?' al chino", "answer": "多少钱？"},
            {"type": "translate", "question": "Traduce 'caro' al chino", "answer": "贵"}
        ]
    }
    chino_lessons["clima"] = {
        "title": "Clima y naturaleza",
        "grammar": {
            "title": "Frases con 天气",
            "explanation": "El clima se describe: 今天 + 天气 + 很 + adjetivo, o con verbos directos: 下雨 (llueve), 下雪 (nieva).",
            "examples": ["今天很热 = hoy hace calor", "明天下雨 = mañana llueve"]
        },
        "vocabulary": [
            {"word": "天气", "pinyin": "tiān qì", "meaning": "clima"},
            {"word": "下雨", "pinyin": "xià yǔ", "meaning": "llover"},
            {"word": "下雪", "pinyin": "xià xuě", "meaning": "nevar"},
            {"word": "太阳", "pinyin": "tài yáng", "meaning": "sol"},
            {"word": "月亮", "pinyin": "yuè liang", "meaning": "luna"},
            {"word": "风", "pinyin": "fēng", "meaning": "viento"},
            {"word": "云", "pinyin": "yún", "meaning": "nube"},
            {"word": "雨", "pinyin": "yǔ", "meaning": "lluvia"},
            {"word": "晴天", "pinyin": "qíng tiān", "meaning": "día soleado"},
            {"word": "阴天", "pinyin": "yīn tiān", "meaning": "día nublado"}
        ],
        "phrases": [
            {"chinese": "今天天气怎么样？", "pinyin": "jīn tiān tiān qì zěn me yàng?", "spanish": "¿Cómo está el clima hoy?"},
            {"chinese": "明天会下雨", "pinyin": "míng tiān huì xià yǔ", "spanish": "Mañana va a llover."},
            {"chinese": "哥伦比亚不冷", "pinyin": "Gē lún bǐ yà bù lěng", "spanish": "En Colombia no hace frío."}
        ],
        "dialogue": [
            {"personA": "今天天气很好，我们去公园吧", "personB": "好主意！"}
        ],
        "exercises": [
            {"type": "translate", "question": "Traduce 'clima' al chino", "answer": "天气"},
            {"type": "translate", "question": "Traduce 'hace calor' al chino", "answer": "很热"}
        ]
    }
    chino_lessons["salud"] = {
        "title": "Cuerpo y salud",
        "grammar": {
            "title": "有点儿 (yǒu diǎnr)",
            "explanation": "有点儿 + adjetivo = 'un poco': 我有点儿累 = estoy un poco cansado. Ojo: se pone ANTES del adjetivo, al revés del español.",
            "examples": ["我有点儿不舒服 = me siento un poco mal", "头有点儿疼 = me duele un poco la cabeza"]
        },
        "vocabulary": [
            {"word": "头", "pinyin": "tóu", "meaning": "cabeza"},
            {"word": "眼睛", "pinyin": "yǎn jing", "meaning": "ojos"},
            {"word": "耳朵", "pinyin": "ěr duo", "meaning": "orejas"},
            {"word": "嘴", "pinyin": "zuǐ", "meaning": "boca"},
            {"word": "手", "pinyin": "shǒu", "meaning": "mano"},
            {"word": "脚", "pinyin": "jiǎo", "meaning": "pie"},
            {"word": "疼", "pinyin": "téng", "meaning": "doler"},
            {"word": "生病", "pinyin": "shēng bìng", "meaning": "enfermarse"},
            {"word": "药", "pinyin": "yào", "meaning": "medicina"},
            {"word": "医生", "pinyin": "yī shēng", "meaning": "médico"},
            {"word": "舒服", "pinyin": "shū fu", "meaning": "estar cómodo/sano"}
        ],
        "phrases": [
            {"chinese": "我头疼", "pinyin": "wǒ tóu téng", "spanish": "Me duele la cabeza."},
            {"chinese": "你不舒服吗？", "pinyin": "nǐ bù shū fu ma?", "spanish": "¿No te sientes bien?"},
            {"chinese": "多喝水，好好休息", "pinyin": "duō hē shuǐ, hǎo hǎo xiū xi", "spanish": "Toma mucha agua y descansa bien."}
        ],
        "dialogue": [
            {"personA": "我生病了", "personB": "去看医生吧。"}
        ],
        "exercises": [
            {"type": "translate", "question": "Traduce 'médico' al chino", "answer": "医生"},
            {"type": "translate", "question": "Traduce 'Me duele la cabeza' al chino", "answer": "我头疼"}
        ]
    }
    chino_lessons["casa"] = {
        "title": "La casa",
        "grammar": {
            "title": "Posesión con 的 (de)",
            "explanation": "的 enlaza poseedor y cosa: 我的手机 = mi celular; 我家的钥匙 = la llave de mi casa.",
            "examples": ["我的家 = mi casa", "这是谁的杯子？= ¿de quién es la taza?"]
        },
        "vocabulary": [
            {"word": "家", "pinyin": "jiā", "meaning": "casa/hogar"},
            {"word": "房间", "pinyin": "fáng jiān", "meaning": "habitación"},
            {"word": "门", "pinyin": "mén", "meaning": "puerta"},
            {"word": "窗", "pinyin": "chuāng", "meaning": "ventana"},
            {"word": "桌子", "pinyin": "zhuō zi", "meaning": "mesa"},
            {"word": "椅子", "pinyin": "yǐ zi", "meaning": "silla"},
            {"word": "床", "pinyin": "chuáng", "meaning": "cama"},
            {"word": "厕所", "pinyin": "cè suǒ", "meaning": "baño"},
            {"word": "厨房", "pinyin": "chú fáng", "meaning": "cocina"},
            {"word": "钥匙", "pinyin": "yào shi", "meaning": "llave"}
        ],
        "phrases": [
            {"chinese": "我的房间很小", "pinyin": "wǒ de fáng jiān hěn xiǎo", "spanish": "Mi habitación es pequeña."},
            {"chinese": "钥匙在桌子上", "pinyin": "yào shi zài zhuō zi shàng", "spanish": "Las llaves están sobre la mesa."},
            {"chinese": "欢迎来我家", "pinyin": "huān yíng lái wǒ jiā", "spanish": "Bienvenido a mi casa."}
        ],
        "dialogue": [
            {"personA": "洗手间在哪里？", "personB": "左边第一个门。"}
        ],
        "exercises": [
            {"type": "translate", "question": "Traduce 'casa' al chino", "answer": "家"},
            {"type": "translate", "question": "Traduce 'mi celular' al chino", "answer": "我的手机"}
        ]
    }
    chino_lessons["trabajo"] = {
        "title": "Trabajo y oficina",
        "grammar": {
            "title": "在 como verbo de ubicación",
            "explanation": "在 + lugar = estar en: 我在办公室 = estoy en la oficina. También indica acción en curso: 我在工作 = estoy trabajando.",
            "examples": ["他在公司 = él está en la empresa", "我在上班 = estoy en el trabajo"]
        },
        "vocabulary": [
            {"word": "工作", "pinyin": "gōng zuò", "meaning": "trabajo"},
            {"word": "公司", "pinyin": "gōng sī", "meaning": "empresa"},
            {"word": "办公室", "pinyin": "bàn gōng shì", "meaning": "oficina"},
            {"word": "会议", "pinyin": "huì yì", "meaning": "reunión"},
            {"word": "电脑", "pinyin": "diàn nǎo", "meaning": "computadora"},
            {"word": "同事", "pinyin": "tóng shì", "meaning": "compañero de trabajo"},
            {"word": "老板", "pinyin": "lǎo bǎn", "meaning": "jefe"},
            {"word": "加班", "pinyin": "jiā bān", "meaning": "horas extra"},
            {"word": "放假", "pinyin": "fàng jià", "meaning": "día libre/vacaciones"},
            {"word": "邮件", "pinyin": "yóu jiàn", "meaning": "correo"}
        ],
        "phrases": [
            {"chinese": "我有一个会议", "pinyin": "wǒ yǒu yī gè huì yì", "spanish": "Tengo una reunión."},
            {"chinese": "今天要加班", "pinyin": "jīn tiān yào jiā bān", "spanish": "Hoy toca hacer horas extra."},
            {"chinese": "你做什么工作？", "pinyin": "nǐ zuò shén me gōng zuò?", "spanish": "¿En qué trabajas?"}
        ],
        "dialogue": [
            {"personA": "老板在开会", "personB": "好，我等他。"}
        ],
        "exercises": [
            {"type": "translate", "question": "Traduce 'trabajo' al chino", "answer": "工作"},
            {"type": "translate", "question": "Traduce 'jefe' al chino", "answer": "老板"}
        ]
    }
    chino_lessons["modales"] = {
        "title": "Modales y cortesía",
        "grammar": {
            "title": "请 (qǐng) y la cortesía china",
            "explanation": "请 = 'por favor' y también 'invitar': 请坐 = siéntese. Disculparse: 对不起 (casual) vs 麻烦你了 (más suave y formal).",
            "examples": ["请喝茶 = toma un té, por favor", "麻烦你了 = disculpe la molestia"]
        },
        "vocabulary": [
            {"word": "请", "pinyin": "qǐng", "meaning": "por favor/invitar"},
            {"word": "麻烦", "pinyin": "má fan", "meaning": "molestia/molestar"},
            {"word": "辛苦了", "pinyin": "xīn kǔ le", "meaning": "gracias por el esfuerzo"},
            {"word": "没关系", "pinyin": "méi guān xi", "meaning": "no importa"},
            {"word": "不用了", "pinyin": "bù yòng le", "meaning": "no hace falta"},
            {"word": "随便", "pinyin": "suí biàn", "meaning": "como quieras/da igual"},
            {"word": "小心", "pinyin": "xiǎo xīn", "meaning": "con cuidado"},
            {"word": "加油", "pinyin": "jiā yóu", "meaning": "¡échale ganas! (ánimo)"}
        ],
        "phrases": [
            {"chinese": "麻烦你了，谢谢", "pinyin": "má fan nǐ le, xiè xiè", "spanish": "Disculpa la molestia, gracias."},
            {"chinese": "辛苦了！休息一下吧", "pinyin": "xīn kǔ le! xiū xi yī xià ba", "spanish": "¡Buen trabajo! Descansa un poco."},
            {"chinese": "加油！你可以的", "pinyin": "jiā yóu! nǐ kě yǐ de", "spanish": "¡Ánimo! Tú puedes."}
        ],
        "dialogue": [
            {"personA": "对不起，我迟到了", "personB": "没关系，请坐。"}
        ],
        "exercises": [
            {"type": "translate", "question": "Traduce 'por favor' al chino", "answer": "请"},
            {"type": "translate", "question": "¿Qué significa 加油?", "answer": "échale ganas / ánimo"}
        ]
    }

    return {"chino": chino_lessons, "japones": japones_lessons}



def _create_default_lessons():
    """Crea en disco las lecciones default que AÚN no existen (aditivo —
    nunca pisa una lección que Harold ya tenga)."""
    for lang, lessons in _default_lessons().items():
        for name, content in lessons.items():
            path = LESSONS_DIR / f"{lang}_{name}.json"
            if not path.exists():
                path.write_text(json.dumps(content, ensure_ascii=False, indent=2))


def _merge_defaults_into(lessons: Dict) -> None:
    """FUSIÓN (2026-09-03): expande las lecciones que ya existen en disco
    con el vocabulario/frases que les falten del set default completo.
    NUNCA borra ni reordena lo que ya hay — solo agrega lo que falta,
    deduplicando por hanzi/frase. Así una instalación vieja (con las 3
    lecciones originales cortas) recibe el set expandido sin perder
    nada de lo que ya tiene, y el archivo fusionado se persiste."""
    for lang, lang_lessons in _default_lessons().items():
        for name, default in lang_lessons.items():
            key = f"{lang}_{name}"
            cur = lessons.get(key)
            if not isinstance(cur, dict):
                continue
            dirty = False
            existing_words = {(v.get("word") or v.get("hanzi") or "").strip()
                              for v in cur.get("vocabulary", [])}
            for v in default.get("vocabulary", []):
                w = (v.get("word") or v.get("hanzi") or "").strip()
                if w and w not in existing_words:
                    cur.setdefault("vocabulary", []).append(v)
                    existing_words.add(w)
                    dirty = True
            existing_phrases = {(p.get("chinese") or "").strip()
                                for p in cur.get("phrases", [])}
            for p in default.get("phrases", []):
                ph = (p.get("chinese") or "").strip()
                if ph and ph not in existing_phrases:
                    cur.setdefault("phrases", []).append(p)
                    existing_phrases.add(ph)
                    dirty = True
            if dirty:
                path = LESSONS_DIR / f"{key}.json"
                try:
                    path.write_text(json.dumps(cur, ensure_ascii=False, indent=2))
                except Exception:
                    pass

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
        return {"items": {}, "stats": self._default_stats()}

    def _save(self):
        SRS_FILE.write_text(json.dumps(self.data, indent=2, ensure_ascii=False))

    @staticmethod
    def _default_stats() -> Dict:
        """Estadísticas base — incluye gamificación (nivel/racha/XP).
        Los campos faltantes se rellenan para compatibilidad con
        srs_data.json viejos que no los tenían."""
        return {
            "total": 0, "learned": 0, "due_today": 0,
            # gamificación
            "total_reviews": 0, "correct_reviews": 0,
            "streak_days": 0, "last_study_date": None,
            "level": 1, "xp": 0,
        }

    def _ensure_stats(self):
        """Rellena campos de gamificación que falten en datos viejos."""
        base = self._default_stats()
        for k, v in base.items():
            self.data["stats"].setdefault(k, v)
        return self.data["stats"]

    def _update_gamification(self, quality: int):
        """Nivel/racha/XP por cada respuesta — mismo diseño del spec de
        Harold: quality>=3 suma XP (quality*10), racha de días
        consecutivos de estudio, nivel cada level*100 XP."""
        st = self._ensure_stats()
        st["total_reviews"] = st.get("total_reviews", 0) + 1
        if quality >= 3:
            st["correct_reviews"] = st.get("correct_reviews", 0) + 1
            st["xp"] = st.get("xp", 0) + quality * 10
        # Racha: días consecutivos de estudio
        today = datetime.now().date().isoformat()
        if st.get("last_study_date") != today:
            last = st.get("last_study_date")
            if last:
                try:
                    last_d = datetime.fromisoformat(last).date()
                    st["streak_days"] = st.get("streak_days", 0) + 1 if (datetime.now().date() - last_d).days == 1 else 1
                except Exception:
                    st["streak_days"] = 1
            else:
                st["streak_days"] = 1
            st["last_study_date"] = today
        # Nivel: se conserva el remanente de XP al subir (no se pierde progreso)
        xp_needed = st["level"] * 100
        while st.get("xp", 0) >= xp_needed:
            st["xp"] -= xp_needed
            st["level"] = st.get("level", 1) + 1
            xp_needed = st["level"] * 100

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
        self._update_gamification(quality)
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
        st = self._ensure_stats()
        total_reviews = st.get("total_reviews", 0)
        return {
            "total_items": total,
            "learned_items": learned,
            "due_today": due_today,
            "retention_rate": round((learned / total * 100) if total > 0 else 0, 1),
            # gamificación
            "total_reviews": total_reviews,
            "correct_reviews": st.get("correct_reviews", 0),
            "accuracy": round((st.get("correct_reviews", 0) / total_reviews * 100) if total_reviews > 0 else 0, 1),
            "streak_days": st.get("streak_days", 0),
            "level": st.get("level", 1),
            "xp": st.get("xp", 0),
            "xp_to_next": st.get("level", 1) * 100,
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
