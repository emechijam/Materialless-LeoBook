// data_repository.dart: data_repository.dart: Widget/screen for App — Repositories.
// Part of LeoBook App — Repositories
//
// Classes: DataRepository

import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import 'package:leobookapp/data/models/match_model.dart';
import 'package:leobookapp/data/models/recommendation_model.dart';
import 'package:leobookapp/data/models/standing_model.dart';
import 'package:leobookapp/data/models/league_model.dart';
import 'dart:convert';
import 'dart:async';

class DataRepository {
  static const String _keyRecommended = 'cached_recommended';
  static const String _keyPredictions = 'cached_predictions';

  final SupabaseClient _supabase = Supabase.instance.client;

  /// Batch-fetch predictions for a list of fixture IDs and return a lookup map.
  /// This is the single source of truth for prediction enrichment.
  Future<Map<String, Map<String, dynamic>>> _fetchPredictionMap({
    String? dateStr,
    List<String>? fixtureIds,
  }) async {
    final Map<String, Map<String, dynamic>> predMap = {};
    try {
      List<dynamic> predRows;
      if (dateStr != null) {
        // Date-based: fetch all predictions for that day
        predRows = await _supabase
            .from('predictions')
            .select()
            .eq('date', dateStr) as List;
      } else if (fixtureIds != null && fixtureIds.isNotEmpty) {
        // ID-based: fetch predictions matching specific fixture IDs
        // Supabase inFilter has a practical limit; batch in chunks of 200
        predRows = [];
        for (int i = 0; i < fixtureIds.length; i += 200) {
          final chunk = fixtureIds.sublist(
            i,
            i + 200 > fixtureIds.length ? fixtureIds.length : i + 200,
          );
          final res = await _supabase
              .from('predictions')
              .select()
              .inFilter('fixture_id', chunk) as List;
          predRows.addAll(res);
        }
      } else {
        return predMap;
      }
      for (var p in predRows) {
        final fid = p['fixture_id']?.toString();
        if (fid != null) predMap[fid] = p;
      }
    } catch (_) {
      // predictions table empty or query failed — return empty map
    }
    return predMap;
  }

  /// Merge schedule rows with prediction data.
  /// Predictions overlay schedule fields (prediction data wins on conflict).
  List<MatchModel> _mergeSchedulesWithPredictions(
    List<dynamic> scheduleRows,
    Map<String, Map<String, dynamic>> predMap,
  ) {
    return scheduleRows.map((row) {
      final fid = row['fixture_id']?.toString() ?? '';
      final pred = predMap[fid];
      final merged = pred != null ? {...row, ...pred} : row;
      return MatchModel.fromCsv(merged, pred != null ? merged : null);
    }).toList();
  }

  /// Paginated fetch: retrieves ALL rows for a date, bypassing the
  /// PostgREST 1,000-row default cap. Uses deterministic ordering
  /// (fixture_id ASC) and a 20-page safety cap (20,000 rows max).
  Future<List<dynamic>> _fetchAllRowsForDate(String dateStr) async {
    const pageSize = 1000;
    const maxPages = 20; // Safety: 20 × 1000 = 20k max

    final List<dynamic> allRows = [];
    int from = 0;
    for (int page = 0; page < maxPages; page++) {
      final pageRows = await _supabase
          .from('schedules')
          .select()
          .eq('date', dateStr)
          .order('fixture_id', ascending: true)
          .range(from, from + pageSize - 1);
      final rows = pageRows as List;
      allRows.addAll(rows);
      if (rows.length < pageSize) break; // Last page
      from += pageSize;
    }
    return allRows;
  }

