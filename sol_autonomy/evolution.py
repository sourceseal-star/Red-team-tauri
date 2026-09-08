"""Motor de evolucion — Sol mejora sus estrategias (SOL 2.0).
Bug del diseno original corregido: el banco de estrategias vivia SOLO en
memoria y se perdia en cada reinicio (ironico). Ahora persiste en
~/.sol/sol_strategies.json."""
import json, os, random
from typing import Dict, List, Optional
from pathlib import Path

class EvolutionEngine:
    def __init__(self, memory, path: Optional[str] = None):
        self.memory = memory
        p = path or os.environ.get("SOL_STRATEGIES") or str(Path.home() / ".sol" / "sol_strategies.json")
        self.strategies_path = Path(p).expanduser()
        self.strategy_bank = self._load_strategies()

    def _seed(self) -> Dict[str, List[Dict]]:
        return {
            "network_scan": [
                {"name": "nmap_sn_first", "description": "nmap -sn primero, TCP fallback si no hay CAP_NET_RAW (Termux)", "success_rate": 80.0, "usage_count": 0},
                {"name": "tcp_connect_fallback", "description": "TCP connect() directo (funciona sin root)", "success_rate": 60.0, "usage_count": 0},
            ],
            "camera_scan": [
                {"name": "standard_ports", "description": "Escanear puertos estandar de camaras", "success_rate": 70.0, "usage_count": 0},
                {"name": "full_port_scan", "description": "Escaneo completo de puertos (lento)", "success_rate": 40.0, "usage_count": 0},
            ],
            "gps_retrieval": [
                {"name": "termux_with_retries", "description": "termux-location con reintentos", "success_rate": 80.0, "usage_count": 0},
                {"name": "termux_location_direct", "description": "termux-location una sola vez", "success_rate": 60.0, "usage_count": 0},
            ],
        }

    def _load_strategies(self) -> Dict[str, List[Dict]]:
        try:
            with open(self.strategies_path, encoding="utf-8") as f:
                data = json.load(f)
            if data:
                return data
        except Exception:
            pass
        return self._seed()

    def _save_strategies(self):
        try:
            self.strategies_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.strategies_path, "w", encoding="utf-8") as f:
                json.dump(self.strategy_bank, f, ensure_ascii=False, indent=1)
        except Exception as e:
            print(f"[SOL-EVO] no se pudo guardar el banco: {e}")

    def select_strategy(self, task_type: str, context: Dict) -> Optional[Dict]:
        strategies = self.strategy_bank.get(task_type, [])
        if not strategies:
            return None
        similar = self.memory.recall_similar(context.get("description", ""))
        for s in strategies:
            matching = [e for e in similar if s["name"] in json.dumps(e)]
            s["adjusted_rate"] = (sum(1 for e in matching if e["type"] == "success") / len(matching)) if matching else s["success_rate"]
        best = max(strategies, key=lambda s: s["adjusted_rate"])
        if random.random() < 0.8:
            return best
        others = [s for s in strategies if s is not best]
        return random.choice(others) if others else strategies[0]

    def update_strategy_performance(self, task_type: str, strategy_name: str, success: bool):
        for s in self.strategy_bank.get(task_type, []):
            if s["name"] == strategy_name:
                n = s["usage_count"]
                s["success_rate"] = (100.0 if success else 0.0) if n == 0 else (s["success_rate"] * n + (100.0 if success else 0.0)) / (n + 1)
                s["usage_count"] = n + 1
                self._save_strategies()
                break

    def evolve(self) -> str:
        log = "🧬 CICLO DE EVOLUCION\n\n🔍 Patrones descubiertos:\n"
        patterns = self.memory.discover_patterns()
        if patterns:
            for p in patterns[:3]:
                log += f"  • {p['outcome'][:60]}... ({p['frequency']} veces)\n"
                if p["frequency"] >= 3:
                    log += "    → Debo desarrollar una nueva estrategia para esto\n"
        else:
            log += "  ✨ No he encontrado patrones problematicos.\n"
        log += "\n📊 Rendimiento de estrategias:\n"
        for task_type, strategies in self.strategy_bank.items():
            if strategies:
                best = max(strategies, key=lambda s: s["success_rate"])
                log += f"  • {task_type}: '{best['name']}' ({best['success_rate']:.0f}% exito, {best['usage_count']} usos)\n"
        return log
