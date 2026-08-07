import 'package:flutter/material.dart';
import 'package:fl_chart/fl_chart.dart';
import '../../../../core/theme/app_theme.dart';

class WifiSignalChart extends StatelessWidget {
  final List<int> signalHistory;

  const WifiSignalChart({super.key, required this.signalHistory});

  @override
  Widget build(BuildContext context) {
    if (signalHistory.isEmpty) return const SizedBox.shrink();

    final spots = signalHistory.asMap().entries.map((e) {
      return FlSpot(e.key.toDouble(), (e.value + 100).toDouble());
    }).toList();

    return Container(
      height: 150,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: const Color(0xFF1A1A24),
        borderRadius: BorderRadius.circular(12),
      ),
      child: LineChart(
        LineChartData(
          gridData: FlGridData(
            show: true,
            drawVerticalLine: false,
            horizontalInterval: 20,
            getDrawingHorizontalLine: (value) => FlLine(
              color: const Color(0xFF2A2A3A),
              strokeWidth: 0.5,
            ),
          ),
          titlesData: FlTitlesData(
            leftTitles: AxisTitles(
              sideTitles: SideTitles(
                showTitles: true,
                reservedSize: 30,
                getTitlesWidget: (value, meta) => Text(
                  '${(value - 100).toInt()}',
                  style: const TextStyle(color: Color(0xFF6B7280), fontSize: 9),
                ),
              ),
            ),
            bottomTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
            topTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
            rightTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
          ),
          borderData: FlBorderData(show: false),
          minY: 0,
          maxY: 80,
          lineBarsData: [
            LineChartBarData(
              spots: spots,
              isCurved: true,
              color: AppTheme.successGreen,
              barWidth: 2,
              isStrokeCapRound: true,
              dotData: const FlDotData(show: false),
              belowBarData: BarAreaData(
                show: true,
                color: AppTheme.successGreen.withAlpha(20),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
