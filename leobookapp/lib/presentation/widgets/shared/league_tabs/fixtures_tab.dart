// fixtures_tab.dart: fixtures_tab.dart: Widget/screen for App — League Tab Widgets.
// Part of LeoBook App — League Tab Widgets
//
// Classes: LeagueFixturesTab, _LeagueFixturesTabState

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:leobookapp/data/models/match_model.dart';
import 'package:leobookapp/data/repositories/data_repository.dart';
import 'package:leobookapp/core/constants/app_colors.dart';
import 'package:leobookapp/core/widgets/leo_shimmer.dart';
import '../match_card.dart';

class LeagueFixturesTab extends StatefulWidget {
  final String leagueId;
  final String leagueName;
  final String? season;
  const LeagueFixturesTab({
    super.key,
    required this.leagueId,
    required this.leagueName,
    this.season,
  });

  @override
  State<LeagueFixturesTab> createState() => _LeagueFixturesTabState();
}

class _LeagueFixturesTabState extends State<LeagueFixturesTab> {
  late Future<List<MatchModel>> _matchesFuture;

  @override
  void initState() {
    super.initState();
    _matchesFuture = _loadFixtures();
  }

  Future<List<MatchModel>> _loadFixtures() async {
    final repo = context.read<DataRepository>();
    final allMatches = await repo.fetchFixturesByLeague(
      widget.leagueId,
      season: widget.season,
    );
    // Only upcoming/scheduled (exclude finished)
    return allMatches
        .where((m) =>
            m.status != 'Finished' &&
            m.displayStatus != 'FINISHED' &&
            !m.isFinished)
        .toList()
      ..sort((a, b) {
        try {
          return DateTime.parse(a.date).compareTo(DateTime.parse(b.date));
        } catch (_) {
          return 0;
        }
      });
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<List<MatchModel>>(
      future: _matchesFuture,
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
                Icon(Icons.sports_soccer, size: 48, color: AppColors.textGrey),
                const SizedBox(height: 16),
                Text(
                  "No fixtures found",
                  style: GoogleFonts.lexend(
                    color: AppColors.textGrey,
                    fontSize: 14,
                  ),
                ),
              ],
            ),
          );
        }

        // Group fixtures by month for stage-like display
        final Map<String, List<MatchModel>> grouped = {};
        for (final m in matches) {
          String monthKey;
          try {
            final dt = DateTime.parse(m.date);
            const months = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN',
                            'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC'];
            monthKey = '${months[dt.month - 1]} ${dt.year}';
          } catch (_) {
            monthKey = 'UPCOMING';
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
              cursor++;
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
