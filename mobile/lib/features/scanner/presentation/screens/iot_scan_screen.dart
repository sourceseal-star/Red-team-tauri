import 'package:flutter/material.dart';
import '../../../../core/theme/app_theme.dart';

class IoTScanScreen extends StatefulWidget {
  const IoTScanScreen({super.key});

  @override
  State<IoTScanScreen> createState() => _IoTScanScreenState();
}

class _IoTScanScreenState extends State<IoTScanScreen> {
  final _targetCtrl = TextEditingController(text: '192.168.1.0/24');
  List<String> selectedProtocols = ['mqtt', 'modbus', 'coap'];
  bool isScanning = false;
  List<Map<String, dynamic>> devices = [];

  final protocols = [
    {'id': 'mqtt', 'name': 'MQTT', 'port': '1883/8883', 'color': Color(0xFFEF4444)},
    {'id': 'coap', 'name': 'CoAP', 'port': '5683/5684', 'color': Color(0xFFF59E0B)},
    {'id': 'modbus', 'name': 'Modbus', 'port': '502', 'color': Color(0xFF10B981)},
    {'id': 'bacnet', 'name': 'BACnet', 'port': '47808', 'color': Color(0xFF3B82F6)},
    {'id': 'ethernet_ip', 'name': 'EtherNet/IP', 'port': '44818', 'color': Color(0xFF8B5CF6)},
    {'id': 's7', 'name': 'S7Comm', 'port': '102', 'color': Color(0xFFEC4899)},
    {'id': 'zigbee', 'name': 'Zigbee', 'port': 'N/A', 'color': Color(0xFFF97316)},
    {'id': 'ble', 'name': 'BLE', 'port': 'N/A', 'color': Color(0xFF06B6D4)},
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.darkTheme.scaffoldBackgroundColor,
      appBar: AppBar(title: const Text('IoT/ICS Scanner')),
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
                  decoration: const InputDecoration(
                    labelText: 'Rango de red',
                    labelStyle: TextStyle(color: Color(0xFF6B7280)),
                    prefixIcon: Icon(Icons.network_check, color: Color(0xFF6B7280)),
                  ),
                ),
                const SizedBox(height: 16),
                Text('Protocolos:', style: Theme.of(context).textTheme.titleLarge?.copyWith(color: Colors.white)),
                const SizedBox(height: 8),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: protocols.map((p) {
                    final isSelected = selectedProtocols.contains(p['id']);
                    return FilterChip(
                      label: Text('${p['name']} (${p['port']})'),
                      selected: isSelected,
                      onSelected: (selected) {
                        setState(() {
                          if (selected) selectedProtocols.add(p['id'] as String);
                          else selectedProtocols.remove(p['id']);
                        });
                      },
                      selectedColor: (p['color'] as Color).withAlpha(40),
                      checkmarkColor: p['color'] as Color,
                      labelStyle: TextStyle(color: isSelected ? Colors.white : const Color(0xFF6B7280), fontSize: 11),
                      backgroundColor: const Color(0xFF1A1A24),
                    );
                  }).toList(),
                ),
                const SizedBox(height: 16),
                SizedBox(
                  width: double.infinity,
                  child: ElevatedButton.icon(
                    icon: isScanning ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white)) : const Icon(Icons.memory),
                    label: Text(isScanning ? 'Escaneando...' : 'Iniciar IoT Scan'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppTheme.infoBlue,
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(vertical: 14),
                    ),
                    onPressed: isScanning ? null : _startScan,
                  ),
                ),
              ],
            ),
          ),
          Expanded(
            child: devices.isEmpty
                ? _buildEmptyState()
                : ListView.builder(
                    padding: const EdgeInsets.all(16),
                    itemCount: devices.length,
                    itemBuilder: (context, index) => _buildDeviceCard(devices[index]),
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
          Icon(Icons.memory, size: 64, color: const Color(0xFF2A2A3A)),
          const SizedBox(height: 16),
          const Text('No hay dispositivos IoT detectados', style: TextStyle(color: Color(0xFF6B7280), fontSize: 16)),
        ],
      ),
    );
  }

  Widget _buildDeviceCard(Map<String, dynamic> dev) {
    final protocolColors = {
      'MQTT': AppTheme.dangerRed,
      'CoAP': AppTheme.warningAmber,
      'Modbus': AppTheme.successGreen,
      'BACnet': AppTheme.infoBlue,
      'EtherNet/IP': const Color(0xFF8B5CF6),
      'S7Comm': const Color(0xFFEC4899),
      'Zigbee': const Color(0xFFF97316),
      'BLE': AppTheme.cyberCyan,
    };
    final color = protocolColors[dev['protocol']] ?? const Color(0xFF6B7280);

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
                  child: Text(dev['protocol'], style: TextStyle(color: color, fontSize: 11, fontWeight: FontWeight.bold)),
                ),
                const Spacer(),
                if (dev['exploitable'] == true)
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                    decoration: BoxDecoration(color: AppTheme.dangerRed.withAlpha(30), borderRadius: BorderRadius.circular(6)),
                    child: const Text('EXPLOITABLE', style: TextStyle(color: AppTheme.dangerRed, fontSize: 10, fontWeight: FontWeight.bold)),
                  ),
              ],
            ),
            const SizedBox(height: 12),
            Text('${dev['ip']}${dev['port'] != null ? ':${dev['port']}' : ''}', style: const TextStyle(color: Colors.white, fontFamily: 'JetBrainsMono', fontSize: 14)),
            const SizedBox(height: 8),
            Text('${dev['device_type']} - ${dev['manufacturer']}', style: const TextStyle(color: Color(0xFFA1A1AA), fontSize: 13)),
            if (dev['firmware'] != null)
              Text('Firmware: ${dev['firmware']}', style: const TextStyle(color: Color(0xFF6B7280), fontSize: 12)),
            if (dev['mac_address'] != null)
              Text('MAC: ${dev['mac_address']}', style: const TextStyle(color: Color(0xFF6B7280), fontSize: 12, fontFamily: 'JetBrainsMono')),
            if (dev['signal_strength'] != null)
              Text('Señal: ${dev['signal_strength']} dBm', style: const TextStyle(color: AppTheme.successGreen, fontSize: 12)),
          ],
        ),
      ),
    );
  }

  void _startScan() {
    setState(() {
      isScanning = true;
      devices = [];
    });

    Future.delayed(const Duration(seconds: 3), () {
      if (!mounted) return;
      setState(() {
        devices = [
          {'ip': '192.168.1.200', 'port': 1883, 'protocol': 'MQTT', 'device_type': 'Smart Gateway', 'manufacturer': 'Shelly', 'firmware': 'v1.2.3', 'exploitable': true},
          {'ip': '192.168.1.201', 'port': 502, 'protocol': 'Modbus', 'device_type': 'PLC', 'manufacturer': 'Siemens', 'exploitable': true},
          {'ip': '192.168.1.202', 'port': 5683, 'protocol': 'CoAP', 'device_type': 'Sensor', 'manufacturer': 'Xiaomi', 'firmware': 'v2.1.0', 'exploitable': false},
          {'ip': '192.168.1.203', 'port': 47808, 'protocol': 'BACnet', 'device_type': 'HVAC Controller', 'manufacturer': 'Johnson Controls', 'exploitable': false},
          {'ip': '192.168.1.150', 'port': null, 'protocol': 'Zigbee', 'device_type': 'Smart Bulb', 'manufacturer': 'Philips Hue', 'mac_address': 'A4:B1:E2:12:34:56', 'signal_strength': -62, 'exploitable': false},
          {'ip': '192.168.1.151', 'port': null, 'protocol': 'BLE', 'device_type': 'Smart Lock', 'manufacturer': 'Yale', 'mac_address': 'B8:27:EB:AB:CD:EF', 'signal_strength': -48, 'exploitable': true},
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
