import 'package:flutter/material.dart';
import '../../../../core/theme/app_theme.dart';

class ReconScreen extends StatelessWidget {
  const ReconScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.darkTheme.scaffoldBackgroundColor,
      appBar: AppBar(title: const Text('OSINT & Reconnaissance')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          _buildReconCard(
            'Shodan Lookup',
            'Buscar dispositivos expuestos en internet por IP, dominio o query',
            Icons.public,
            AppTheme.dangerRed,
            () => _showShodanDialog(context),
          ),
          _buildReconCard(
            'WHOIS Lookup',
            'Información de registro de dominios: registrar, DNS, fechas',
            Icons.domain,
            AppTheme.warningAmber,
            () => _showWhoisDialog(context),
          ),
          _buildReconCard(
            'DNS Enumeration',
            'Subdominios, registros MX, TXT, NS, SPF, DMARC',
            Icons.dns,
            AppTheme.successGreen,
            () => _showDnsDialog(context),
          ),
          _buildReconCard(
            'IP Geolocation',
            'Ubicación geográfica de IPs, ASN, ISP, rango',
            Icons.location_on,
            AppTheme.infoBlue,
            () {},
          ),
          _buildReconCard(
            'Social Engineering',
            'Email harvesting, username enumeration, breach check',
            Icons.people,
            AppTheme.cyberCyan,
            () {},
          ),
          _buildReconCard(
            'Dark Web Monitor',
            'Monitoreo de leaks, credenciales expuestas, dumps',
            Icons.dark_mode,
            const Color(0xFF8B5CF6),
            () {},
          ),
        ],
      ),
    );
  }

  Widget _buildReconCard(String title, String desc, IconData icon, Color color, VoidCallback onTap) {
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(16),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            children: [
              Container(padding: const EdgeInsets.all(12), decoration: BoxDecoration(color: color.withAlpha(20), borderRadius: BorderRadius.circular(12)), child: Icon(icon, color: color, size: 28)),
              const SizedBox(width: 16),
              Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(title, style: const TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.w600)),
                const SizedBox(height: 4),
                Text(desc, style: const TextStyle(color: Color(0xFF6B7280), fontSize: 13)),
              ])),
              const Icon(Icons.arrow_forward_ios, color: Color(0xFF4B5563), size: 16),
            ],
          ),
        ),
      ),
    );
  }

  void _showShodanDialog(BuildContext context) {
    final ctrl = TextEditingController();
    showDialog(context: context, builder: (ctx) => AlertDialog(
      backgroundColor: const Color(0xFF141419),
      title: const Text('Shodan Lookup', style: TextStyle(color: Colors.white)),
      content: TextField(controller: ctrl, style: const TextStyle(color: Colors.white), decoration: const InputDecoration(labelText: 'Query (IP, dominio, org)', labelStyle: TextStyle(color: Color(0xFF6B7280)))),
      actions: [
        TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancelar')),
        ElevatedButton(style: ElevatedButton.styleFrom(backgroundColor: AppTheme.dangerRed), onPressed: () => Navigator.pop(ctx), child: const Text('Buscar')),
      ],
    ));
  }

  void _showWhoisDialog(BuildContext context) {
    final ctrl = TextEditingController();
    showDialog(context: context, builder: (ctx) => AlertDialog(
      backgroundColor: const Color(0xFF141419),
      title: const Text('WHOIS Lookup', style: TextStyle(color: Colors.white)),
      content: TextField(controller: ctrl, style: const TextStyle(color: Colors.white), decoration: const InputDecoration(labelText: 'Dominio (ej: example.com)', labelStyle: TextStyle(color: Color(0xFF6B7280)))),
      actions: [
        TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancelar')),
        ElevatedButton(style: ElevatedButton.styleFrom(backgroundColor: AppTheme.warningAmber), onPressed: () => Navigator.pop(ctx), child: const Text('Lookup')),
      ],
    ));
  }

  void _showDnsDialog(BuildContext context) {
    final ctrl = TextEditingController();
    showDialog(context: context, builder: (ctx) => AlertDialog(
      backgroundColor: const Color(0xFF141419),
      title: const Text('DNS Enumeration', style: TextStyle(color: Colors.white)),
      content: TextField(controller: ctrl, style: const TextStyle(color: Colors.white), decoration: const InputDecoration(labelText: 'Dominio', labelStyle: TextStyle(color: Color(0xFF6B7280)))),
      actions: [
        TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancelar')),
        ElevatedButton(style: ElevatedButton.styleFrom(backgroundColor: AppTheme.successGreen), onPressed: () => Navigator.pop(ctx), child: const Text('Enumerar')),
      ],
    ));
  }
}
