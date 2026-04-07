// match_model.dart: match_model.dart: Widget/screen for App — Data Models.
// Part of LeoBook App — Data Models
//
// Classes: MatchModel

// ignore_for_file: avoid_dynamic_calls
import 'dart:convert';

/// Decodes a JSON string to Map<String, dynamic>. Returns null on any error.
Map<String, dynamic>? _jsonDecodeMap(String raw) {
  try {
    final decoded = jsonDecode(raw);
    if (decoded is Map) return decoded.cast<String, dynamic>();
  } catch (_) {}
  return null;
}

class MatchModel {
  final String date;
  final String time;
  final String homeTeam;
  final String awayTeam;
  final String? homeScore;
  final String? awayScore;
  final String status; // Scheduled, Live, Finished
  final String? prediction;
  final String? odds; // e.g. "1.68"
  final String? confidence; // High/Medium/Low
  final String? league; // e.g. "ENGLAND: Premier League"
  final String? leagueId; // Internal ID (e.g. 1_100_KEUqwJAr)
  final String sport;

  final String fixtureId; // Key for merging
  final String? liveMinute;
  final bool isFeatured;
  final String? valueTag;

  final String? homeCrestUrl;
  final String? awayCrestUrl;
  final String? regionFlagUrl;
  final String? leagueCrestUrl;
  final double? reliabilityScore;
  final double? xgHome;
  final double? xgAway;
  final String? reasonTags;
  final int? homeFormN;
  final int? awayFormN;

  final String? chosenMarket;
  final String? marketId;
  final String? ruleExplanation;
  final String? overrideReason;
  final double? statisticalEdge;
  final String? pureModelSuggestion;

  final String? homeTeamId;
  final String? awayTeamId;
  final String? outcomeCorrect; // From predictions CSV outcome_correct column
  final bool isAvailableInBookie;

  final int homeRedCards;
  final int awayRedCards;
  final String? winner; // 'home', 'away', 'draw', or null
  final String? leagueStage; // e.g. 'Round 32'
  final String? season; // e.g. '2025/2026'

  final Map<String, dynamic>? formHome;
  final Map<String, dynamic>? formAway;
  final List<dynamic>? h2hSummary;
  final Map<String, dynamic>? standingsHome;
  final Map<String, dynamic>? standingsAway;
  final String? ruleEngineDecision;
  final Map<String, dynamic>? rlDecision;
  final Map<String, dynamic>? ensembleWeights;
  final Map<String, dynamic>? recQualifications;

  // v9.8.0 — basketball period scores + market period targeting
  /// JSON: {"q1":{"home":28,"away":22}, "q2":..., "h1":..., "ot":...} — null for football.
  final Map<String, dynamic>? periodScores;
  /// The O/U line this prediction targets (e.g. 220.5). Null for 1X2.
  final double? marketLine;
  /// Period targeted: 'full' | 'h1' | 'h2' | 'q1'–'q4'. Null for football.
  final String? marketPeriod;

  MatchModel({
    required this.fixtureId,
    required this.date,
    required this.time,
    required this.homeTeam,
    required this.awayTeam,
    this.homeTeamId,
    this.awayTeamId,
    this.homeScore,
    this.awayScore,
    required this.status,
    required this.sport,
    this.league,
    this.leagueId,
    this.prediction,
    this.odds,
    this.confidence,
    this.liveMinute,
    this.isFeatured = false,
    this.valueTag,
    this.homeCrestUrl,
    this.awayCrestUrl,
    this.regionFlagUrl,
    this.leagueCrestUrl,
    this.reliabilityScore,
    this.xgHome,
    this.xgAway,
    this.reasonTags,
    this.homeFormN,
    this.awayFormN,
    this.chosenMarket,
    this.marketId,
    this.ruleExplanation,
    this.overrideReason,
    this.statisticalEdge,
    this.pureModelSuggestion,
    this.outcomeCorrect,
    this.isAvailableInBookie = false,
    this.homeRedCards = 0,
    this.awayRedCards = 0,
    this.winner,
    this.leagueStage,
    this.season,
    this.formHome,
    this.formAway,
    this.h2hSummary,
    this.standingsHome,
    this.standingsAway,
    this.ruleEngineDecision,
    this.rlDecision,
    this.ensembleWeights,
    this.recQualifications,
    this.periodScores,
    this.marketLine,
    this.marketPeriod,
  });

