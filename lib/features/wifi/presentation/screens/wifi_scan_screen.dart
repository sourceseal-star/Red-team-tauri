import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../../../core/theme/app_theme.dart';
import '../widgets/wifi_security_card.dart';
import '../widgets/wifi_signal_chart.dart';

class WifiScanScreen extends StatefulWidget {
  const WifiScanScreen({super.key});

  @override
  State<WifiScanScreen> createState() => _WifiScanScreenState();
}

class _WifiScanScreenState extends State<WifiScanScreen> with SingleTickerProviderStateMixin {
  late TabController _tabController;
  bool isScanning = false;
  List<Map<String, dynamic>> networks = [];
  List<Map<String, dynamic>> connectedDevices = [];
  Map<String, dynamic>? selectedNetwork;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.darkTheme.scaffoldBackgroundColor,
      appBar: AppBar(
        title: const Text('WiFi Scanner'),
        actions: [
          IconButton(
            icon: isScanning
                ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                : const Icon(Icons.radar, color: AppTheme.successGreen),
            onPressed: isScanning ? null : _startScan,
          ),
        ],
        bottom: TabBar(
          controller: _tabController,
          indicatorColor: AppTheme.infoBlue,
          labelColor: AppTheme.infoBlue,
          unselectedLabelColor: const Color(0xFF6B7280),
          tabs: const [
            Tab(icon: Icon(Icons.wifi), text: 'Networks'),
            Tab(icon: Icon(Icons.devices), text: 'Devices'),
            Tab(icon: Icon(Icons.security), text: 'Audit'),
          ],
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: [
          _buildNetworksTab(),
          _buildDevicesTab(),
          _buildAuditTab(),
        ],
      ),
    );
  }

  Widget _buildNetworksTab() {
    if (networks.isEmpty) {
      return _buildEmptyState('No hay redes detectadas', 'Inicia un scan WiFi para descubrir APs cercanos', Icons.wifi_off);
    }
    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: networks.length,
      itemBuilder: (context, index) => _buildNetworkCard(networks[index]),
    );
  }

  Widget _buildDevicesTab() {
    if (connectedDevices.isEmpty) {
      return _buildEmptyState('No hay dispositivos', 'Selecciona una red para ver dispositivos conectados', Icons.devices);
    }
    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: connectedDevices.length,
      itemBuilder: (context, index) => _buildDeviceCard(connectedDevices[index]),
    );
  }

  Widget _buildAuditTab() {
    if (networks.isEmpty) {
      return _buildEmptyState('Sin datos de auditoría', 'Escanea primero para analizar seguridad', Icons.security);
    }
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        _buildAuditSummary(),
        const SizedBox(height: 20),
        Text('Análisis por Red', style: Theme.of(context).textTheme.headlineMedium?.copyWith(color: Colors.white)),
        const SizedBox(height: 12),
        ...networks.map((n) => WifiSecurityCard(network: n)).toList(),
      ],
    );
  }

  Widget _buildEmptyState(String title, String subtitle, IconData icon) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(icon, size: 64, color: const Color(0xFF2A2A3A)),
          const SizedBox(height: 16),
          Text(title, style: const TextStyle(color: Color(0xFF6B7280), fontSize: 16)),
          const SizedBox(height: 8),
          Text(subtitle, style: const TextStyle(color: Color(0xFF4B5563), fontSize: 13)),
        ],
      ),
    );
  }

  Widget _buildNetworkCard(Map<String, dynamic> net) {
    final securityColor = _getSecurityColor(net['security']);
    final signalPercent = ((net['signal_dbm'] as num) + 100).clamp(0, 100);

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: InkWell(
        onTap: () => _showNetworkDetail(net),
        borderRadius: BorderRadius.circular(16),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Icon(Icons.wifi, color: securityColor, size: 24),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(net['ssid'], style: const TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.w600)),
                        Text('BSSID: ${net['bssid']}', style: const TextStyle(color: Color(0xFF6B7280), fontSize: 11, fontFamily: 'JetBrainsMono')),
                      ],
                    ),
                  ),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                    decoration: BoxDecoration(
                      color: securityColor.withAlpha(30),
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: securityColor.withAlpha(60)),
                    ),
                    child: Text(
                      net['security'],
                      style: TextStyle(color: securityColor, fontSize: 11, fontWeight: FontWeight.bold),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              Row(
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            const Text('Señal: ', style: TextStyle(color: Color(0xFF6B7280), fontSize: 12)),
                            Text('${net['signal_dbm']} dBm', style: TextStyle(
                              color: signalPercent > 70 ? AppTheme.successGreen : signalPercent > 40 ? AppTheme.warningAmber : AppTheme.dangerRed,
                              fontSize: 12,
                              fontWeight: FontWeight.w600,
                            )),
                          ],
                        ),
                        const SizedBox(height: 4),
                        ClipRRect(
                          borderRadius: BorderRadius.circular(4),
                          child: LinearProgressIndicator(
                            value: signalPercent / 100,
                            backgroundColor: const Color(0xFF2A2A3A),
                            valueColor: AlwaysStoppedAnimation(
                              signalPercent > 70 ? AppTheme.successGreen : signalPercent > 40 ? AppTheme.warningAmber : AppTheme.dangerRed,
                            ),
                            minHeight: 6,
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(width: 20),
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.end,
                    children: [
                      Text('Ch ${net['channel']}', style: const TextStyle(color: Colors.white, fontSize: 13, fontWeight: FontWeight.w500)),
                      Text('${net['frequency']} GHz', style: const TextStyle(color: Color(0xFF6B7280), fontSize: 11)),
                    ],
                  ),
                ],
              ),
              const SizedBox(height: 12),
              Row(
                children: [
                  _buildInfoChip('${net['connected_devices']} devices', Icons.devices, const Color(0xFF3B82F6)),
                  const SizedBox(width: 8),
                  _buildInfoChip(net['vendor'] ?? 'Unknown', Icons.business, const Color(0xFF8B5CF6)),
                  const SizedBox(width: 8),
                  if (net['wps'] == true)
                    _buildInfoChip('WPS', Icons.lock_open, AppTheme.warningAmber),
                  if (net['hidden'] == true)
                    _buildInfoChip('Hidden', Icons.visibility_off, AppTheme.dangerRed),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildDeviceCard(Map<String, dynamic> dev) {
    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      child: ListTile(
        leading: Container(
          padding: const EdgeInsets.all(8),
          decoration: BoxDecoration(color: AppTheme.infoBlue.withAlpha(20), borderRadius: BorderRadius.circular(8)),
          child: Icon(_getDeviceIcon(dev['type']), color: AppTheme.infoBlue, size: 20),
        ),
        title: Text(dev['hostname'] ?? 'Unknown Device', style: const TextStyle(color: Colors.white, fontSize: 14)),
        subtitle: Text('${dev['ip']} | ${dev['mac']}', style: const TextStyle(color: Color(0xFF6B7280), fontSize: 12, fontFamily: 'JetBrainsMono')),
        trailing: Text(dev['vendor'] ?? '', style: const TextStyle(color: Color(0xFF4B5563), fontSize: 11)),
      ),
    );
  }

  Widget _buildAuditSummary() {
    final openNetworks = networks.where((n) => n['security'] == 'Open').length;
    final wepNetworks = networks.where((n) => n['security'] == 'WEP').length;
    final wpaNetworks = networks.where((n) => n['security'] == 'WPA').length;
    final wpa2Networks = networks.where((n) => n['security'] == 'WPA2').length;
    final wpa3Networks = networks.where((n) => n['security'] == 'WPA3').length;
    final wpsEnabled = networks.where((n) => n['wps'] == true).length;

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFF141419),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: const Color(0xFF2A2A3A)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Resumen de Seguridad WiFi', style: Theme.of(context).textTheme.headlineMedium?.copyWith(color: Colors.white)),
          const SizedBox(height: 16),
          Row(
            children: [
              _buildAuditStat('Open', openNetworks, AppTheme.dangerRed),
              _buildAuditStat('WEP', wepNetworks, AppTheme.warningAmber),
              _buildAuditStat('WPA', wpaNetworks, const Color(0xFFF97316)),
              _buildAuditStat('WPA2', wpa2Networks, AppTheme.successGreen),
              _buildAuditStat('WPA3', wpa3Networks, AppTheme.infoBlue),
            ],
          ),
          const SizedBox(height: 12),
          if (wpsEnabled > 0)
            Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: AppTheme.warningAmber.withAlpha(15),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: AppTheme.warningAmber.withAlpha(40)),
              ),
              child: Row(
                children: [
                  Icon(Icons.warning_amber, color: AppTheme.warningAmber, size: 18),
                  const SizedBox(width: 8),
                  Text('$wpsEnabled redes tienen WPS habilitado (vulnerable a PIN brute force)', style: TextStyle(color: AppTheme.warningAmber, fontSize: 12)),
                ],
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildAuditStat(String label, int count, Color color) {
    return Expanded(
      child: Container(
        margin: const EdgeInsets.symmetric(horizontal: 4),
        padding: const EdgeInsets.symmetric(vertical: 12),
        decoration: BoxDecoration(
          color: color.withAlpha(15),
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: color.withAlpha(30)),
        ),
        child: Column(
          children: [
            Text('$count', style: TextStyle(color: color, fontSize: 22, fontWeight: FontWeight.bold)),
            const SizedBox(height: 4),
            Text(label, style: const TextStyle(color: Color(0xFF6B7280), fontSize: 11)),
          ],
        ),
      ),
    );
  }

  Widget _buildInfoChip(String label, IconData icon, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: color.withAlpha(15),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, color: color, size: 12),
          const SizedBox(width: 4),
          Text(label, style: TextStyle(color: color, fontSize: 10)),
        ],
      ),
    );
  }

  Color _getSecurityColor(String security) {
    switch (security) {
      case 'Open': return AppTheme.dangerRed;
      case 'WEP': return AppTheme.warningAmber;
      case 'WPA': return const Color(0xFFF97316);
      case 'WPA2': return AppTheme.successGreen;
      case 'WPA3': return AppTheme.infoBlue;
      case 'Enterprise': return AppTheme.cyberCyan;
      default: return const Color(0xFF6B7280);
    }
  }

  IconData _getDeviceIcon(String? type) {
    switch (type) {
      case 'phone': return Icons.smartphone;
      case 'laptop': return Icons.laptop;
      case 'tv': return Icons.tv;
      case 'iot': return Icons.memory;
      case 'printer': return Icons.print;
      case 'router': return Icons.router;
      default: return Icons.devices;
    }
  }

  void _showNetworkDetail(Map<String, dynamic> net) {
    setState(() => selectedNetwork = net);
    showModalBottomSheet(
      context: context,
      backgroundColor: const Color(0xFF141419),
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(24))),
      builder: (context) => DraggableScrollableSheet(
        initialChildSize: 0.7,
        minChildSize: 0.5,
        maxChildSize: 0.9,
        expand: false,
        builder: (context, scrollController) => SingleChildScrollView(
          controller: scrollController,
          child: Padding(
            padding: const EdgeInsets.all(20),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Center(
                  child: Container(width: 40, height: 4, decoration: BoxDecoration(color: const Color(0xFF2A2A3A), borderRadius: BorderRadius.circular(2))),
                ),
                const SizedBox(height: 20),
                Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: _getSecurityColor(net['security']).withAlpha(20),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Icon(Icons.wifi, color: _getSecurityColor(net['security']), size: 28),
                    ),
                    const SizedBox(width: 16),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(net['ssid'], style: const TextStyle(color: Colors.white, fontSize: 20, fontWeight: FontWeight.bold)),
                          Text(net['bssid'], style: const TextStyle(color: Color(0xFF6B7280), fontSize: 12, fontFamily: 'JetBrainsMono')),
                        ],
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 20),
                WifiSignalChart(signalHistory: net['signal_history'] ?? []),
                const SizedBox(height: 20),
                _buildDetailRow('Seguridad', net['security'], _getSecurityColor(net['security'])),
                _buildDetailRow('Frecuencia', '${net['frequency']} GHz', Colors.white),
                _buildDetailRow('Canal', 'Ch ${net['channel']}', Colors.white),
                _buildDetailRow('Señal actual', '${net['signal_dbm']} dBm', AppTheme.successGreen),
                _buildDetailRow('Vendor', net['vendor'] ?? 'Unknown', const Color(0xFF8B5CF6)),
                _buildDetailRow('Dispositivos', '${net['connected_devices']}', AppTheme.infoBlue),
                const SizedBox(height: 20),
                if (net['security'] != 'Open')
                  SizedBox(
                    width: double.infinity,
                    child: ElevatedButton.icon(
                      icon: const Icon(Icons.wifi_tethering, size: 18),
                      label: const Text('Handshake Capture'),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: AppTheme.dangerRed,
                        foregroundColor: Colors.white,
                        padding: const EdgeInsets.symmetric(vertical: 14),
                      ),
                      onPressed: () {},
                    ),
                  ),
                const SizedBox(height: 12),
                SizedBox(
                  width: double.infinity,
                  child: OutlinedButton.icon(
                    icon: const Icon(Icons.devices, size: 18),
                    label: const Text('Ver Dispositivos Conectados'),
                    style: OutlinedButton.styleFrom(foregroundColor: AppTheme.infoBlue, padding: const EdgeInsets.symmetric(vertical: 14)),
                    onPressed: () {
                      Navigator.pop(context);
                      _tabController.animateTo(1);
                    },
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildDetailRow(String label, String value, Color valueColor) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: const TextStyle(color: Color(0xFF6B7280), fontSize: 14)),
          Text(value, style: TextStyle(color: valueColor, fontSize: 14, fontWeight: FontWeight.w600)),
        ],
      ),
    );
  }

  void _startScan() {
    setState(() {
      isScanning = true;
      networks = [];
      connectedDevices = [];
    });

    Future.delayed(const Duration(seconds: 3), () {
      if (!mounted) return;
      setState(() {
        networks = [
          {
            'ssid': 'CORP_WIFI_5G',
            'bssid': 'AA:BB:CC:DD:EE:01',
            'security': 'WPA2-Enterprise',
            'signal_dbm': -42,
            'frequency': 5.2,
            'channel': 36,
            'vendor': 'Cisco',
            'connected_devices': 24,
            'wps': false,
            'hidden': false,
            'signal_history': [-45, -43, -42, -44, -42, -41, -42],
          },
          {
            'ssid': 'Guest_Network',
            'bssid': 'AA:BB:CC:DD:EE:02',
            'security': 'Open',
            'signal_dbm': -55,
            'frequency': 2.4,
            'channel': 6,
            'vendor': 'Ubiquiti',
            'connected_devices': 8,
            'wps': false,
            'hidden': false,
            'signal_history': [-58, -56, -55, -57, -55, -54, -55],
          },
          {
            'ssid': 'HomeRouter_2G',
            'bssid': 'FF:EE:DD:CC:BB:AA',
            'security': 'WPA2',
            'signal_dbm': -38,
            'frequency': 2.4,
            'channel': 11,
            'vendor': 'TP-Link',
            'connected_devices': 12,
            'wps': true,
            'hidden': false,
            'signal_history': [-40, -39, -38, -38, -37, -38, -38],
          },
          {
            'ssid': 'IoT_Gateway',
            'bssid': '11:22:33:44:55:66',
            'security': 'WPA3',
            'signal_dbm': -62,
            'frequency': 2.4,
            'channel': 1,
            'vendor': 'Amazon',
            'connected_devices': 6,
            'wps': false,
            'hidden': false,
            'signal_history': [-65, -63, -62, -64, -62, -61, -62],
          },
          {
            'ssid': 'Hidden_Network',
            'bssid': '99:88:77:66:55:44',
            'security': 'WEP',
            'signal_dbm': -72,
            'frequency': 2.4,
            'channel': 3,
            'vendor': 'Unknown',
            'connected_devices': 2,
            'wps': true,
            'hidden': true,
            'signal_history': [-75, -73, -72, -74, -72, -71, -72],
          },
        ];

        connectedDevices = [
          {'hostname': 'iPhone-Admin', 'ip': '192.168.1.105', 'mac': 'A4:B1:E2:12:34:56', 'vendor': 'Apple', 'type': 'phone'},
          {'hostname': 'DESKTOP-WIN10', 'ip': '192.168.1.110', 'mac': 'B8:27:EB:AB:CD:EF', 'vendor': 'Dell', 'type': 'laptop'},
          {'hostname': 'SmartTV-LG', 'ip': '192.168.1.115', 'mac': 'CC:44:88:AA:BB:22', 'vendor': 'LG', 'type': 'tv'},
          {'hostname': 'Nest-Thermostat', 'ip': '192.168.1.120', 'mac': 'DD:55:99:CC:DD:33', 'vendor': 'Google', 'type': 'iot'},
          {'hostname': 'Printer-HP', 'ip': '192.168.1.125', 'mac': 'EE:66:AA:DD:EE:44', 'vendor': 'HP', 'type': 'printer'},
          {'hostname': 'Router-AP', 'ip': '192.168.1.1', 'mac': 'FF:77:BB:EE:FF:55', 'vendor': 'Cisco', 'type': 'router'},
        ];

        isScanning = false;
      });
    });
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }
}
