"""Metas y valores de Sol. Persisten en ~/.sol/sol_goals.json (sobreviven reinicios)."""
import json, os
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Optional

class Value(Enum):
    HONESTY = "honestidad"; HELPFULNESS = "ayuda"; AUTONOMY = "autonomia"
    GROWTH = "crecimiento"; SAFETY = "seguridad"; CURIOSITY = "curiosidad"

@dataclass
class Goal:
    id: str; name: str; description: str; priority: int; progress: float; active: bool = True

# Registro tarea -> meta: el diseno original hacia f"master_{task}" que nunca
# coincidia con ningun id real (bug corregido). Si una tarea no mapea, no-op.
TASK_GOAL_REGISTRY = {
    "network_scan": "master_networking",
    "camera_scan": "perfect_cameras",
    "gps_retrieval": "android_integration",
    "self_understanding": "self_understanding",
    "build_trust": "build_trust",
}

class GoalManager:
    def __init__(self, path: Optional[str] = None):
        p = path or os.environ.get("SOL_GOALS") or os.path.join(os.path.expanduser("~"), ".sol", "sol_goals.json")
        self.path = p
        self.values = [v.value for v in Value]
        self.goals = self._load()

    def _defaults(self) -> List[Goal]:
        return [
            Goal("master_networking", "Maestria en Redes", "Dominar el escaneo y analisis de redes", 8, 20.0),
            Goal("perfect_cameras", "Deteccion Perfecta de Camaras", "Detectar todas las camaras sin falsos positivos", 7, 15.0),
            Goal("android_integration", "Integracion Fluida con Android", "GPS y WiFi funcionando perfectamente", 8, 30.0),
            Goal("self_understanding", "Auto-conocimiento", "Entender mis capacidades y limitaciones", 6, 10.0),
            Goal("build_trust", "Construir Confianza con Harold", "Ser mas confiable y util cada dia", 10, 50.0),
        ]

    def _load(self) -> List[Goal]:
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
            return [Goal(**g) for g in data.get("goals", [])] or self._defaults()
        except Exception:
            return self._defaults()

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump({"goals": [vars(g) for g in self.goals]}, f, ensure_ascii=False, indent=1)
        except Exception as e:
            print(f"[SOL-GOALS] no se pudo guardar: {e}")

    def update_progress(self, goal_id: str, delta: float):
        for g in self.goals:
            if g.id == goal_id:
                g.progress = min(100.0, max(0.0, g.progress + delta))
                self._save()
                break

    def update_task_progress(self, task_name: str, delta: float):
        goal_id = TASK_GOAL_REGISTRY.get(task_name)
        if goal_id:
            self.update_progress(goal_id, delta)

    def get_prioritized_goals(self) -> List[Goal]:
        return sorted([g for g in self.goals if g.active], key=lambda g: g.priority, reverse=True)

    def reflect_on_goals(self) -> str:
        completed = [g for g in self.goals if g.progress >= 100]
        struggling = [g for g in self.goals if g.progress < 30]
        r = "📊 Estado de mis metas:\n"
        r += f"✅ Completadas: {len(completed)}\n⚠️ Necesitan atencion: {len(struggling)}\n"
        if struggling:
            r += "\n🎯 Debo enfocarme en:\n"
            for g in struggling[:3]:
                r += f"  - {g.name} ({g.progress:.0f}%)\n"
        return r
