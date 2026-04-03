// home_cubit.dart: HomeCubit — dashboard data loading and realtime subscriptions.
// Part of LeoBook App — State Management (Cubit)

import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:leobookapp/data/models/match_model.dart';
import 'package:leobookapp/data/repositories/data_repository.dart';
import 'package:leobookapp/data/repositories/news_repository.dart';

import 'home_state.dart';
import 'home_filter.dart';

export 'home_state.dart';

class HomeCubit extends Cubit<HomeState> {
  final DataRepository _dataRepository;
  final NewsRepository _newsRepository;
  StreamSubscription? _predictionsSub;
  StreamSubscription? _liveScoresSub;
  StreamSubscription? _schedulesSub;
  StreamSubscription? _teamCrestsSub;
  Timer? _refreshTimer;
  bool _isRefreshing = false;

  HomeCubit(this._dataRepository, this._newsRepository) : super(HomeInitial());

  Future<void> loadDashboard() async {
    emit(HomeLoading());
    try {
      final now = DateTime.now();

      // Fetch news once
      final news = await _newsRepository.fetchNews();

      // Try fetching predictions for today
      List<MatchModel> matches = await _dataRepository.fetchMatches(date: now);
      List<RecommendationModel> recommendations =
          await _dataRepository.fetchRecommendations();

      DateTime selectionDate = now;

      // If no matches for today, find the most recent date with predictions
      if (matches.isEmpty) {
        final allRecent =
            await _dataRepository.fetchMatches(); // Get latest 200
        if (allRecent.isNotEmpty) {
          final latestDateStr = allRecent
              .map((m) => m.date)
              .reduce((a, b) => a.compareTo(b) > 0 ? a : b);
          selectionDate = DateTime.parse(latestDateStr);
          matches = allRecent.where((m) => m.date == latestDateStr).toList();
        }
      }

      const defaultSport = 'ALL';
      final filteredRecs = filterRecommendations(
        recommendations,
        selectionDate,
        defaultSport,
      );

      final live = matches.where((m) => m.isLive).toList();

      // Featured logic
      final featured = matches
          .where((m) => m.confidence != null && m.confidence!.contains('High'))
          .toList();

      final sportsSet = {'ALL'};
      final leaguesSet = <String>{};
      final typesSet = <String>{};

      for (var m in matches) {
        sportsSet.add(m.sport.toUpperCase());
        if (m.league != null) leaguesSet.add(m.league!);
        if (m.prediction != null) typesSet.add(m.prediction!);
      }
      for (var r in recommendations) {
        sportsSet.add(r.sport.toUpperCase());
        leaguesSet.add(r.league);
        typesSet.add(r.prediction);
      }
      final availableSports = sportsSet.toList()..sort();
      final availableLeagues = leaguesSet.toList()..sort();
      final availablePredictionTypes = typesSet.toList()..sort();

      emit(
        HomeLoaded(
          allMatches: matches,
          filteredMatches: matches,
          featuredMatches: featured,
          liveMatches: live,
          news: news,
          allRecommendations: recommendations,
          filteredRecommendations: filteredRecs,
          selectedDate: selectionDate,
          selectedSport: defaultSport,
          availableSports: availableSports,
          isAllMatchesExpanded: false,
          availableLeagues: availableLeagues,
          availablePredictionTypes: availablePredictionTypes,
        ),
      );

      // --- Start Realtime Subscriptions (skip on Web — broken realtime_client) ---
      _predictionsSub?.cancel();
      _liveScoresSub?.cancel();
      _schedulesSub?.cancel();
      _teamCrestsSub?.cancel();
      _predictionsSub = null;
      _liveScoresSub = null;
      _schedulesSub = null;
      _teamCrestsSub = null;

      _predictionsSub = _dataRepository
          .watchPredictions(date: selectionDate)
          .listen((updatedMatches) {
        _handleRealtimeUpdate(updatedMatches);
      }, onError: (e) {
        debugPrint("Predictions Stream Error: $e");
      });

      _liveScoresSub = _dataRepository.watchLiveScores().listen((liveUpdates) {
        _handleRealtimeUpdate(liveUpdates);
      }, onError: (e) {
        debugPrint("LiveScores Stream Error: $e");
      });

      _schedulesSub = _dataRepository
          .watchSchedules(date: selectionDate)
          .listen((scheduleUpdates) {
        _handleRealtimeUpdate(scheduleUpdates);
      }, onError: (e) {
        debugPrint("Schedules Stream Error: $e");
      });

      _teamCrestsSub =
          _dataRepository.watchTeamCrestUpdates().listen((crestMap) {
        _handleCrestUpdate(crestMap);
      }, onError: (e) {
        debugPrint("TeamCrests Stream Error: $e");
      });

      // --- Start 15-second periodic refresh (upsert-only, skips if no changes) ---
      _refreshTimer?.cancel();
      _refreshTimer = Timer.periodic(
        const Duration(seconds: 15),
        (_) => _periodicRefresh(),
      );
    } catch (e) {
      emit(HomeError("Failed to load dashboard: $e"));
    }
  }

