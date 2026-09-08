"""Wrapper — Sol autonomo envolviendo las operaciones del dashboard (SOL 2.0).
IMPORTANTE (regla #1): NUNCA reemplazar rutas existentes. La instrumentacion
es en los call-sites (pre_task/post_task), aditiva y a prueba de fallos: si
este modulo falla, la operacion original sigue exactamente igual."""
from datetime import datetime
from typing import Dict, Optional
from .memory import SolMemory
from .goals import GoalManager
from .reflection import ReflectionEngine
from .evolution import EvolutionEngine
from .learning import LearningEngine

class AutonomousSol:
    def __init__(self, db_path: Optional[str] = None):
        self.memory = SolMemory(db_path)
        self.goals = GoalManager()
        self.reflection = ReflectionEngine(self.memory)
        self.evolution = EvolutionEngine(self.memory)
        self.learning = LearningEngine(self.memory, self.goals)

    def pre_task(self, task_name: str, context: Dict) -> Dict:
        similar = self.memory.recall_similar(f"{task_name} {context.get('target', '')}")
        strategy = self.evolution.select_strategy(task_name, context)
        advice = ""
        recent_failures = [s for s in similar if s["type"] == "failure"][:2]
        if recent_failures:
            advice = "⚠️ Ten cuidado: " + str(recent_failures[0]["lesson"])
        return {"strategy": strategy["name"] if strategy else "default",
                "advice": advice,
                "confidence": (strategy.get("adjusted_rate", 0.5) if strategy else 0.5) / 100.0,
                "similar_experiences": len(similar)}

    def post_task(self, task_name: str, success: bool, context: Dict, outcome: str) -> str:
        self.learning.learn_from_task(task_name, success, context, outcome)
        if "strategy" in context:
            self.evolution.update_strategy_performance(task_name, context["strategy"], success)
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        stats = self.memory.daily_stats(today)
        total = sum(stats.values())
        if total > 0 and total % 10 == 0:
            return self.reflection.daily_reflection()
        return ""

    def evolve_cycle(self) -> str:
        return "🧬 Iniciando ciclo de evolucion...\n" + "=" * 60 + "\n" + \
               self.evolution.evolve() + "\n" + self.reflection.generate_self_report()

    def morning_briefing(self) -> str:
        r = "🌅 BUENOS DIAS HAROLD\n\n" + self.goals.reflect_on_goals() + "\n"
        weak = self.memory.get_weak_skills()
        if weak:
            r += "📚 Hoy deberia practicar:\n"
            for s in weak[:3]:
                r += f"  • {s['name']} ({s['proficiency']:.0f}%)\n"
        r += "\n💭 Leccion reciente importante:\n"
        learnings = self.memory.get_learnings(limit=1)
        if learnings:
            r += f"  {learnings[0]['lesson']}\n"
        return r
