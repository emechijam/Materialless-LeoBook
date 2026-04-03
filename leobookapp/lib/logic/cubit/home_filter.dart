// home_filter.dart: Pure filter functions for HomeCubit.
// Part of LeoBook App — State Management (Cubit)

import 'package:leobookapp/data/models/match_model.dart';
import 'package:leobookapp/data/models/recommendation_model.dart';

List<MatchModel> filterMatches(
  List<MatchModel> matches,
  DateTime date,
  String sport, {
  List<String> leagues = const [],
  List<String> types = const [],
  double minO = 1.0,
  double maxO = 10.0,
  double minRel = 0.0,
  List<String> confs = const [],
  bool onlyAvail = false,
}) {
  final targetDateStr = formatDateForMatching(date);
  return matches.where((m) {
    final dateMatch = m.date == targetDateStr;
    final sportMatch =
        (sport == 'ALL') || (m.sport.toUpperCase() == sport.toUpperCase());

    bool leagueMatch =
        leagues.isEmpty || (m.league != null && leagues.contains(m.league));
    bool typeMatch = types.isEmpty ||
        (m.prediction != null && types.any((t) => m.prediction!.contains(t)));

    double mOdds = double.tryParse(m.odds ?? '1.0') ?? 1.0;
    bool oddsMatch = mOdds >= minO && mOdds <= maxO;

    double rel = m.reliabilityScore ?? 0.0;
    bool relMatch = rel >= minRel;

    bool confMatch = confs.isEmpty ||
        (m.confidence != null && confs.contains(m.confidence));

    bool availMatch = !onlyAvail || m.isAvailableInBookie;

    return dateMatch &&
        sportMatch &&
        leagueMatch &&
        typeMatch &&
        oddsMatch &&
        relMatch &&
        confMatch &&
        availMatch;
  }).toList();
}

List<RecommendationModel> filterRecommendations(
  List<RecommendationModel> recs,
  DateTime date,
  String sport, {
  List<String> leagues = const [],
  List<String> types = const [],
  double minO = 1.0,
  double maxO = 10.0,
  double minRel = 0.0,
  List<String> confs = const [],
  bool onlyAvail = false,
}) {
  // NOTE: No date filter — recommendations are ranked globally by score,
  // not tied to a specific day. The query fetches top 100 by recommendation_score.
  return recs.where((r) {
    final sportMatch =
        (sport == 'ALL') || (r.sport.toUpperCase() == sport.toUpperCase());

    bool leagueMatch = leagues.isEmpty || leagues.contains(r.league);
    bool typeMatch =
        types.isEmpty || types.any((t) => r.prediction.contains(t));

    double rOdds = r.marketOdds;
    bool oddsMatch = rOdds >= minO && rOdds <= maxO;

    bool relMatch = r.reliabilityScore >= minRel;
    bool confMatch = confs.isEmpty || confs.contains(r.confidence);
    bool availMatch = !onlyAvail || r.isAvailable;

    return sportMatch &&
        leagueMatch &&
        typeMatch &&
        oddsMatch &&
        relMatch &&
        confMatch &&
        availMatch;
  }).toList();
}

String formatDateForMatching(DateTime date) {
  return "${date.year}-${date.month.toString().padLeft(2, '0')}-${date.day.toString().padLeft(2, '0')}";
}