  /// Periodic background refresh — fetches latest data and upserts only changed matches.
  Future<void> _periodicRefresh() async {
    if (isClosed || _isRefreshing || state is! HomeLoaded) return;
    _isRefreshing = true;
    try {
      final currentState = state as HomeLoaded;
      final freshMatches =
          await _dataRepository.fetchMatches(date: currentState.selectedDate);

      // Guard: if we have good data and fresh fetch is suspiciously small,
      // it's likely a transient Supabase timeout — skip this refresh cycle.
      if (freshMatches.isEmpty || isClosed) return;
      if (currentState.allMatches.length > 10 &&
          freshMatches.length < currentState.allMatches.length * 0.3) {
        debugPrint('Periodic refresh: skipping suspicious result '
            '(${freshMatches.length} vs ${currentState.allMatches.length})');
        return;
      }

      // Upsert: only merge if data actually changed
      final Map<String, MatchModel> matchMap = {
        for (var m in currentState.allMatches) m.fixtureId: m,
      };

      bool anyChanged = false;
      for (var fresh in freshMatches) {
        final existing = matchMap[fresh.fixtureId];
        if (existing == null) {
          matchMap[fresh.fixtureId] = fresh;
          anyChanged = true;
        } else {
          // Compare key volatile fields
          if (existing.status != fresh.status ||
              existing.homeScore != fresh.homeScore ||
              existing.awayScore != fresh.awayScore ||
              existing.liveMinute != fresh.liveMinute ||
              existing.odds != fresh.odds ||
              existing.prediction != fresh.prediction) {
            matchMap[fresh.fixtureId] = existing.mergeWith(fresh);
            anyChanged = true;
          }
        }
      }

      if (!anyChanged || isClosed) return;

      final mergedMatches = matchMap.values.toList();
      final filteredMatches = filterMatches(
        mergedMatches,
        currentState.selectedDate,
        currentState.selectedSport,
        leagues: currentState.selectedLeagues,
        types: currentState.selectedPredictionTypes,
        minO: currentState.minOdds,
        maxO: currentState.maxOdds,
        minRel: currentState.minReliability,
        confs: currentState.selectedConfidenceLevels,
        onlyAvail: currentState.onlyAvailable,
      );

      emit(HomeLoaded(
        allMatches: mergedMatches,
        filteredMatches: filteredMatches,
        featuredMatches: mergedMatches
            .where(
                (m) => m.confidence != null && m.confidence!.contains('High'))
            .toList(),
        liveMatches: mergedMatches.where((m) => m.isLive).toList(),
        news: currentState.news,
        allRecommendations: currentState.allRecommendations,
        filteredRecommendations: currentState.filteredRecommendations,
        selectedDate: currentState.selectedDate,
        selectedSport: currentState.selectedSport,
        availableSports: currentState.availableSports,
        isAllMatchesExpanded: currentState.isAllMatchesExpanded,
        selectedLeagues: currentState.selectedLeagues,
        selectedPredictionTypes: currentState.selectedPredictionTypes,
        minOdds: currentState.minOdds,
        maxOdds: currentState.maxOdds,
        minReliability: currentState.minReliability,
        selectedConfidenceLevels: currentState.selectedConfidenceLevels,
        onlyAvailable: currentState.onlyAvailable,
        availableLeagues: currentState.availableLeagues,
        availablePredictionTypes: currentState.availablePredictionTypes,
      ));
    } catch (e) {
      debugPrint('Periodic refresh error: $e');
    } finally {
      _isRefreshing = false;
    }
  }

