import 'package:flutter/material.dart';
import '../../../../core/theme/app_theme.dart';

class WifiSecurityCard extends StatelessWidget {
  final Map<String, dynamic> network;

  const WifiSecurityCard({super.key, required this.network});

  @override
  Widget build(BuildContext context) {
    final security = network['security'] as String;
    final riskLevel = _getRiskLevel(security);
    final riskColor = _getRiskColor(riskLevel);
    final recommendations = _getRecommendations(security, network);

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(network['ssid'], style: const TextStyle(color: Colors.white, fontSize: 15, fontWeight: FontWeight.w600)),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                  decoration: BoxDecoration(
                    color: riskColor.withAlpha(30),
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: riskColor.withAlpha(60)),
                  ),
                  child: Text(
                    riskLevel.toUpperCase(),
                    style: TextStyle(color: riskColor, fontSize: 11, fontWeight: FontWeight.bold),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            _buildSecurityBar(security),
            const SizedBox(height: 16),
            Text('Recomendaciones:', style: TextStyle(color: Colors.white.withAlpha(200), fontSize: 13, fontWeight: FontWeight.w500)),
            const SizedBox(height: 8),
            ...recommendations.map((r) => Padding(
              padding: const EdgeInsets.only(bottom: 6),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(Icons.arrow_right, color: riskColor, size: 18),
                  const SizedBox(width: 4),
                  Expanded(child: Text(r, style: const TextStyle(color: Color(0xFFA1A1AA), fontSize: 12))),
                ],
              ),
            )).toList(),
            if (network['wps'] == true) ...[
              const SizedBox(height: 12),
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
                    Expanded(
                      child: Text(
                        'WPS está habilitado. Vulnerable a ataques de fuerza bruta de PIN (Pixie Dust, Reaver).',
                        style: TextStyle(color: AppTheme.warningAmber, fontSize: 12),
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildSecurityBar(String security) {
    final protocols = ['Open', 'WEP', 'WPA', 'WPA2', 'WPA3', 'Enterprise'];
    final currentIndex = protocols.indexOf(security.split('-')[0]);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text('Fortaleza del Protocolo', style: TextStyle(color: Color(0xFF6B7280), fontSize: 11)),
        const SizedBox(height: 8),
        Row(
          children: protocols.asMap().entries.map((entry) {
            final index = entry.key;
            final protocol = entry.value;
            final isActive = index <= currentIndex;
            final isCurrent = index == currentIndex;

            return Expanded(
              child: Container(
                margin: const EdgeInsets.symmetric(horizontal: 2),
                height: 8,
                decoration: BoxDecoration(
                  color: isCurrent
                      ? _getProtocolColor(protocol)
                      : isActive
                          ? _getProtocolColor(protocol).withAlpha(60)
                          : const Color(0xFF2A2A3A),
                  borderRadius: BorderRadius.circular(4),
                ),
              ),
            );
          }).toList(),
        ),
        const SizedBox(height: 8),
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: protocols.map((p) => Text(
            p,
            style: TextStyle(
              color: p == security.split('-')[0] ? _getProtocolColor(p) : const Color(0xFF4B5563),
              fontSize: 9,
              fontWeight: p == security.split('-')[0] ? FontWeight.bold : FontWeight.normal,
            ),
          )).toList(),
        ),
      ],
    );
  }

  Color _getProtocolColor(String protocol) {
    switch (protocol) {
      case 'Open': return AppTheme.dangerRed;
      case 'WEP': return AppTheme.warningAmber;
      case 'WPA': return const Color(0xFFF97316);
      case 'WPA2': return AppTheme.successGreen;
      case 'WPA3': return AppTheme.infoBlue;
      case 'Enterprise': return AppTheme.cyberCyan;
      default: return const Color(0xFF6B7280);
    }
  }

  String _getRiskLevel(String security) {
    if (security == 'Open') return 'critical';
    if (security == 'WEP') return 'high';
    if (security.startsWith('WPA') && !security.contains('Enterprise')) return 'medium';
    if (security.contains('Enterprise') || security == 'WPA3') return 'low';
    return 'medium';
  }

  Color _getRiskColor(String risk) {
    switch (risk) {
      case 'critical': return AppTheme.dangerRed;
      case 'high': return AppTheme.warningAmber;
      case 'medium': return const Color(0xFFF97316);
      case 'low': return AppTheme.successGreen;
      default: return const Color(0xFF6B7280);
    }
  }

  List<String> _getRecommendations(String security, Map<String, dynamic> net) {
    final recs = <String>[];

    if (security == 'Open') {
      recs.add('La red está completamente abierta. Cualquiera puede interceptar tráfico.');
      recs.add('Implementar WPA2-Enterprise o WPA3 inmediatamente.');
      recs.add('Usar VPN para todo el tráfico si no se puede cambiar la configuración.');
    } else if (security == 'WEP') {
      recs.add('WEP es obsoleto y se rompe en minutos con Aircrack-ng.');
      recs.add('Migrar a WPA2 mínimo, preferiblemente WPA3 o Enterprise.');
      recs.add('Cambiar la contraseña y usar AES en lugar de TKIP.');
    } else if (security == 'WPA') {
      recs.add('WPA con TKIP tiene vulnerabilidades conocidas (KRACK).');
      recs.add('Actualizar a WPA2-AES o WPA3.');
    } else if (security == 'WPA2') {
      recs.add('WPA2 es aceptable pero vulnerable a KRACK si no está parcheado.');
      recs.add('Verificar que todos los dispositivos soporten el último firmware.');
      recs.add('Considerar migrar a WPA3 si el hardware lo soporta.');
    }

    if (net['wps'] == true) {
      recs.add('Deshabilitar WPS inmediatamente. Vulnerable a ataques de PIN.');
    }

    if (net['hidden'] == true) {
      recs.add('SSID oculto no proporciona seguridad real. Se puede descubrir fácilmente.');
    }

    return recs;
  }
}
