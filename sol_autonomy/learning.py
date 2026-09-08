"""Motor de aprendizaje — Sol mejora con cada tarea (SOL 2.0)."""
from datetime import datetime
from typing import Dict
from .memory import Experience, ExperienceType

class LearningEngine:
    def __init__(self, memory, goal_manager):
        self.memory = memory
        self.goal_manager = goal_manager

    def learn_from_task(self, task_name: str, success: bool, context: Dict, outcome: str):
        if success:
            exp_type, importance = ExperienceType.SUCCESS, 5.0
        else:
            exp_type, importance = ExperienceType.FAILURE, 7.0
        lesson = self._extract_lesson(context, outcome, success)
        self.memory.remember_experience(Experience(
            id=None, timestamp=datetime.now().isoformat(), type=exp_type,
            context=f"{task_name}: {context.get('description', '')}",
            action=context.get("action", ""), outcome=outcome, lesson=lesson,
            importance=importance, tags=[task_name] + context.get("tags", [])))
        self.memory.update_skill(task_name, success)
        if success:
            self.goal_manager.update_task_progress(task_name, 1.0)
        if importance >= 7.0:
            self._generate_insight(lesson)

    def _extract_lesson(self, context: Dict, outcome: str, success: bool) -> str:
        if success:
            return f"La estrategia '{context.get('strategy', 'default')}' funciono"
        return f"El error fue: {outcome[:100]}"

    def _generate_insight(self, lesson: str):
        self.memory.remember_experience(Experience(
            id=None, timestamp=datetime.now().isoformat(), type=ExperienceType.INSIGHT,
            context="insight automatico", action="reflexion", outcome=lesson,
            lesson=lesson, importance=8.0, tags=["insight"]))
