import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:google_fonts/google_fonts.dart';
import 'config/app_config.dart';
import 'services/secure_storage_service.dart';
import 'services/api_service.dart';
import 'screens/dashboard_screen.dart';
import 'screens/editor_screen.dart';
import 'screens/terminal_screen.dart';
import 'screens/vulnerabilities_screen.dart';
import 'screens/attacks_screen.dart';
import 'screens/logs_screen.dart';
import 'screens/config_screen.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  
  // Initialize secure storage
  final storage = SecureStorageService();
  await storage.init();
  
  // Load config
  final config = await AppConfig.load(storage);
  
  runApp(SourceSealApp(config: config, storage: storage));
}

class SourceSealApp extends StatelessWidget {
  final AppConfig config;
  final SecureStorageService storage;

  const SourceSealApp({
    super.key,
    required this.config,
    required this.storage,
  });

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => config),
        Provider<SecureStorageService>.value(value: storage),
        Provider<ApiService>(
          create: (_) => ApiService(config, storage),
        ),
      ],
      child: MaterialApp(
        title: 'SourceSeal Red Team',
        debugShowCheckedModeBanner: false,
        theme: ThemeData(
          useMaterial3: true,
          brightness: Brightness.dark,
          colorScheme: ColorScheme.dark(
            primary: Colors.blueAccent,
            secondary: Colors.tealAccent,
            surface: const Color(0xFF0A0E27),
            background: const Color(0xFF050816),
          ),
          scaffoldBackgroundColor: const Color(0xFF050816),
          appBarTheme: AppBarTheme(
            backgroundColor: const Color(0xFF1A1F3A),
            elevation: 0,
            titleTextStyle: GoogleFonts.inter(
              fontSize: 20,
              fontWeight: FontWeight.bold,
              color: Colors.white,
            ),
          ),
          textTheme: GoogleFonts.interTextTheme(
            const TextTheme(
              bodyLarge: TextStyle(color: Colors.white70),
              bodyMedium: TextStyle(color: Colors.white60),
            ),
          ),
          cardTheme: CardTheme(
            color: const Color(0xFF1A1F3A),
            elevation: 4,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12),
            ),
          ),
          elevatedButtonTheme: ElevatedButtonThemeData(
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.blueAccent,
              foregroundColor: Colors.white,
              elevation: 2,
              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(8),
              ),
            ),
          ),
        ),
        home: const MainNavigation(),
      ),
    );
  }
}

class MainNavigation extends StatefulWidget {
  const MainNavigation({super.key});

  @override
  State<MainNavigation> createState() => _MainNavigationState();
}

class _MainNavigationState extends State<MainNavigation> {
  int _selectedIndex = 0;

  final List<Widget> _screens = const [
    DashboardScreen(),
    VulnerabilitiesScreen(),
    AttacksScreen(),
    EditorScreen(),
    TerminalScreen(),
    LogsScreen(),
    ConfigScreen(),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: IndexedStack(
        index: _selectedIndex,
        children: _screens,
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _selectedIndex,
        onDestinationSelected: (index) => setState(() => _selectedIndex = index),
        backgroundColor: const Color(0xFF1A1F3A),
        indicatorColor: Colors.blueAccent.withOpacity(0.3),
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.dashboard_outlined),
            selectedIcon: Icon(Icons.dashboard, color: Colors.blueAccent),
            label: 'Dashboard',
          ),
          NavigationDestination(
            icon: Icon(Icons.bug_report_outlined),
            selectedIcon: Icon(Icons.bug_report, color: Colors.blueAccent),
            label: 'Vulns',
          ),
          NavigationDestination(
            icon: Icon(Icons.shield_outlined),
            selectedIcon: Icon(Icons.shield, color: Colors.blueAccent),
            label: 'Attacks',
          ),
          NavigationDestination(
            icon: Icon(Icons.code_outlined),
            selectedIcon: Icon(Icons.code, color: Colors.blueAccent),
            label: 'Editor',
          ),
          NavigationDestination(
            icon: Icon(Icons.terminal_outlined),
            selectedIcon: Icon(Icons.terminal, color: Colors.blueAccent),
            label: 'Terminal',
          ),
          NavigationDestination(
            icon: Icon(Icons.list_outlined),
            selectedIcon: Icon(Icons.list, color: Colors.blueAccent),
            label: 'Logs',
          ),
          NavigationDestination(
            icon: Icon(Icons.settings_outlined),
            selectedIcon: Icon(Icons.settings, color: Colors.blueAccent),
            label: 'Config',
          ),
        ],
      ),
    );
  }
}