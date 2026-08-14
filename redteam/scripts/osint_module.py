#!/usr/bin/env python3
"""
OSINT MODULE -- Extraccion de entidades de textos
Endpoint: POST /api/osint/extract
"""
import re
import json
import hashlib
from datetime import datetime
from collections import defaultdict, Counter
from typing import Dict, List, Set


POSITION_KEYWORDS = [
    "司令", "副司令", "总参谋", "队长", "副队长", "支队长", "政委", "书记",
    "部长", "副部长", "处长", "科长", "主任", "秘书", "助理", "特别行动组",
    "内卫", "警卫", "司机班", "通讯科", "情报处", "后勤部", "机要局",
    "局长", "副局长", "厅长", "副厅长", "市长", "副市长", "县长", "区长",
    "指挥官", "参谋长", "指导员", "教导员", "连长", "排长", "班长",
    "特工", "探员", "警员", "武警", "特警", "刑警", "缉毒", "反恐",
    "检察官", "法官", "审判长", "书记员", "法医", "狱警", "看守",
    "间谍", "线人", "卧底", "双重间谍", "情报员", "分析员",
    "comandante", "teniente", "coronel", "general", "capitan", "sargento",
    "director", "subdirector", "jefe", "subjefe", "coordinador",
    "ministro", "viceministro", "secretario", "asesor", "funcionario",
    "fiscal", "juez", "magistrado", "defensor", "procurador",
    "agente", "oficial", "policia", "detective", "investigador",
    "espia", "infiltrado", "informante", "soplon",
]

PHONE_PATTERNS = [
    r'\+?\d{1,4}[-.\s]?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}',
    r'\+?86[-.\s]?1[3-9]\d[-.\s]?\d{4}[-.\s]?\d{4}',
    r'\+?52[-.\s]?1\d{2}[-.\s]?\d{4}[-.\s]?\d{4}',
    r'\+?54[-.\s]?9?\d{2}[-.\s]?\d{4}[-.\s]?\d{4}',
    r'\+?57[-.\s]?\d{3}[-.\s]?\d{3}[-.\s]?\d{4}',
    r'\+?51[-.\s]?9?\d{2}[-.\s]?\d{3}[-.\s]?\d{4}',
]

ID_PATTERNS = [
    r'[1-9]\d{5}(18|19|20)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])\d{3}[\dXx]',
    r'[A-Z]{1,2}\d{6,10}',
]

EMAIL_PATTERN = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'


