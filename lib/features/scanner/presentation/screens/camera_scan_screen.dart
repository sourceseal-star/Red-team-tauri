import 'package:flutter/material.dart';
import '../../../../core/theme/app_theme.dart';

class CameraScanScreen extends StatefulWidget {
  const CameraScanScreen({super.key});

  @override
  State<CameraScanScreen> createState() => _CameraScanScreenState();
}

class _CameraScanScreenState extends State<CameraScanScreen> {
  final _targetCtrl = TextEditingController(text: '192.168.1.0/24');
  List<String> selectedBrands = ['hikvision', 'dahua', 'axis', 'foscam'];
  bool isScanning = false;
  List<Map<String, dynamic>> results = [];

  final List<Map<String, dynamic>> brands = [
    {'id': 'hikvision', 'name': 'Hikvision', 'color': Color(0xFFEF4444)},
    {'id': 'dahua', 'name': 'Dahua', 'color': Color(0xFFF59E0B)},
    {'id': 'axis', 'name': 'Axis', 'color': Color(0xFF10B981)},
    {'id': 'foscam', 'name': 'Foscam', 'color': Color(0xFF3B82F6)},
    {'id': 'avigilon', 'name': 'Avigilon', 'color': Color(0xFF8B5CF6)},
    {'id': 'hanwha', 'name': 'Hanwha', 'color': Color(0xFFEC4899)},
    {'id': 'bosch', 'name': 'Bosch', 'color': Color(0xFFF97316)},
    {'id': 'panasonic', 'name': 'Panasonic', 'color': Color(0xFF06B6D4)},
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.darkTheme.scaffoldBackgroundColor,
      appBar: AppBar(
        title: const Text('Camera Scanner'),
        actions: [
          IconButton(
            icon: const Icon(Icons.play_arrow, color: AppTheme.successGreen),
            onPressed: isScanning ? null : _startScan,
          ),
        ],
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                TextField(
                  controller: _targetCtrl,
                  style: const TextStyle(color: Colors.white, fontFamily: 'JetBrainsMono'),
                  decoration: InputDecoration(
                    labelText: 'Rango de red',
                    labelStyle: const TextStyle(color: Color(0xFF6B7280)),
                    prefixIcon: const Icon(Icons.network_check, color: Color(0xFF6B7280)),
                    suffixIcon: IconButton(
                      icon: const Icon(Icons.clear, color: Color(0xFF6B7280)),
                      onPressed: () => _targetCtrl.clear(),
                    ),
                  ),
                ),
                const SizedBox(height: 16),
                Text('Marcas a escanear:', style: Theme.of(context).textTheme.titleLarge?.copyWith(color: Colors.white)),
                const SizedBox(height: 8),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: brands.map((b) {
                    final isSelected = selectedBrands.contains(b['id']);
                    return FilterChip(
                      label: Text(b['name']),
                      selected: isSelected,
                      onSelected: (selected) {
                        setState(() {
                          if (selected) {
                            selectedBrands.add(b['id']);
                          } else {
                            selectedBrands.remove(b['id']);
                          }
                        });
                      },
                      selectedColor: (b['color'] as Color).withAlpha(40),
                      checkmarkColor: b['color'] as Color,
                      labelStyle: TextStyle(
                        color: isSelected ? Colors.white : const Color(0xFF6B7280),
                        fontSize: 12,
                      ),
                      backgroundColor: const Color(0xFF1A1A24),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                    );
                  }).toList(),
                ),
              ],
            ),
          ),
          if (isScanning)
            const Padding(
              padding: EdgeInsets.symmetric(horizontal: 16),
              child: LinearProgressIndicator(backgroundColor: Color(0xFF2A2A3A), valueColor: AlwaysStoppedAnimation(AppTheme.warningAmber)),
            ),
          Expanded(
            child: results.isEmpty
                ? _buildEmptyState()
                : ListView.builder(
                    padding: const EdgeInsets.all(16),
                    itemCount: results.length,
                    itemBuilder: (context, index) => _buildCameraCard(results[index]),
                  ),
          ),
        ],
      ),
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.videocam_off, size: 64, color: const Color(0xFF2A2A3A)),
          const SizedBox(height: 16),
          const Text('No hay cámaras detectadas', style: TextStyle(color: Color(0xFF6B7280), fontSize: 16)),
          const SizedBox(height: 8),
          const Text('Inicia un scan para descubrir dispositivos', style: TextStyle(color: Color(0xFF4B5563), fontSize: 13)),
        ],
      ),
    );
  }

  Widget _buildCameraCard(Map<String, dynamic> cam) {
    final brandColors = {
      'hikvision': AppTheme.dangerRed,
      'dahua': AppTheme.warningAmber,
      'axis': AppTheme.successGreen,
      'foscam': AppTheme.infoBlue,
    };
    final color = brandColors[cam['brand']] ?? const Color(0xFF6B7280);

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(color: color.withAlpha(30), borderRadius: BorderRadius.circular(6)),
                  child: Text(
                    (cam['brand'] as String).toUpperCase(),
                    style: TextStyle(color: color, fontSize: 11, fontWeight: FontWeight.bold),
                  ),
                ),
                const Spacer(),
                if (cam['vulnerabilities']?.isNotEmpty == true)
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                    decoration: BoxDecoration(color: AppTheme.dangerRed.withAlpha(30), borderRadius: BorderRadius.circular(6)),
                    child: Text(
                      '${cam['vulnerabilities'].length} CVEs',
                      style: const TextStyle(color: AppTheme.dangerRed, fontSize: 11, fontWeight: FontWeight.bold),
                    ),
                  ),
              ],
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                const Icon(Icons.router, color: Color(0xFF6B7280), size: 16),
                const SizedBox(width: 8),
                Text('${cam['ip']}:${cam['port']}', style: const TextStyle(color: Colors.white, fontFamily: 'JetBrainsMono', fontSize: 14)),
              ],
            ),
            const SizedBox(height: 8),
            if (cam['model'] != null)
              Row(
                children: [
                  const Icon(Icons.devices, color: Color(0xFF6B7280), size: 16),
                  const SizedBox(width: 8),
                  Text('Modelo: ${cam['model']}', style: const TextStyle(color: Color(0xFFA1A1AA), fontSize: 13)),
                ],
              ),
            const SizedBox(height: 8),
            Row(
              children: [
                const Icon(Icons.link, color: Color(0xFF6B7280), size: 16),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    cam['http_url'] ?? '',
                    style: const TextStyle(color: AppTheme.cyberCyan, fontSize: 12, fontFamily: 'JetBrainsMono'),
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
              ],
            ),
            if (cam['rtsp_url'] != null) ...[
              const SizedBox(height: 8),
              Row(
                children: [
                  const Icon(Icons.live_tv, color: Color(0xFF6B7280), size: 16),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      cam['rtsp_url'],
                      style: const TextStyle(color: AppTheme.successGreen, fontSize: 12, fontFamily: 'JetBrainsMono'),
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                ],
              ),
            ],
            if (cam['default_credentials']?.isNotEmpty == true) ...[
              const SizedBox(height: 12),
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: AppTheme.dangerRed.withAlpha(10),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: AppTheme.dangerRed.withAlpha(30)),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('Credenciales Default Detectadas:', style: TextStyle(color: AppTheme.dangerRed, fontSize: 12, fontWeight: FontWeight.w600)),
                    const SizedBox(height: 4),
                    ...cam['default_credentials'].map<Widget>((c) => Text(
                      '  • ${c[0]} / ${c[1]}',
                      style: const TextStyle(color: Color(0xFFA1A1AA), fontSize: 12, fontFamily: 'JetBrainsMono'),
                    )).toList(),
                  ],
                ),
              ),
            ],
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    icon: const Icon(Icons.open_in_browser, size: 16),
                    label: const Text('Abrir'),
                    onPressed: () {},
                    style: OutlinedButton.styleFrom(foregroundColor: AppTheme.cyberCyan),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: OutlinedButton.icon(
                    icon: const Icon(Icons.play_arrow, size: 16),
                    label: const Text('Stream'),
                    onPressed: () {},
                    style: OutlinedButton.styleFrom(foregroundColor: AppTheme.successGreen),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: OutlinedButton.icon(
                    icon: const Icon(Icons.bug_report, size: 16),
                    label: const Text('Exploit'),
                    onPressed: () {},
                    style: OutlinedButton.styleFrom(foregroundColor: AppTheme.dangerRed),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  void _startScan() {
    setState(() {
      isScanning = true;
      results = [];
    });

    // Simular scan progresivo
    Future.delayed(const Duration(seconds: 2), () {
      if (!mounted) return;
      setState(() {
        results = [
          {
            'ip': '192.168.1.105',
            'port': 80,
            'brand': 'hikvision',
            'model': 'DS-2CD2143G0-I',
            'http_url': 'http://192.168.1.105',
            'rtsp_url': 'rtsp://192.168.1.105:554/Streaming/Channels/101',
            'vulnerabilities': ['CVE-2021-36260', 'CVE-2021-33044'],
            'default_credentials': [['admin', '12345'], ['admin', 'admin']],
          },
          {
            'ip': '192.168.1.110',
            'port': 80,
            'brand': 'dahua',
            'model': 'IPC-HDW1230T',
            'http_url': 'http://192.168.1.110',
            'rtsp_url': 'rtsp://192.168.1.110:554/cam/realmonitor?channel=1&subtype=0',
            'vulnerabilities': ['CVE-2021-33037'],
            'default_credentials': [['admin', 'admin']],
          },
          {
            'ip': '192.168.1.120',
            'port': 80,
            'brand': 'axis',
            'model': 'M3027-PVE',
            'http_url': 'http://192.168.1.120',
            'rtsp_url': 'rtsp://192.168.1.120:554/axis-media/media.amp',
            'vulnerabilities': [],
            'default_credentials': [['root', 'pass']],
          },
        ];
        isScanning = false;
      });
    });
  }

  @override
  void dispose() {
    _targetCtrl.dispose();
    super.dispose();
  }
}
