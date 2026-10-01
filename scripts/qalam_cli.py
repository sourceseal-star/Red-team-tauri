#!/usr/bin/env python3
"""Cliente local Qalam: no ejecuta sugerencias ni imprime credenciales."""
import argparse
import json
import os
from pathlib import Path
import shlex
import sys
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
ROOT = Path(__file__).resolve().parents[1]

def read_key():
    if os.environ.get('REDTEAM_API_KEY'):
        return os.environ['REDTEAM_API_KEY']
    try:
        for line in (ROOT / '.env').read_text().splitlines():
            name, sep, value = line.strip().partition('=')
            if sep and name.removeprefix('export ').strip() == 'REDTEAM_API_KEY':
                parts = shlex.split(value, comments=True)
                return parts[0] if len(parts) == 1 else ''
    except (OSError, ValueError):
        pass
    return ''

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('accion', choices=['estado', 'entrenar', 'predecir', 'eco'])
    parser.add_argument('texto', nargs='?', default='')
    args = parser.parse_args()
    key = read_key()
    if not key:
        print('Falta REDTEAM_API_KEY en el entorno o .env. No se cambió ninguna credencial.', file=sys.stderr)
        return 1
    post = args.accion in ('entrenar', 'predecir')
    body = json.dumps({'texto': args.texto} if args.accion == 'predecir' else {}).encode() if post else None
    req = Request('http://127.0.0.1:8001/api/qalam/' + args.accion, data=body,
                  headers={'X-API-Key': key, 'Content-Type': 'application/json'},
                  method='POST' if post else 'GET')
    try:
        with urlopen(req, timeout=25) as response:
            result = json.load(response)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except HTTPError as exc:
        print(f'Qalam HTTP {exc.code}. 409: falta historial; 401: credencial; 404: router no cargado.', file=sys.stderr)
    except (URLError, TimeoutError, ValueError):
        print('No se pudo consultar Qalam. Comprueba el dashboard en :8001.', file=sys.stderr)
    return 1

if __name__ == '__main__':
    sys.exit(main())