  void _handleRealtimeUpdate(List<MatchModel> updatedMatches) {
    if (state is HomeLoaded) {
      final currentState = state as HomeLoaded;

      // Merge updated matches into the current state preservation prediction data
      final Map<String, MatchModel> matchMap = {
        for (var m in currentState.allMatches) m.fixtureId: m,
      };

      for (var updated in updatedMatches) {
        final existing = matchMap[updated.fixtureId];
        if (existing != null) {
          matchMap[updated.fixtureId] = existing.mergeWith(updated);
        } else if (updated.homeTeam.isNotEmpty &&
            updated.awayTeam.isNotEmpty &&
            updated.date.isNotEmpty) {
          matchMap[updated.fixtureId] = updated;
        }
      }

      final mergedMatches = matchMap.values.toList();

      final filteredMatches = filterMatches(
        mergedMatches,
        currentState.selectedDate,
        currentState.selectedSport,
        leagues: currentState.selectedLeagues,
        types: currentState.selectedPredictionTypes,
        minO: currentState.minOdds,
        maxO: currentState.maxOdds,
        minRel: currentState.minReliability,
        confs: currentState.selectedConfidenceLevels,
        onlyAvail: currentState.onlyAvailable,
      );

      final live = mergedMatches.where((m) => m.isLive).toList();
      final featured = mergedMatches
          .where((m) => m.confidence != null && m.confidence!.contains('High'))
          .toList();

      emit(
        HomeLoaded(
          allMatches: mergedMatches,
          filteredMatches: filteredMatches,
          featuredMatches: featured,
          liveMatches: live,
          news: currentState.news,
          allRecommendations: currentState.allRecommendations,
          filteredRecommendations: currentState.filteredRecommendations,
          selectedDate: currentState.selectedDate,
          selectedSport: currentState.selectedSport,
          availableSports: currentState.availableSports,
          isAllMatchesExpanded: currentState.isAllMatchesExpanded,
          selectedLeagues: currentState.selectedLeagues,
          selectedPredictionTypes: currentState.selectedPredictionTypes,
          minOdds: currentState.minOdds,
          maxOdds: currentState.maxOdds,
          minReliability: currentState.minReliability,
          selectedConfidenceLevels: currentState.selectedConfidenceLevels,
          onlyAvailable: currentState.onlyAvailable,
          availableLeagues: currentState.availableLeagues,
          availablePredictionTypes: currentState.availablePredictionTypes,
        ),
      );
    }
  }

