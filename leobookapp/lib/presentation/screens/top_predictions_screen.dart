// top_predictions_screen.dart: top_predictions_screen.dart: Widget/screen for App — Screens.
// Part of LeoBook App — Screens
//
// Classes: TopPredictionsScreen

import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:leobookapp/core/constants/app_colors.dart';
import 'package:leobookapp/core/constants/responsive_constants.dart';
import 'package:leobookapp/data/models/recommendation_model.dart';
import 'package:leobookapp/data/models/match_model.dart';
import 'package:leobookapp/logic/cubit/home_cubit.dart';
import '../widgets/shared/recommendation_card.dart';
import 'package:leobookapp/core/widgets/leo_loading_indicator.dart';
import 'match_details_screen.dart';
import '../widgets/shared/recommendation_filter_modal.dart';
import '../widgets/shared/sport_switcher.dart';

/// Unified Top Predictions screen — lives inside MainScreen's IndexedStack.
/// No own Scaffold/AppBar. Shows recommendations for SCHEDULED matches,
/// sorted by time (latest first).
class TopPredictionsScreen extends StatelessWidget {
  const TopPredictionsScreen({super.key});

  void _navigateToMatch(
    BuildContext context,
    RecommendationModel rec,
    List<MatchModel> allMatches,
  ) {
    MatchModel? match;
    try {
      match = allMatches.firstWhere(
        (m) => m.fixtureId == rec.fixtureId && rec.fixtureId.isNotEmpty,
      );
    } catch (_) {
      try {
        match = allMatches.firstWhere(
          (m) =>
              rec.match.toLowerCase().contains(m.homeTeam.toLowerCase()) &&
              rec.match.toLowerCase().contains(m.awayTeam.toLowerCase()),
        );
      } catch (_) {}
    }

    if (match != null) {
      Navigator.push(
        context,
        MaterialPageRoute(builder: (_) => MatchDetailsScreen(match: match!)),
      );
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text("Match details not found in schedule.")),
      );
    }
  }

  void _showFilterModal(BuildContext context, HomeLoaded state) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => RecommendationFilterModal(
        initialLeagues: state.selectedLeagues,
        initialPredictionTypes: state.selectedPredictionTypes,
        initialMinOdds: state.minOdds,
        initialMaxOdds: state.maxOdds,
        initialMinReliability: state.minReliability,
        initialConfidenceLevels: state.selectedConfidenceLevels,
        initialOnlyAvailable: state.onlyAvailable,
        availableLeagues: state.availableLeagues,
        availablePredictionTypes: state.availablePredictionTypes,
        onApply: ({
          required leagues,
          required types,
          required minOdds,
          required maxOdds,
          required minReliability,
          required confidenceLevels,
          required onlyAvailable,
        }) {
          context.read<HomeCubit>().applyFilters(
            leagues: leagues,
            types: types,
            minOdds: minOdds,
            maxOdds: maxOdds,
            minReliability: minReliability,
            confidenceLevels: confidenceLevels,
            onlyAvailable: onlyAvailable,
          );
        },
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return BlocBuilder<HomeCubit, HomeState>(
      builder: (context, state) {
        if (state is! HomeLoaded) {
          return const LeoLoadingIndicator(label: 'Loading predictions...');
        }

        // Use filtered recommendations
        final recs = List<RecommendationModel>.from(state.filteredRecommendations);

        // Optional: Filter for upcoming only if desirable,
        // but often 'Top Predictions' includes the most relevant ones.
        // We sort by time (latest first as requested before).
        recs.sort((a, b) => b.time.compareTo(a.time));

        return Column(
          children: [
            // ── Header Row ──
            Padding(
              padding: EdgeInsets.fromLTRB(
                Responsive.sp(context, 14),
                Responsive.sp(context, 14),
                Responsive.sp(context, 14),
                Responsive.sp(context, 8),
              ),
              child: Row(
                children: [
                  Icon(
                    Icons.auto_awesome,
                    color: AppColors.primary,
                    size: Responsive.sp(context, 16),
                  ),
                  SizedBox(width: Responsive.sp(context, 6)),
                  Expanded(
                    child: Text(
                      "TOP PREDICTIONS",
                      style: TextStyle(
                        fontSize: Responsive.sp(context, 13),
                        fontWeight: FontWeight.w900,
                        letterSpacing: 1.5,
                        color: Colors.white,
                      ),
                    ),
                  ),
                  
                  // Filter Button
                  IconButton(
                    onPressed: () => _showFilterModal(context, state),
                    icon: Icon(
                      Icons.tune,
                      color: state.selectedLeagues.isNotEmpty || 
                             state.selectedPredictionTypes.isNotEmpty ||
                             state.minReliability > 0 ||
                             state.onlyAvailable ||
                             state.minOdds > 1.0 ||
                             state.maxOdds < 10.0
                          ? AppColors.primary 
                          : Colors.white70,
                      size: Responsive.sp(context, 20),
                    ),
                    tooltip: "Filter Predictions",
                  ),
                ],
              ),
            ),

            // ── Sport Switcher ──
            const SportSwitcher(),
            SizedBox(height: Responsive.sp(context, 4)),

            if (recs.isEmpty)
              Expanded(
                child: Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(
                        Icons.search_off,
                        size: Responsive.sp(context, 48),
                        color: Colors.white24,
                      ),
                      SizedBox(height: Responsive.sp(context, 16)),
                      Text(
                        "No matching predictions found",
                        style: TextStyle(
                          color: Colors.white70,
                          fontSize: Responsive.sp(context, 14),
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                      SizedBox(height: Responsive.sp(context, 8)),
                      TextButton(
                        onPressed: () => context.read<HomeCubit>().resetFilters(),
                        child: const Text("Reset Filters"),
                      ),
                    ],
                  ),
                ),
              )
            else
              Expanded(
                child: ListView.builder(
                  padding: EdgeInsets.zero,
                  itemCount: recs.length,
                  itemBuilder: (context, index) {
                    final rec = recs[index];
                    return Padding(
                      padding: EdgeInsets.symmetric(
                        horizontal: Responsive.sp(context, 12),
                        vertical: Responsive.sp(context, 6),
                      ),
                      child: RecommendationCard(
                        recommendation: rec,
                        onTap: () => _navigateToMatch(
                          context,
                          rec,
                          state.allMatches,
                        ),
                      ),
                    );
                  },
                ),
              ),
          ],
        );
      },
    );
  }
}