  bool get isLive =>
      status.toLowerCase().contains('live') ||
      (liveMinute != null && liveMinute!.isNotEmpty);
  bool get isFinished =>
      status.toLowerCase().contains('ft') ||
      status.toLowerCase().contains('finished') ||
      status.toLowerCase().contains('aet') ||
      status.toLowerCase().contains('pen');
  bool get isStartingSoon =>
      !isLive && !isFinished && status.toLowerCase() != 'postponed';

  String get displayStatus {
    if (isLive) return liveMinute ?? 'Live';
    return status;
  }

  bool get isPredictionAccurate {
    if (!isFinished || winner == null || prediction == null) return false;
    final p = prediction!.toLowerCase();
    final w = winner!.toLowerCase();
    if (p.contains('home') && w == 'home') return true;
    if (p.contains('away') && w == 'away') return true;
    if (p.contains('draw') && w == 'draw') return true;
    return false;
  }

  double get probHome =>
      (ensembleWeights?['home'] ?? rlDecision?['home_win_prob'] ?? 0.0);
  double get probDraw =>
      (ensembleWeights?['draw'] ?? rlDecision?['draw_prob'] ?? 0.0);
  double get probAway =>
      (ensembleWeights?['away'] ?? rlDecision?['away_win_prob'] ?? 0.0);

  String get aiReasoningSentence =>
      ruleExplanation ?? ruleEngineDecision ?? "AI analyzing patterns...";
  String get ruleOutput => ruleExplanation ?? ruleEngineDecision ?? "";

  Map<String, dynamic> toJson() {
    return {
      'fixture_id': fixtureId,
      'date': date,
      'time': time,
      'home_team': homeTeam,
      'away_team': awayTeam,
      'home_team_id': homeTeamId,
      'away_team_id': awayTeamId,
      'home_score': homeScore,
      'away_score': awayScore,
      'status': status,
      'sport': sport,
      'league': league,
      'league_id': leagueId,
      'prediction': prediction,
      'odds': odds,
      'confidence': confidence,
      'live_minute': liveMinute,
      'is_featured': isFeatured,
      'value_tag': valueTag,
      'home_crest_url': homeCrestUrl,
      'away_crest_url': awayCrestUrl,
      'region_flag_url': regionFlagUrl,
      'league_crest_url': leagueCrestUrl,
      'reliability_score': reliabilityScore,
      'xg_home': xgHome,
      'xg_away': xgAway,
      'reason_tags': reasonTags,
      'home_form_n': homeFormN,
      'away_form_n': awayFormN,
      'chosen_market': chosenMarket,
      'market_id': marketId,
      'rule_explanation': ruleExplanation,
      'override_reason': overrideReason,
      'statistical_edge': statisticalEdge,
      'pure_model_suggestion': pureModelSuggestion,
      'outcome_correct': outcomeCorrect,
      'is_available_in_bookie': isAvailableInBookie,
      'home_red_cards': homeRedCards,
      'away_red_cards': awayRedCards,
      'winner': winner,
      'league_stage': leagueStage,
      'season': season,
      'form_home': formHome,
      'form_away': formAway,
      'h2h_summary': h2hSummary,
      'standings_home': standingsHome,
      'standings_away': standingsAway,
      'rule_engine_decision': ruleEngineDecision,
      'rl_decision': rlDecision,
      'ensemble_weights': ensembleWeights,
      'rec_qualifications': recQualifications,
      'period_scores': periodScores,
      'market_line': marketLine,
      'market_period': marketPeriod,
    };
  }

