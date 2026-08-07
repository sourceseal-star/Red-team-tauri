import 'package:flutter/material.dart';
import 'package:graphview/GraphView.dart';
import '../../../../core/theme/app_theme.dart';

class TopologyGraph extends StatelessWidget {
  final List<Map<String, dynamic>> hosts;
  final List<Map<String, dynamic>> connections;
  final Function(Map<String, dynamic>) onNodeTap;

  const TopologyGraph({
    super.key,
    required this.hosts,
    required this.connections,
    required this.onNodeTap,
  });

  @override
  Widget build(BuildContext context) {
    final graph = Graph();
    final nodeMap = <String, Node>{};

    // Crear nodos
    for (final host in hosts) {
      final node = Node.Id(host['id']);
      nodeMap[host['id']] = node;
      graph.addNode(node);
    }

    // Crear edges
    for (final conn in connections) {
      final from = nodeMap[conn['from']];
      final to = nodeMap[conn['to']];
      if (from != null && to != null) {
        graph.addEdge(from, to);
      }
    }

    final builder = FruchtermanReingoldAlgorithm()
      ..iterations = 1000
      ..showGrid = false
      ..repulsionRate = 10.0
      ..attractionRate = 0.05;

    return InteractiveViewer(
      constrained: false,
      boundaryMargin: const EdgeInsets.all(100),
      minScale: 0.01,
      maxScale: 5.0,
      child: GraphView(
        graph: graph,
        algorithm: builder,
        paint: Paint()
          ..color = const Color(0xFF2A2A3A)
          ..strokeWidth = 1.5
          ..style = PaintingStyle.stroke,
        builder: (Node node) {
          final hostId = node.key!.value as String;
          final host = hosts.firstWhere((h) => h['id'] == hostId);
          return _buildNodeWidget(host);
        },
      ),
    );
  }

  Widget _buildNodeWidget(Map<String, dynamic> host) {
    final color = _getTypeColor(host['type']);
    final hasVulns = (host['vulnerabilities']?.length ?? 0) > 0;
    final isCritical = hasVulns && host['type'] == 'server';

    return GestureDetector(
      onTap: () => onNodeTap(host),
      child: Container(
        width: 100,
        padding: const EdgeInsets.all(8),
        decoration: BoxDecoration(
          color: const Color(0xFF141419),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
            color: isCritical ? AppTheme.dangerRed : color.withAlpha(100),
            width: isCritical ? 2 : 1,
          ),
          boxShadow: [
            BoxShadow(
              color: isCritical ? AppTheme.dangerRed.withAlpha(60) : color.withAlpha(30),
              blurRadius: isCritical ? 12 : 6,
              spreadRadius: isCritical ? 2 : 0,
            ),
          ],
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Stack(
              children: [
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: color.withAlpha(20),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Icon(_getTypeIcon(host['type']), color: color, size: 24),
                ),
                if (hasVulns)
                  Positioned(
                    right: -4,
                    top: -4,
                    child: Container(
                      padding: const EdgeInsets.all(2),
                      decoration: const BoxDecoration(color: Color(0xFF141419), shape: BoxShape.circle),
                      child: Icon(Icons.warning, color: AppTheme.dangerRed, size: 12),
                    ),
                  ),
              ],
            ),
            const SizedBox(height: 6),
            Text(
              host['hostname'],
              style: const TextStyle(color: Colors.white, fontSize: 10, fontWeight: FontWeight.w600),
              textAlign: TextAlign.center,
              overflow: TextOverflow.ellipsis,
            ),
            const SizedBox(height: 2),
            Text(
              host['ip'],
              style: const TextStyle(color: Color(0xFF6B7280), fontSize: 8, fontFamily: 'JetBrainsMono'),
              textAlign: TextAlign.center,
            ),
            if (hasVulns) ...[
              const SizedBox(height: 4),
              Text(
                '${host['vulnerabilities'].length} CVEs',
                style: TextStyle(color: AppTheme.dangerRed, fontSize: 8, fontWeight: FontWeight.bold),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Color _getTypeColor(String type) {
    switch (type) {
      case 'router': return const Color(0xFFEF4444);
      case 'server': return const Color(0xFF3B82F6);
      case 'workstation': return const Color(0xFF10B981);
      case 'camera': return const Color(0xFFF59E0B);
      case 'iot': return const Color(0xFF06B6D4);
      case 'printer': return const Color(0xFF8B5CF6);
      default: return const Color(0xFF6B7280);
    }
  }

  IconData _getTypeIcon(String type) {
    switch (type) {
      case 'router': return Icons.router;
      case 'server': return Icons.dns;
      case 'workstation': return Icons.computer;
      case 'camera': return Icons.videocam;
      case 'iot': return Icons.memory;
      case 'printer': return Icons.print;
      default: return Icons.device_unknown;
    }
  }
}