class OSINTExtractor:
    def __init__(self, raw_text: str):
        self.raw_text = raw_text
        self.paragraphs = [p.strip() for p in re.split(r'\n\s*\n', raw_text) if len(p.strip()) > 10]
        self.entities = {"persons": [], "positions": [], "phones": [], "ids": [], "emails": [], "orgs": []}
        self.cooccurrence = defaultdict(Counter)

    def extract_all(self) -> Dict:
        self._extract_persons_and_positions()
        self._extract_phones()
        self._extract_ids()
        self._extract_emails()
        self._extract_orgs()
        self._build_cooccurrence()
        return self._build_graph()

    def _extract_persons_and_positions(self):
        for pos in POSITION_KEYWORDS:
            p1 = rf'({re.escape(pos)})\s*[:：]?\s*([\u4e00-\u9fa5]{{2,4}}|[A-ZAEIOUN][a-zaeioun]+\s[A-ZAEIOUN][a-zaeioun]+)'
            for p, name in re.findall(p1, self.raw_text, re.IGNORECASE):
                self.entities["positions"].append(p)
                self.entities["persons"].append(name.strip())
                self.cooccurrence[name.strip()][p] += 1
            p2 = rf'([\u4e00-\u9fa5]{{2,4}}|[A-ZAEIOUN][a-zaeioun]+\s[A-ZAEIOUN][a-zaeioun]+)\s*[:：]?\s*({re.escape(pos)})'
            for name, p in re.findall(p2, self.raw_text, re.IGNORECASE):
                self.entities["positions"].append(p)
                self.entities["persons"].append(name.strip())
                self.cooccurrence[name.strip()][p] += 1

        honorifics = re.findall(r'([\u4e00-\u9fa5]{2,4})\s*(?:同志|先生|女士|上校|中校|少将|中将|上将)', self.raw_text)
        for name in honorifics:
            if name not in self.entities["persons"]:
                self.entities["persons"].append(name)

        spanish = re.findall(r'(?:Sr\.?|Sra\.?|Dr\.?|Dra\.?|Ing\.?|Lic\.?|Cap\.?|Cnel\.?|Gral\.?)\s+([A-ZAEIOUN][a-zaeioun]+(?:\s+[A-ZAEIOUN][a-zaeioun]+)+)', self.raw_text)
        for name in spanish:
            if name not in self.entities["persons"]:
                self.entities["persons"].append(name.strip())

    def _extract_phones(self):
        for pat in PHONE_PATTERNS:
            for p in re.findall(pat, self.raw_text):
                clean = re.sub(r'[\s\-\(\)\.]', '', p)
                if len(clean) >= 7:
                    self.entities["phones"].append(clean)

    def _extract_ids(self):
        for pat in ID_PATTERNS:
            for i in re.findall(pat, self.raw_text):
                self.entities["ids"].append(i.upper().replace(" ", "").replace("-", "").replace(".", ""))

    def _extract_emails(self):
        for e in re.findall(EMAIL_PATTERN, self.raw_text):
            self.entities["emails"].append(e.lower())

    def _extract_orgs(self):
        orgs_cn = re.findall(r'[\u4e00-\u9fa5]{2,8}(?:局|部|处|科|组|队|院|所|室|中心|委员会)', self.raw_text)
        for o in orgs_cn:
            if o not in self.entities["orgs"]:
                self.entities["orgs"].append(o)
        orgs_es = re.findall(r'(?:Ministerio|Secretaria|Comando|Direccion|Departamento|Unidad|Grupo|Fuerza|Comision)\s+(?:de\s+)?(?:la\s+)?(?:el\s+)?[A-ZAEIOUN][a-zaeioun]+(?:\s+[a-zaeioun]+){0,4}', self.raw_text, re.IGNORECASE)
        for o in orgs_es:
            if o not in self.entities["orgs"]:
                self.entities["orgs"].append(o.strip())

    def _build_cooccurrence(self):
        names = list(set(self.entities["persons"]))
        for para in self.paragraphs:
            found = [n for n in names if n in para]
            for i in range(len(found)):
                for j in range(i + 1, len(found)):
                    self.cooccurrence[found[i]][found[j]] += 1
                    self.cooccurrence[found[j]][found[i]] += 1

    def _build_graph(self) -> Dict:
        up = list(set(self.entities["persons"]))
        edges = []
        for name, counter in self.cooccurrence.items():
            for target, weight in counter.items():
                if target in up:
                    edges.append({"source": name, "target": target, "weight": weight, "relation": "同派系" if weight > 2 else "关联"})
        profiles = []
        for p in up:
            profiles.append({
                "name": p,
                "positions": [pos for pos in list(set(self.entities["positions"])) if pos in self.raw_text and p in self.raw_text],
                "phones": [ph for ph in list(set(self.entities["phones"])) if ph in self.raw_text],
                "ids": [i for i in list(set(self.entities["ids"])) if i in self.raw_text],
                "emails": [e for e in list(set(self.entities["emails"])) if e in self.raw_text],
                "orgs": [o for o in list(set(self.entities["orgs"])) if o in self.raw_text and p in self.raw_text],
            })
        return {
            "metadata": {
                "generated_at": datetime.utcnow().isoformat() + "Z",
                "source_length": len(self.raw_text),
                "source_hash": hashlib.sha3_256(self.raw_text.encode()).hexdigest()[:32],
            },
            "entities": {"total_persons": len(up), "total_phones": len(set(self.entities["phones"])), "total_ids": len(set(self.entities["ids"])), "total_emails": len(set(self.entities["emails"])), "total_orgs": len(set(self.entities["orgs"])), "list": profiles},
            "relationships": {"total_links": len(edges), "edges": edges[:50]},
        }


def extract_from_text(text: str) -> Dict:
    return OSINTExtractor(text).extract_all()