  void updateDate(DateTime date) async {
    if (state is HomeLoaded) {
      final currentState = state as HomeLoaded;

      final matches = await _dataRepository.fetchMatches(date: date);

      final filteredMatches = filterMatches(
        matches,
        date,
        currentState.selectedSport,
        leagues: currentState.selectedLeagues,
        types: currentState.selectedPredictionTypes,
        minO: currentState.minOdds,
        maxO: currentState.maxOdds,
        minRel: currentState.minReliability,
        confs: currentState.selectedConfidenceLevels,
        onlyAvail: currentState.onlyAvailable,
      );

      final filteredRecs = filterRecommendations(
        currentState.allRecommendations,
        date,
        currentState.selectedSport,
        leagues: currentState.selectedLeagues,
        types: currentState.selectedPredictionTypes,
        minO: currentState.minOdds,
        maxO: currentState.maxOdds,
        minRel: currentState.minReliability,
        confs: currentState.selectedConfidenceLevels,
        onlyAvail: currentState.onlyAvailable,
      );

      final featured = filteredMatches
          .where((m) => m.confidence != null && m.confidence!.contains('High'))
          .toList();

      final sportsSet = {'ALL'};
      final leaguesSet = <String>{};
      final typesSet = <String>{};

      for (var m in matches) {
        sportsSet.add(m.sport.toUpperCase());
        if (m.league != null) leaguesSet.add(m.league!);
        if (m.prediction != null) typesSet.add(m.prediction!);
      }
      for (var r in currentState.allRecommendations) {
        sportsSet.add(r.sport.toUpperCase());
        leaguesSet.add(r.league);
        typesSet.add(r.prediction);
      }
      final availableSports = sportsSet.toList()..sort();
      final availableLeagues = leaguesSet.toList()..sort();
      final availablePredictionTypes = typesSet.toList()..sort();

      emit(
        HomeLoaded(
          allMatches: matches,
          filteredMatches: filteredMatches,
          featuredMatches: featured,
          liveMatches: matches.where((m) => m.isLive).toList(),
          news: currentState.news,
          allRecommendations: currentState.allRecommendations,
          filteredRecommendations: filteredRecs,
          selectedDate: date,
          selectedSport: currentState.selectedSport,
          availableSports: availableSports,
          isAllMatchesExpanded: false,
          selectedLeagues: currentState.selectedLeagues,
          selectedPredictionTypes: currentState.selectedPredictionTypes,
          minOdds: currentState.minOdds,
          maxOdds: currentState.maxOdds,
          minReliability: currentState.minReliability,
          selectedConfidenceLevels: currentState.selectedConfidenceLevels,
          onlyAvailable: currentState.onlyAvailable,
          availableLeagues: availableLeagues,
          availablePredictionTypes: availablePredictionTypes,
        ),
      );

      // Re-subscribe for the new date
      _predictionsSub?.cancel();
      _schedulesSub?.cancel();
      _predictionsSub = null;
      _schedulesSub = null;

      // Delay slightly to allow the previous channel to leave cleanly
      await Future.delayed(const Duration(milliseconds: 300));

      if (isClosed) return;

      _predictionsSub =
          _dataRepository.watchPredictions(date: date).listen((updatedMatches) {
        _handleRealtimeUpdate(updatedMatches);
      }, onError: (e) {
        debugPrint("Predictions Stream (Update) Error: $e");
      });

      _schedulesSub =
          _dataRepository.watchSchedules(date: date).listen((scheduleUpdates) {
        _handleRealtimeUpdate(scheduleUpdates);
      }, onError: (e) {
        debugPrint("Schedules Stream (Update) Error: $e");
      });
    }
  }

  void updateSport(String sport) {
    if (state is HomeLoaded) {
      final currentState = state as HomeLoaded;

      final filteredMatches = filterMatches(
        currentState.allMatches,
        currentState.selectedDate,
        sport,
        leagues: currentState.selectedLeagues,
        types: currentState.selectedPredictionTypes,
        minO: currentState.minOdds,
        maxO: currentState.maxOdds,
        minRel: currentState.minReliability,
        confs: currentState.selectedConfidenceLevels,
        onlyAvail: currentState.onlyAvailable,
      );
      final filteredRecs = filterRecommendations(
        currentState.allRecommendations,
        currentState.selectedDate,
        sport,
        leagues: currentState.selectedLeagues,
        types: currentState.selectedPredictionTypes,
        minO: currentState.minOdds,
        maxO: currentState.maxOdds,
        minRel: currentState.minReliability,
        confs: currentState.selectedConfidenceLevels,
        onlyAvail: currentState.onlyAvailable,
      );

      final featured = filteredMatches
          .where((m) => m.confidence != null && m.confidence!.contains('High'))
          .toList();

      emit(
        HomeLoaded(
          allMatches: currentState.allMatches,
          filteredMatches: filteredMatches,
          featuredMatches: featured,
          liveMatches: currentState.liveMatches,
          news: currentState.news,
          allRecommendations: currentState.allRecommendations,
          filteredRecommendations: filteredRecs,
          selectedDate: currentState.selectedDate,
          selectedSport: sport,
          availableSports: currentState.availableSports,
          isAllMatchesExpanded: false,
          selectedLeagues: currentState.selectedLeagues,
          selectedPredictionTypes: currentState.selectedPredictionTypes,
          minOdds: currentState.minOdds,
          maxOdds: currentState.maxOdds,
          minReliability: currentState.minReliability,
          selectedConfidenceLevels: currentState.selectedConfidenceLevels,
          onlyAvailable: currentState.onlyAvailable,
          availableLeagues: currentState.availableLeagues,
          availablePredictionTypes: currentState.availablePredictionTypes,
        ),
      );
    }
  }

