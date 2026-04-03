import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:leobookapp/core/constants/app_colors.dart';
import 'package:leobookapp/data/models/match_model.dart';
import 'dart:ui';

class MatchRationaleSheet extends StatelessWidget {
  final MatchModel match;

  const MatchRationaleSheet({super.key, required this.match});

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    
    return Container(
      decoration: BoxDecoration(
        color: isDark ? AppColors.neutral900.withValues(alpha: 0.9) : Colors.white.withValues(alpha: 0.9),
        borderRadius: const BorderRadius.vertical(top: Radius.circular(30)),
      ),
      child: ClipRRect(
        borderRadius: const BorderRadius.vertical(top: Radius.circular(30)),
        child: BackdropFilter(
          filter: ImageFilter.blur(sigmaX: 20, sigmaY: 20),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Container(
                  width: 40,
                  height: 4,
                  decoration: BoxDecoration(
                    color: Colors.grey.withValues(alpha: 0.3),
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
                const SizedBox(height: 20),
                _buildHeader(),
                const SizedBox(height: 20),
                Flexible(
                  child: SingleChildScrollView(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        _buildAiVerdict(),
                        const SizedBox(height: 20),
                        _buildFormComparison(),
                        const SizedBox(height: 20),
                        _buildH2hSummary(),
                        const SizedBox(height: 20),
                        _buildStandingsGlance(),
                        const SizedBox(height: 30),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildHeader() {
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        Column(
          children: [
            Text(
              "ANALYTICAL RATIONALE",
              style: GoogleFonts.dmSans(
                fontSize: 10,
                fontWeight: FontWeight.w900,
                letterSpacing: 2,
                color: AppColors.primary,
              ),
            ),
            const SizedBox(height: 4),
            Text(
              "${match.homeTeam} vs ${match.awayTeam}",
              style: GoogleFonts.dmSans(
                fontSize: 16,
                fontWeight: FontWeight.bold,
              ),
            ),
          ],
        ),
      ],
    );
  }

  Widget _buildAiVerdict() {
    final recScore = match.reliabilityScore ?? 0.0;
    
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.primary.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: AppColors.primary.withValues(alpha: 0.2)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.psychology, color: AppColors.primary, size: 20),
              const SizedBox(width: 8),
              Text(
                "SMART ENSEMBLE DECISION",
                style: GoogleFonts.dmSans(
                  fontSize: 11,
                  fontWeight: FontWeight.w900,
                  color: AppColors.primary,
                ),
              ),
              const Spacer(),
              _buildConfidenceBadge(recScore),
            ],
          ),
          const SizedBox(height: 12),
          Text(
            match.ruleExplanation ?? "AI analyzing historical patterns and current momentum...",
            style: GoogleFonts.dmSans(
              fontSize: 13,
              height: 1.5,
              fontWeight: FontWeight.w500,
            ),
          ),
          if (match.recQualifications != null) ...[
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: (match.recQualifications?['badges'] as List? ?? []).map((b) => _buildBadge(b.toString())).toList(),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildConfidenceBadge(double score) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: AppColors.primary,
        borderRadius: BorderRadius.circular(10),
      ),
      child: Text(
        "${score.toInt()}%",
        style: GoogleFonts.dmSans(
          fontSize: 12,
          fontWeight: FontWeight.w900,
          color: Colors.white,
        ),
      ),
    );
  }

  Widget _buildBadge(String text) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: Colors.grey.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: Colors.grey.withValues(alpha: 0.2)),
      ),
      child: Text(
        text,
        style: GoogleFonts.dmSans(
          fontSize: 10,
          fontWeight: FontWeight.bold,
          color: AppColors.textGrey,
        ),
      ),
    );
  }

  Widget _buildFormComparison() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _buildSectionTitle("CURRENT MOMENTUM (LAST 5)"),
        const SizedBox(height: 12),
        Row(
          children: [
            Expanded(child: _buildTeamForm(match.homeTeam, match.formHome)),
            const SizedBox(width: 16),
            Expanded(child: _buildTeamForm(match.awayTeam, match.formAway, isRight: true)),
          ],
        ),
      ],
    );
  }

  Widget _buildTeamForm(String name, Map<String, dynamic>? formData, {bool isRight = false}) {
    // In our new schema, formData might be the raw list or a summary.
    // For now, let's assume it has 'matches' if coming from intelligence_context.
    final List<dynamic> matches = (formData?['matches'] ?? []) as List<dynamic>;
    
    return Column(
      crossAxisAlignment: isRight ? CrossAxisAlignment.end : CrossAxisAlignment.start,
      children: [
        Text(
          name.toUpperCase(),
          style: GoogleFonts.dmSans(
            fontSize: 10,
            fontWeight: FontWeight.w900,
            color: AppColors.textGrey,
          ),
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
        ),
        const SizedBox(height: 8),
        Row(
          mainAxisAlignment: isRight ? MainAxisAlignment.end : MainAxisAlignment.start,
          children: matches.reversed.take(5).map((m) {
            final res = _getResult(m, name);
            return Container(
              margin: EdgeInsets.only(left: isRight ? 4 : 0, right: isRight ? 0 : 4),
              width: 24,
              height: 24,
              decoration: BoxDecoration(
                color: _getResultColor(res).withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(6),
                border: Border.all(color: _getResultColor(res).withValues(alpha: 0.3)),
              ),
              child: Center(
                child: Text(
                  res,
                  style: GoogleFonts.dmSans(
                    fontSize: 11,
                    fontWeight: FontWeight.w900,
                    color: _getResultColor(res),
                  ),
                ),
              ),
            );
          }).toList(),
        ),
      ],
    );
  }

  String _getResult(dynamic match, String teamName) {
    final score = match['score']?.toString() ?? '0-0';
    final parts = score.split('-');
    if (parts.length != 2) return 'D';
    final h = int.tryParse(parts[0]) ?? 0;
    final a = int.tryParse(parts[1]) ?? 0;
    final isHome = match['home'] == teamName;
    if (h == a) return 'D';
    if (isHome) return h > a ? 'W' : 'L';
    return a > h ? 'W' : 'L';
  }

  Color _getResultColor(String res) {
    if (res == 'W') return AppColors.success;
    if (res == 'L') return AppColors.error;
    return AppColors.warning;
  }

  Widget _buildH2hSummary() {
    final h2h = match.h2hSummary ?? [];
    if (h2h.isEmpty) return const SizedBox();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _buildSectionTitle("HEAD TO HEAD HISTORY"),
        const SizedBox(height: 12),
        Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: Colors.grey.withValues(alpha: 0.05),
            borderRadius: BorderRadius.circular(16),
          ),
          child: Column(
            children: h2h.reversed.take(3).map((m) {
              return Padding(
                padding: const EdgeInsets.symmetric(vertical: 4),
                child: Row(
                  children: [
                    Text(
                      m['date'] ?? '',
                      style: GoogleFonts.dmSans(fontSize: 10, color: AppColors.textGrey),
                    ),
                    const Spacer(),
                    Text(
                      m['home'] ?? '',
                      style: GoogleFonts.dmSans(fontSize: 11, fontWeight: FontWeight.bold),
                    ),
                    Container(
                      margin: const EdgeInsets.symmetric(horizontal: 10),
                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                      decoration: BoxDecoration(
                        color: AppColors.neutral800,
                        borderRadius: BorderRadius.circular(4),
                      ),
                      child: Text(
                        m['score'] ?? '0-0',
                        style: GoogleFonts.dmSans(fontSize: 11, fontWeight: FontWeight.w900, color: Colors.white),
                      ),
                    ),
                    Text(
                      m['away'] ?? '',
                      style: GoogleFonts.dmSans(fontSize: 11, fontWeight: FontWeight.bold),
                    ),
                  ],
                ),
              );
            }).toList(),
          ),
        ),
      ],
    );
  }

  Widget _buildStandingsGlance() {
    final stdHome = match.standingsHome;
    final stdAway = match.standingsAway;
    if (stdHome == null || stdAway == null) return const SizedBox();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _buildSectionTitle("TABLE POSITION"),
        const SizedBox(height: 12),
        Row(
          children: [
            _buildStandingItem(match.homeTeam, stdHome),
            const Spacer(),
            _buildStandingItem(match.awayTeam, stdAway, isRight: true),
          ],
        ),
      ],
    );
  }

  Widget _buildStandingItem(String name, Map<String, dynamic> std, {bool isRight = false}) {
    return Row(
      children: [
        if (!isRight) _buildPosCircle(std['position']?.toString() ?? '?'),
        const SizedBox(width: 12),
        Column(
          crossAxisAlignment: isRight ? CrossAxisAlignment.end : CrossAxisAlignment.start,
          children: [
            Text(
              name,
              style: GoogleFonts.dmSans(fontSize: 12, fontWeight: FontWeight.bold),
            ),
            Text(
              "Pts: ${std['points']} | GD: ${std['goal_difference']}",
              style: GoogleFonts.dmSans(fontSize: 10, color: AppColors.textGrey),
            ),
          ],
        ),
        const SizedBox(width: 12),
        if (isRight) _buildPosCircle(std['position']?.toString() ?? '?'),
      ],
    );
  }

  Widget _buildPosCircle(String pos) {
    return Container(
      width: 28,
      height: 28,
      decoration: BoxDecoration(
        color: AppColors.neutral800,
        shape: BoxShape.circle,
      ),
      child: Center(
        child: Text(
          pos,
          style: GoogleFonts.dmSans(fontSize: 12, fontWeight: FontWeight.w900, color: Colors.white),
        ),
      ),
    );
  }

  Widget _buildSectionTitle(String title) {
    return Text(
      title,
      style: GoogleFonts.dmSans(
        fontSize: 10,
        fontWeight: FontWeight.w900,
        color: AppColors.textGrey,
        letterSpacing: 1,
      ),
    );
  }
}
