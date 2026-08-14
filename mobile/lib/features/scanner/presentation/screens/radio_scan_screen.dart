import 'package:flutter/material.dart';
import 'package:fl_chart/fl_chart.dart';
import '../../../../core/theme/app_theme.dart';

class RadioScanScreen extends StatefulWidget {
  const RadioScanScreen({super.key});

  @override
  State<RadioScanScreen> createState() => _RadioScanScreenState();
}

class _RadioScanScreenState extends State<RadioScanScreen> {
  final _freqStartCtrl = TextEditingController(text: '88');
  final _freqEndCtrl = TextEditingController(text: '108');
  String mode = 'fm';
  bool isScanning = false;
  List<Map<String, dynamic>> signals = [];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.darkTheme.scaffoldBackgroundColor,
      appBar: AppBar(title: const Text('Radio/SDR Scanner')),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: TextField(
                        controller: _freqStartCtrl,
                        style: const TextStyle(color: Colors.white, fontFamily: 'JetBrainsMono'),
                        keyboardType: TextInputType.number,
                        decoration: const InputDecoration(labelText: 'Freq Start (MHz)', labelStyle: TextStyle(color: Color(0xFF6B7280))),
                      ),
                    ),
                    const SizedBox(width: 16),
                    Expanded(
                      child: TextField(
                        controller: _freqEndCtrl,
                        style: const TextStyle(color: Colors.white, fontFamily: 'JetBrainsMono'),
                        keyboardType: TextInputType.number,
                        decoration: const InputDecoration(labelText: 'Freq End (MHz)', labelStyle: TextStyle(color: Color(0xFF6B7280))),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 16),
                Row(
                  children: [
                    const Text('Modo:', style: TextStyle(color: Color(0xFF6B7280), fontSize: 14)),
                    const SizedBox(width: 12),
                    SegmentedButton<String>(
                      segments: const [
                        ButtonSegment(value: 'fm', label: Text('FM')),
                        ButtonSegment(value: 'am', label: Text('AM')),
                        ButtonSegment(value: 'digital', label: Text('Digital')),
                      ],
                      selected: {mode},
                      onSelectionChanged: (Set<String> newSelection) {
                        setState(() => mode = newSelection.first);
                      },
                      style: SegmentedButton.styleFrom(
                        backgroundColor: const Color(0xFF1A1A24),
                        selectedBackgroundColor: AppTheme.successGreen.withAlpha(40),
                        selectedForegroundColor: AppTheme.successGreen,
                        foregroundColor: const Color(0xFF6B7280),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 16),
                SizedBox(
                  width: double.infinity,
                  child: ElevatedButton.icon(
                    icon: isScanning ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white)) : const Icon(Icons.radar),
                    label: Text(isScanning ? 'Escaneando...' : 'Iniciar Scan'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppTheme.successGreen,
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(vertical: 14),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                    ),
                    onPressed: isScanning ? null : _startScan,
                  ),
                ),
              ],
            ),
          ),
          if (signals.isNotEmpty)
            Container(
              height: 200,
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: _buildSpectrumChart(),
            ),
          Expanded(
            child: signals.isEmpty
                ? _buildEmptyState()
                : ListView.builder(
                    padding: const EdgeInsets.all(16),
                    itemCount: signals.length,
                    itemBuilder: (context, index) => _buildSignalCard(signals[index]),
                  ),
          ),
        ],
      ),
    );
  }

  Widget _buildSpectrumChart() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: BarChart(
          BarChartData(
            gridData: FlGridData(show: true, drawVerticalLine: false, horizontalInterval: 20, getDrawingHorizontalLine: (value) => FlLine(color: const Color(0xFF2A2A3A), strokeWidth: 0.5)),
            titlesData: FlTitlesData(
              bottomTitles: AxisTitles(sideTitles: SideTitles(showTitles: true, reservedSize: 30, getTitlesWidget: (value, meta) => Text('${value.toInt()}', style: const TextStyle(color: Color(0xFF6B7280), fontSize: 10)))),
              leftTitles: AxisTitles(sideTitles: SideTitles(showTitles: true, reservedSize: 35, getTitlesWidget: (value, meta) => Text('${value.toInt()}', style: const TextStyle(color: Color(0xFF6B7280), fontSize: 10)))),
              topTitles: AxisTitles(sideTitles: SideTitles(showTitles: false)),
              rightTitles: AxisTitles(sideTitles: SideTitles(showTitles: false)),
            ),
            borderData: FlBorderData(show: false),
            barGroups: signals.asMap().entries.map((e) {
              return BarChartGroupData(
                x: e.key,
                barRods: [BarChartRodData(toY: (e.value['power_dbm'] as num).toDouble() + 100, color: _getSignalColor(e.value['type']), width: 12, borderRadius: const BorderRadius.vertical(top: Radius.circular(4)))],
              );
            }).toList(),
          ),
        ),
      ),
    );
  }

  Color _getSignalColor(String type) {
    switch (type) {
      case 'FM Radio': return AppTheme.successGreen;
      case 'Military/Police': return AppTheme.dangerRed;
      case 'WiFi/BLE': return AppTheme.infoBlue;
      case 'ISM/LoRa': return AppTheme.warningAmber;
      default: return const Color(0xFF6B7280);
    }
  }

  Widget _buildEmptyState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.radar, size: 64, color: const Color(0xFF2A2A3A)),
          const SizedBox(height: 16),
          const Text('Espectro vacío', style: TextStyle(color: Color(0xFF6B7280), fontSize: 16)),
          const SizedBox(height: 8),
          const Text('Inicia un scan para detectar señales', style: TextStyle(color: Color(0xFF4B5563), fontSize: 13)),
        ],
      ),
    );
  }

  Widget _buildSignalCard(Map<String, dynamic> signal) {
    final color = _getSignalColor(signal['type']);
    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      child: ListTile(
        leading: Container(
          padding: const EdgeInsets.all(8),
          decoration: BoxDecoration(color: color.withAlpha(20), borderRadius: BorderRadius.circular(8)),
          child: Icon(Icons.wifi_tethering, color: color, size: 20),
        ),
        title: Text('${signal['frequency_mhz']} MHz - ${signal['station']}', style: const TextStyle(color: Colors.white, fontSize: 14, fontWeight: FontWeight.w500)),
        subtitle: Text('${signal['type']} | ${signal['modulation']} | ${signal['power_dbm']} dBm', style: const TextStyle(color: Color(0xFF6B7280), fontSize: 12)),
        trailing: Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
          decoration: BoxDecoration(color: color.withAlpha(30), borderRadius: BorderRadius.circular(6)),
          child: Text('${signal['confidence']}%', style: TextStyle(color: color, fontSize: 11, fontWeight: FontWeight.bold)),
        ),
      ),
    );
  }

  void _startScan() {
    setState(() {
      isScanning = true;
      signals = [];
    });

    Future.delayed(const Duration(seconds: 3), () {
      if (!mounted) return;
      setState(() {
        signals = [
          {'frequency_mhz': 88.5, 'power_dbm': -45, 'type': 'FM Radio', 'station': 'Radio Local', 'bandwidth_khz': 200, 'modulation': 'FM', 'confidence': 95},
          {'frequency_mhz': 92.3, 'power_dbm': -38, 'type': 'FM Radio', 'station': 'FM 92.3', 'bandwidth_khz': 200, 'modulation': 'FM', 'confidence': 98},
          {'frequency_mhz': 96.5, 'power_dbm': -41, 'type': 'FM Radio', 'station': 'FM 96.5', 'bandwidth_khz': 200, 'modulation': 'FM', 'confidence': 92},
          {'frequency_mhz': 100.7, 'power_dbm': -35, 'type': 'FM Radio', 'station': 'FM 100.7', 'bandwidth_khz': 200, 'modulation': 'FM', 'confidence': 99},
          {'frequency_mhz': 151.0, 'power_dbm': -65, 'type': 'Military/Police', 'station': 'Tactical Freq', 'bandwidth_khz': 25, 'modulation': 'NFM', 'confidence': 78},
          {'frequency_mhz': 446.0, 'power_dbm': -70, 'type': 'PMR446', 'station': 'Walkie-Talkie', 'bandwidth_khz': 12.5, 'modulation': 'FM', 'confidence': 85},
          {'frequency_mhz': 868.0, 'power_dbm': -80, 'type': 'ISM/LoRa', 'station': 'IoT Gateway', 'bandwidth_khz': 125, 'modulation': 'LoRa', 'confidence': 72},
        ];
        isScanning = false;
      });
    });
  }

  @override
  void dispose() {
    _freqStartCtrl.dispose();
    _freqEndCtrl.dispose();
    super.dispose();
  }
}
