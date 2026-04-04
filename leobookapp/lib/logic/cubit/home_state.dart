// home_state.dart: State classes for HomeCubit.
// Part of LeoBook App — State Management (Cubit)

import 'package:leobookapp/data/models/match_model.dart';
import 'package:leobookapp/data/models/news_model.dart';
import 'package:leobookapp/data/models/recommendation_model.dart';

abstract class HomeState {}

class HomeInitial extends HomeState {}

class HomeLoading extends HomeState {}

class HomeLoaded extends HomeState {
  final List<MatchModel> allMatches;
  final List<MatchModel> filteredMatches;
  final List<MatchModel> featuredMatches;
  final List<MatchModel> liveMatches;
  final List<NewsModel> news;
  final List<RecommendationModel> allRecommendations;
  final List<RecommendationModel> filteredRecommendations;
  final DateTime selectedDate;
  final String selectedSport;
  final List<String> availableSports;
  final bool isAllMatchesExpanded;

  // Advanced Filters
  final List<String> selectedLeagues;
  final List<String> selectedPredictionTypes;
  final double minOdds;
  final double maxOdds;
  final double minReliability;
  final List<String> selectedConfidenceLevels;
  final bool onlyAvailable;

  // Available Filter Options
  final List<String> availableLeagues;
  final List<String> availablePredictionTypes;

  HomeLoaded({
    required this.allMatches,
    required this.filteredMatches,
    required this.featuredMatches,
    this.liveMatches = const [],
    this.news = const [],
    required this.allRecommendations,
    required this.filteredRecommendations,
    required this.selectedDate,
    this.selectedSport = 'ALL',
    this.availableSports = const ['ALL'],
    this.isAllMatchesExpanded = false,
    this.selectedLeagues = const [],
    this.selectedPredictionTypes = const [],
    this.minOdds = 1.0,
    this.maxOdds = 10.0,
    this.minReliability = 0.0,
    this.selectedConfidenceLevels = const [],
    this.onlyAvailable = false,
    this.availableLeagues = const [],
    this.availablePredictionTypes = const [],
  });
}

class HomeError extends HomeState {
  final String message;
  HomeError(this.message);
}