  factory MatchModel.fromCsv(Map<String, dynamic> row,
      [Map<String, dynamic>? predictionData]) {
    final fixtureId = row['fixture_id']?.toString() ?? '';
    final rawDate = row['date']?.toString() ?? '';
    String formattedDate = rawDate;
    if (rawDate.isNotEmpty && rawDate.contains('/')) {
      final parts = rawDate.split('/');
      if (parts.length == 3) {
        formattedDate =
            "${parts[2]}-${parts[1].padLeft(2, '0')}-${parts[0].padLeft(2, '0')}";
      }
    }

    final hScore = row['home_score']?.toString();
    final aScore = row['away_score']?.toString();
    final sport = row['sport']?.toString() ?? 'Football';

    String? prediction;
    String? confidence;
    String? odds;
    double? reliabilityScore;
    double? xgHome;
    double? xgAway;
    String? reasonTags;
    String? chosenMarket;
    String? marketId;
    String? ruleExplanation;
    String? overrideReason;
    double? statisticalEdge;
    String? pureModelSuggestion;
    bool isFeatured = false;

    if (predictionData != null) {
      prediction = predictionData['prediction']?.toString();
      confidence = predictionData['confidence']?.toString();
      odds = predictionData['odds']?.toString();
      reliabilityScore = double.tryParse(
              predictionData['reliability_score']?.toString() ?? '') ??
          double.tryParse(
              predictionData['recommendation_score']?.toString() ?? '') ??
          double.tryParse(
              predictionData['market_reliability_score']?.toString() ?? '') ??
          0.0;
      xgHome = double.tryParse(predictionData['xg_home']?.toString() ?? '');
      xgAway = double.tryParse(predictionData['xg_away']?.toString() ?? '');
      reasonTags = predictionData['reason_tags']?.toString() ??
          predictionData['reason']?.toString();

      chosenMarket = predictionData['chosen_market']?.toString();
      marketId = predictionData['market_id']?.toString();
      ruleExplanation = predictionData['rule_explanation']?.toString();
      overrideReason = predictionData['override_reason']?.toString();
      statisticalEdge =
          double.tryParse(predictionData['statistical_edge']?.toString() ?? '');
      pureModelSuggestion = predictionData['pure_model_suggestion']?.toString();

      if (confidence != null &&
          (confidence.contains('High') || confidence.contains('Very High'))) {
        isFeatured = true;
      }
    }

    final isAvailable = predictionData?['is_available_in_bookie'] == true ||
        predictionData?['is_available'] == true ||
        row['is_available_in_bookie'] == true;

    return MatchModel(
      fixtureId: fixtureId,
      date: formattedDate,
      time: (row['time'] ?? row['match_time'] ?? '').toString(),
      homeTeam: (row['home_team_name'] ?? row['home_team'] ?? '').toString(),
      awayTeam: (row['away_team_name'] ?? row['away_team'] ?? '').toString(),
      homeTeamId: row['home_team_id']?.toString(),
      awayTeamId: row['away_team_id']?.toString(),
      homeScore: hScore,
      awayScore: aScore,
      status: (row['match_status'] ?? row['status'] ?? 'Scheduled').toString(),
      sport: sport,
      league:
          (row['league_name'] ?? row['league'] ?? row['country_league'] ?? '')
              .toString(),
      leagueId: row['league_id']?.toString(),
      prediction: prediction,
      confidence: confidence,
      odds: odds,
      reliabilityScore: reliabilityScore,
      xgHome: xgHome,
      xgAway: xgAway,
      reasonTags: reasonTags,
      isFeatured: isFeatured,
      homeCrestUrl:
          (row['home_crest_url'] ?? row['home_crest'] ?? '').toString(),
      awayCrestUrl:
          (row['away_crest_url'] ?? row['away_crest'] ?? '').toString(),
      regionFlagUrl: row['region_flag_url']?.toString(),
      leagueCrestUrl: row['league_crest_url']?.toString(),
      chosenMarket: chosenMarket,
      marketId: marketId,
      ruleExplanation: ruleExplanation,
      overrideReason: overrideReason,
      statisticalEdge: statisticalEdge,
      pureModelSuggestion: pureModelSuggestion,
      isAvailableInBookie: isAvailable,
      homeRedCards: int.tryParse(row['home_red_cards']?.toString() ?? '') ?? 0,
      awayRedCards: int.tryParse(row['away_red_cards']?.toString() ?? '') ?? 0,
      winner: row['winner']?.toString(),
      leagueStage: row['league_stage']?.toString(),
      season: row['season']?.toString(),
      formHome: predictionData?['form_home'],
      formAway: predictionData?['form_away'],
      h2hSummary: predictionData?['h2h_summary'],
      standingsHome: predictionData?['standings_home'],
      standingsAway: predictionData?['standings_away'],
      ruleEngineDecision: predictionData?['rule_engine_decision'],
      rlDecision: predictionData?['rl_decision'],
      ensembleWeights: predictionData?['ensemble_weights'],
      recQualifications: predictionData?['rec_qualifications'],
      periodScores: () {
        final raw = row['period_scores'];
        if (raw is Map) return raw.cast<String, dynamic>();
        if (raw is String && raw.isNotEmpty) {
          final decoded = _jsonDecodeMap(raw);
          if (decoded != null) return decoded;
        }
        return null;
      }(),
      marketLine: double.tryParse(
          predictionData?['market_line']?.toString() ?? ''),
      marketPeriod: predictionData?['market_period']?.toString(),
    );
  }

