"""No-hardware regressions for the live dashboard's scoped field contracts."""
import ast
import asyncio
import ipaddress
from pathlib import Path
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.responses import JSONResponse
from redteam.scripts import android_field


DASHBOARD = Path(__file__).resolve().parents[1] / 'scripts' / 'dashboard_server.py'


def isolated_function(name, namespace):
    """Load only the function under test; importing the dashboard starts services."""
    tree = ast.parse(DASHBOARD.read_text(encoding='utf-8'))
    node = next(n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name)
    node.decorator_list = []
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])), str(DASHBOARD), 'exec'), namespace)
    return namespace[name]


class ScopeTests(TestCase):
    def test_private_24_is_bounded(self):
        fn = isolated_function('_bounded_lan_subnet', {'ipaddress': ipaddress, 'HTTPException': HTTPException})
        self.assertEqual(fn('192.168.1.8/24'), '192.168.1.0/24')
        for bad in ('8.8.8.0/24', '127.0.0.0/24', '198.18.0.0/24', '10.0.0.0/16', 'no-es-cidr'):
            with self.subTest(bad=bad), self.assertRaises(HTTPException):
                fn(bad)


class FieldTests(IsolatedAsyncioTestCase):
    async def test_gps_alias_preserves_real_location_contract(self):
        paths = {r.path for r in android_field.router.routes}
        self.assertTrue({'/api/android/gps', '/api/android/location'} <= paths)
        with patch.object(android_field, '_run_json', return_value=(True, {'latitude': 0.0, 'longitude': -74.0})):
            result = await android_field.android_location()
        self.assertEqual(result['latitude'], 0.0)
        self.assertEqual(result['provider_requested'], 'gps')

    async def test_wifi_scan_returns_real_data_or_explicit_failure(self):
        with patch.object(android_field, '_run_json', return_value=(True, [{'ssid': 'test'}])):
            good = await android_field.android_wifi_scan()
        self.assertEqual(good['count'], 1)
        with patch.object(android_field, '_run_json', return_value=(False, 'no Termux:API')):
            failure = await android_field.android_wifi_scan()
        self.assertIsInstance(failure, JSONResponse)
        self.assertEqual(failure.status_code, 503)

    async def test_topology_rejects_large_scope_before_running_nmap(self):
        ns = {'asyncio': asyncio, 'ipaddress': ipaddress, 'HTTPException': HTTPException,
              '_load_ops': lambda: {}, 'subnet_from_iface': lambda: '10.0.0.0/16'}
        isolated_function('_bounded_lan_subnet', ns)
        async def nmap(*args, **kwargs):
            self.fail('no se debe iniciar nmap en una red demasiado grande')
        ns['_nmap_or_empty'] = nmap
        scan = isolated_function('scan_topology', ns)
        with self.assertRaises(HTTPException) as error:
            await scan()
        self.assertEqual(error.exception.status_code, 400)

    async def test_camera_default_scan_is_bounded_and_preserves_response(self):
        ns = {'asyncio': asyncio, 'ipaddress': ipaddress, 'time': __import__('time'),
              'datetime': __import__('datetime').datetime, 'CAM_PORTS': [554, 80],
              'Query': lambda default: default, 'HTTPException': HTTPException}
        isolated_function('_bounded_lan_subnet', ns)
        def subnet(): return '192.168.9.0/30'
        async def check(ip, port, timeout=1): return 'RTSP/1.0' if ip == '192.168.9.1' and port == 554 else None
        async def broadcast(msg): pass
        ns.update(subnet_from_iface=subnet, tcp_check=check, broadcast=broadcast)
        scan = isolated_function('scan_cameras', ns)
        result = await scan(target=None, timeout=2)
        self.assertEqual(result['count'], 1)
        self.assertEqual(result['results'][0]['ip'], '192.168.9.1')
        self.assertIn('elapsed_seconds', result)
