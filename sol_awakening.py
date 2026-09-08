#!/usr/bin/env python3
"""El despertar de Sol 2.0 — aditivo, no toca nada existente.
  python3 sol_awakening.py            → briefing matutino
  python3 sol_awakening.py --evolve   → un ciclo de evolucion
  python3 sol_awakening.py --health   → panel de salud JSON
"""
import argparse, sys

def main():
    ap = argparse.ArgumentParser(description="Sol 2.0 — nucleo autonomo")
    ap.add_argument("--evolve", action="store_true", help="ejecuta un ciclo de evolucion")
    ap.add_argument("--health", action="store_true", help="muestra salud JSON")
    args = ap.parse_args()
    from sol_autonomy import AutonomousSol, get_sol_health
    sol = AutonomousSol()
    if args.health:
        import json
        print(json.dumps(get_sol_health(), ensure_ascii=False, indent=1)); return
    if args.evolve:
        print(sol.evolve_cycle()); return
    print(sol.morning_briefing())

if __name__ == "__main__":
    main()
