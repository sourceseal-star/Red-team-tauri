import 'package:go_router/go_router.dart';
import 'package:flutter/material.dart';
import '../../features/dashboard/presentation/screens/dashboard_screen.dart';
import '../../features/scanner/presentation/screens/scanner_screen.dart';
import '../../features/scanner/presentation/screens/camera_scan_screen.dart';
import '../../features/scanner/presentation/screens/radio_scan_screen.dart';
import '../../features/scanner/presentation/screens/iot_scan_screen.dart';
import '../../features/wifi/presentation/screens/wifi_scan_screen.dart';
import '../../features/topology/presentation/screens/topology_screen.dart';
import '../../features/recon/presentation/screens/recon_screen.dart';
import '../../features/c2/presentation/screens/c2_screen.dart';
import '../../features/report/presentation/screens/report_screen.dart';

class AppRouter {
  static final router = GoRouter(
    initialLocation: '/',
    routes: [
      GoRoute(path: '/', builder: (context, state) => const DashboardScreen()),
      GoRoute(path: '/scanner', builder: (context, state) => const ScannerScreen()),
      GoRoute(path: '/scanner/cameras', builder: (context, state) => const CameraScanScreen()),
      GoRoute(path: '/scanner/radio', builder: (context, state) => const RadioScanScreen()),
      GoRoute(path: '/scanner/iot', builder: (context, state) => const IoTScanScreen()),
      GoRoute(path: '/wifi', builder: (context, state) => const WifiScanScreen()),
      GoRoute(path: '/topology', builder: (context, state) => const TopologyScreen()),
      GoRoute(path: '/recon', builder: (context, state) => const ReconScreen()),
      GoRoute(path: '/c2', builder: (context, state) => const C2Screen()),
      GoRoute(path: '/reports', builder: (context, state) => const ReportScreen()),
    ],
  );
}