  MatchModel mergeWith(MatchModel other) {
    String preferString(String current, String incoming) {
      return incoming.trim().isNotEmpty ? incoming : current;
    }

    String? preferNullableString(String? current, String? incoming) {
      if (incoming == null || incoming.trim().isEmpty) {
        return current;
      }

      return incoming;
    }

    return MatchModel(
      fixtureId: fixtureId,
      date: preferString(date, other.date),
      time: preferString(time, other.time),
      homeTeam: preferString(homeTeam, other.homeTeam),
      awayTeam: preferString(awayTeam, other.awayTeam),
      homeTeamId: other.homeTeamId ?? homeTeamId,
      awayTeamId: other.awayTeamId ?? awayTeamId,
      homeScore: other.homeScore ?? homeScore,
      awayScore: other.awayScore ?? awayScore,
      status: preferString(status, other.status),
      sport: preferString(sport, other.sport),
      league: preferNullableString(league, other.league),
      leagueId: other.leagueId ?? leagueId,
      prediction: preferNullableString(prediction, other.prediction),
      odds: preferNullableString(odds, other.odds),
      confidence: preferNullableString(confidence, other.confidence),
      liveMinute: preferNullableString(liveMinute, other.liveMinute),
      isFeatured: isFeatured || other.isFeatured,
      valueTag: preferNullableString(valueTag, other.valueTag),
      homeCrestUrl: preferNullableString(homeCrestUrl, other.homeCrestUrl),
      awayCrestUrl: preferNullableString(awayCrestUrl, other.awayCrestUrl),
      regionFlagUrl: preferNullableString(regionFlagUrl, other.regionFlagUrl),
      leagueCrestUrl:
          preferNullableString(leagueCrestUrl, other.leagueCrestUrl),
      reliabilityScore: other.reliabilityScore ?? reliabilityScore,
      xgHome: other.xgHome ?? xgHome,
      xgAway: other.xgAway ?? xgAway,
      reasonTags: preferNullableString(reasonTags, other.reasonTags),
      homeFormN: other.homeFormN ?? homeFormN,
      awayFormN: other.awayFormN ?? awayFormN,
      chosenMarket: preferNullableString(chosenMarket, other.chosenMarket),
      marketId: preferNullableString(marketId, other.marketId),
      ruleExplanation:
          preferNullableString(ruleExplanation, other.ruleExplanation),
      overrideReason:
          preferNullableString(overrideReason, other.overrideReason),
      statisticalEdge: other.statisticalEdge ?? statisticalEdge,
      pureModelSuggestion:
          preferNullableString(pureModelSuggestion, other.pureModelSuggestion),
      outcomeCorrect:
          preferNullableString(outcomeCorrect, other.outcomeCorrect),
      isAvailableInBookie: isAvailableInBookie || other.isAvailableInBookie,
      homeRedCards: other.homeRedCards > 0 || homeRedCards == 0
          ? other.homeRedCards
          : homeRedCards,
      awayRedCards: other.awayRedCards > 0 || awayRedCards == 0
          ? other.awayRedCards
          : awayRedCards,
      winner: preferNullableString(winner, other.winner),
      leagueStage: preferNullableString(leagueStage, other.leagueStage),
      season: preferNullableString(season, other.season),
      formHome: other.formHome ?? formHome,
      formAway: other.formAway ?? formAway,
      h2hSummary: other.h2hSummary ?? h2hSummary,
      standingsHome: other.standingsHome ?? standingsHome,
      standingsAway: other.standingsAway ?? standingsAway,
      ruleEngineDecision: other.ruleEngineDecision ?? ruleEngineDecision,
      rlDecision: other.rlDecision ?? rlDecision,
      ensembleWeights: other.ensembleWeights ?? ensembleWeights,
      recQualifications: other.recQualifications ?? recQualifications,
      periodScores: other.periodScores ?? periodScores,
      marketLine: other.marketLine ?? marketLine,
      marketPeriod: preferNullableString(marketPeriod, other.marketPeriod),
    );
  }
}
