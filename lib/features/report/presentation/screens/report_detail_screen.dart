import 'package:flutter/material.dart';

class ReportDetailScreen extends StatelessWidget {
  final String reportId;
  const ReportDetailScreen({super.key, required this.reportId});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('Report $reportId')),
      body: const Center(child: Text('Report Detail')),
    );
  }
}
