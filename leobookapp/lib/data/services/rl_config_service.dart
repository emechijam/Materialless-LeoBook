// rl_config_service.dart: Supabase-backed CRUD for user_rl_config.
// Part of LeoBook App — Services
//
// Classes: RlConfig, RlConfigService

import 'package:supabase_flutter/supabase_flutter.dart';

/// Mirrors the backend user_rl_config table row.
class RlConfig {
  final String userId;
  final double minConfidence;
  final double minOdds;
  final double maxOdds;
  final String riskAppetite;  // 'low' | 'medium' | 'high'
  final double maxStakePct;
  final List<String> enabledSports;
  final Map<String, dynamic>? marketWeights;

  const RlConfig({
    required this.userId,
    this.minConfidence = 0.6,
    this.minOdds = 1.5,
    this.maxOdds = 8.0,
    this.riskAppetite = 'medium',
    this.maxStakePct = 0.05,
    this.enabledSports = const ['football', 'basketball'],
    this.marketWeights,
  });

  factory RlConfig.defaults(String userId) => RlConfig(userId: userId);

  factory RlConfig.fromJson(Map<String, dynamic> json) {
    final sports = (json['enabled_sports'] as String? ?? 'football,basketball')
        .split(',')
        .map((s) => s.trim())
        .where((s) => s.isNotEmpty)
        .toList();

    return RlConfig(
      userId: json['user_id'] as String? ?? '',
      minConfidence: (json['min_confidence'] as num? ?? 0.6).toDouble(),
      minOdds: (json['min_odds'] as num? ?? 1.5).toDouble(),
      maxOdds: (json['max_odds'] as num? ?? 8.0).toDouble(),
      riskAppetite: json['risk_appetite'] as String? ?? 'medium',
      maxStakePct: (json['max_stake_pct'] as num? ?? 0.05).toDouble(),
      enabledSports: sports,
      marketWeights: json['market_weights'] as Map<String, dynamic>?,
    );
  }

  Map<String, dynamic> toJson() => {
        'user_id': userId,
        'min_confidence': minConfidence,
        'min_odds': minOdds,
        'max_odds': maxOdds,
        'risk_appetite': riskAppetite,
        'max_stake_pct': maxStakePct,
        'enabled_sports': enabledSports.join(','),
        if (marketWeights != null) 'market_weights': marketWeights,
      };

  RlConfig copyWith({
    double? minConfidence,
    double? minOdds,
    double? maxOdds,
    String? riskAppetite,
    double? maxStakePct,
    List<String>? enabledSports,
    Map<String, dynamic>? marketWeights,
  }) {
    return RlConfig(
      userId: userId,
      minConfidence: minConfidence ?? this.minConfidence,
      minOdds: minOdds ?? this.minOdds,
      maxOdds: maxOdds ?? this.maxOdds,
      riskAppetite: riskAppetite ?? this.riskAppetite,
      maxStakePct: maxStakePct ?? this.maxStakePct,
      enabledSports: enabledSports ?? this.enabledSports,
      marketWeights: marketWeights ?? this.marketWeights,
    );
  }
}

/// Supabase-backed service for user_rl_config.
///
/// All methods are safe to call even if the user is not logged in —
/// they return defaults or silently no-op.
class RlConfigService {
  final SupabaseClient _supabase = Supabase.instance.client;

  String? get _userId => _supabase.auth.currentUser?.id;

  /// Load config for the current user.
  /// Returns defaults if no row exists or user is not logged in.
  Future<RlConfig> load() async {
    final uid = _userId;
    if (uid == null) return RlConfig.defaults('');

    try {
      final rows = await _supabase
          .from('user_rl_config')
          .select()
          .eq('user_id', uid) as List;

      if (rows.isNotEmpty) {
        return RlConfig.fromJson(Map<String, dynamic>.from(rows.first as Map));
      }
    } catch (_) {}

    return RlConfig.defaults(uid);
  }

  /// Upsert the full config for the current user.
  /// No-ops if user is not logged in.
  Future<void> save(RlConfig config) async {
    final uid = _userId;
    if (uid == null) return;

    try {
      await _supabase.from('user_rl_config').upsert(config.toJson());
    } catch (e) {
      // Non-fatal — local rule engine file remains the source of truth
      // for the backtest/rule engine feature; this is best-effort sync.
      print('[RlConfigService] save failed: $e');
    }
  }

  /// Patch a single field without loading the full row.
  Future<void> patch(Map<String, dynamic> fields) async {
    final uid = _userId;
    if (uid == null) return;

    try {
      await _supabase
          .from('user_rl_config')
          .upsert({'user_id': uid, ...fields});
    } catch (e) {
      print('[RlConfigService] patch failed: $e');
    }
  }

  /// Delete the config row for the current user.
  Future<void> delete() async {
    final uid = _userId;
    if (uid == null) return;

    try {
      await _supabase
          .from('user_rl_config')
          .delete()
          .eq('user_id', uid);
    } catch (e) {
      print('[RlConfigService] delete failed: $e');
    }
  }
}
