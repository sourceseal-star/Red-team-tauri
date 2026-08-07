import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../../../core/theme/app_theme.dart';
import '../widgets/dashboard_card.dart';
import '../widgets/stats_row.dart';
import '../widgets/recent_activity.dart';

class DashboardScreen extends StatelessWidget {
  const DashboardScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.darkTheme.scaffoldBackgroundColor,
      body: CustomScrollView(
        slivers: [
          SliverAppBar(
            expandedHeight: 140,
            floating: false,
            pinned: true,
            flexibleSpace: FlexibleSpaceBar(
              title: const Text('SourceSeal Console', style: TextStyle(fontWeight: FontWeight.bold)),
              background: Container(
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                    colors: [
                      const Color(0xFF0A0A0F),
                      const Color(0xFF1A0A0F),
                      const Color(0xFF0A0A1F),
                    ],
                  ),
                ),
                child: Stack(
                  children: [
                    Positioned(
                      right: -50,
                      top: -30,
                      child: Container(
                        width: 200,
                        height: 200,
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          color: AppTheme.dangerRed.withAlpha(20),
                        ),
                      ),
                    ),
                    Positioned(
                      left: -30,
                      bottom: 20,
                      child: Container(
                        width: 120,
                        height: 120,
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          color: AppTheme.cyberCyan.withAlpha(15),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
          SliverToBoxAdapter(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const StatsRow(),
                  const SizedBox(height: 24),
                  Text(
                    'Módulos de Operación',
                    style: Theme.of(context).textTheme.headlineMedium?.copyWith(color: Colors.white),
                  ),
                  const SizedBox(height: 16),
                  GridView.count(
                    shrinkWrap: true,
                    physics: const NeverScrollableScrollPhysics(),
                    crossAxisCount: 2,
                    mainAxisSpacing: 12,
                    crossAxisSpacing: 12,
                    childAspectRatio: 1.1,
                    children: [
                      DashboardCard(
                        title: 'Port Scanner',
                        subtitle: 'TCP/UDP/Service',
                        icon: Icons.network_check,
                        color: AppTheme.dangerRed,
                        onTap: () => context.push('/scanner'),
                      ),
                      DashboardCard(
                        title: 'Cámaras IP',
                        subtitle: 'Hikvision, Dahua, Axis',
                        icon: Icons.videocam,
                        color: AppTheme.warningAmber,
                        onTap: () => context.push('/scanner/cameras'),
                      ),
                      DashboardCard(
                        title: 'Radio/SDR',
                        subtitle: 'FM/AM/Digital Scan',
                        icon: Icons.radio,
                        color: AppTheme.successGreen,
                        onTap: () => context.push('/scanner/radio'),
                      ),
                      DashboardCard(
                        title: 'IoT/ICS',
                        subtitle: 'MQTT, Modbus, BLE',
                        icon: Icons.memory,
                        color: AppTheme.infoBlue,
                        onTap: () => context.push('/scanner/iot'),
                      ),
                      DashboardCard(
                        title: 'WiFi Scanner',
                        subtitle: 'APs, Security, Audit',
                        icon: Icons.wifi,
                        color: const Color(0xFF8B5CF6),
                        onTap: () => context.push('/wifi'),
                      ),
                      DashboardCard(
                        title: 'Topology Map',
                        subtitle: 'Network Graph, Hosts',
                        icon: Icons.device_hub,
                        color: AppTheme.cyberCyan,
                        onTap: () => context.push('/topology'),
                      ),
                      DashboardCard(
                        title: 'OSINT/Recon',
                        subtitle: 'Shodan, WHOIS, DNS',
                        icon: Icons.search,
                        color: const Color(0xFFEC4899),
                        onTap: () => context.push('/recon'),
                      ),
                      DashboardCard(
                        title: 'C2 Control',
                        subtitle: 'Implants & Beacons',
                        icon: Icons.terminal,
                        color: const Color(0xFFF97316),
                        onTap: () => context.push('/c2'),
                      ),
                      DashboardCard(
                        title: 'Reportes',
                        subtitle: 'PDF, DOCX, Executive',
                        icon: Icons.assessment,
                        color: const Color(0xFF14B8A6),
                        onTap: () => context.push('/reports'),
                      ),
                      DashboardCard(
                        title: 'Exploits',
                        subtitle: 'CVE Database & Run',
                        icon: Icons.bug_report,
                        color: AppTheme.dangerRed,
                        onTap: () => _showExploitSheet(context),
                      ),
                    ],
                  ),
                  const SizedBox(height: 24),
                  Text(
                    'Actividad Reciente',
                    style: Theme.of(context).textTheme.headlineMedium?.copyWith(color: Colors.white),
                  ),
                  const SizedBox(height: 12),
                  const RecentActivity(),
                  const SizedBox(height: 32),
                ],
              ),
            ),
          ),
        ],
      ),
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: 0,
        backgroundColor: const Color(0xFF0A0A0F),
        selectedItemColor: AppTheme.dangerRed,
        unselectedItemColor: const Color(0xFF6B7280),
        type: BottomNavigationBarType.fixed,
        items: const [
          BottomNavigationBarItem(icon: Icon(Icons.dashboard), label: 'Dashboard'),
          BottomNavigationBarItem(icon: Icon(Icons.scanner), label: 'Scan'),
          BottomNavigationBarItem(icon: Icon(Icons.terminal), label: 'C2'),
          BottomNavigationBarItem(icon: Icon(Icons.settings), label: 'Config'),
        ],
        onTap: (index) {
          if (index == 1) context.push('/scanner');
          if (index == 2) context.push('/c2');
        },
      ),
    );
  }

  void _showExploitSheet(BuildContext context) {
    showModalBottomSheet(
      context: context,
      backgroundColor: const Color(0xFF141419),
      shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(20))),
      builder: (context) => Container(
        padding: const EdgeInsets.all(20),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Exploit Framework', style: Theme.of(context).textTheme.headlineMedium?.copyWith(color: Colors.white)),
            const SizedBox(height: 16),
            ListTile(
              leading: const Icon(Icons.bug_report, color: AppTheme.dangerRed),
              title: const Text('CVE-2021-36260 - Hikvision RCE', style: TextStyle(color: Colors.white)),
              subtitle: const Text('Cámara IP - RCE Remoto', style: TextStyle(color: Color(0xFF6B7280))),
              trailing: const Icon(Icons.play_arrow, color: AppTheme.successGreen),
              onTap: () => Navigator.pop(context),
            ),
            ListTile(
              leading: const Icon(Icons.bug_report, color: AppTheme.warningAmber),
              title: const Text('CVE-2021-33044 - Dahua Auth Bypass', style: TextStyle(color: Colors.white)),
              subtitle: const Text('Cámara IP - Bypass Autenticación', style: TextStyle(color: Color(0xFF6B7280))),
              trailing: const Icon(Icons.play_arrow, color: AppTheme.successGreen),
              onTap: () => Navigator.pop(context),
            ),
            ListTile(
              leading: const Icon(Icons.bug_report, color: AppTheme.infoBlue),
              title: const Text('MS17-010 - EternalBlue', style: TextStyle(color: Colors.white)),
              subtitle: const Text('Windows - SMB RCE', style: TextStyle(color: Color(0xFF6B7280))),
              trailing: const Icon(Icons.play_arrow, color: AppTheme.successGreen),
              onTap: () => Navigator.pop(context),
            ),
          ],
        ),
      ),
    );
  }
}