  Future<List<MatchModel>> fetchMatches({DateTime? date}) async {
    try {
      // Primary source: schedules (always populated).
      // Predictions table is optional enrichment.
      String? dateStr;
      if (date != null) {
        dateStr =
            "${date.year}-${date.month.toString().padLeft(2, '0')}-${date.day.toString().padLeft(2, '0')}";
      }

      // Paginated fetch for a specific date; capped fetch otherwise
      final List<dynamic> scheduleRows;
      if (dateStr != null) {
        scheduleRows = await _fetchAllRowsForDate(dateStr);
      } else {
        final response = await _supabase
            .from('schedules')
            .select()
            .order('date', ascending: false)
            .limit(300);
        scheduleRows = response as List;
      }

      // Always enrich with predictions
      final predMap = dateStr != null
          ? await _fetchPredictionMap(dateStr: dateStr)
          : await _fetchPredictionMap(
              fixtureIds: scheduleRows
                  .map((r) => r['fixture_id']?.toString() ?? '')
                  .where((id) => id.isNotEmpty)
                  .toList(),
            );

      final matches = _mergeSchedulesWithPredictions(scheduleRows, predMap);

      // Stable in-memory sort by match time for display order
      matches.sort((a, b) {
        final timeCompare = a.time.compareTo(b.time);
        if (timeCompare != 0) return timeCompare;
        return a.fixtureId.compareTo(b.fixtureId); // Deterministic tie-breaker
      });

      // Cache a small subset locally
      try {
        final prefs = await SharedPreferences.getInstance();
        final listToCache = scheduleRows.take(50).toList();
        await prefs.setString(_keyPredictions, jsonEncode(listToCache));
      } catch (e) {
        debugPrint('Warning: Could not cache matches (quota exceeded): $e');
      }

      return matches;
    } catch (e) {
      debugPrint("DataRepository Error (Supabase): $e");

      // Fallback to cache
      final prefs = await SharedPreferences.getInstance();
      final cachedString = prefs.getString(_keyPredictions);

      if (cachedString != null) {
        try {
          final List<dynamic> cachedData = jsonDecode(cachedString);
          return cachedData
              .map((row) => MatchModel.fromCsv(row, row))
              .toList();
        } catch (cacheError) {
          debugPrint("Failed to load from cache: $cacheError");
        }
      }
      return [];
    }
  }

  Future<List<MatchModel>> fetchMatchesByLeague(String leagueId) async {
    try {
      final response = await _supabase
          .from('schedules')
          .select()
          .eq('league_id', leagueId)
          .order('date', ascending: false)
          .limit(100);

      final rows = response as List;
      final fixtureIds =
          rows.map((r) => r['fixture_id']?.toString() ?? '').toList();
      final predMap = await _fetchPredictionMap(fixtureIds: fixtureIds);

      final matches = _mergeSchedulesWithPredictions(rows, predMap);
      return matches;
    } catch (e) {
      debugPrint("DataRepository Error (League Matches): $e");
      return [];
    }
  }

  Future<List<MatchModel>> getTeamMatches(String teamName) async {
    try {
      var schedList = await _supabase
          .from('schedules')
          .select()
          .or('home_team.eq."$teamName",away_team.eq."$teamName"')
          .order('date', ascending: false)
          .limit(20);

      List<dynamic> rows = schedList as List<dynamic>;

      // Fuzzy fallback if empty
      if (rows.isEmpty) {
        final fuzzy = await _supabase
            .from('schedules')
            .select()
            .or('home_team.ilike."%$teamName%",away_team.ilike."%$teamName%"')
            .order('date', ascending: false)
            .limit(20);
        rows = fuzzy as List<dynamic>;
      }

      // Enrich with predictions
      final fixtureIds = rows
          .map((r) => r['fixture_id']?.toString() ?? '')
          .where((id) => id.isNotEmpty)
          .toList();
      final predMap = await _fetchPredictionMap(fixtureIds: fixtureIds);
      final matches = _mergeSchedulesWithPredictions(rows, predMap);

      matches.sort((a, b) {
        try {
          return DateTime.parse(b.date).compareTo(DateTime.parse(a.date));
        } catch (_) {
          return 0;
        }
      });

      return matches;
    } catch (e) {
      debugPrint("DataRepository Error (Team Matches): $e");
      return [];
    }
  }

  /// Dedicated H2H query: finds matches where BOTH teams participated
  Future<List<MatchModel>> getH2HMatches(String teamA, String teamB) async {
    try {
      // Query both combinations: A vs B and B vs A
      final response = await _supabase
          .from('schedules')
          .select()
          .or('and(home_team.eq."$teamA",away_team.eq."$teamB"),and(home_team.eq."$teamB",away_team.eq."$teamA")')
          .order('date', ascending: false)
          .limit(10);

      return (response as List).map((row) => MatchModel.fromCsv(row)).toList();
    } catch (e) {
      debugPrint("DataRepository Error (H2H): $e");
      return [];
    }
  }

