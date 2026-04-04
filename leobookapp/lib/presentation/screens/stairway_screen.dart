// stairway_screen.dart: Project Stairway — step/cycle/ROI dashboard.
// Part of LeoBook App — Screens
//
// Shows current cycle stats, today's recommended picks, and historical ROI.
// Pro-gated via TierGate (canAccessChapter2).

import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import 'package:leobookapp/core/constants/app_colors.dart';
import 'package:leobookapp/data/models/recommendation_model.dart';
import 'package:leobookapp/logic/cubit/home_cubit.dart';
import 'package:leobookapp/presentation/widgets/shared/tier_gate.dart';

class StairwayScreen extends StatelessWidget {
  const StairwayScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return const TierGate(
      requirement: TierRequirement.canAccessChapter2,
      featureName: 'Project Stairway',
      featureDescription:
          'Track every cycle, stake, and ROI on your growth journey. Pro only.',
      child: _StairwayContent(),
    );
  }
}

class _StairwayContent extends StatefulWidget {
  const _StairwayContent();

  @override
  State<_StairwayContent> createState() => _StairwayContentState();
}

class _StairwayContentState extends State<_StairwayContent> {
  Map<String, dynamic>? _report;
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _fetchReport();
  }

  Future<void> _fetchReport() async {
    setState(() { _loading = true; _error = null; });
    try {
      final data = await Supabase.instance.client
          .from('accuracy_reports')
          .select()
          .order('timestamp', ascending: false)
          .limit(1) as List?;
      setState(() {
        _report = (data != null && data.isNotEmpty)
            ? Map<String, dynamic>.from(data.first as Map)
            : null;
        _loading = false;
      });
    } catch (e) {
      setState(() { _error = e.toString(); _loading = false; });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.neutral900,
      body: SafeArea(
        child: CustomScrollView(
          slivers: [
            SliverToBoxAdapter(child: _buildHeader(context)),
            if (_loading)
              const SliverFillRemaining(child: Center(child: CircularProgressIndicator()))
            else if (_error != null)
              SliverToBoxAdapter(child: _buildError())
            else ...[
              SliverToBoxAdapter(child: _buildCycleCard()),
              SliverToBoxAdapter(child: _buildStatsRow()),
              SliverToBoxAdapter(
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(20, 24, 20, 8),
                  child: Text(
                    "Today's Picks",
                    style: GoogleFonts.dmSans(
                      fontSize: 16,
                      fontWeight: FontWeight.w700,
                      color: Colors.white,
                    ),
                  ),
                ),
              ),
              _buildPicksList(),
            ],
          ],
        ),
      ),
    );
  }

  // ─── Header ──────────────────────────────────────────────────────────

  Widget _buildHeader(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 8),
      child: Row(
        children: [
          if (Navigator.of(context).canPop())
            GestureDetector(
              onTap: () => Navigator.of(context).pop(),
              child: const Icon(Icons.arrow_back_ios_new_rounded,
                  color: Colors.white, size: 20),
            ),
          if (Navigator.of(context).canPop()) const SizedBox(width: 12),
          Text(
            'Project Stairway',
            style: GoogleFonts.dmSans(
              fontSize: 22,
              fontWeight: FontWeight.w800,
              color: Colors.white,
            ),
          ),
          const Spacer(),
          GestureDetector(
            onTap: _fetchReport,
            child: const Icon(Icons.refresh_rounded,
                color: AppColors.textTertiary, size: 20),
          ),
        ],
      ),
    );
  }

  // ─── Cycle Card ───────────────────────────────────────────────────────

  Widget _buildCycleCard() {
    final roi = _report?['return_pct'] as num? ?? 0.0;
    final winRate = _report?['win_rate'] as num? ?? 0.0;
    final volume = _report?['volume'] as num? ?? 0;
    final roiColor = roi >= 0 ? AppColors.success : AppColors.warning;

    return Container(
      margin: const EdgeInsets.fromLTRB(20, 12, 20, 0),
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [
            AppColors.primary.withValues(alpha: 0.25),
            AppColors.neutral800,
          ],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: AppColors.primary.withValues(alpha: 0.3),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.stairs_rounded,
                  color: AppColors.primary, size: 20),
              const SizedBox(width: 8),
              Text(
                'Current Performance',
                style: GoogleFonts.dmSans(
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                  color: AppColors.textTertiary,
                ),
              ),
              const Spacer(),
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  color: AppColors.primary.withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Text(
                  'Last 24h',
                  style: GoogleFonts.dmSans(
                    fontSize: 10,
                    fontWeight: FontWeight.w600,
                    color: AppColors.primary,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              Expanded(
                child: _bigStat(
                  label: 'ROI',
                  value:
                      '${roi >= 0 ? '+' : ''}${roi.toStringAsFixed(1)}%',
                  color: roiColor,
                ),
              ),
              Expanded(
                child: _bigStat(
                  label: 'Win Rate',
                  value: '${winRate.toStringAsFixed(1)}%',
                  color: Colors.white,
                ),
              ),
              Expanded(
                child: _bigStat(
                  label: 'Volume',
                  value: '$volume',
                  color: Colors.white,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _bigStat({
    required String label,
    required String value,
    required Color color,
  }) {
    return Column(
      children: [
        Text(
          value,
          style: GoogleFonts.dmSans(
            fontSize: 24,
            fontWeight: FontWeight.w800,
            color: color,
          ),
        ),
        const SizedBox(height: 2),
        Text(
          label,
          style: GoogleFonts.dmSans(
            fontSize: 11,
            color: AppColors.textTertiary,
          ),
        ),
      ],
    );
  }

  // ─── Stats Row ────────────────────────────────────────────────────────

  Widget _buildStatsRow() {
    final avgOdds = _report?['avg_odds'] as num? ?? 0.0;
    final totalStaked = _report?['total_staked'] as num? ?? 0.0;
    final totalReturned = _report?['total_returned'] as num? ?? 0.0;

    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 12, 20, 0),
      child: Row(
        children: [
          Expanded(child: _statCard('Avg Odds', avgOdds.toStringAsFixed(2))),
          const SizedBox(width: 8),
          Expanded(
              child: _statCard(
                  'Staked', '₦${totalStaked.toStringAsFixed(0)}')),
          const SizedBox(width: 8),
          Expanded(
              child: _statCard(
                  'Returned', '₦${totalReturned.toStringAsFixed(0)}')),
        ],
      ),
    );
  }

  Widget _statCard(String label, String value) {
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 12),
      decoration: BoxDecoration(
        color: AppColors.neutral800,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
            color: Colors.white.withValues(alpha: 0.06)),
      ),
      child: Column(
        children: [
          Text(
            value,
            style: GoogleFonts.dmSans(
              fontSize: 16,
              fontWeight: FontWeight.w700,
              color: Colors.white,
            ),
          ),
          const SizedBox(height: 2),
          Text(
            label,
            style: GoogleFonts.dmSans(
              fontSize: 10,
              color: AppColors.textTertiary,
            ),
          ),
        ],
      ),
    );
  }

  // ─── Picks List ───────────────────────────────────────────────────────

  Widget _buildPicksList() {
    return BlocBuilder<HomeCubit, HomeState>(
      builder: (context, state) {
        if (state is! HomeLoaded) {
          return const SliverToBoxAdapter(
            child: Center(
              child: Padding(
                padding: EdgeInsets.all(32),
                child: CircularProgressIndicator(),
              ),
            ),
          );
        }
        final picks = state.filteredRecommendations
            .where((r) => r.isAvailable)
            .toList();

        if (picks.isEmpty) {
          return SliverToBoxAdapter(child: _emptyPicks());
        }

        return SliverList(
          delegate: SliverChildBuilderDelegate(
            (context, i) => _pickRow(picks[i]),
            childCount: picks.length,
          ),
        );
      },
    );
  }

  Widget _emptyPicks() {
    return Padding(
      padding: const EdgeInsets.all(32),
      child: Center(
        child: Text(
          'No picks available for today.',
          style: GoogleFonts.dmSans(
            fontSize: 14,
            color: AppColors.textTertiary,
          ),
        ),
      ),
    );
  }

  Widget _pickRow(RecommendationModel rec) {
    return Container(
      margin: const EdgeInsets.fromLTRB(20, 4, 20, 4),
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      decoration: BoxDecoration(
        color: AppColors.neutral800,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.white.withValues(alpha: 0.06)),
      ),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  rec.match,
                  style: GoogleFonts.dmSans(
                    fontSize: 13,
                    fontWeight: FontWeight.w600,
                    color: Colors.white,
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
                const SizedBox(height: 3),
                Text(
                  '${rec.market} • ${rec.league}',
                  style: GoogleFonts.dmSans(
                    fontSize: 11,
                    color: AppColors.textTertiary,
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ],
            ),
          ),
          const SizedBox(width: 8),
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text(
                'Odds ${rec.marketOdds.toStringAsFixed(2)}',
                style: GoogleFonts.dmSans(
                  fontSize: 13,
                  fontWeight: FontWeight.w700,
                  color: AppColors.accentPrimary,
                ),
              ),
              const SizedBox(height: 2),
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                decoration: BoxDecoration(
                  color: _confidenceColor(rec.confidence)
                      .withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(4),
                ),
                child: Text(
                  rec.confidence,
                  style: GoogleFonts.dmSans(
                    fontSize: 9,
                    fontWeight: FontWeight.w700,
                    color: _confidenceColor(rec.confidence),
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Color _confidenceColor(String conf) {
    switch (conf.toLowerCase()) {
      case 'very high':
        return AppColors.success;
      case 'high':
        return AppColors.accentSecondary;
      case 'medium':
        return AppColors.warning;
      default:
        return AppColors.textTertiary;
    }
  }

  // ─── Error ────────────────────────────────────────────────────────────

  Widget _buildError() {
    return Padding(
      padding: const EdgeInsets.all(32),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(Icons.cloud_off_outlined,
              color: AppColors.textTertiary, size: 40),
          const SizedBox(height: 12),
          Text(
            'Could not load report',
            style: GoogleFonts.dmSans(
              fontSize: 14,
              color: AppColors.textTertiary,
            ),
          ),
          const SizedBox(height: 12),
          GestureDetector(
            onTap: _fetchReport,
            child: Text(
              'Retry',
              style: GoogleFonts.dmSans(
                fontSize: 13,
                color: AppColors.primary,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
