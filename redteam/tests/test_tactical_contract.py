"""Regresión del contrato /api/tactical/ports y del fallback de interfaces."""
import ast
import asyncio
import ipaddress
from pathlib import Path
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import patch

from fastapi import HTTPException

DASHBOARD = Path(__file__).resolve().parents[1] / 'scripts' / 'dashboard_server.py'


def isolated_function(name, namespace):
    """Carga SOLO la función bajo prueba: importar el dashboard arranca servicios."""
    tree = ast.parse(DASHBOARD.read_text(encoding='utf-8'))
    node = next(n for n in tree.body
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name)
    node.decorator_list = []
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])),
                 str(DASHBOARD), 'exec'), namespace)
    return namespace[name]


class TacticalPortsTests(IsolatedAsyncioTestCase):
    async def test_ports_endpoint_returns_port_and_service_objects(self):
        ns = {'_TACTICAL_OK': True, '_TACTICAL_PORTS': [22, 554, 37777],
              '_TACTICAL_SERVICE_NAMES': {22: 'ssh', 554: 'rtsp', 37777: 'dvr-rtsp'}}
        endpoint = isolated_function('tactical_default_ports', ns)
        result = await endpoint()
        self.assertEqual(result, {"ports": [
            {"port": 22, "service": "ssh"},
            {"port": 554, "service": "rtsp"},
            {"port": 37777, "service": "dvr-rtsp"},
        ]})
        # El frontend renderiza ":{p.port} {p.service}": cada fila debe ser legible.
        for item in result["ports"]:
            self.assertRegex(f":{item['port']} {item['service']}", r"^:\d+ \S+$")

    async def test_ports_endpoint_reports_missing_module(self):
        endpoint = isolated_function('tactical_default_ports', {'_TACTICAL_OK': False, '_TACTICAL_PORTS': []})
        self.assertEqual(await endpoint(), {"error": "no disponible"})


class InterfaceFallbackTests(IsolatedAsyncioTestCase):
    async def test_interfaces_endpoint_never_500_when_detection_fails(self):
        ns = {'asyncio': asyncio, 'ipaddress': ipaddress, 'HTTPException': HTTPException,
              'ipaddress': ipaddress}

        def boom(*_a, **_k):
            raise RuntimeError("SELinux bloquea /proc/net/route (Termux sin root)")
        async def ifaces():
            return []
        ns.update(subnet_from_iface=boom, _detect_local_network=lambda: {"ip": ""})
        endpoint = isolated_function('list_network_interfaces', ns)
        result = await endpoint()
        self.assertIsInstance(result, list)  # nunca una excepción sin capturar
        self.assertTrue(any(i.get("type_hint") == "error" for i in result),
                        "la causa del fallo debe viajar en la respuesta y en el log")
        self.assertTrue(all(i.get("is_up") is False or i.get("network_cidr") for i in result if i.get("type_hint") == "error"))

    async def test_interfaces_fallback_still_uses_subnet_when_available(self):
        ns = {'asyncio': asyncio, 'ipaddress': ipaddress, 'HTTPException': HTTPException}
        def subnet(): return "192.168.43.0/24"
        ns.update(subnet_from_iface=subnet, _detect_local_network=lambda: {"ip": "192.168.43.1"})
        endpoint = isolated_function('list_network_interfaces', ns)
        result = await endpoint()
        auto = next(i for i in result if i.get("type_hint") == "auto-detected")
        self.assertEqual(auto["network_cidr"], "192.168.43.0/24")
        self.assertTrue(auto["is_up"])