  Future<List<RecommendationModel>> fetchRecommendations() async {
    final prefs = await SharedPreferences.getInstance();
    try {
      final response = await _supabase
          .from('predictions')
          .select()
          .gt('recommendation_score', 0)
          .order('recommendation_score', ascending: false)
          .limit(100);

      debugPrint('Loaded ${response.length} recommendations from Supabase');

      // SharedPreferences String length limit quota can trigger on large arrays.
      // Cache only the top 30 highest scoring recommendations to avoid exceeding quota.
      final listToCache = (response as List).take(30).toList();
      try {
        await prefs.setString(_keyRecommended, jsonEncode(listToCache));
      } catch (e) {
        debugPrint('Warning: Could not save recommendations cache due to size limit: $e');
        try { await prefs.remove(_keyRecommended); } catch (_) {}
      }

      return (response)
          .map((json) => RecommendationModel.fromJson(json))
          .toList();
    } catch (e) {
      debugPrint("Error fetching recommendations (Supabase): $e");
      final cached = prefs.getString(_keyRecommended);
      if (cached != null) {
        try {
          final List<dynamic> jsonList = jsonDecode(cached);
          return jsonList
              .map((json) => RecommendationModel.fromJson(json))
              .toList();
        } catch (cacheError) {
          debugPrint("Failed to load recommendations from cache: $cacheError");
        }
      }
      return [];
    }
  }

  Future<List<StandingModel>> fetchStandings({required String leagueId, String? season}) async {
    try {
      var query = _supabase
          .from('computed_standings_mv')
          .select()
          .eq('league_id', leagueId);
      
      if (season != null) {
        query = query.eq('season', season);
      }

      final response = await query
          .order('points', ascending: false)
          .order('goal_difference', ascending: false);

      // Enrich standings with team crests from teams table
      final standings =
          (response as List).map((row) => StandingModel.fromJson(row)).toList();

      if (standings.isNotEmpty) {
        try {
          final teamNames = standings.map((s) => s.teamName).toList();
          final teamsResponse = await _supabase
              .from('teams')
              .select('name, crest')
              .inFilter('name', teamNames);
          final Map<String, String> crestMap = {};
          for (var row in (teamsResponse as List)) {
            final name = row['name']?.toString();
            final crest = row['crest']?.toString();
            if (name != null &&
                crest != null &&
                crest.isNotEmpty &&
                crest != 'Unknown') {
              crestMap[name] = crest;
            }
          }
          // Merge crests into standings
          for (int i = 0; i < standings.length; i++) {
            final crest = crestMap[standings[i].teamName];
            if (crest != null && standings[i].teamCrestUrl == null) {
              standings[i] = StandingModel(
                teamName: standings[i].teamName,
                teamId: standings[i].teamId,
                teamCrestUrl: crest,
                position: standings[i].position,
                played: standings[i].played,
                wins: standings[i].wins,
                draws: standings[i].draws,
                losses: standings[i].losses,
                goalsFor: standings[i].goalsFor,
                goalsAgainst: standings[i].goalsAgainst,
                points: standings[i].points,
                leagueName: standings[i].leagueName,
              );
            }
          }
        } catch (e) {
          debugPrint("Could not fetch team crests for standings: $e");
        }
      }

      return standings;
    } catch (e) {
      debugPrint("DataRepository Error (Standings): $e");
      return [];
    }
  }

  Future<Map<String, String>> fetchTeamCrests() async {
    try {
      final response = await _supabase.from('teams').select('team_name, team_crest');
      final Map<String, String> crests = {};
      for (var row in (response as List)) {
        if (row['team_name'] != null && row['team_crest'] != null) {
          crests[row['team_name'].toString()] = row['team_crest'].toString();
        }
      }
      return crests;
    } catch (e) {
      debugPrint("DataRepository Error (Team Crests): $e");
      return {};
    }
  }

