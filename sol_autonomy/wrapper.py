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
from .seed import seed_initial_knowledge
from .observability import get_sol_health

class AutonomousSol:
    def __init__(self, db_path: Optional[str] = None):
        self.memory = SolMemory(db_path)
        self.goals = GoalManager()
        self.reflection = ReflectionEngine(self.memory)
        self.evolution = EvolutionEngine(self.memory)
        self.learning = LearningEngine(self.memory, self.goals)
        try:
            seeded = seed_initial_knowledge(self.memory)  # honesta: solo si esta vacio
            if seeded:
                print("[SOL-AUTONOMY] cerebro nuevo → sembrado con lo que Sol ya sabe")
        except Exception:
            pass  # nunca bloquear el arranque

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
        h = get_sol_health()
        r = "🌅 BUENOS DIAS HAROLD\n\n"
        r += f"❤️ Salud: {h['health_score']}/100 · {h['total_experiences']} experiencias · {h['strong_patterns']} patrones fuertes\n\n"
        r += self.goals.reflect_on_goals() + "\n"
        top = self.memory.get_top_skills(3)
        if top:
            r += "🏆 Mis habilidades mas fuertes hoy:\n"
            for s_ in top:
                r += f"  • {s_['name']}: {s_['proficiency']:.0f}% (exito {s_['success_rate']:.0f}%)\n"
            r += "\n"
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
