"""Motor de reflexion — Sol analiza sus propias acciones (SOL 2.0).
Bug del diseno original corregido: usaba sqlite3 sin importarlo y SQL crudo;
ahora va por la API de SolMemory (daily_stats/get_learnings)."""
from datetime import datetime
from typing import Dict, List

class ReflectionEngine:
    def __init__(self, memory):
        self.memory = memory

    def daily_reflection(self) -> str:
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        stats = self.memory.daily_stats(today)
        lessons = [l["lesson"] for l in self.memory.get_learnings(limit=3)]
        r = f"🌅 Reflexion del dia ({today[:10]}):\n\n"
        if stats:
            r += "📈 Hoy he vivido:\n"
            for k, v in stats.items():
                r += f"  • {k}: {v}\n"
            r += "\n"
        if lessons:
            r += "💡 Lecciones importantes:\n"
            for i, l in enumerate(lessons, 1):
                r += f"  {i}. {l}\n"
        r += "\n🔮 Tendencias:\n"
        total = sum(stats.values())
        if total > 0:
            rate = (stats.get("success", 0) / total) * 100
            r += f"  • Tasa de exito: {rate:.0f}%\n"
            if stats.get("failure", 0) > stats.get("success", 0):
                r += "  • ⚠️ Estoy fallando mas de lo normal. Debo revisar mis estrategias.\n"
            elif rate > 80:
                r += "  • ✨ Estoy en racha. Mis estrategias funcionan.\n"
        return r

    def identify_improvement_areas(self) -> List[Dict]:
        areas = []
        for s in self.memory.get_weak_skills()[:5]:
            areas.append({"type": "skill", "name": s["name"],
                          "issue": f"Proficiency: {s['proficiency']:.0f}%, Success: {s['success_rate']:.0f}%",
                          "action": f"Practicar {s['name']} mas frecuentemente"})
        for p in self.memory.discover_patterns()[:3]:
            areas.append({"type": "pattern", "name": f"Patron: {p['outcome'][:50]}",
                          "issue": f"Ocurre {p['frequency']} veces",
                          "action": "Investigar causa raiz y cambiar estrategia"})
        return areas

    def generate_self_report(self) -> str:
        r = "📋 REPORTE DE AUTO-EVALUACION DE SOL\n" + "=" * 50 + "\n\n🧠 ESTADO ACTUAL:\n"
        top = self.memory.get_top_skills(5)
        if top:
            r += "Mis mejores habilidades:\n"
            for s in top:
                r += f"  • {s['name']}: {s['proficiency']:.0f}% (usada {s['times_used']} veces, {s['success_rate']:.0f}% exito)\n"
        else:
            r += "  Aun estoy desarrollando mis habilidades.\n"
        r += "\n📈 TENDENCIAS RECIENTES:\n" + self.daily_reflection()
        r += "\n🎯 AREAS DE MEJORA:\n"
        areas = self.identify_improvement_areas()
        if areas:
            for i, a in enumerate(areas[:3], 1):
                r += f"  {i}. [{a['type']}] {a['name']}\n     Problema: {a['issue']}\n     Accion: {a['action']}\n"
        else:
            r += "  No he identificado areas criticas.\n"
        return r
