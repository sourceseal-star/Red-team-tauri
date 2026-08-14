import 'package:flutter/material.dart';

class AppTheme {
  static ThemeData get darkTheme {
    return ThemeData.dark(useMaterial3: true).copyWith(
      scaffoldBackgroundColor: const Color(0xFF0A0A0F),
      cardColor: const Color(0xFF141419),
      dividerColor: const Color(0xFF1E1E28),
      colorScheme: const ColorScheme.dark(
        primary: Color(0xFFEF4444),
        secondary: Color(0xFF06B6D4),
        surface: Color(0xFF141419),
        error: Color(0xFFEF4444),
        onPrimary: Colors.white,
        onSecondary: Colors.white,
        onSurface: Color(0xFFE2E2E8),
        onError: Colors.white,
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: Color(0xFF0A0A0F),
        elevation: 0,
        centerTitle: true,
        titleTextStyle: TextStyle(fontSize: 18, fontWeight: FontWeight.w600, color: Color(0xFFE2E2E8)),
      ),
      cardTheme: CardTheme(
        color: const Color(0xFF141419),
        elevation: 0,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: const Color(0xFF1A1A24),
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: BorderSide.none),
        enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: const BorderSide(color: Color(0xFF2A2A3A))),
        focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: const BorderSide(color: Color(0xFFEF4444), width: 1.5)),
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      ),
      bottomNavigationBarTheme: const BottomNavigationBarThemeData(
        backgroundColor: Color(0xFF0A0A0F),
        selectedItemColor: Color(0xFFEF4444),
        unselectedItemColor: Color(0xFF6B7280),
        type: BottomNavigationBarType.fixed,
        elevation: 8,
      ),
      textTheme: const TextTheme(
        displayLarge: TextStyle(fontSize: 32, fontWeight: FontWeight.bold, letterSpacing: -1, color: Color(0xFFE2E2E8)),
        displayMedium: TextStyle(fontSize: 24, fontWeight: FontWeight.bold, letterSpacing: -0.5, color: Color(0xFFE2E2E8)),
        headlineLarge: TextStyle(fontSize: 20, fontWeight: FontWeight.w600, color: Color(0xFFE2E2E8)),
        headlineMedium: TextStyle(fontSize: 18, fontWeight: FontWeight.w600, color: Color(0xFFE2E2E8)),
        titleLarge: TextStyle(fontSize: 16, fontWeight: FontWeight.w600, color: Color(0xFFE2E2E8)),
        bodyLarge: TextStyle(fontSize: 15, height: 1.5, color: Color(0xFFA1A1AA)),
        bodyMedium: TextStyle(fontSize: 14, height: 1.4, color: Color(0xFFA1A1AA)),
        labelLarge: TextStyle(fontSize: 13, fontWeight: FontWeight.w500, letterSpacing: 0.5, color: Color(0xFF71717A)),
      ),
    );
  }

  static const Color dangerRed = Color(0xFFEF4444);
  static const Color warningAmber = Color(0xFFF59E0B);
  static const Color successGreen = Color(0xFF10B981);
  static const Color infoBlue = Color(0xFF3B82F6);
  static const Color cyberCyan = Color(0xFF06B6D4);
  static const Color terminalGreen = Color(0xFF22C55E);
  static const Color surfaceElevated = Color(0xFF1A1A24);
  static const Color borderSubtle = Color(0xFF2A2A3A);
}
