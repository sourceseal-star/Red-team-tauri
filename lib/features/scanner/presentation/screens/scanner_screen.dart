import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../../../core/theme/app_theme.dart';

class ScannerScreen extends StatelessWidget {
  const ScannerScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.darkTheme.scaffoldBackgroundColor,
      appBar: AppBar(title: const Text('Scanner Modules')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          _buildScanCard(
            context,
            'Port Scanner',
            'Escaneo TCP/UDP completo con banner grabbing, detección de servicios y fingerprinting OS',
            Icons.network_check,
            AppTheme.dangerRed,
            () => _showPortScanDialog(context),
          ),
          const SizedBox(height: 12),
          _buildScanCard(
            context,
            'Camera Scanner',
            'Descubre cámaras IP (Hikvision, Dahua, Axis, Foscam) y extrae RTSP streams',
            Icons.videocam,
            AppTheme.warningAmber,
            () => context.push('/scanner/cameras'),
          ),
          const SizedBox(height: 12),
          _buildScanCard(
            context,
            'Radio/SDR Scanner',
            'Escaneo de frecuencias FM/AM/Digital. Detecta estaciones, walkies, IoT radio',
            Icons.radio,
            AppTheme.successGreen,
            () => context.push('/scanner/radio'),
          ),
          const SizedBox(height: 12),
          _buildScanCard(
            context,
            'IoT/ICS Scanner',
            'MQTT, Modbus, BACnet, CoAP, Zigbee, BLE. SCADA & Industrial Control Systems',
            Icons.memory,
            AppTheme.infoBlue,
            () => context.push('/scanner/iot'),
          ),
          const SizedBox(height: 12),
          _buildScanCard(
            context,
            'Vulnerability Scan',
            'CVE matching, version detection, default credentials, misconfiguration checks',
            Icons.security,
            const Color(0xFF8B5CF6),
            () => _showVulnScanDialog(context),
          ),
          const SizedBox(height: 12),
          _buildScanCard(
            context,
            'Network Discovery',
            'ARP scan, ping sweep, OS fingerprinting, topology mapping',
            Icons.device_hub,
            const Color(0xFFEC4899),
            () => _showNetDiscoveryDialog(context),
          ),
        ],
      ),
    );
  }

  Widget _buildScanCard(BuildContext context, String title, String desc, IconData icon, Color color, VoidCallback onTap) {
    return Card(
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(16),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            children: [
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(color: color.withAlpha(20), borderRadius: BorderRadius.circular(12)),
                child: Icon(icon, color: color, size: 28),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(title, style: const TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.w600)),
                    const SizedBox(height: 4),
                    Text(desc, style: const TextStyle(color: Color(0xFF6B7280), fontSize: 13)),
                  ],
                ),
              ),
              const Icon(Icons.arrow_forward_ios, color: Color(0xFF4B5563), size: 16),
            ],
          ),
        ),
      ),
    );
  }

  void _showPortScanDialog(BuildContext context) {
    final targetCtrl = TextEditingController(text: '192.168.1.0/24');
    final portsCtrl = TextEditingController(text: '1-1000');
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: const Color(0xFF141419),
        title: const Text('Port Scan', style: TextStyle(color: Colors.white)),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: targetCtrl,
              style: const TextStyle(color: Colors.white),
              decoration: const InputDecoration(labelText: 'Target (IP/CIDR/Domain)', labelStyle: TextStyle(color: Color(0xFF6B7280))),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: portsCtrl,
              style: const TextStyle(color: Colors.white),
              decoration: const InputDecoration(labelText: 'Ports (ej: 80,443,1-1000)', labelStyle: TextStyle(color: Color(0xFF6B7280))),
            ),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancelar')),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: AppTheme.dangerRed),
            onPressed: () {
              Navigator.pop(context);
              _showScanProgress(context, 'Port Scan', targetCtrl.text);
            },
            child: const Text('Iniciar Scan'),
          ),
        ],
      ),
    );
  }

  void _showVulnScanDialog(BuildContext context) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: const Color(0xFF141419),
        title: const Text('Vulnerability Scan', style: TextStyle(color: Colors.white)),
        content: const Text('Escaneo de vulnerabilidades con base de datos CVE actualizada.', style: TextStyle(color: Color(0xFFA1A1AA))),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancelar')),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF8B5CF6)),
            onPressed: () => Navigator.pop(context),
            child: const Text('Iniciar'),
          ),
        ],
      ),
    );
  }

  void _showNetDiscoveryDialog(BuildContext context) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: const Color(0xFF141419),
        title: const Text('Network Discovery', style: TextStyle(color: Colors.white)),
        content: const Text('Descubrimiento de hosts activos en la red con ARP/Ping sweep.', style: TextStyle(color: Color(0xFFA1A1AA))),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancelar')),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFFEC4899)),
            onPressed: () => Navigator.pop(context),
            child: const Text('Iniciar'),
          ),
        ],
      ),
    );
  }

  void _showScanProgress(BuildContext context, String type, String target) {
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (context) => AlertDialog(
        backgroundColor: const Color(0xFF141419),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const CircularProgressIndicator(color: AppTheme.dangerRed),
            const SizedBox(height: 20),
            Text('$type en progreso...', style: const TextStyle(color: Colors.white, fontSize: 16)),
            const SizedBox(height: 8),
            Text('Target: $target', style: const TextStyle(color: Color(0xFF6B7280), fontSize: 13)),
            const SizedBox(height: 16),
            const LinearProgressIndicator(value: 0.45, backgroundColor: Color(0xFF2A2A3A), valueColor: AlwaysStoppedAnimation(AppTheme.dangerRed)),
          ],
        ),
      ),
    );
    Future.delayed(const Duration(seconds: 3), () => Navigator.pop(context));
  }
}