  /// Fetch all schedules, enriched with predictions when available.
  Future<List<MatchModel>> fetchAllSchedules({DateTime? date}) async {
    // Delegate to fetchMatches which already merges predictions
    return fetchMatches(date: date);
  }

  Future<StandingModel?> getTeamStanding(String teamName) async {
    try {
      final response = await _supabase
          .from('computed_standings_mv')
          .select()
          .eq('team_name', teamName)
          .maybeSingle();

      if (response != null) {
        return StandingModel.fromJson(response);
      }
      return null;
    } catch (e) {
      debugPrint("DataRepository Error (Team Standing): $e");
      return null;
    }
  }

  // --- Realtime Streams (Postgres Changes Style) ---

  Stream<List<MatchModel>> watchLiveScores() {
    return _supabase.from('live_scores').stream(primaryKey: ['fixture_id']).map(
        (rows) => rows.map((row) => MatchModel.fromCsv(row)).toList());
  }

  Stream<List<MatchModel>> watchPredictions({DateTime? date}) {
    var query =
        _supabase.from('predictions').stream(primaryKey: ['fixture_id']);

    return query.map((rows) {
      var matches = rows.map((row) => MatchModel.fromCsv(row, row)).toList();
      if (date != null) {
        final dateStr =
            "${date.year}-${date.month.toString().padLeft(2, '0')}-${date.day.toString().padLeft(2, '0')}";
        matches = matches.where((m) => m.date == dateStr).toList();
      }
      return matches;
    });
  }

  Stream<List<MatchModel>> watchSchedules({DateTime? date}) {
    // Schedules are stored in the fixtures table
    var query = _supabase.from('schedules').stream(primaryKey: ['fixture_id']);

    return query.map((rows) {
      var matches = rows.map((row) => MatchModel.fromCsv(row)).toList();
      if (date != null) {
        final dateStr =
            "${date.year}-${date.month.toString().padLeft(2, '0')}-${date.day.toString().padLeft(2, '0')}";
        matches = matches.where((m) => m.date == dateStr).toList();
      }
      return matches;
    });
  }

  Stream<List<StandingModel>> watchStandings({required String leagueId, String? season}) {
    final controller = StreamController<List<StandingModel>>.broadcast();

    void fetchAndEmit() async {
      try {
        final data = await fetchStandings(leagueId: leagueId, season: season);
        if (!controller.isClosed) controller.add(data);
      } catch (e) {
        debugPrint('Error fetching standings view: $e');
      }
    }

    // Initial fetch
    fetchAndEmit();

    // Listen to underlying schedules table for changes since computed_standings view doesn't emit realtime events natively
    final channel = _supabase.channel('schedules:standings-$leagueId');
    channel.onPostgresChanges(
      event: PostgresChangeEvent.all,
      schema: 'public',
      table: 'schedules',
      filter: PostgresChangeFilter(
        type: PostgresChangeFilterType.eq,
        column: 'league_id',
        value: leagueId,
      ),
      callback: (payload) {
        fetchAndEmit();
      },
    ).subscribe();

    controller.onCancel = () {
      _supabase.removeChannel(channel);
    };

    return controller.stream;
  }


  Stream<Map<String, String>> watchTeamCrestUpdates() {
    return _supabase.from('teams').stream(primaryKey: ['team_id']).map((rows) {
      final Map<String, String> crests = {};
      for (var row in rows) {
        if (row['team_name'] != null && row['team_crest'] != null) {
          crests[row['team_name'].toString()] = row['team_crest'].toString();
        }
      }
      return crests;
    });
  }

  final Map<String, List<Map<String, dynamic>>> _oddsCache = {};

  Future<List<Map<String, dynamic>>> getMatchOdds(String fixtureId) async {
    if (_oddsCache.containsKey(fixtureId)) return _oddsCache[fixtureId]!;
    try {
      final response = await _supabase
          .from('match_odds')
          .select()
          .eq('fixture_id', fixtureId);
      final list = List<Map<String, dynamic>>.from(response);
      _oddsCache[fixtureId] = list;
      return list;
    } catch (e) {
      debugPrint('Error fetching odds for $fixtureId: $e');
      return [];
    }
  }

