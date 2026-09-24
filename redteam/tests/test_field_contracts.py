"""No-hardware regressions for the live dashboard's scoped field contracts."""
import ast
import asyncio
import ipaddress
import os
import re
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
    def test_private_networks_allow_wider_than_24_but_reject_public(self):
        fn = isolated_function('_bounded_lan_subnet', {
            'ipaddress': ipaddress,
            'HTTPException': HTTPException,
        })
        self.assertEqual(fn('192.168.1.8/24'), '192.168.1.0/24')
        self.assertEqual(fn('10.8.4.12/16'), '10.8.0.0/16')
        for bad in ('8.8.8.0/24', '127.0.0.0/24', '198.18.0.0/24', 'no-es-cidr'):
            with self.subTest(bad=bad), self.assertRaises(HTTPException):
                fn(bad)

    def test_multiple_networks_are_normalized_deduplicated_and_bounded(self):
        ns = {
            'ipaddress': ipaddress,
            'HTTPException': HTTPException,
            're': re,
            'os': os,
        }
        isolated_function('_bounded_lan_subnet', ns)
        isolated_function('_scan_value_tokens', ns)
        parse = isolated_function('_parse_scan_networks', ns)
        result = parse(['192.168.2.1/24', '10.0.0.0/16'], '192.168.2.0/24')
        self.assertEqual([str(network) for network in result], [
            '192.168.2.0/24',
            '10.0.0.0/16',
        ])
        with self.assertRaises(HTTPException) as error:
            parse('10.0.0.0/8')
        self.assertEqual(error.exception.status_code, 413)


class FieldTests(IsolatedAsyncioTestCase):
    async def test_automatic_discovery_keeps_all_private_interfaces(self):
        interfaces = [
            {'name': 'wlan0', 'network_cidr': '10.20.0.0/24', 'is_up': True, 'type_hint': 'wifi'},
            {'name': 'eth0', 'network_cidr': '172.22.5.0/24', 'is_up': True, 'type_hint': 'ethernet'},
            {'name': 'wan0', 'network_cidr': '8.8.8.0/24', 'is_up': True, 'type_hint': 'unknown'},
            {'name': 'lo', 'network_cidr': '127.0.0.0/8', 'is_up': True, 'type_hint': 'loopback'},
        ]

        async def list_interfaces():
            return interfaces

        ns = {
            'asyncio': asyncio,
            'ipaddress': ipaddress,
            'os': os,
            're': re,
            'HTTPException': HTTPException,
            'list_network_interfaces': list_interfaces,
            'subnet_from_iface': lambda: '10.20.0.0/24',
        }
        isolated_function('_bounded_lan_subnet', ns)
        isolated_function('_scan_value_tokens', ns)
        isolated_function('_parse_scan_networks', ns)
        auto = isolated_function('_auto_scan_networks', ns)
        result = await auto()
        self.assertEqual([str(network) for network in result], [
            '10.20.0.0/24',
            '172.22.5.0/24',
        ])

    async def test_network_discovery_merges_reports_without_duplicate_hosts(self):
        ns = {
            'ipaddress': ipaddress,
            'HTTPException': HTTPException,
            'Query': lambda default: default,
            'datetime': __import__('datetime').datetime,
            're': re,
            'os': os,
        }
        isolated_function('_bounded_lan_subnet', ns)
        isolated_function('_scan_value_tokens', ns)
        isolated_function('_parse_scan_networks', ns)

        async def discover_single(subnet):
            return {
                'results': [
                    {'ip': '10.20.0.9'},
                    {'ip': '172.22.5.12'} if subnet.endswith('5.0/24') else {'ip': '10.20.0.9'},
                ],
                'subnet': subnet,
                'gateway': subnet.split('/')[0],
                'local_ip': subnet.split('/')[0],
                'method': 'mocked',
            }

        ns['_auto_scan_networks'] = lambda: asyncio.sleep(
            0,
            result=[
                ipaddress.ip_network('10.20.0.0/24'),
                ipaddress.ip_network('172.22.5.0/24'),
            ],
        )
        ns['_discover_network_single'] = discover_single
        discover = isolated_function('discover_network', ns)
        result = await discover()
        self.assertEqual(result['subnets'], ['10.20.0.0/24', '172.22.5.0/24'])
        self.assertEqual(
            [host['ip'] for host in result['results']],
            ['10.20.0.9', '172.22.5.12'],
        )

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
        ns = {
            'asyncio': asyncio,
            'ipaddress': ipaddress,
            'HTTPException': HTTPException,
            're': re,
            'os': os,
            'Query': lambda default: default,
            '_load_ops': lambda: {'scan_subnet': '8.8.8.0/24'},
            'subnet_from_iface': lambda: '10.0.0.0/16',
        }
        isolated_function('_bounded_lan_subnet', ns)
        isolated_function('_scan_value_tokens', ns)
        isolated_function('_parse_scan_networks', ns)
        async def nmap(*args, **kwargs):
            self.fail('no se debe iniciar nmap en una red demasiado grande')
        ns['_nmap_or_empty'] = nmap
        scan = isolated_function('scan_topology', ns)
        with self.assertRaises(HTTPException) as error:
            await scan()
        self.assertEqual(error.exception.status_code, 400)

    async def test_camera_evidence_is_required_for_classification(self):
        ns = {
            'asyncio': asyncio,
            're': re,
            'datetime': __import__('datetime').datetime,
            'CAM_PORTS': [554, 80],
        }

        async def probe(ip, port, timeout):
            if ip == '192.168.9.1' and port == 554:
                return {
                    'port': port, 'banner': 'RTSP/1.0 401 Unauthorized',
                    'evidence': True, 'rtsp_evidence': True,
                    'vendor_evidence': False, 'protocol': 'rtsp',
                }
            if ip == '192.168.9.2' and port == 80:
                return {
                    'port': port, 'banner': 'HTTP/1.1 200 OK',
                    'evidence': False, 'rtsp_evidence': False,
                    'vendor_evidence': False, 'protocol': 'http',
                }
            return None

        ns['_camera_probe'] = probe
        host_probe = isolated_function('_camera_probe_host', ns)
        evidence = await host_probe('192.168.9.1', 2, asyncio.Semaphore(2))
        generic = await host_probe('192.168.9.2', 2, asyncio.Semaphore(2))
        self.assertEqual(evidence['type'], 'camera')
        self.assertEqual(evidence['confidence'], 'confirmed')
        self.assertIsNone(generic)

    def test_camera_target_scope_rejects_public_ip(self):
        fn = isolated_function('_is_rfc1918_ip', {'ipaddress': ipaddress})
        self.assertTrue(fn('192.168.1.20'))
        self.assertFalse(fn('8.8.8.8'))
