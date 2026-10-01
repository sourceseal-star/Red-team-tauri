"""Test actual router registration and dashboard auth without starting services."""
import ast
import asyncio
import importlib.util
from pathlib import Path
from unittest.mock import patch
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
ROOT = Path(__file__).resolve().parents[1]

def test_actual_mount_and_auth():
    tree = ast.parse((ROOT / 'redteam/scripts/dashboard_server.py').read_text())
    app = FastAPI()
    ns = {'app': app, 'asyncio': asyncio, 'Request': Request,
          'JSONResponse': JSONResponse, 'API_KEY': 'fixture-only-key', '_rate_check': lambda _: True}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in ('PUBLIC_PATHS', 'SOL_AUTH_REQUIRED_PATHS'):
                    ns[target.id] = ast.literal_eval(node.value)
    mount = next(node for node in tree.body if isinstance(node, ast.Try) and any(
        isinstance(child, ast.ImportFrom) and child.module == 'redteam.modules.qalam_ancestral' for child in node.body))
    middleware = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef) and node.name == 'security_middleware')
    exec(compile(ast.fix_missing_locations(ast.Module(body=[mount, middleware], type_ignores=[])), '<real-qalam-mount>', 'exec'), ns)
    assert {'/api/qalam/estado', '/api/qalam/eco', '/api/qalam/predecir', '/api/qalam/entrenar'} <= set(app.openapi()["paths"])
    with TestClient(app) as client:
        for path in ('estado', 'eco'):
            assert client.get('/api/qalam/' + path).status_code == 401
            assert client.get('/api/qalam/' + path, headers={'X-API-Key': 'wrong'}).status_code == 401
            assert client.get('/api/qalam/' + path, headers={'X-API-Key': 'fixture-only-key'}).status_code == 200
        assert client.post('/api/qalam/entrenar', json={}).status_code == 401
        assert client.post('/api/qalam/predecir', json={'texto': 'git'}).status_code == 401

def test_cli_reads_dotenv_without_exposing_key(tmp_path, capsys):
    spec = importlib.util.spec_from_file_location('qalam_cli_test', ROOT / 'scripts/qalam_cli.py')
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    (tmp_path / '.env').write_text('REDTEAM_API_KEY="fixture-only-key"\n')
    with patch.object(cli, 'ROOT', tmp_path), patch.dict(cli.os.environ, {}, clear=True):
        assert cli.read_key() == 'fixture-only-key'
        with patch.object(cli.sys, 'argv', ['qalam_cli.py', 'estado']), patch.object(cli, 'urlopen', side_effect=cli.URLError('offline')):
            assert cli.main() == 1
    captured = capsys.readouterr()
    assert 'fixture-only-key' not in captured.out + captured.err