  /// Watch match_odds table for realtime odds updates
  Stream<List<Map<String, dynamic>>> watchMatchOdds(String fixtureId) {
    return _supabase
        .from('match_odds')
        .stream(primaryKey: ['fixture_id', 'market_id', 'exact_outcome', 'line'])
        .eq('fixture_id', fixtureId)
        .map((rows) => List<Map<String, dynamic>>.from(rows));
  }

  // --- League Data ---

  Future<List<LeagueModel>> fetchLeagues() async {
    try {
      final response = await _supabase
          .from('leagues')
          .select(
              'league_id, fs_league_id, name, crest, continent, region, region_flag, current_season, country_code, url')
          .order('name', ascending: true);

      return (response as List)
          .map((row) => LeagueModel.fromJson(row))
          .toList();
    } catch (e) {
      debugPrint("DataRepository Error (Leagues): $e");
      return [];
    }
  }

  Future<LeagueModel?> fetchLeagueById(String leagueId) async {
    try {
      final response = await _supabase
          .from('leagues')
          .select()
          .eq('league_id', leagueId)
          .maybeSingle();

      if (response != null) {
        // Null-safe accessor for 'region' to handle Supabase schema drift (missing column)
        final data = Map<String, dynamic>.from(response);
        if (!data.containsKey('region')) {
          data['region'] = '';
        }
        return LeagueModel.fromJson(data);
      }
      return null;
    } catch (e) {
      debugPrint("DataRepository Error (League by ID): $e");
      return null;
    }
  }

  /// Paginated fetch for all fixtures in a league+season, bypassing the
  /// PostgREST 1,000-row cap. Same pattern as _fetchAllRowsForDate.
  Future<List<dynamic>> _fetchAllRowsForLeague(String leagueId,
      {String? season}) async {
    const pageSize = 1000;
    const maxPages = 20;

    final List<dynamic> allRows = [];
    int from = 0;
    for (int page = 0; page < maxPages; page++) {
      var query = _supabase
          .from('schedules')
          .select()
          .eq('league_id', leagueId);
      if (season != null) {
        query = query.eq('season', season);
      }
      final pageRows = await query
          .order('fixture_id', ascending: true)
          .range(from, from + pageSize - 1);
      final rows = pageRows as List;
      allRows.addAll(rows);
      if (rows.length < pageSize) break;
      from += pageSize;
    }
    return allRows;
  }

  Future<List<MatchModel>> fetchFixturesByLeague(String leagueId,
      {String? season}) async {
    try {
      final rows = await _fetchAllRowsForLeague(leagueId, season: season);

      // Enrich with predictions
      final fixtureIds = rows
          .map((r) => r['fixture_id']?.toString() ?? '')
          .where((id) => id.isNotEmpty)
          .toList();
      final predMap = await _fetchPredictionMap(fixtureIds: fixtureIds);

      final matches = _mergeSchedulesWithPredictions(rows, predMap);

      // Stable sort: match_time ASC, fixture_id ASC
      matches.sort((a, b) {
        final dateCompare = a.date.compareTo(b.date);
        if (dateCompare != 0) return dateCompare;
        final timeCompare = a.time.compareTo(b.time);
        if (timeCompare != 0) return timeCompare;
        return a.fixtureId.compareTo(b.fixtureId);
      });

      return matches;
    } catch (e) {
      debugPrint("DataRepository Error (Fixtures by League): $e");
      return [];
    }
  }
  Future<List<String>> fetchLeagueSeasons(String leagueId) async {
    try {
      // Fetch distinct seasons from schedules for this league
      final response = await _supabase
          .from('schedules')
          .select('season')
          .eq('league_id', leagueId)
          .not('season', 'is', null)
          .order('season', ascending: false);

      final Set<String> seasons = {};
      for (var row in (response as List)) {
        final s = row['season']?.toString() ?? '';
        if (s.isNotEmpty) seasons.add(s);
      }
      return seasons.toList()..sort((a, b) => b.compareTo(a));
    } catch (e) {
      debugPrint("DataRepository Error (League Seasons): $e");
      return [];
    }
  }
}
