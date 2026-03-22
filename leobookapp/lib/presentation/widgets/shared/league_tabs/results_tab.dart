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
    final allMatches = await repo.fetchFixturesByLeague(
      widget.leagueId,
      season: widget.season,
    );
    return allMatches
        .where((m) =>
            m.status == 'Finished' ||
            m.displayStatus == 'FINISHED' ||
            m.isFinished)
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

        // Group matches by month for stage-like display
        final Map<String, List<MatchModel>> grouped = {};
        for (final m in matches) {
          String monthKey;
          try {
            final dt = DateTime.parse(m.date);
            const months = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN',
                            'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC'];
            monthKey = '${months[dt.month - 1]} ${dt.year}';
          } catch (_) {
            monthKey = 'UNKNOWN';
          }
          grouped.putIfAbsent(monthKey, () => []).add(m);
        }
        final sections = grouped.entries.toList();

        return ListView.builder(
          padding: const EdgeInsets.only(top: 16, bottom: 100),
          itemCount: sections.fold<int>(0, (sum, e) => sum + 1 + e.value.length),
          itemBuilder: (context, index) {
            int cursor = 0;
            for (final section in sections) {
              if (index == cursor) {
                // Section header
                return Padding(
                  padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
                  child: Text(
                    section.key,
                    style: GoogleFonts.lexend(
                      fontSize: 11,
                      fontWeight: FontWeight.w800,
                      color: AppColors.primary,
                      letterSpacing: 1.5,
                    ),
                  ),
                );
              }
              cursor++; // header
              if (index < cursor + section.value.length) {
                final match = section.value[index - cursor];
                return Padding(
                  padding: const EdgeInsets.only(bottom: 4),
                  child: MatchCard(match: match),
                );
              }
              cursor += section.value.length;
            }
            return const SizedBox.shrink();
          },
        );
      },
    );
  }
}
