import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:flutter_animate/flutter_animate.dart';

class AttacksScreen extends StatefulWidget {
  const AttacksScreen({super.key});

  @override
  State<AttacksScreen> createState() => _AttacksScreenState();
}

class _AttacksScreenState extends State<AttacksScreen> {
  String _selectedCategory = 'all';

  final List<Map<String, dynamic>> _attackModules = [
    {
      'name': 'XDR Correlator',
      'category': 'xdr',
      'description': 'Correlaciona 20+ técnicas MITRE ATT&CK con detección en tiempo real',
      'icon': Icons.analytics,
      'color': Colors.purple,
      'techniques': 20,
      'status': 'active',
    },
    {
      'name': 'Kill Chain Analyzer',
      'category': 'xdr',
      'description': '7 fases Lockheed Martin con mapping MITRE y predicción de fases siguientes',
      'icon': Icons.link,
      'color': Colors.deepPurple,
      'techniques': 7,
      'status': 'active',
    },
    {
      'name': 'Attack Surface Mapper',
      'category': 'xdr',
      'description': 'Mapea superficie de ataque con risk scoring y comparación histórica',
      'icon': Icons.radar,
      'color': Colors.indigo,
      'techniques': 15,
      'status': 'active',
    },
    {
      'name': 'RASP Agent',
      'category': 'rasp',
      'description': 'Runtime self-protection: root, Frida, Xposed, debugger, emulador, Play Integrity',
      'icon': Icons.security,
      'color': Colors.blue,
      'techniques': 8,
      'status': 'active',
    },
    {
      'name': 'Android RASP (Kotlin)',
      'category': 'rasp',
      'description': 'RASP nativo Android: root detection, Frida, Xposed, debug, emulador',
      'icon': Icons.android,
      'color': Colors.lightBlue,
      'techniques': 6,
      'status': 'active',
    },
    {
      'name': 'iOS RASP (Swift)',
      'category': 'rasp',
      'description': 'RASP nativo iOS: jailbreak, Frida, debugger, emulador detection',
      'icon': Icons.phone_iphone,
      'color': Colors.cyan,
      'techniques': 5,
      'status': 'active',
    },
    {
      'name': 'NDR Engine',
      'category': 'ndr',
      'description': 'Network detection: C2 beaconing, DNS tunneling, ICMP exfiltration, DGA',
      'icon': Icons.wifi_tethering,
      'color': Colors.teal,
      'techniques': 12,
      'status': 'active',
    },
    {
      'name': 'ML Network Detector',
      'category': 'ndr',
      'description': 'IsolationForest + heurísticas para detección de anomalías de red',
      'icon': Icons.memory,
      'color': Colors.tealAccent,
      'techniques': 10,
      'status': 'active',
    },
    {
      'name': 'Deception Mesh',
      'category': 'deception',
      'description': 'Canary tokens, decoy endpoints, synthetic sessions para defensa activa',
      'icon': Icons.filter_vintage,
      'color': Colors.green,
      'techniques': 9,
      'status': 'active',
    },
    {
      'name': 'Honeytoken Rotation',
      'category': 'deception',
      'description': 'JWT, AWS keys, DB credentials, GitHub tokens con rotación automática',
      'icon': Icons.vpn_key,
      'color': Colors.lightGreen,
      'techniques': 4,
      'status': 'active',
    },
    {
      'name': 'STIX/TAXII TIP',
      'category': 'tip',
      'description': 'Threat Intelligence Platform con 50 técnicas MITRE ATT&CK + TAXII 2.1',
      'icon': Icons.psychology,
      'color': Colors.red,
      'techniques': 50,
      'status': 'active',
    },
    {
      'name': 'JNI Bridge (Native)',
      'category': 'native',
      'description': 'C bridge: SHA-256 + ptrace anti-debug + detección Frida por puertos/libs',
      'icon': Icons.code,
      'color': Colors.orange,
      'techniques': 3,
      'status': 'active',
    },
  ];

  List<Map<String, dynamic>> get _filteredAttacks {
    if (_selectedCategory == 'all') return _attackModules;
    return _attackModules.where((a) => a['category'] == _selectedCategory).toList();
  }