  void applyFilters({
    required List<String> leagues,
    required List<String> types,
    required double minOdds,
    required double maxOdds,
    required double minReliability,
    required List<String> confidenceLevels,
    required bool onlyAvailable,
  }) {
    if (state is HomeLoaded) {
      final currentState = state as HomeLoaded;

      final filteredMatches = filterMatches(
        currentState.allMatches,
        currentState.selectedDate,
        currentState.selectedSport,
        minO: minOdds,
        maxO: maxOdds,
        minRel: minReliability,
        confs: confidenceLevels,
        onlyAvail: onlyAvailable,
      );
      final filteredRecs = filterRecommendations(
        currentState.allRecommendations,
        currentState.selectedDate,
        currentState.selectedSport,
        leagues: leagues,
        types: types,
        minO: minOdds,
        maxO: maxOdds,
        minRel: minReliability,
        confs: confidenceLevels,
        onlyAvail: onlyAvailable,
      );

      final featured = filteredMatches
          .where((m) => m.confidence != null && m.confidence!.contains('High'))
          .toList();

      emit(
        HomeLoaded(
          allMatches: currentState.allMatches,
          filteredMatches: filteredMatches,
          featuredMatches: featured,
          liveMatches: currentState.liveMatches,
          news: currentState.news,
          allRecommendations: currentState.allRecommendations,
          filteredRecommendations: filteredRecs,
          selectedDate: currentState.selectedDate,
          selectedSport: currentState.selectedSport,
          availableSports: currentState.availableSports,
          isAllMatchesExpanded: currentState.isAllMatchesExpanded,
          selectedLeagues: leagues,
          selectedPredictionTypes: types,
          minOdds: minOdds,
          maxOdds: maxOdds,
          minReliability: minReliability,
          selectedConfidenceLevels: confidenceLevels,
          onlyAvailable: onlyAvailable,
          availableLeagues: currentState.availableLeagues,
          availablePredictionTypes: currentState.availablePredictionTypes,
        ),
      );
    }
  }

  void resetFilters() {
    if (state is HomeLoaded) {
      final currentState = state as HomeLoaded;
      updateSport(
        currentState.selectedSport,
      ); // This will effectively reset if we pass empty filters
    }
  }

  void toggleAllMatchesExpansion() {
    if (state is HomeLoaded) {
      final currentState = state as HomeLoaded;
      emit(
        HomeLoaded(
          allMatches: currentState.allMatches,
          filteredMatches: currentState.filteredMatches,
          featuredMatches: currentState.featuredMatches,
          liveMatches: currentState.liveMatches,
          news: currentState.news,
          allRecommendations: currentState.allRecommendations,
          filteredRecommendations: currentState.filteredRecommendations,
          selectedDate: currentState.selectedDate,
          selectedSport: currentState.selectedSport,
          availableSports: currentState.availableSports,
          isAllMatchesExpanded: !currentState.isAllMatchesExpanded,
          selectedLeagues: currentState.selectedLeagues,
          selectedPredictionTypes: currentState.selectedPredictionTypes,
          minOdds: currentState.minOdds,
          maxOdds: currentState.maxOdds,
          minReliability: currentState.minReliability,
          selectedConfidenceLevels: currentState.selectedConfidenceLevels,
          onlyAvailable: currentState.onlyAvailable,
          availableLeagues: currentState.availableLeagues,
          availablePredictionTypes: currentState.availablePredictionTypes,
        ),
      );
    }
  }

