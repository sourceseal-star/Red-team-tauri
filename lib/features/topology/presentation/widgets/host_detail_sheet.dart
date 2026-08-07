import 'package:flutter/material.dart';
import '../../../../core/theme/app_theme.dart';

class HostDetailSheet extends StatelessWidget {
  final Map<String, dynamic> host;

  const HostDetailSheet({super.key, required this.host});

  @override
  Widget build(BuildContext context) {
    final color = _getTypeColor(host['type']);
    final hasVulns = (host['vulnerabilities']?.length ?? 0) > 0;

    return DraggableScrollableSheet(
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
                    padding: const EdgeInsets.all(14),
                    decoration: BoxDecoration(color: color.withAlpha(20), borderRadius: BorderRadius.circular(14)),
                    child: Icon(_getTypeIcon(host['type']), color: color, size: 32),
                  ),
                  const SizedBox(width: 16),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(host['hostname'], style: const TextStyle(color: Colors.white, fontSize: 20, fontWeight: FontWeight.bold)),
                        const SizedBox(height: 4),
                        Text('${host['ip']} | ${host['mac']}', style: const TextStyle(color: Color(0xFF6B7280), fontSize: 12, fontFamily: 'JetBrainsMono')),
                      ],
                    ),
                  ),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                    decoration: BoxDecoration(color: color.withAlpha(30), borderRadius: BorderRadius.circular(8)),
                    child: Text((host['type'] as String).toUpperCase(), style: TextStyle(color: color, fontSize: 10, fontWeight: FontWeight.bold)),
                  ),
                ],
              ),
              const SizedBox(height: 24),
              _buildSectionTitle('Información del Sistema'),
              _buildDetailRow('Sistema Operativo', host['os'] ?? 'Unknown', Colors.white),
              _buildDetailRow('Vendor', host['vendor'] ?? 'Unknown', const Color(0xFF8B5CF6)),
              _buildDetailRow('Tipo', host['type'] ?? 'Unknown', color),
              const SizedBox(height: 20),
              _buildSectionTitle('Servicios Detectados'),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: (host['services'] as List<dynamic>? ?? []).map<Widget>((service) {
                  return Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                    decoration: BoxDecoration(
                      color: const Color(0xFF1A1A24),
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: const Color(0xFF2A2A3A)),
                    ),
                    child: Text(service.toString(), style: const TextStyle(color: Colors.white, fontSize: 12)),
                  );
                }).toList(),
              ),
              const SizedBox(height: 20),
              _buildSectionTitle('Puertos Abiertos'),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: (host['ports'] as List<dynamic>? ?? []).map<Widget>((port) {
                  return Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                    decoration: BoxDecoration(
                      color: AppTheme.infoBlue.withAlpha(15),
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: AppTheme.infoBlue.withAlpha(40)),
                    ),
                    child: Text('$port', style: TextStyle(color: AppTheme.infoBlue, fontSize: 12, fontFamily: 'JetBrainsMono')),
                  );
                }).toList(),
              ),
              if (hasVulns) ...[
                const SizedBox(height: 20),
                _buildSectionTitle('Vulnerabilidades', color: AppTheme.dangerRed),
                const SizedBox(height: 8),
                ...host['vulnerabilities'].map<Widget>((cve) => Container(
                  margin: const EdgeInsets.only(bottom: 8),
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: AppTheme.dangerRed.withAlpha(10),
                    borderRadius: BorderRadius.circular(10),
                    border: Border.all(color: AppTheme.dangerRed.withAlpha(40)),
                  ),
                  child: Row(
                    children: [
                      const Icon(Icons.warning, color: AppTheme.dangerRed, size: 18),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(cve, style: const TextStyle(color: AppTheme.dangerRed, fontSize: 13, fontWeight: FontWeight.w600)),
                            const SizedBox(height: 2),
                            const Text('Vulnerabilidad crítica detectada. Requiere parcheo inmediato.', style: TextStyle(color: Color(0xFFA1A1AA), fontSize: 11)),
                          ],
                        ),
                      ),
                    ],
                  ),
                )).toList(),
              ],
              const SizedBox(height: 20),
              Row(
                children: [
                  Expanded(
                    child: ElevatedButton.icon(
                      icon: const Icon(Icons.terminal, size: 18),
                      label: const Text('Shell'),
                      style: ElevatedButton.styleFrom(backgroundColor: AppTheme.terminalGreen, foregroundColor: Colors.white, padding: const EdgeInsets.symmetric(vertical: 14)),
                      onPressed: () {},
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: ElevatedButton.icon(
                      icon: const Icon(Icons.bug_report, size: 18),
                      label: const Text('Exploit'),
                      style: ElevatedButton.styleFrom(backgroundColor: AppTheme.dangerRed, foregroundColor: Colors.white, padding: const EdgeInsets.symmetric(vertical: 14)),
                      onPressed: () {},
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 20),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildSectionTitle(String title, {Color color = Colors.white}) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Text(title, style: TextStyle(color: color, fontSize: 14, fontWeight: FontWeight.w600)),
    );
  }

  Widget _buildDetailRow(String label, String value, Color valueColor) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: const TextStyle(color: Color(0xFF6B7280), fontSize: 13)),
          Text(value, style: TextStyle(color: valueColor, fontSize: 13, fontWeight: FontWeight.w500)),
        ],
      ),
    );
  }

  Color _getTypeColor(String type) {
    switch (type) {
      case 'router': return const Color(0xFFEF4444);
      case 'server': return const Color(0xFF3B82F6);
      case 'workstation': return const Color(0xFF10B981);
      case 'camera': return const Color(0xFFF59E0B);
      case 'iot': return const Color(0xFF06B6D4);
      case 'printer': return const Color(0xFF8B5CF6);
      default: return const Color(0xFF6B7280);
    }
  }

  IconData _getTypeIcon(String type) {
    switch (type) {
      case 'router': return Icons.router;
      case 'server': return Icons.dns;
      case 'workstation': return Icons.computer;
      case 'camera': return Icons.videocam;
      case 'iot': return Icons.memory;
      case 'printer': return Icons.print;
      default: return Icons.device_unknown;
    }
  }
}
