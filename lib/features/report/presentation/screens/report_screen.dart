import 'package:flutter/material.dart';
import '../../../../core/theme/app_theme.dart';

class ReportScreen extends StatelessWidget {
  const ReportScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.darkTheme.scaffoldBackgroundColor,
      appBar: AppBar(title: const Text('Report Generator')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          _buildReportCard(
            'Executive Summary',
            'Reporte de alto nivel para C-Level. Gráficos, riesgo, recomendaciones.',
            Icons.business,
            const Color(0xFF8B5CF6),
          ),
          _buildReportCard(
            'Technical Report',
            'Detalle completo de vulnerabilidades, exploits, evidencias, PoCs.',
            Icons.code,
            AppTheme.infoBlue,
          ),
          _buildReportCard(
            'Compliance Report',
            'NIST CSF, ISO 27001, OWASP Top 10, PCI-DSS mapping.',
            Icons.verified,
            AppTheme.successGreen,
          ),
          _buildReportCard(
            'Remediation Roadmap',
            'Plan de acción priorizado por riesgo con timelines y owners.',
            Icons.map,
            AppTheme.warningAmber,
          ),
          const SizedBox(height: 24),
          Text('Formatos de Exportación', style: Theme.of(context).textTheme.headlineMedium?.copyWith(color: Colors.white)),
          const SizedBox(height: 16),
          Row(
            children: [
              Expanded(child: _buildFormatButton('PDF', Icons.picture_as_pdf, AppTheme.dangerRed)),
              const SizedBox(width: 12),
              Expanded(child: _buildFormatButton('DOCX', Icons.description, AppTheme.infoBlue)),
              const SizedBox(width: 12),
              Expanded(child: _buildFormatButton('XLSX', Icons.table_chart, AppTheme.successGreen)),
              const SizedBox(width: 12),
              Expanded(child: _buildFormatButton('HTML', Icons.web, AppTheme.cyberCyan)),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildReportCard(String title, String desc, IconData icon, Color color) {
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
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
            Checkbox(value: true, onChanged: (v) {}, activeColor: color),
          ],
        ),
      ),
    );
  }

  Widget _buildFormatButton(String label, IconData icon, Color color) {
    return ElevatedButton.icon(
      icon: Icon(icon, size: 18),
      label: Text(label),
      style: ElevatedButton.styleFrom(
        backgroundColor: color.withAlpha(30),
        foregroundColor: color,
        padding: const EdgeInsets.symmetric(vertical: 12),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      ),
      onPressed: () {},
    );
  }
}