  final List<Map<String, dynamic>> _categories = [
    {'key': 'all', 'label': 'Todos'},
    {'key': 'xdr', 'label': 'XDR'},
    {'key': 'rasp', 'label': 'RASP'},
    {'key': 'ndr', 'label': 'NDR'},
    {'key': 'deception', 'label': 'Deception'},
    {'key': 'tip', 'label': 'TIP'},
    {'key': 'native', 'label': 'Native'},
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Módulos de Ataque'),
        actions: [
          IconButton(
            icon: const Icon(Icons.flash_on),
            onPressed: () {
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(
                  content: Text('Lanzando scan completo de todos los módulos...'),
                  backgroundColor: Colors.redAccent,
                ),
              );
            },
          ),
        ],
      ),
      body: Column(
        children: [
          // Category filter chips
          Container(
            height: 56,
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            child: ListView.builder(
              scrollDirection: Axis.horizontal,
              itemCount: _categories.length,
              itemBuilder: (context, index) {
                final cat = _categories[index];
                final isSelected = _selectedCategory == cat['key'];
                return Padding(
                  padding: const EdgeInsets.only(right: 8),
                  child: FilterChip(
                    label: Text(cat['label']),
                    selected: isSelected,
                    onSelected: (selected) {
                      if (selected) {
                        setState(() => _selectedCategory = cat['key']);
                      }
                    },
                    backgroundColor: const Color(0xFF1A1F3A),
                    selectedColor: Colors.blueAccent.withOpacity(0.3),
                    labelStyle: TextStyle(
                      color: isSelected ? Colors.blueAccent : Colors.white60,
                      fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
                    ),
                  ),
                );
              },
            ),
          ),
          // Attack modules grid
          Expanded(
            child: GridView.builder(
              padding: const EdgeInsets.all(16),
              gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                crossAxisCount: 2,
                mainAxisSpacing: 12,
                crossAxisSpacing: 12,
                childAspectRatio: 0.85,
              ),
              itemCount: _filteredAttacks.length,
              itemBuilder: (context, index) {
                final module = _filteredAttacks[index];
                return Card(
                  child: InkWell(
                    onTap: () {
                      ScaffoldMessenger.of(context).showSnackBar(
                        SnackBar(
                          content: Text('Ejecutando ${module['name']}...'),
                          backgroundColor: module['color'] as Color,
                        ),
                      );
                    },
                    borderRadius: BorderRadius.circular(12),
                    child: Padding(
                      padding: const EdgeInsets.all(16),
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: [
                              Icon(
                                module['icon'] as IconData,
                                size: 32,
                                color: module['color'] as Color,
                              ),
                              Container(
                                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                                decoration: BoxDecoration(
                                  color: (module['color'] as Color).withOpacity(0.2),
                                  borderRadius: BorderRadius.circular(12),
                                ),
                                child: Text(
                                  '${module['techniques']} T',
                                  style: TextStyle(
                                    color: module['color'] as Color,
                                    fontSize: 11,
                                    fontWeight: FontWeight.bold,
                                  ),
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 12),
                          Text(
                            module['name'],
                            style: GoogleFonts.inter(
                              fontWeight: FontWeight.bold,
                              fontSize: 14,
                            ),
                            maxLines: 2,
                          ),
                          const SizedBox(height: 6),
                          Text(
                            module['description'],
                            style: const TextStyle(
                              fontSize: 11,
                              color: Colors.white54,
                            ),
                            maxLines: 3,
                            overflow: TextOverflow.ellipsis,
                          ),
                          const Spacer(),
                          Row(
                            children: [
                              Container(
                                width: 8,
                                height: 8,
                                decoration: BoxDecoration(
                                  color: Colors.greenAccent,
                                  borderRadius: BorderRadius.circular(4),
                                ),
                              ),
                              const SizedBox(width: 6),
                              Text(
                                (module['status'] as String).toUpperCase(),
                                style: const TextStyle(
                                  fontSize: 10,
                                  color: Colors.greenAccent,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                            ],
                          ),
                        ],
                      ),
                    ),
                  ),
                ).animate().fadeIn(delay: Duration(milliseconds: index * 50));
              },
            ),
          ),
        ],
      ),
    );
  }
}
