import 'package:flutter/material.dart';
import '../../../../core/theme/app_theme.dart';

class C2Screen extends StatefulWidget {
  const C2Screen({super.key});

  @override
  State<C2Screen> createState() => _C2ScreenState();
}

class _C2ScreenState extends State<C2Screen> with SingleTickerProviderStateMixin {
  late TabController _tabController;
  final List<Map<String, dynamic>> sessions = [
    {'id': 'sess_001', 'target': '192.168.1.50', 'implant': 'Meterpreter', 'status': 'active', 'user': 'NT AUTHORITY\\SYSTEM', 'last_seen': '2s ago'},
    {'id': 'sess_002', 'target': '10.0.0.15', 'implant': 'Cobalt Strike', 'status': 'active', 'user': 'CORP\\admin', 'last_seen': '45s ago'},
    {'id': 'sess_003', 'target': '172.16.0.8', 'implant': 'Sliver', 'status': 'sleeping', 'user': 'root', 'last_seen': '5m ago'},
  ];

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
        title: const Text('C2 Command & Control'),
        bottom: TabBar(
          controller: _tabController,
          indicatorColor: AppTheme.dangerRed,
          labelColor: AppTheme.dangerRed,
          unselectedLabelColor: const Color(0xFF6B7280),
          tabs: const [
            Tab(icon: Icon(Icons.terminal), text: 'Sessions'),
            Tab(icon: Icon(Icons.upload_file), text: 'Payloads'),
            Tab(icon: Icon(Icons.settings), text: 'Listeners'),
          ],
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: [
          _buildSessionsTab(),
          _buildPayloadsTab(),
          _buildListenersTab(),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        backgroundColor: AppTheme.dangerRed,
        icon: const Icon(Icons.add),
        label: const Text('New Session'),
        onPressed: () {},
      ),
    );
  }

  Widget _buildSessionsTab() {
    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: sessions.length,
      itemBuilder: (context, index) {
        final s = sessions[index];
        final isActive = s['status'] == 'active';
        return Card(
          margin: const EdgeInsets.only(bottom: 12),
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Container(
                      width: 10,
                      height: 10,
                      decoration: BoxDecoration(shape: BoxShape.circle, color: isActive ? AppTheme.successGreen : AppTheme.warningAmber, boxShadow: [BoxShadow(color: (isActive ? AppTheme.successGreen : AppTheme.warningAmber).withAlpha(100), blurRadius: 8)]),
                    ),
                    const SizedBox(width: 8),
                    Text(s['id'], style: const TextStyle(color: Colors.white, fontFamily: 'JetBrainsMono', fontSize: 13)),
                    const Spacer(),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                      decoration: BoxDecoration(color: (isActive ? AppTheme.successGreen : AppTheme.warningAmber).withAlpha(30), borderRadius: BorderRadius.circular(6)),
                      child: Text(s['status'].toUpperCase(), style: TextStyle(color: isActive ? AppTheme.successGreen : AppTheme.warningAmber, fontSize: 10, fontWeight: FontWeight.bold)),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                Text('Target: ${s['target']}', style: const TextStyle(color: Colors.white, fontSize: 14)),
                Text('Implant: ${s['implant']}', style: const TextStyle(color: Color(0xFFA1A1AA), fontSize: 13)),
                Text('User: ${s['user']}', style: const TextStyle(color: AppTheme.cyberCyan, fontSize: 13, fontFamily: 'JetBrainsMono')),
                const SizedBox(height: 12),
                Row(
                  children: [
                    Expanded(child: OutlinedButton.icon(icon: const Icon(Icons.terminal, size: 16), label: const Text('Shell'), onPressed: () {}, style: OutlinedButton.styleFrom(foregroundColor: AppTheme.terminalGreen))),
                    const SizedBox(width: 8),
                    Expanded(child: OutlinedButton.icon(icon: const Icon(Icons.folder_open, size: 16), label: const Text('Files'), onPressed: () {}, style: OutlinedButton.styleFrom(foregroundColor: AppTheme.infoBlue))),
                    const SizedBox(width: 8),
                    Expanded(child: OutlinedButton.icon(icon: const Icon(Icons.stop, size: 16), label: const Text('Kill'), onPressed: () {}, style: OutlinedButton.styleFrom(foregroundColor: AppTheme.dangerRed))),
                  ],
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  Widget _buildPayloadsTab() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.upload_file, size: 64, color: const Color(0xFF2A2A3A)),
          const SizedBox(height: 16),
          const Text('Payload Generator', style: TextStyle(color: Color(0xFF6B7280), fontSize: 18)),
          const SizedBox(height: 8),
          const Text('Genera implants para Windows, Linux, macOS, Android, iOS', style: TextStyle(color: Color(0xFF4B5563), fontSize: 13)),
        ],
      ),
    );
  }

  Widget _buildListenersTab() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.settings_input_antenna, size: 64, color: const Color(0xFF2A2A3A)),
          const SizedBox(height: 16),
          const Text('C2 Listeners', style: TextStyle(color: Color(0xFF6B7280), fontSize: 18)),
          const SizedBox(height: 8),
          const Text('Configura HTTP, HTTPS, DNS, SMB listeners', style: TextStyle(color: Color(0xFF4B5563), fontSize: 13)),
        ],
      ),
    );
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }
}
