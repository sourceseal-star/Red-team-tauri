import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../models/vulnerability_model.dart';

class VulnerabilitiesScreen extends StatefulWidget {
  const VulnerabilitiesScreen({super.key});

  @override
  State<VulnerabilitiesScreen> createState() => _VulnerabilitiesScreenState();
}

class _VulnerabilitiesScreenState extends State<VulnerabilitiesScreen> {
  String _filter = 'all';
  
  // Datos simulados basados EXACTAMENTE en tu JSON redteam-1785243252338.json
  final List<Vulnerability> _vulnerabilities = [
    Vulnerability(
      scenario: 'sourcesealcorp',
      severity: 'critical',
      title: '6 controles de seguridad de SOURCESEALCORP FALLARON',
      description: 'Ataques que NO pasaron: A1(Reuso de hash), A2(Time-lock), A4(Rate limiting), A5(HMAC), A6(Replay), A7(Path traversal).',
      evidencePath: '/evidence/scan-20260727/sourceseal-attacks.json',
      remediation: 'Revisar inmediatamente cada control. Detalle por ataque en el JSON.',
      timestamp: '2026-07-27T14:27:58.757506',
    ),
    Vulnerability(
      scenario: 'multiplatform',
      severity: 'high',
      title: 'Sin uso del almacén seguro nativo de Android',
      description: 'Esperado alguno de: AndroidKeyStore. Riesgo: claves expuestas.',
      evidencePath: '/evidence/multiplatform-strings.txt',
      remediation: 'Usar el mecanismo nativo: AndroidKeyStore. Nunca cifrar claves con contraseña hardcodeada.',
      timestamp: '2026-07-27T14:27:59.030440',
    ),
    Vulnerability(
      scenario: 'pinning',
      severity: 'critical',
      title: 'Backend no presenta certificado TLS válido',
      description: '[Errno -2] Name or service not known. URL malformada detectada.',
      evidencePath: '',
      remediation: 'Activar HTTPS en producción, configurar HSTS, deshabilitar HTTP plano.',
      timestamp: '2026-07-27T14:27:59.138254',
    ),
    Vulnerability(
      scenario: 'recovery_page',
      severity: 'high',
      title: 'Endpoint de hash responde sin auth (IDOR)',
      description: 'GET /api/hashes/{id} devolvió datos sin token válido.',
      evidencePath: '/evidence/recovery-idor.json',
      remediation: 'Validar sesión + ownership antes de servir datos de hash.',
      timestamp: '2026-07-27T14:27:59.291486',
    ),
  ];

  List<Vulnerability> get _filteredVulns {
    if (_filter == 'all') return _vulnerabilities;
    return _vulnerabilities.where((v) => v.severity == _filter).toList();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Hallazgos de Seguridad'),
        actions: [
          PopupMenuButton<String>(
            onSelected: (value) => setState(() => _filter = value),
            itemBuilder: (context) => [
              const PopupMenuItem(value: 'all', child: Text('Todos (24)')),
              const PopupMenuItem(value: 'critical', child: Text('Críticos (2)')),
              const PopupMenuItem(value: 'high', child: Text('Altos (13)')),
              const PopupMenuItem(value: 'medium', child: Text('Medios (3)')),
            ],
            icon: const Icon(Icons.filter_list),
          ),
        ],
      ),
      body: ListView.builder(
        padding: const EdgeInsets.all(16),
        itemCount: _filteredVulns.length,
        itemBuilder: (context, index) {
          final vuln = _filteredVulns[index];
          return Card(
            margin: const EdgeInsets.only(bottom: 16),
            child: ExpansionTile(
              leading: Container(
                width: 4,
                height: 60,
                color: Color(vuln.severityColor),
              ),
              title: Text(
                vuln.title,
                style: GoogleFonts.inter(fontWeight: FontWeight.bold, fontSize: 16),
              ),
              subtitle: Row(
                children: [
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                    decoration: BoxDecoration(
                      color: Color(vuln.severityColor).withOpacity(0.2),
                      borderRadius: BorderRadius.circular(4),
                    ),
                    child: Text(
                      vuln.severity.toUpperCase(),
                      style: TextStyle(color: Color(vuln.severityColor), fontWeight: FontWeight.bold, fontSize: 12),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Text(vuln.scenario, style: const TextStyle(color: Colors.grey)),
                ],
              ),
              children: [
                Padding(
                  padding: const EdgeInsets.all(16.0),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('Descripción:', style: GoogleFonts.inter(fontWeight: FontWeight.bold, color: Colors.white70)),
                      const SizedBox(height: 4),
                      Text(vuln.description, style: const TextStyle(color: Colors.white70)),
                      const SizedBox(height: 16),
                      Text('Remediación:', style: GoogleFonts.inter(fontWeight: FontWeight.bold, color: Colors.greenAccent)),
                      const SizedBox(height: 4),
                      Text(vuln.remediation, style: const TextStyle(color: Colors.white70)),
                      if (vuln.evidencePath.isNotEmpty) ...[
                        const SizedBox(height: 16),
                        Text('Evidencia:', style: GoogleFonts.inter(fontWeight: FontWeight.bold, color: Colors.blueAccent)),
                        const SizedBox(height: 4),
                        Text(vuln.evidencePath, style: const TextStyle(color: Colors.white54, fontSize: 12, fontFamily: 'monospace')),
                      ],
                    ],
                  ),
                ),
              ],
            ),
          );
        },
      ),
    );
  }
}