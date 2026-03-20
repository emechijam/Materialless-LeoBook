// results_tab.dart: Shows completed (finished) matches for a league.
// Part of LeoBook App — League Tab Widgets

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:leobookapp/data/models/match_model.dart';
import 'package:leobookapp/data/repositories/data_repository.dart';
import 'package:leobookapp/core/constants/app_colors.dart';
import 'package:leobookapp/core/widgets/leo_shimmer.dart';
import '../match_card.dart';

class LeagueResultsTab extends StatefulWidget {
  final String leagueId;
  final String leagueName;
  final String? season;

  const LeagueResultsTab({
    super.key,
    required this.leagueId,
    required this.leagueName,
    this.season,
  });

  @override
  State<LeagueResultsTab> createState() => _LeagueResultsTabState();
}

class _LeagueResultsTabState extends State<LeagueResultsTab> {
  late Future<List<MatchModel>> _resultsFuture;

  @override
  void initState() {
    super.initState();
    _resultsFuture = _loadResults();
  }

  Future<List<MatchModel>> _loadResults() async {
    final repo = context.read<DataRepository>();
    final allMatches = await repo.fetchMatches();
    return allMatches
        .where((m) =>
            (m.leagueId == widget.leagueId || m.league == widget.leagueName) &&
            (m.status == 'Finished' ||
                m.displayStatus == 'FINISHED' ||
                m.isFinished))
        .toList()
      ..sort((a, b) {
        try {
          return DateTime.parse(b.date).compareTo(DateTime.parse(a.date));
        } catch (_) {
          return 0;
        }
      });
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<List<MatchModel>>(
      future: _resultsFuture,
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const MatchListSkeleton();
        }
        if (snapshot.hasError) {
          return Center(child: Text('Error: ${snapshot.error}'));
        }

        final matches = snapshot.data ?? [];

        if (matches.isEmpty) {
          return Center(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const Icon(Icons.scoreboard_outlined,
                    size: 48, color: AppColors.textGrey),
                const SizedBox(height: 16),
                Text(
                  "No results found",
                  style: GoogleFonts.lexend(
                    color: AppColors.textGrey,
                    fontSize: 14,
                  ),
                ),
              ],
            ),
          );
        }

        return ListView.builder(
          padding: const EdgeInsets.only(top: 16, bottom: 32),
          itemCount: matches.length,
          itemBuilder: (context, index) {
            return Padding(
              padding: const EdgeInsets.only(bottom: 4),
              child: MatchCard(match: matches[index]),
            );
          },
        );
      },
    );
  }
}
