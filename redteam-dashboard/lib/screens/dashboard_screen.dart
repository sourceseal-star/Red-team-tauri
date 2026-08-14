import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:google_fonts/google_fonts.dart';
import '../config/app_config.dart';
import '../services/api_service.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  bool _isLoading = true;
  Map<String, dynamic> _healthData = {};

  @override
  void initState() {
    super.initState();
    _checkHealth();
  }

  Future<void> _checkHealth() async {
    setState(() => _isLoading = true);
    final apiService = Provider.of<ApiService>(context, listen: false);
    final data = await apiService.getHealth();
    setState(() {
      _healthData = data;
      _isLoading = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    final config = Provider.of<AppConfig>(context);
    
    return Scaffold(
      appBar: AppBar(
        title: const Text('SourceSeal Enterprise'),
        actions: [
          IconButton(icon: const Icon(Icons.refresh), onPressed: _checkHealth),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: _checkHealth,
              child: SingleChildScrollView(
                physics: const AlwaysScrollableScrollPhysics(),
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // Status Banner
                    Container(
                      width: double.infinity,
                      padding: const EdgeInsets.all(20),
                      decoration: BoxDecoration(
                        gradient: const LinearGradient(
                          colors: [Color(0xFF1A1F3A), Color(0xFF2A305A)],
                          begin: Alignment.topLeft,
                          end: Alignment.bottomRight,
                        ),
                        borderRadius: BorderRadius.circular(16),
                        border: Border.all(color: Colors.blueAccent.withOpacity(0.3)),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              Icon(
                                _healthData['status'] == 'ok' || _healthData['status'] == 'healthy' 
                                    ? Icons.check_circle 
                                    : Icons.warning,
                                color: _healthData['status'] == 'ok' || _healthData['status'] == 'healthy' ? Colors.greenAccent : Colors.orange,
                                size: 32,
                              ),
                              const SizedBox(width: 12),
                              Text(
                                'Backend: ${_healthData['status'] ?? 'Desconectado'}',
                                style: GoogleFonts.inter(fontSize: 22, fontWeight: FontWeight.bold),
                              ),
                            ],
                          ),
                          const SizedBox(height: 8),
                          Text(
                            config.backendUrl,
                            style: const TextStyle(color: Colors.white60, fontFamily: 'monospace', fontSize: 12),
                          ),
                        ],
                      ),
                    ),

                    const SizedBox(height: 24),
                    Text('Módulos Red Team', style: GoogleFonts.inter(fontSize: 18, fontWeight: FontWeight.bold)),
                    const SizedBox(height: 12),

                    // Grid de Módulos
                    GridView.count(
                      shrinkWrap: true,
                      physics: const NeverScrollableScrollPhysics(),
                      crossAxisCount: 2,
                      mainAxisSpacing: 12,
                      crossAxisSpacing: 12,
                      childAspectRatio: 1.2,
                      children: [
                        _buildModuleCard('XDR', 'MITRE ATT&CK', Icons.analytics, Colors.purple),
                        _buildModuleCard('RASP', 'App Protection', Icons.security, Colors.blue),
                        _buildModuleCard('NDR', 'Network Detect', Icons.wifi_tethering, Colors.teal),
                        _buildModuleCard('SOAR', 'Automation', Icons.auto_awesome, Colors.orange),
                        _buildModuleCard('TIP', 'Threat Intel', Icons.psychology, Colors.red),
                        _buildModuleCard('Deception', 'Honeytokens', Icons.filter_vintage, Colors.green),
                      ],
                    ),

                    const SizedBox(height: 24),
                    ElevatedButton.icon(
                      onPressed: () async {
                        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Ejecutando playbook de contención...')));
                        final apiService = Provider.of<ApiService>(context, listen: false);
                        final result = await apiService.executeSoarPlaybook('ransomware_containment');
                        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Resultado: ${result['status']}')));
                      },
                      icon: const Icon(Icons.play_arrow),
                      label: const Text('Ejecutar Playbook SOAR: Contención'),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: Colors.redAccent,
                        minimumSize: const Size(double.infinity, 56),
                      ),
                    ),
                  ],
                ),
              ),
            ),
    );
  }

  Widget _buildModuleCard(String title, String subtitle, IconData icon, Color color) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(icon, size: 36, color: color),
            const SizedBox(height: 8),
            Text(title, style: GoogleFonts.inter(fontWeight: FontWeight.bold, fontSize: 16)),
            const SizedBox(height: 4),
            Text(subtitle, style: const TextStyle(fontSize: 12, color: Colors.white60), textAlign: TextAlign.center),
          ],
        ),
      ),
    );
  }
}