import 'package:flutter/material.dart';
import 'package:graphview/GraphView.dart';
import '../../../../core/theme/app_theme.dart';
import '../widgets/topology_graph.dart';
import '../widgets/host_detail_sheet.dart';

class TopologyScreen extends StatefulWidget {
  const TopologyScreen({super.key});

  @override
  State<TopologyScreen> createState() => _TopologyScreenState();
}

class _TopologyScreenState extends State<TopologyScreen> {
  bool isScanning = false;
  List<Map<String, dynamic>> hosts = [];
  List<Map<String, dynamic>> connections = [];
  Map<String, dynamic>? selectedHost;
  String filterType = 'all';

  final List<String> filterOptions = ['all', 'router', 'server', 'workstation', 'camera', 'iot', 'printer'];

  @override
  Widget build(BuildContext context) {
    final filteredHosts = filterType == 'all'
        ? hosts
        : hosts.where((h) => h['type'] == filterType).toList();

    return Scaffold(
      backgroundColor: AppTheme.darkTheme.scaffoldBackgroundColor,
      appBar: AppBar(
        title: const Text('Network Topology'),
        actions: [
          PopupMenuButton<String>(
            icon: const Icon(Icons.filter_list, color: Colors.white),
            color: const Color(0xFF141419),
            onSelected: (value) => setState(() => filterType = value),
            itemBuilder: (context) => filterOptions.map((f) => PopupMenuItem(
              value: f,
              child: Text(f.toUpperCase(), style: const TextStyle(color: Colors.white, fontSize: 12)),
            )).toList(),
          ),
          IconButton(
            icon: isScanning
                ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                : const Icon(Icons.radar, color: AppTheme.cyberCyan),
            onPressed: isScanning ? null : _startTopologyScan,
          ),
        ],
      ),
      body: Column(
        children: [
          if (hosts.isNotEmpty)
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
              decoration: const BoxDecoration(
                color: Color(0xFF141419),
                border: Border(bottom: BorderSide(color: Color(0xFF2A2A3A))),
              ),
              child: Row(
                children: [
                  _buildLegendItem('Router', const Color(0xFFEF4444)),
                  _buildLegendItem('Server', const Color(0xFF3B82F6)),
                  _buildLegendItem('Workstation', const Color(0xFF10B981)),
                  _buildLegendItem('Camera', const Color(0xFFF59E0B)),
                  _buildLegendItem('IoT', const Color(0xFF06B6D4)),
                  _buildLegendItem('Printer', const Color(0xFF8B5CF6)),
                ],
              ),
            ),
          Expanded(
            child: hosts.isEmpty
                ? _buildEmptyState()
                : TopologyGraph(
                    hosts: filteredHosts,
                    connections: connections,
                    onNodeTap: (host) => _showHostDetail(host),
                  ),
          ),
          if (hosts.isNotEmpty)
            Container(
              padding: const EdgeInsets.all(16),
              decoration: const BoxDecoration(
                color: Color(0xFF141419),
                border: Border(top: BorderSide(color: Color(0xFF2A2A3A))),
              ),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceAround,
                children: [
                  _buildStat('Hosts', '${hosts.length}', Colors.white),
                  _buildStat('Conexiones', '${connections.length}', AppTheme.cyberCyan),
                  _buildStat('Vulnerables', '${hosts.where((h) => (h['vulnerabilities']?.length ?? 0) > 0).length}', AppTheme.dangerRed),
                  _buildStat('Segmentos', '${_countSegments()}', AppTheme.successGreen),
                ],
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildLegendItem(String label, Color color) {
    return Padding(
      padding: const EdgeInsets.only(right: 12),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(width: 8, height: 8, decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(2))),
          const SizedBox(width: 4),
          Text(label, style: const TextStyle(color: Color(0xFF6B7280), fontSize: 10)),
        ],
      ),
    );
  }

  Widget _buildStat(String label, String value, Color color) {
    return Column(
      children: [
        Text(value, style: TextStyle(color: color, fontSize: 18, fontWeight: FontWeight.bold, fontFamily: 'JetBrainsMono')),
        const SizedBox(height: 2),
        Text(label, style: const TextStyle(color: Color(0xFF6B7280), fontSize: 10)),
      ],
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.device_hub, size: 80, color: const Color(0xFF2A2A3A)),
          const SizedBox(height: 20),
          const Text('Topología vacía', style: TextStyle(color: Color(0xFF6B7280), fontSize: 18)),
          const SizedBox(height: 8),
          const Text('Inicia un scan de red para mapear la topología', style: TextStyle(color: Color(0xFF4B5563), fontSize: 13)),
          const SizedBox(height: 24),
          ElevatedButton.icon(
            icon: const Icon(Icons.radar),
            label: const Text('Iniciar Network Discovery'),
            style: ElevatedButton.styleFrom(
              backgroundColor: AppTheme.cyberCyan,
              foregroundColor: Colors.white,
              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 14),
            ),
            onPressed: _startTopologyScan,
          ),
        ],
      ),
    );
  }

  int _countSegments() {
    final subnets = <String>{};
    for (final host in hosts) {
      final ip = host['ip'] as String;
      final parts = ip.split('.');
      if (parts.length == 4) {
        subnets.add('${parts[0]}.${parts[1]}.${parts[2]}.0/24');
      }
    }
    return subnets.length;
  }

  void _showHostDetail(Map<String, dynamic> host) {
    showModalBottomSheet(
      context: context,
      backgroundColor: const Color(0xFF141419),
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(24))),
      builder: (context) => HostDetailSheet(host: host),
    );
  }

  void _startTopologyScan() {
    setState(() {
      isScanning = true;
      hosts = [];
      connections = [];
    });

    Future.delayed(const Duration(seconds: 4), () {
      if (!mounted) return;
      setState(() {
        hosts = [
          {
            'id': 'gw_001',
            'ip': '192.168.1.1',
            'hostname': 'Gateway-Router',
            'mac': 'AA:BB:CC:DD:EE:01',
            'type': 'router',
            'os': 'Cisco IOS',
            'vendor': 'Cisco',
            'ports': [80, 443, 22],
            'vulnerabilities': ['CVE-2023-20198'],
            'services': ['HTTP', 'HTTPS', 'SSH'],
          },
          {
            'id': 'srv_001',
            'ip': '192.168.1.10',
            'hostname': 'DC-01',
            'mac': 'AA:BB:CC:DD:EE:02',
            'type': 'server',
            'os': 'Windows Server 2019',
            'vendor': 'Microsoft',
            'ports': [53, 88, 135, 139, 445, 389, 636],
            'vulnerabilities': ['CVE-2021-34527', 'CVE-2020-1472'],
            'services': ['DNS', 'Kerberos', 'SMB', 'LDAP'],
          },
          {
            'id': 'srv_002',
            'ip': '192.168.1.11',
            'hostname': 'WEB-01',
            'mac': 'AA:BB:CC:DD:EE:03',
            'type': 'server',
            'os': 'Ubuntu 22.04',
            'vendor': 'Canonical',
            'ports': [22, 80, 443, 3306],
            'vulnerabilities': [],
            'services': ['SSH', 'HTTP', 'HTTPS', 'MySQL'],
          },
          {
            'id': 'ws_001',
            'ip': '192.168.1.50',
            'hostname': 'DESKTOP-ADMIN',
            'mac': 'AA:BB:CC:DD:EE:04',
            'type': 'workstation',
            'os': 'Windows 10',
            'vendor': 'Dell',
            'ports': [445, 3389],
            'vulnerabilities': ['CVE-2023-36884'],
            'services': ['SMB', 'RDP'],
          },
          {
            'id': 'ws_002',
            'ip': '192.168.1.51',
            'hostname': 'MAC-DEV',
            'mac': 'AA:BB:CC:DD:EE:05',
            'type': 'workstation',
            'os': 'macOS 14',
            'vendor': 'Apple',
            'ports': [22, 445, 5900],
            'vulnerabilities': [],
            'services': ['SSH', 'SMB', 'VNC'],
          },
          {
            'id': 'cam_001',
            'ip': '192.168.1.100',
            'hostname': 'CAM-LOBBY',
            'mac': 'AA:BB:CC:DD:EE:06',
            'type': 'camera',
            'os': 'Linux (embedded)',
            'vendor': 'Hikvision',
            'ports': [80, 554, 8000],
            'vulnerabilities': ['CVE-2021-36260', 'CVE-2021-33044'],
            'services': ['HTTP', 'RTSP'],
          },
          {
            'id': 'cam_002',
            'ip': '192.168.1.101',
            'hostname': 'CAM-PARKING',
            'mac': 'AA:BB:CC:DD:EE:07',
            'type': 'camera',
            'os': 'Linux (embedded)',
            'vendor': 'Dahua',
            'ports': [80, 554, 37777],
            'vulnerabilities': ['CVE-2021-33037'],
            'services': ['HTTP', 'RTSP'],
          },
          {
            'id': 'iot_001',
            'ip': '192.168.1.200',
            'hostname': 'Smart-Hub',
            'mac': 'AA:BB:CC:DD:EE:08',
            'type': 'iot',
            'os': 'Embedded Linux',
            'vendor': 'Amazon',
            'ports': [80, 1883, 8883],
            'vulnerabilities': [],
            'services': ['HTTP', 'MQTT'],
          },
          {
            'id': 'iot_002',
            'ip': '192.168.1.201',
            'hostname': 'PLC-LINE1',
            'mac': 'AA:BB:CC:DD:EE:09',
            'type': 'iot',
            'os': 'VxWorks',
            'vendor': 'Siemens',
            'ports': [502, 102],
            'vulnerabilities': ['CVE-2019-10953'],
            'services': ['Modbus', 'S7Comm'],
          },
          {
            'id': 'prt_001',
            'ip': '192.168.1.250',
            'hostname': 'PRINTER-HR',
            'mac': 'AA:BB:CC:DD:EE:10',
            'type': 'printer',
            'os': 'Embedded',
            'vendor': 'HP',
            'ports': [80, 443, 9100],
            'vulnerabilities': [],
            'services': ['HTTP', 'HTTPS', 'RAW'],
          },
        ];

        connections = [
          {'from': 'gw_001', 'to': 'srv_001', 'type': 'ethernet'},
          {'from': 'gw_001', 'to': 'srv_002', 'type': 'ethernet'},
          {'from': 'gw_001', 'to': 'ws_001', 'type': 'wifi'},
          {'from': 'gw_001', 'to': 'ws_002', 'type': 'wifi'},
          {'from': 'gw_001', 'to': 'cam_001', 'type': 'wifi'},
          {'from': 'gw_001', 'to': 'cam_002', 'type': 'wifi'},
          {'from': 'gw_001', 'to': 'iot_001', 'type': 'wifi'},
          {'from': 'gw_001', 'to': 'iot_002', 'type': 'ethernet'},
          {'from': 'gw_001', 'to': 'prt_001', 'type': 'wifi'},
          {'from': 'srv_001', 'to': 'ws_001', 'type': 'domain'},
          {'from': 'srv_001', 'to': 'ws_002', 'type': 'domain'},
          {'from': 'srv_002', 'to': 'iot_001', 'type': 'api'},
        ];

        isScanning = false;
      });
    });
  }
}
