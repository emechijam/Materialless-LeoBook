import 'dart:convert';

class RecommendationModel {
  final String match;
  final String fixtureId;
  final String time;
  final String date;
  final String prediction;
  final String market;
  final String confidence;
  final String overallAcc;
  final String recentAcc;
  final String trend;
  final double marketOdds;
  final double reliabilityScore;
  final String sport;
  final String? homeCrestUrl;
  final String? awayCrestUrl;
  final String? leagueCrestUrl;
  final String? regionFlagUrl;
  final String league;
  final bool isAvailable;
  final Map<String, dynamic>? formHome;
  final Map<String, dynamic>? formAway;
  final List<dynamic>? h2hSummary;
  final Map<String, dynamic>? standingsHome;
  final Map<String, dynamic>? standingsAway;
  final String? ruleEngineDecision;
  final Map<String, dynamic>? rlDecision;
  final Map<String, dynamic>? ensembleWeights;
  final Map<String, dynamic>? recQualifications;

  RecommendationModel({
    required this.match,
    required this.fixtureId,
    required this.time,
    required this.date,
    required this.prediction,
    required this.market,
    required this.confidence,
    required this.overallAcc,
    required this.recentAcc,
    required this.trend,
    required this.marketOdds,
    required this.reliabilityScore,
    required this.league,
    this.sport = 'Football',
    this.homeCrestUrl,
    this.awayCrestUrl,
    this.leagueCrestUrl,
    this.regionFlagUrl,
    this.isAvailable = false,
    this.formHome,
    this.formAway,
    this.h2hSummary,
    this.standingsHome,
    this.standingsAway,
    this.ruleEngineDecision,
    this.rlDecision,
    this.ensembleWeights,
    this.recQualifications,
  });

  String get homeTeam {
    if (match.contains(' vs ')) {
      return match.split(' vs ')[0].trim();
    }
    if (match.contains(' - ')) {
      return match.split(' - ')[0].trim();
    }
    return match;
  }

  String get awayTeam {
    if (match.contains(' vs ')) {
      return match.split(' vs ')[1].trim();
    }
    if (match.contains(' - ')) {
      return match.split(' - ')[1].trim();
    }
    return '';
  }

  String get homeShort {
    final t = homeTeam;
    if (t.length <= 3) {
      return t.toUpperCase();
    }
    return t.substring(0, 3).toUpperCase();
  }

  String get awayShort {
    final t = awayTeam;
    if (t.isEmpty) {
      return '???';
    }
    if (t.length <= 3) {
      return t.toUpperCase();
    }
    return t.substring(0, 3).toUpperCase();
  }

  factory RecommendationModel.fromJson(Map<String, dynamic> json) {
    final leagueStr =
        (json['country_league'] ?? json['region_league'] ?? json['league'] ?? '').toString();

    String matchStr = json['match'] ?? '';
    if (matchStr.isEmpty &&
        json['home_team'] != null &&
        json['away_team'] != null) {
      matchStr = "${json['home_team']} vs ${json['away_team']}";
    }

    String sportType = 'Football';
    final l = leagueStr.toLowerCase();
    if (l.contains('nba') || l.contains('basketball') || l.contains('euroleague')) {
      sportType = 'Basketball';
    } else if (l.contains('atp') || l.contains('wta') || l.contains('itf') || l.contains('tennis')) {
      sportType = 'Tennis';
    }

    dynamic parseJsonField(dynamic field) {
      if (field == null) return null;
      if (field is String && (field.startsWith('{') || field.startsWith('['))) {
        try {
          return jsonDecode(field);
        } catch (_) {
          return null;
        }
      }
      return field;
    }

    return RecommendationModel(
      match: matchStr,
      fixtureId: json['fixture_id']?.toString() ?? '',
      time: (json['match_time'] ?? json['time'] ?? '').toString(),
      date: (json['date'] ?? '').toString(),
      prediction: (json['prediction'] ?? '').toString(),
      market: (json['prediction'] ?? json['market'] ?? '').toString(),
      confidence: (json['confidence'] ?? '').toString(),
      overallAcc: (json['overall_acc'] ?? '85%').toString(),
      recentAcc: (json['recent_acc'] ?? '90%').toString(),
      trend: (json['trend'] ?? 'UP').toString(),
      marketOdds: double.tryParse(json['odds']?.toString() ?? '') ??
          double.tryParse(json['market_odds']?.toString() ?? '') ??
          0.0,
      reliabilityScore:
          double.tryParse(json['market_reliability_score']?.toString() ?? '') ??
              double.tryParse(json['reliability_score']?.toString() ?? '') ??
              double.tryParse(json['recommendation_score']?.toString() ?? '') ??
              0.0,
      league: leagueStr,
      sport: sportType,
      homeCrestUrl: json['home_crest_url']?.toString(),
      awayCrestUrl: json['away_crest_url']?.toString(),
      leagueCrestUrl: json['league_crest_url']?.toString(),
      regionFlagUrl: json['region_flag_url']?.toString(),
      isAvailable: json['is_available'] == true ||
          json['is_available'] == 1 ||
          json['is_available'] == '1',
      formHome: parseJsonField(json['form_home']),
      formAway: parseJsonField(json['form_away']),
      h2hSummary: parseJsonField(json['h2h_summary']),
      standingsHome: parseJsonField(json['standings_home']),
      standingsAway: parseJsonField(json['standings_away']),
      ruleEngineDecision: json['rule_engine_decision']?.toString(),
      rlDecision: parseJsonField(json['rl_decision']),
      ensembleWeights: parseJsonField(json['ensemble_weights']),
      recQualifications: parseJsonField(json['rec_qualifications']),
    );
  }
}
