"""Panel de observabilidad — salud de Sol 2.0."""
from typing import Dict, Optional
from .memory import SolMemory

def get_sol_health(db_path: Optional[str] = None) -> Dict:
    mem = SolMemory(db_path)
    stats = mem.daily_stats()
    top = mem.get_top_skills(5)
    total_exp = mem.count_experiences()
    strong_patterns = mem.strong_patterns_count()
    total_recent = sum(stats.values())
    success_rate = (stats.get("success", 0) / total_recent * 100) if total_recent > 0 else 50.0
    health = (success_rate * 0.4 + min(100, total_exp / 10) * 0.3 +
              min(100, len(top) * 20) * 0.2 + min(100, strong_patterns * 10) * 0.1)
    return {"health_score": round(health, 1), "total_experiences": total_exp,
            "recent_stats": stats, "top_skills": top, "strong_patterns": strong_patterns}
