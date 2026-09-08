"""SOL 2.0 — nucleo de autonomia y auto-evolucion (2026-09-08).

Paquete ADITIVO (regla #1 y #3): NO sustituye ni sombrea a sol_core.py ni a
sol_memory.py existentes. El cerebro vive en ~/.sol/sol_brain.db — la misma
casa de memory.jsonl y libro_vida.json. Tres memorias, tres papeles:
  - memory.jsonl  -> recuerdos conversacionales (quien es Harold)
  - libro_vida    -> hechos duraderos destilados por el LLM (regla #56)
  - sol_brain.db  -> experiencias OPERATIVAS: que hice, si funciono, que aprendi
"""
from .memory import SolMemory, Experience, ExperienceType, Skill, Pattern
from .goals import GoalManager, Goal, Value
from .reflection import ReflectionEngine
from .evolution import EvolutionEngine
from .learning import LearningEngine
from .wrapper import AutonomousSol
from .observability import get_sol_health
from .seed import seed_initial_knowledge
from .llm import deep_insight
