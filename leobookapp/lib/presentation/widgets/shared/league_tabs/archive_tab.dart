// archive_tab.dart: Shows available seasons for a league from the schedules table.
// Part of LeoBook App — League Tab Widgets

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:leobookapp/data/repositories/data_repository.dart';
import 'package:leobookapp/core/constants/app_colors.dart';
import 'package:leobookapp/core/widgets/leo_loading_indicator.dart';
import 'package:leobookapp/core/widgets/glass_container.dart';
import 'package:leobookapp/presentation/screens/league_screen.dart';

class LeagueArchiveTab extends StatefulWidget {
  final String leagueId;
  final String leagueName;

  const LeagueArchiveTab({
    super.key,
    required this.leagueId,
    required this.leagueName,
  });

  @override
  State<LeagueArchiveTab> createState() => _LeagueArchiveTabState();
}

class _LeagueArchiveTabState extends State<LeagueArchiveTab> {
  late Future<List<String>> _seasonsFuture;

  @override
  void initState() {
    super.initState();
    _seasonsFuture = context.read<DataRepository>().fetchLeagueSeasons(widget.leagueId);
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return FutureBuilder<List<String>>(
      future: _seasonsFuture,
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const LeoLoadingIndicator(label: 'Loading seasons...');
        }
        if (snapshot.hasError) {
          return Center(child: Text('Error: ${snapshot.error}'));
        }

        final seasons = snapshot.data ?? [];

        if (seasons.isEmpty) {
          return Center(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const Icon(Icons.archive_outlined, size: 48, color: AppColors.textGrey),
                const SizedBox(height: 16),
                Text(
                  "No archived seasons found",
                  style: GoogleFonts.dmSans(color: AppColors.textGrey, fontSize: 14),
                ),
              ],
            ),
          );
        }

        return ListView.builder(
          padding: const EdgeInsets.all(16),
          itemCount: seasons.length,
          itemBuilder: (context, index) {
            final season = seasons[index];
            return Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: GlassContainer(
                borderRadius: 14,
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                interactive: true,
                onTap: () {
                  Navigator.push(
                    context,
                    MaterialPageRoute(
                      builder: (_) => LeagueScreen(
                        leagueId: widget.leagueId,
                        leagueName: widget.leagueName,
                        season: season,
                      ),
                    ),
                  );
                },
                child: Row(
                  children: [
                    Container(
                      width: 40,
                      height: 40,
                      decoration: BoxDecoration(
                        color: AppColors.primary.withValues(alpha: 0.12),
                        borderRadius: BorderRadius.circular(10),
                      ),
                      child: const Icon(
                        Icons.calendar_today_outlined,
                        color: AppColors.primary,
                        size: 18,
                      ),
                    ),
                    const SizedBox(width: 14),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            season,
                            style: GoogleFonts.dmSans(
                              fontSize: 15,
                              fontWeight: FontWeight.w700,
                              color: isDark ? Colors.white : AppColors.textDark,
                            ),
                          ),
                          Text(
                            widget.leagueName,
                            style: GoogleFonts.dmSans(
                              fontSize: 10,
                              color: AppColors.textGrey,
                            ),
                          ),
                        ],
                      ),
                    ),
                    Icon(
                      Icons.chevron_right,
                      color: AppColors.textGrey.withValues(alpha: 0.5),
                      size: 20,
                    ),
                  ],
                ),
              ),
            );
          },
        );
      },
    );
  }
}
