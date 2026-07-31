import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class LogsScreen extends StatefulWidget {
  const LogsScreen({super.key});

  @override
  State<LogsScreen> createState() => _LogsScreenState();
}

class _LogsScreenState extends State<LogsScreen> {
  final List<Map<String, dynamic>> _logs = [
    {'time': '14:27:59', 'level': 'CRITICAL', 'module': 'PINNING', 'message': 'Backend no presenta certificado TLS válido'},
    {'time': '14:27:58', 'level': 'HIGH', 'module': 'SOURCESEAL', 'message': 'A5: Validación de firma HMAC FALLÓ'},
    {'time': '14:27:58', 'level': 'HIGH', 'module': 'SOURCESEAL', 'message': 'A6: Replay attack FALLÓ'},
    {'time': '14:27:59', 'level': 'HIGH', 'module': 'MULTIPLATFORM', 'message': 'Sin uso del almacén seguro nativo (AndroidKeyStore)'},
    {'time': '14:27:59', 'level': 'MEDIUM', 'module': 'RECOVERY', 'message': 'Vulnerable a clickjacking (Falta X-Frame-Options)'},
    {'time': '14:28:05', 'level': 'INFO', 'module': 'SYSTEM', 'message': 'Usuario inició sesión en SourceSeal Control Center'},
  ];

  Color _getLevelColor(String level) {
    switch (level) {
      case 'CRITICAL': return Colors.redAccent;
      case 'HIGH': return Colors.orange;
      case 'MEDIUM': return Colors.yellow;
      case 'INFO': return Colors.blueAccent;
      default: return Colors.grey;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Logs de Auditoría')),
      body: ListView.builder(
        padding: const EdgeInsets.all(16),
        itemCount: _logs.length,
        itemBuilder: (context, index) {
          final log = _logs[index];
          return Card(
            margin: const EdgeInsets.only(bottom: 8),
            child: ListTile(
              leading: CircleAvatar(
                backgroundColor: _getLevelColor(log['level']).withOpacity(0.2),
                child: Text(log['level'][0], style: TextStyle(color: _getLevelColor(log['level']), fontWeight: FontWeight.bold)),
              ),
              title: Text(log['message'], style: GoogleFonts.inter(fontSize: 14)),
              subtitle: Text('${log['module']} • ${log['time']}', style: const TextStyle(color: Colors.grey, fontSize: 12)),
              trailing: Icon(Icons.chevron_right, color: Colors.grey.shade600),
            ),
          );
        },
      ),
    );
  }
}