  void _handleCrestUpdate(Map<String, String> crestMap) {
    if (state is HomeLoaded && crestMap.isNotEmpty) {
      final currentState = state as HomeLoaded;
      final updatedMatches = currentState.allMatches.map((m) {
        final homeCrest = crestMap[m.homeTeam] ?? m.homeCrestUrl;
        final awayCrest = crestMap[m.awayTeam] ?? m.awayCrestUrl;
        if (homeCrest != m.homeCrestUrl || awayCrest != m.awayCrestUrl) {
          return MatchModel(
            fixtureId: m.fixtureId,
            date: m.date,
            time: m.time,
            homeTeam: m.homeTeam,
            awayTeam: m.awayTeam,
            homeTeamId: m.homeTeamId,
            awayTeamId: m.awayTeamId,
            homeScore: m.homeScore,
            awayScore: m.awayScore,
            status: m.status,
            sport: m.sport,
            league: m.league,
            prediction: m.prediction,
            odds: m.odds,
            confidence: m.confidence,
            liveMinute: m.liveMinute,
            isFeatured: m.isFeatured,
            valueTag: m.valueTag,
            homeCrestUrl: homeCrest,
            awayCrestUrl: awayCrest,
            regionFlagUrl: m.regionFlagUrl,
            reliabilityScore: m.reliabilityScore,
            xgHome: m.xgHome,
            xgAway: m.xgAway,
            reasonTags: m.reasonTags,
            homeFormN: m.homeFormN,
            awayFormN: m.awayFormN,
            outcomeCorrect: m.outcomeCorrect,
          );
        }
        return m;
      }).toList();

      emit(
        HomeLoaded(
          allMatches: updatedMatches,
          filteredMatches: filterMatches(
            updatedMatches,
            currentState.selectedDate,
            currentState.selectedSport,
            leagues: currentState.selectedLeagues,
            types: currentState.selectedPredictionTypes,
            minO: currentState.minOdds,
            maxO: currentState.maxOdds,
            minRel: currentState.minReliability,
            confs: currentState.selectedConfidenceLevels,
            onlyAvail: currentState.onlyAvailable,
          ),
          featuredMatches: updatedMatches
              .where(
                  (m) => m.confidence != null && m.confidence!.contains('High'))
              .toList(),
          liveMatches: updatedMatches.where((m) => m.isLive).toList(),
          news: currentState.news,
          allRecommendations: currentState.allRecommendations,
          filteredRecommendations: currentState.filteredRecommendations,
          selectedDate: currentState.selectedDate,
          selectedSport: currentState.selectedSport,
          availableSports: currentState.availableSports,
          isAllMatchesExpanded: currentState.isAllMatchesExpanded,
          selectedLeagues: currentState.selectedLeagues,
          selectedPredictionTypes: currentState.selectedPredictionTypes,
          minOdds: currentState.minOdds,
          maxOdds: currentState.maxOdds,
          minReliability: currentState.minReliability,
          selectedConfidenceLevels: currentState.selectedConfidenceLevels,
          onlyAvailable: currentState.onlyAvailable,
          availableLeagues: currentState.availableLeagues,
          availablePredictionTypes: currentState.availablePredictionTypes,
        ),
      );
    }
  }

  @override
  Future<void> close() async {
    _refreshTimer?.cancel();
    _refreshTimer = null;
    for (final sub in [
      _predictionsSub,
      _liveScoresSub,
      _schedulesSub,
      _teamCrestsSub
    ]) {
      try {
        await sub?.cancel();
      } catch (e) {
        debugPrint("Error canceling subscription: $e");
      }
    }
    _predictionsSub = null;
    _liveScoresSub = null;
    _schedulesSub = null;
    _teamCrestsSub = null;
    return super.close();
  }
}
