"""Memoria operativa de Sol — SQLite. Aprende de cada interaccion (SOL 2.0)."""
import sqlite3, json, os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

class ExperienceType(Enum):
    SUCCESS = "success"; FAILURE = "failure"; LEARNING = "learning"
    INSIGHT = "insight"; MISTAKE = "mistake"; DISCOVERY = "discovery"

@dataclass
class Experience:
    id: Optional[int]; timestamp: str; type: ExperienceType
    context: str; action: str; outcome: str; lesson: str
    importance: float; tags: List[str]
    related_experiences: Optional[List[int]] = None

@dataclass
class Skill:
    id: Optional[int]; name: str; description: str; proficiency: float
    last_used: str; times_used: int; success_rate: float
    dependencies: Optional[List[str]] = None

@dataclass
class Pattern:
    id: Optional[int]; name: str; description: str; frequency: int
    confidence: float; examples: List[str]; action_strategy: str

class SolMemory:
    """Memoria operativa de largo plazo. Conexiones por llamada (thread-safe)."""

    def __init__(self, db_path: Optional[str] = None):
        p = db_path or os.environ.get("SOL_BRAIN_DB") or str(Path.home() / ".sol" / "sol_brain.db")
        self.db_path = Path(p).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _conn(self):
        c = sqlite3.connect(self.db_path, timeout=15)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        return c

    def _init_db(self):
        with self._conn() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS experiences (
                id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL,
                type TEXT NOT NULL, context TEXT, action TEXT, outcome TEXT,
                lesson TEXT, importance REAL DEFAULT 5.0, tags TEXT,
                related_experiences TEXT)""")
            conn.execute("""CREATE TABLE IF NOT EXISTS skills (
                id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL,
                description TEXT, proficiency REAL DEFAULT 0.0, last_used TEXT,
                times_used INTEGER DEFAULT 0, success_rate REAL DEFAULT 0.0,
                dependencies TEXT)""")
            conn.execute("""CREATE TABLE IF NOT EXISTS patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL,
                description TEXT, frequency INTEGER DEFAULT 1,
                confidence REAL DEFAULT 0.5, examples TEXT, action_strategy TEXT)""")
            conn.execute("""CREATE TABLE IF NOT EXISTS goals (
                id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
                description TEXT, priority INTEGER DEFAULT 5,
                progress REAL DEFAULT 0.0, completed BOOLEAN DEFAULT FALSE,
                created_at TEXT NOT NULL)""")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_exp_type_ts ON experiences(type, timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_exp_importance ON experiences(importance)")

    def remember_experience(self, exp: Experience) -> int:
        with self._conn() as conn:
            cur = conn.execute("""INSERT INTO experiences
                (timestamp, type, context, action, outcome, lesson, importance, tags, related_experiences)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                (exp.timestamp, exp.type.value, exp.context, exp.action, exp.outcome,
                 exp.lesson, exp.importance, json.dumps(exp.tags),
                 json.dumps(exp.related_experiences or [])))
            return cur.lastrowid

    def recall_similar(self, context: str, limit: int = 5) -> List[Dict]:
        keywords = [w for w in context.lower().split() if len(w) > 2]
        if not keywords:
            return []
        with self._conn() as conn:
            conds = " OR ".join(["context LIKE ?" for _ in keywords])
            rows = conn.execute(
                f"SELECT * FROM experiences WHERE {conds} ORDER BY importance DESC, timestamp DESC LIMIT ?",
                [f"%{kw}%" for kw in keywords] + [limit]).fetchall()
            return [dict(r) for r in rows]

    def get_learnings(self, type_filter: Optional[ExperienceType] = None, limit: int = 20) -> List[Dict]:
        with self._conn() as conn:
            if type_filter:
                rows = conn.execute("SELECT * FROM experiences WHERE type=? AND lesson != '' ORDER BY importance DESC LIMIT ?",
                                    (type_filter.value, limit)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM experiences WHERE lesson != '' ORDER BY importance DESC LIMIT ?",
                                    (limit,)).fetchall()
            return [dict(r) for r in rows]

    def update_skill(self, skill_name: str, success: bool):
        now = datetime.now().isoformat()
        with self._conn() as conn:
            row = conn.execute("SELECT proficiency, times_used, success_rate FROM skills WHERE name = ?",
                               (skill_name,)).fetchone()
            if row:
                n = row["times_used"] + 1
                new_rate = (row["success_rate"] * row["times_used"] + (100.0 if success else 0.0)) / n
                new_prof = min(100.0, max(0.0, row["proficiency"] + (1.0 if success else -0.5)))
                conn.execute("UPDATE skills SET proficiency=?, last_used=?, times_used=?, success_rate=? WHERE name=?",
                             (new_prof, now, n, new_rate, skill_name))
            else:
                conn.execute("""INSERT INTO skills (name, proficiency, last_used, times_used, success_rate)
                    VALUES (?,?,?,?,?)""",
                    (skill_name, 50.0 if success else 25.0, now, 1, 100.0 if success else 0.0))

    def get_top_skills(self, limit: int = 10) -> List[Dict]:
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM skills ORDER BY proficiency DESC, times_used DESC LIMIT ?",
                                (limit,)).fetchall()
            return [dict(r) for r in rows]

    def get_weak_skills(self) -> List[Dict]:
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM skills WHERE proficiency < 50 OR success_rate < 60 ORDER BY proficiency ASC").fetchall()
            return [dict(r) for r in rows]

    def add_pattern(self, pattern: Pattern):
        with self._conn() as conn:
            row = conn.execute("SELECT frequency FROM patterns WHERE name = ?", (pattern.name,)).fetchone()
            if row:
                conn.execute("UPDATE patterns SET frequency=?, confidence=MIN(1.0, confidence+0.1), examples=? WHERE name=?",
                             (row["frequency"] + 1, json.dumps(pattern.examples), pattern.name))
            else:
                conn.execute("""INSERT INTO patterns (name, description, frequency, confidence, examples, action_strategy)
                    VALUES (?,?,?,?,?,?)""",
                    (pattern.name, pattern.description, 1, pattern.confidence,
                     json.dumps(pattern.examples), pattern.action_strategy))

    def discover_patterns(self) -> List[Dict]:
        with self._conn() as conn:
            rows = conn.execute("""SELECT outcome, COUNT(*) as count,
                GROUP_CONCAT(context, '|||') as contexts FROM experiences
                WHERE type='failure' GROUP BY outcome HAVING count > 2 ORDER BY count DESC""").fetchall()
            return [{"type": "recurring_failure", "outcome": r["outcome"], "frequency": r["count"],
                     "contexts": (r["contexts"] or "").split("|||")[:5]} for r in rows]

    def daily_stats(self, since_iso: Optional[str] = None) -> Dict[str, int]:
        since_iso = since_iso or datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        with self._conn() as conn:
            rows = conn.execute("SELECT type, COUNT(*) as c FROM experiences WHERE timestamp >= ? GROUP BY type",
                                (since_iso,)).fetchall()
            return {r["type"]: r["c"] for r in rows}

    def count_experiences(self) -> int:
        with self._conn() as conn:
            return conn.execute("SELECT COUNT(*) FROM experiences").fetchone()[0]

    def strong_patterns_count(self) -> int:
        with self._conn() as conn:
            return conn.execute("SELECT COUNT(*) FROM patterns WHERE confidence > 0.7").fetchone()[0]
