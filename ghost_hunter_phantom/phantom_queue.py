"""
GHOST HUNTER v3.0 PHANTOM — Sistema de colas persistente
Fallback: Redis → SQLite → JSON (en ese orden)
"""

import json
import os
import sqlite3
import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path

logger = logging.getLogger("phantom.queue")


class PhantomQueue:
    """Cola persistente con degradación graceful"""

    def __init__(self, db_path: str = "phantom_queue.db"):
        self.db_path = db_path
        self.redis_client = None
        self.use_redis = False
        self.use_sqlite = False
        self.json_path = "phantom_queue.json"
        self._init_storage()

    def _init_storage(self):
        # Intentar Redis primero
        try:
            import redis
            redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
            self.redis_client = redis.from_url(redis_url, decode_responses=True)
            self.redis_client.ping()
            self.use_redis = True
            logger.info("Cola: Redis activo")
        except Exception:
            pass

        # Fallback a SQLite
        if not self.use_redis:
            try:
                self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
                self.conn.row_factory = sqlite3.Row
                self._init_sqlite()
                self.use_sqlite = True
                logger.info(f"Cola: SQLite activo ({self.db_path})")
            except Exception as e:
                logger.warning(f"Cola: SQLite falló: {e}")

        # Fallback final a JSON
        if not self.use_redis and not self.use_sqlite:
            if not Path(self.json_path).exists():
                Path(self.json_path).write_text("[]")
            logger.warning("Cola: JSON (no recomendado para producción)")

    def _init_sqlite(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                status TEXT DEFAULT 'queued',
                created_at TEXT,
                updated_at TEXT,
                retries INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS results (
                id TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                task_id TEXT,
                created_at TEXT,
                FOREIGN KEY (task_id) REFERENCES tasks(id)
            );
            CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
            CREATE INDEX IF NOT EXISTS idx_results_task ON results(task_id);
        """)
        self.conn.commit()

    def enqueue(self, task: Dict) -> str:
        task_id = task.get("id") or str(uuid.uuid4())
        task["id"] = task_id
        task["status"] = "queued"
        now = datetime.utcnow().isoformat()
        task.setdefault("created_at", now)
        task["updated_at"] = now

        if self.use_redis:
            self.redis_client.hset(f"task:{task_id}", mapping={k: json.dumps(v) if not isinstance(v, str) else v for k, v in task.items()})
            self.redis_client.lpush("tasks:queue", task_id)
        elif self.use_sqlite:
            self.conn.execute(
                "INSERT OR REPLACE INTO tasks (id, data, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (task_id, json.dumps(task), "queued", task["created_at"], now)
            )
            self.conn.commit()
        else:
            tasks = json.loads(Path(self.json_path).read_text())
            tasks.append(task)
            Path(self.json_path).write_text(json.dumps(tasks))
        return task_id

    def dequeue(self) -> Optional[Dict]:
        if self.use_redis:
            task_id = self.redis_client.rpoplpush("tasks:queue", "tasks:processing")
            if task_id:
                data = self.redis_client.hgetall(f"task:{task_id}")
                if data:
                    return {k: json.loads(v) if v and v.startswith(("{", "[")) else v for k, v in data.items()}
            return None
        elif self.use_sqlite:
            row = self.conn.execute(
                "SELECT id, data FROM tasks WHERE status = 'queued' ORDER BY created_at ASC LIMIT 1"
            ).fetchone()
            if row:
                task_id, data = row["id"], row["data"]
                self.conn.execute(
                    "UPDATE tasks SET status = 'processing', updated_at = ? WHERE id = ?",
                    (datetime.utcnow().isoformat(), task_id)
                )
                self.conn.commit()
                task = json.loads(data)
                task["id"] = task_id
                return task
            return None
        else:
            tasks = json.loads(Path(self.json_path).read_text())
            for i, t in enumerate(tasks):
                if t.get("status") == "queued":
                    tasks[i]["status"] = "processing"
                    Path(self.json_path).write_text(json.dumps(tasks))
                    return t
            return None

    def update(self, task_id: str, updates: Dict):
        if self.use_redis:
            for k, v in updates.items():
                self.redis_client.hset(f"task:{task_id}", k, json.dumps(v) if not isinstance(v, str) else v)
        elif self.use_sqlite:
            row = self.conn.execute("SELECT data FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if row:
                task = json.loads(row["data"])
                task.update(updates)
                now = datetime.utcnow().isoformat()
                self.conn.execute(
                    "UPDATE tasks SET data = ?, status = ?, updated_at = ? WHERE id = ?",
                    (json.dumps(task), updates.get("status", "processing"), now, task_id)
                )
                self.conn.commit()
        else:
            tasks = json.loads(Path(self.json_path).read_text())
            for t in tasks:
                if t.get("id") == task_id:
                    t.update(updates)
                    break
            Path(self.json_path).write_text(json.dumps(tasks))

    def store_result(self, task_id: str, result: Dict):
        result_id = str(uuid.uuid4())
        result["id"] = result_id
        result["task_id"] = task_id
        result["created_at"] = datetime.utcnow().isoformat()

        if self.use_redis:
            self.redis_client.hset(f"result:{result_id}", mapping={k: json.dumps(v) if not isinstance(v, str) else v for k, v in result.items()})
            self.redis_client.lpush(f"results:{task_id}", result_id)
        elif self.use_sqlite:
            self.conn.execute(
                "INSERT INTO results (id, data, task_id, created_at) VALUES (?, ?, ?, ?)",
                (result_id, json.dumps(result), task_id, result["created_at"])
            )
            self.conn.commit()
        # JSON fallback: no implementa resultados

    def get_results(self, task_id: str) -> List[Dict]:
        if self.use_redis:
            ids = self.redis_client.lrange(f"results:{task_id}", 0, -1)
            results = []
            for rid in ids:
                data = self.redis_client.hgetall(f"result:{rid}")
                if data:
                    results.append({k: json.loads(v) if v and v.startswith(("{", "[")) else v for k, v in data.items()})
            return results
        elif self.use_sqlite:
            rows = self.conn.execute("SELECT data FROM results WHERE task_id = ?", (task_id,)).fetchall()
            return [json.loads(r["data"]) for r in rows]
        return []

    def get_all_tasks(self) -> List[Dict]:
        if self.use_sqlite:
            rows = self.conn.execute("SELECT data FROM tasks ORDER BY created_at DESC LIMIT 100").fetchall()
            return [json.loads(r["data"]) for r in rows]
        return []

    def cleanup(self):
        if self.use_sqlite:
            self.conn.execute("DELETE FROM tasks WHERE status = 'completed'")
            self.conn.execute("DELETE FROM results WHERE task_id NOT IN (SELECT id FROM tasks)")
            self.conn.commit()
        elif not self.use_redis:
            tasks = json.loads(Path(self.json_path).read_text())
            tasks = [t for t in tasks if t.get("status") != "completed"]
            Path(self.json_path).write_text(json.dumps(tasks))
