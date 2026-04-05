// theme_cubit.dart — LeoBook Design System v2.0
// Part of LeoBook App — Core Theme
//
// Description: Cubit managing ThemeMode for the app.
// Supports system (default), dark, and light. Persists via SharedPreferences.
// Classes: ThemeCubit

import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:shared_preferences/shared_preferences.dart';

class ThemeCubit extends Cubit<ThemeMode> {
  static const _key = 'leo_theme_mode';

  ThemeCubit() : super(ThemeMode.system) {
    _loadSaved();
  }

  Future<void> _loadSaved() async {
    final prefs = await SharedPreferences.getInstance();
    emit(_fromString(prefs.getString(_key) ?? 'system'));
  }

  Future<void> setMode(ThemeMode mode) async {
    emit(mode);
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_key, _toString(mode));
  }

  void setSystem() => setMode(ThemeMode.system);
  void setDark() => setMode(ThemeMode.dark);
  void setLight() => setMode(ThemeMode.light);

  // Kept for back-compat
  void toggleTheme() =>
      setMode(state == ThemeMode.dark ? ThemeMode.light : ThemeMode.dark);

  bool get isDark => state == ThemeMode.dark;

  ThemeMode _fromString(String s) => switch (s) {
        'dark' => ThemeMode.dark,
        'light' => ThemeMode.light,
        _ => ThemeMode.system,
      };

  String _toString(ThemeMode m) => switch (m) {
        ThemeMode.dark => 'dark',
        ThemeMode.light => 'light',
        _ => 'system',
      };
}
