// accuracy_dashboard_screen.dart: Accuracy & ROI dashboard screen.
// Part of LeoBook App — Screens
//
// Shows per-market win rates, streak data, avg odds, total staked/returned.
// Pro-gated via TierGate.

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import 'package:leobookapp/core/constants/app_colors.dart';
import 'package:leobookapp/presentation/widgets/shared/tier_gate.dart';

class AccuracyDashboardScreen extends StatelessWidget {
  const AccuracyDashboardScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return const TierGate(
      requirement: TierRequirement.pro,
      featureName: 'Accuracy Dashboard',
      featureDescription:
          'View your per-market win rates, streaks, and ROI analytics. Pro only.',
      child: _AccuracyContent(),
    );
  }
}

class _AccuracyContent extends StatefulWidget {
  const _AccuracyContent();

  @override
  State<_AccuracyContent> createState() => _AccuracyContentState();
}

class _AccuracyContentState extends State<_AccuracyContent> {
  List<Map<String, dynamic>> _reports = [];
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _fetchReports();
  }

  Future<void> _fetchReports() async {
    setState(() { _loading = true; _error = null; });
    try {
      final data = (await Supabase.instance.client
          .from('accuracy_reports')
          .select()
          .order('timestamp', ascending: false)
          .limit(30) as List?) ?? [];
      setState(() {
        _reports = data
            .map((r) => Map<String, dynamic>.from(r as Map))
            .toList();
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
        child: _loading
            ? const Center(child: CircularProgressIndicator())
            : _error != null
                ? _buildError()
                : CustomScrollView(
                    slivers: [
                      SliverToBoxAdapter(child: _buildHeader(context)),
                      SliverToBoxAdapter(child: _buildSummaryRow()),
                      SliverToBoxAdapter(child: _buildStreakCard()),
                      SliverToBoxAdapter(
                        child: Padding(
                          padding:
                              const EdgeInsets.fromLTRB(20, 24, 20, 8),
                          child: Text(
                            'Recent Reports',
                            style: GoogleFonts.dmSans(
                              fontSize: 16,
                              fontWeight: FontWeight.w700,
                              color: Colors.white,
                            ),
                          ),
                        ),
                      ),
                      _buildReportsList(),
                    ],
                  ),
      ),
    );
  }

  // ─── Header ────────────────────────────────────────────────────────────

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
            'Accuracy & ROI',
            style: GoogleFonts.dmSans(
              fontSize: 22,
              fontWeight: FontWeight.w800,
              color: Colors.white,
            ),
          ),
          const Spacer(),
          GestureDetector(
            onTap: _fetchReports,
            child: const Icon(Icons.refresh_rounded,
                color: AppColors.textTertiary, size: 20),
          ),
        ],
      ),
    );
  }

  // ─── Summary Row ───────────────────────────────────────────────────────

  Widget _buildSummaryRow() {
    if (_reports.isEmpty) {
      return Padding(
        padding: const EdgeInsets.fromLTRB(20, 12, 20, 0),
        child: Text(
          'No reports yet.',
          style: GoogleFonts.dmSans(
            fontSize: 14,
            color: AppColors.textTertiary,
          ),
        ),
      );
    }

    final latest = _reports.first;
    final winRate = (latest['win_rate'] as num? ?? 0.0);
    final roi = (latest['return_pct'] as num? ?? 0.0);
    final volume = (latest['volume'] as num? ?? 0);
    final avgOdds = (latest['avg_odds'] as num? ?? 0.0);

    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 12, 20, 0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Latest Report',
            style: GoogleFonts.dmSans(
              fontSize: 12,
              color: AppColors.textTertiary,
            ),
          ),
          const SizedBox(height: 8),
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: AppColors.neutral800,
              borderRadius: BorderRadius.circular(14),
              border: Border.all(
                  color: Colors.white.withValues(alpha: 0.06)),
            ),
            child: Row(
              children: [
                Expanded(
                    child: _summaryCell(
                        'Win Rate',
                        '${winRate.toStringAsFixed(1)}%',
                        winRate >= 60
                            ? AppColors.success
                            : AppColors.warning)),
                _divider(),
                Expanded(
                    child: _summaryCell(
                        'ROI',
                        '${roi >= 0 ? '+' : ''}${roi.toStringAsFixed(1)}%',
                        roi >= 0 ? AppColors.success : AppColors.warning)),
                _divider(),
                Expanded(
                    child: _summaryCell(
                        'Picks', '$volume', Colors.white)),
                _divider(),
                Expanded(
                    child: _summaryCell(
                        'Avg Odds',
                        avgOdds.toStringAsFixed(2),
                        AppColors.accentPrimary)),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _summaryCell(String label, String value, Color color) {
    return Column(
      children: [
        Text(
          value,
          style: GoogleFonts.dmSans(
            fontSize: 18,
            fontWeight: FontWeight.w800,
            color: color,
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
    );
  }

  Widget _divider() => Container(
      width: 1,
      height: 32,
      color: Colors.white.withValues(alpha: 0.06));

  // ─── Streak Card ──────────────────────────────────────────────────────

  Widget _buildStreakCard() {
    if (_reports.isEmpty) return const SizedBox.shrink();

    final latest = _reports.first;
    final streak = latest['current_streak'] as int? ?? 0;
    final longestWin = latest['longest_win_streak'] as int? ?? 0;
    final totalStaked = (latest['total_staked'] as num? ?? 0.0);
    final totalReturned = (latest['total_returned'] as num? ?? 0.0);

    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 12, 20, 0),
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: AppColors.neutral800,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(
              color: Colors.white.withValues(alpha: 0.06)),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Streaks & Stakes',
              style: GoogleFonts.dmSans(
                fontSize: 13,
                fontWeight: FontWeight.w600,
                color: AppColors.textTertiary,
              ),
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                    child: _streakTile(
                        Icons.bolt_rounded,
                        'Current Streak',
                        streak >= 0
                            ? '+$streak W'
                            : '$streak L',
                        streak >= 0
                            ? AppColors.success
                            : AppColors.warning)),
                Expanded(
                    child: _streakTile(
                        Icons.emoji_events_outlined,
                        'Best Streak',
                        '$longestWin W',
                        AppColors.warning)),
              ],
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                Expanded(
                    child: _streakTile(
                        Icons.arrow_upward_rounded,
                        'Total Staked',
                        '₦${totalStaked.toStringAsFixed(0)}',
                        AppColors.textTertiary)),
                Expanded(
                    child: _streakTile(
                        Icons.arrow_downward_rounded,
                        'Returned',
                        '₦${totalReturned.toStringAsFixed(0)}',
                        totalReturned >= totalStaked
                            ? AppColors.success
                            : AppColors.warning)),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _streakTile(
      IconData icon, String label, String value, Color color) {
    return Row(
      children: [
        Icon(icon, color: color, size: 18),
        const SizedBox(width: 8),
        Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              value,
              style: GoogleFonts.dmSans(
                fontSize: 14,
                fontWeight: FontWeight.w700,
                color: color,
              ),
            ),
            Text(
              label,
              style: GoogleFonts.dmSans(
                fontSize: 10,
                color: AppColors.textTertiary,
              ),
            ),
          ],
        ),
      ],
    );
  }

  // ─── Reports List ──────────────────────────────────────────────────────

  Widget _buildReportsList() {
    if (_reports.isEmpty) {
      return SliverToBoxAdapter(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Center(
            child: Text(
              'No accuracy reports yet.',
              style: GoogleFonts.dmSans(
                fontSize: 14,
                color: AppColors.textTertiary,
              ),
            ),
          ),
        ),
      );
    }

    return SliverList(
      delegate: SliverChildBuilderDelegate(
        (context, i) => _reportRow(_reports[i]),
        childCount: _reports.length,
      ),
    );
  }

  Widget _reportRow(Map<String, dynamic> report) {
    final ts = report['timestamp']?.toString() ?? '';
    final winRate = (report['win_rate'] as num? ?? 0.0);
    final roi = (report['return_pct'] as num? ?? 0.0);
    final volume = (report['volume'] as num? ?? 0);
    final period = report['period']?.toString() ?? 'period';
    final roiColor = roi >= 0 ? AppColors.success : AppColors.warning;

    // Trim timestamp to date only
    final displayDate = ts.length >= 10 ? ts.substring(0, 10) : ts;

    return Container(
      margin: const EdgeInsets.fromLTRB(20, 4, 20, 4),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      decoration: BoxDecoration(
        color: AppColors.neutral800,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: Colors.white.withValues(alpha: 0.05)),
      ),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  displayDate,
                  style: GoogleFonts.dmSans(
                    fontSize: 13,
                    fontWeight: FontWeight.w600,
                    color: Colors.white,
                  ),
                ),
                Text(
                  '$period • $volume picks',
                  style: GoogleFonts.dmSans(
                    fontSize: 11,
                    color: AppColors.textTertiary,
                  ),
                ),
              ],
            ),
          ),
          Text(
            '${winRate.toStringAsFixed(1)}%',
            style: GoogleFonts.dmSans(
              fontSize: 13,
              fontWeight: FontWeight.w700,
              color: Colors.white,
            ),
          ),
          const SizedBox(width: 12),
          Text(
            '${roi >= 0 ? '+' : ''}${roi.toStringAsFixed(1)}%',
            style: GoogleFonts.dmSans(
              fontSize: 13,
              fontWeight: FontWeight.w700,
              color: roiColor,
            ),
          ),
        ],
      ),
    );
  }

  // ─── Error ─────────────────────────────────────────────────────────────

  Widget _buildError() {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(Icons.cloud_off_outlined,
              color: AppColors.textTertiary, size: 40),
          const SizedBox(height: 12),
          Text(
            'Could not load accuracy data',
            style: GoogleFonts.dmSans(
              fontSize: 14,
              color: AppColors.textTertiary,
            ),
          ),
          const SizedBox(height: 12),
          GestureDetector(
            onTap: _fetchReports,
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
