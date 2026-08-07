import 'package:flutter/material.dart';

class RecentActivity extends StatelessWidget {
  const RecentActivity({super.key});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFF141419),
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        children: [
          _buildActivityItem(
            'Port Scan completado',
            '192.168.1.0/24 - 42 puertos abiertos',
            '2 min ago',
            Icons.check_circle,
            const Color(0xFF10B981),
          ),
          const Divider(color: Color(0xFF2A2A3A), height: 24),
          _buildActivityItem(
            'Cámara detectada',
            'Hikvision DS-2CD2143G0-I en 192.168.1.105',
            '15 min ago',
            Icons.videocam,
            const Color(0xFFF59E0B),
          ),
          const Divider(color: Color(0xFF2A2A3A), height: 24),
          _buildActivityItem(
            'IoT Device found',
            'MQTT Broker en 192.168.1.200:1883',
            '1h ago',
            Icons.memory,
            const Color(0xFF3B82F6),
          ),
        ],
      ),
    );
  }

  Widget _buildActivityItem(String title, String desc, String time, IconData icon, Color color) {
    return Row(
      children: [
        Container(
          padding: const EdgeInsets.all(8),
          decoration: BoxDecoration(color: color.withAlpha(20), borderRadius: BorderRadius.circular(8)),
          child: Icon(icon, color: color, size: 18),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(title, style: const TextStyle(color: Colors.white, fontSize: 14, fontWeight: FontWeight.w500)),
              const SizedBox(height: 2),
              Text(desc, style: const TextStyle(color: Color(0xFF6B7280), fontSize: 12)),
            ],
          ),
        ),
        Text(time, style: const TextStyle(color: Color(0xFF4B5563), fontSize: 11)),
      ],
    );
  }
}
