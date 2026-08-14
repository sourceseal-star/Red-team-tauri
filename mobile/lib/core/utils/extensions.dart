import 'package:flutter/material.dart';

extension StringExtension on String {
  String get capitalize => isEmpty ? this : '${this[0].toUpperCase()}${substring(1)}';
}

extension ColorExtension on Color {
  Color withOpacityValue(double value) => withAlpha((value * 255).round());
}
