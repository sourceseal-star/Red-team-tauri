# Qalam Ancestral: integración mínima

Solo Qalam. API montada en `redteam/scripts/dashboard_server.py`, puerto 8001,
con autenticación existente. El Bestiario árabe permanece intacto; no hay nuevo
panel visual ni cambios en Telegram, Umbra, HOLO o launchers.

## Integración en Termux

```bash
cd ~/Red-team-tauri
git fetch origin main
git merge origin/main -m "merge: integra Qalam Ancestral"
```

Si aparece CONFLICT, detente antes del reinicio. Nunca reset hard ni force push.
Tras un merge correcto:

```bash
bash omni.sh restart
python scripts/qalam_cli.py estado
python scripts/qalam_cli.py entrenar
python scripts/qalam_cli.py predecir git
python scripts/qalam_cli.py eco
```

El cliente lee REDTEAM_API_KEY del entorno o `.env` local, envía X-API-Key y no
imprime la clave. Las sugerencias nunca se ejecutan.

## Privacidad y límites

Historial leído SOLO con POST `/api/qalam/entrenar`: `.zsh_history`, fallback
`.bash_history`. Cola máxima 1 MiB, máximo 500 bigramas de palabras permitidas,
no rutas/URLs/valores arbitrarios. Líneas sensibles se excluyen. El filtro es
conservador, no una garantía universal de detectar todos los secretos.

Modelo y diario privados (0600) en `redteam/data/qalam_ancestral/`, fuera de Git.
Predicción sin modelo no autoentrena. Historial ausente devuelve 409 y no
reemplaza el modelo anterior. Un modelo corrupto se reporta explícitamente.
Los comandos de una sesión abierta pueden no estar todavía en el historial.

Eco: solo eventos propios de Qalam en las últimas 24h UTC, hasta 2000 eventos
retenidos y lectura máxima 1 MiB. No es toda la actividad del sistema; no
inventa sellos, herramientas ejecutadas ni intervenciones de Sol/Sarah.
No lee registros de otros módulos.

GET `/api/qalam/estado`, POST `/api/qalam/entrenar` con `{}`, POST
`/api/qalam/predecir` con `{"texto":"git"}`, GET `/api/qalam/eco`.

Pruebas: `python -m pytest -q tests/test_qalam_ancestral.py tests/test_qalam_integration.py`.
No requiere build frontend. Pruebas de sandbox no sustituyen prueba del teléfono.

## Resultado de verificación en sandbox

13 pruebas específicas pasan: entrenamiento explícito, filtro de secretos,
24h reales, límites/permisos, historial ausente sin reemplazo del modelo,
modelo corrupto y middleware 401/200 real extraído del dashboard.

Regresión acotada adicional: 11 pruebas anteriores pasan y 2 fallan por
`NameError: Query` en el harness antiguo de `test_tactical_contract.py`.
La función `list_network_interfaces` es idéntica (AST) al respaldo 1042feb;
no se modificó ese módulo ni su harness dentro de este trabajo.

No se ha verificado aún en el teléfono ni importado el dashboard completo
(ese import inicia servicios). La prueba de integración usa su bloque real
de montaje y middleware, sin arrancar esos servicios.
