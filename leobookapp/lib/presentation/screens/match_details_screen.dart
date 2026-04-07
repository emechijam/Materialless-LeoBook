// match_details_screen.dart: match_details_screen.dart: Widget/screen for App  -  Screens.
// Part of LeoBook App  -  Screens
//
// Classes: MatchDetailsScreen, _MatchDetailsScreenState

import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:cached_network_image/cached_network_image.dart';
import 'package:leobookapp/core/constants/app_colors.dart';
import 'package:leobookapp/data/models/match_model.dart';
import 'package:leobookapp/data/models/standing_model.dart';
import 'package:leobookapp/data/repositories/data_repository.dart';
import 'package:leobookapp/core/constants/responsive_constants.dart';
import 'team_screen.dart';
import 'league_screen.dart';

import '../widgets/shared/match_card.dart';
import 'package:leobookapp/core/widgets/leo_loading_indicator.dart';

class MatchDetailsScreen extends StatefulWidget {
  final MatchModel match;

  const MatchDetailsScreen({super.key, required this.match});

  @override
  State<MatchDetailsScreen> createState() => _MatchDetailsScreenState();
}

class _MatchDetailsScreenState extends State<MatchDetailsScreen> {
  bool _isLoadingIndices = true;
  List<MatchModel> _homeHistory = [];
  List<MatchModel> _awayHistory = [];
  List<MatchModel> _h2hHistory = [];
  List<StandingModel> _standings = [];
  bool _homeExpanded = false;
  bool _awayExpanded = false;
  bool _h2hExpanded = false;

  MatchModel get match => widget.match;

  @override
  void initState() {
    super.initState();
    _loadHistory();
  }

  Future<void> _loadHistory() async {
    setState(() => _isLoadingIndices = true);
    final repository = context.read<DataRepository>();
    final homeMatches = await repository.getTeamMatches(match.homeTeam);
    final awayMatches = await repository.getTeamMatches(match.awayTeam);

    // Fetch Standings — use actual leagueId (not display name)
    List<StandingModel> sTable = [];
    if (match.leagueId != null && match.leagueId!.isNotEmpty) {
      sTable = await repository.fetchStandings(
        leagueId: match.leagueId!,
      );
    }

    // H2H: dedicated query for both team combinations
    final h2h = await repository.getH2HMatches(match.homeTeam, match.awayTeam);

    // Past matches only
    final now = DateTime.now();

    bool isPast(MatchModel m) {
      try {
        final date = DateTime.parse(m.date);
        return date.isBefore(now) || m.status == 'Finished';
      } catch (_) {
        return false;
      }
    }

    final pastHome = homeMatches.where(isPast).take(10).toList();
    final pastAway = awayMatches.where(isPast).take(10).toList();
    final pastH2H = h2h.where(isPast).take(10).toList();

    if (mounted) {
      setState(() {
        _homeHistory = pastHome;
        _awayHistory = pastAway;
        _h2hHistory = pastH2H;
        _standings = sTable;
        _isLoadingIndices = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.neutral900,
      body: Column(
        children: [
          Expanded(
            child: SingleChildScrollView(
              child: Column(
                children: [
                  // 1. Stadium Header
                  _buildStadiumHeader(context),

                  // Main Content
                  Transform.translate(
                    offset: const Offset(0, -16),
                    child: Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 16),
                      child: Column(
                        children: [
                          // 2. Basketball Period Scoreboard (only for basketball)
                          if (_isBasketball && match.periodScores != null)
                            _buildPeriodScoreboard(),

                          if (_isBasketball && match.periodScores != null)
                            const SizedBox(height: 16),

                          // 3. AI Win / O-U Probability
                          _buildWinProbabilitySection(),

                          const SizedBox(height: 16),

                          // 3. Expert Prediction
                          _buildExpertPrediction(),

                          const SizedBox(height: 16),

                          // 4. Prediction Insights (all data/stats that led to prediction)
                          _buildPredictionInsights(),

                          const SizedBox(height: 16),

                          // 5. Standings
                          _buildStandingsSection(),

                          const SizedBox(height: 16),

                          // 6. Home Team History
                          _buildMatchHistorySection(
                            "${match.homeTeam}  -  LAST MATCHES",
                            _homeHistory,
                            _homeExpanded,
                            () =>
                                setState(() => _homeExpanded = !_homeExpanded),
                          ),

                          const SizedBox(height: 16),

                          // 7. Away Team History
                          _buildMatchHistorySection(
                            "${match.awayTeam}  -  LAST MATCHES",
                            _awayHistory,
                            _awayExpanded,
                            () =>
                                setState(() => _awayExpanded = !_awayExpanded),
                          ),

                          const SizedBox(height: 16),

                          // 8. H2H History
                          _buildMatchHistorySection(
                            "HEAD-TO-HEAD",
                            _h2hHistory,
                            _h2hExpanded,
                            () => setState(() => _h2hExpanded = !_h2hExpanded),
                          ),

                          const SizedBox(height: 40),
                        ],
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildStadiumHeader(BuildContext context) {
    return Container(
      padding: EdgeInsets.only(
        top: MediaQuery.of(context).padding.top + 8,
        bottom: 24,
        left: 16,
        right: 16,
      ),
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [
            Color(0xFF0F172A),
            Color(0xFF1E293B),
            AppColors.neutral900,
          ],
          stops: [0.0, 0.6, 1.0],
        ),
      ),
      child: Column(
        children: [
          // Back button row
          Align(
            alignment: Alignment.centerLeft,
            child: CircleAvatar(
              backgroundColor: Colors.white10,
              radius: 18,
              child: IconButton(
                icon: const Icon(Icons.arrow_back_ios_new, size: 16, color: Colors.white),
                onPressed: () => Navigator.pop(context),
                padding: EdgeInsets.zero,
              ),
            ),
          ),
          const SizedBox(height: 16),
          // Three-column layout: Home | Center | Away
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // HOME TEAM column
              Expanded(
                child: Column(
                  children: [
                    Container(
                      width: 72,
                      height: 72,
                      decoration: BoxDecoration(
                        color: Colors.white10,
                        borderRadius: BorderRadius.circular(18),
                        border: Border.all(color: match.isFinished && match.winner == 'home'
                            ? AppColors.success.withValues(alpha: 0.5)
                            : Colors.white24),
                      ),
                      child: ClipRRect(
                        borderRadius: BorderRadius.circular(16),
                        child: match.homeCrestUrl != null && match.homeCrestUrl!.isNotEmpty
                            ? CachedNetworkImage(
                                imageUrl: match.homeCrestUrl!,
                                width: 44,
                                height: 44,
                                fit: BoxFit.contain,
                                errorWidget: (_, __, ___) => const Icon(Icons.shield, size: 36, color: Colors.white),
                              )
                            : const Icon(Icons.shield, size: 36, color: Colors.white),
                      ),
                    ),
                    const SizedBox(height: 10),
                    Text(
                      match.homeTeam,
                      style: GoogleFonts.dmSans(
                        color: match.isFinished && match.winner == 'home' ? AppColors.success : Colors.white,
                        fontSize: 13,
                        fontWeight: match.isFinished && match.winner == 'home' ? FontWeight.w900 : FontWeight.w700,
                      ),
                      textAlign: TextAlign.center,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                    if (match.homeRedCards > 0) ...[                      const SizedBox(height: 4),
                      _buildRedCardBadge(match.homeRedCards),
                    ],
                  ],
                ),
              ),
              // CENTER column: league, date, VS
              Expanded(
                child: Column(
                  children: [
                    const SizedBox(height: 8),
                    GestureDetector(
                      onTap: () {
                        Navigator.push(context, MaterialPageRoute(
                          builder: (context) => LeagueScreen(
                            leagueId: match.leagueId ?? match.league ?? '',
                            leagueName: match.league ?? '',
                          ),
                        ));
                      },
                      child: Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          if (match.leagueCrestUrl != null && match.leagueCrestUrl!.isNotEmpty)
                            Padding(
                              padding: const EdgeInsets.only(right: 4),
                              child: CachedNetworkImage(
                                imageUrl: match.leagueCrestUrl!,
                                width: 12,
                                height: 12,
                                fit: BoxFit.contain,
                                errorWidget: (_, __, ___) => const SizedBox.shrink(),
                              ),
                            ),
                          // Sport pill — only shown for non-football
                          if (match.sport.toLowerCase() == 'basketball')
                            Container(
                              margin: const EdgeInsets.only(right: 4),
                              padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 1),
                              decoration: BoxDecoration(
                                color: Colors.orange.withValues(alpha: 0.15),
                                borderRadius: BorderRadius.circular(3),
                              ),
                              child: const Text('🏀', style: TextStyle(fontSize: 8)),
                            ),
                          Flexible(
                            child: Text(
                              _parseLeagueName(match.league ?? ''),
                              style: GoogleFonts.dmSans(color: AppColors.primary, fontSize: 9, fontWeight: FontWeight.bold, letterSpacing: 1.5),
                              overflow: TextOverflow.ellipsis,
                              textAlign: TextAlign.center,
                            ),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      '${match.date} • ${match.time}',
                      style: GoogleFonts.dmSans(color: Colors.white60, fontSize: 10),
                      textAlign: TextAlign.center,
                    ),
                    const SizedBox(height: 12),
                    Text(
                      match.displayStatus == 'FINISHED' || match.isLive
                          ? '${match.homeScore} : ${match.awayScore}'
                          : 'VS',
                      style: GoogleFonts.dmSans(
                        color: match.isLive
                            ? AppColors.liveRed
                            : (match.isFinished ? Colors.white : Colors.white24),
                        fontSize: 28,
                        fontWeight: FontWeight.w900,
                        fontStyle: FontStyle.italic,
                      ),
                    ),
                    if (match.leagueStage != null && match.leagueStage!.isNotEmpty) ...[
                      const SizedBox(height: 4),
                      Text(
                        match.leagueStage!,
                        style: GoogleFonts.dmSans(
                          color: Colors.white30,
                          fontSize: 9,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ],
                    if (match.displayStatus.isNotEmpty) ...[
                      const SizedBox(height: 6),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 3),
                        decoration: BoxDecoration(
                          color: AppColors.primary.withValues(alpha: 0.15),
                          borderRadius: BorderRadius.circular(20),
                          border: Border.all(color: AppColors.primary.withValues(alpha: 0.3)),
                        ),
                        child: Text(
                          match.displayStatus,
                          style: GoogleFonts.dmSans(color: AppColors.primary, fontSize: 9, fontWeight: FontWeight.bold),
                        ),
                      ),
                    ],
                  ],
                ),
              ),
              // AWAY TEAM column
              Expanded(
                child: Column(
                  children: [
                    Container(
                      width: 72,
                      height: 72,
                      decoration: BoxDecoration(
                        color: Colors.white10,
                        borderRadius: BorderRadius.circular(18),
                        border: Border.all(color: match.isFinished && match.winner == 'away'
                            ? AppColors.success.withValues(alpha: 0.5)
                            : Colors.white24),
                      ),
                      child: ClipRRect(
                        borderRadius: BorderRadius.circular(16),
                        child: match.awayCrestUrl != null && match.awayCrestUrl!.isNotEmpty
                            ? CachedNetworkImage(
                                imageUrl: match.awayCrestUrl!,
                                width: 44,
                                height: 44,
                                fit: BoxFit.contain,
                                errorWidget: (_, __, ___) => const Icon(Icons.shield, size: 36, color: Colors.white),
                              )
                            : const Icon(Icons.shield, size: 36, color: Colors.white),
                      ),
                    ),
                    const SizedBox(height: 10),
                    Text(
                      match.awayTeam,
                      style: GoogleFonts.dmSans(
                        color: match.isFinished && match.winner == 'away' ? AppColors.success : Colors.white,
                        fontSize: 13,
                        fontWeight: match.isFinished && match.winner == 'away' ? FontWeight.w900 : FontWeight.w700,
                      ),
                      textAlign: TextAlign.center,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                    if (match.awayRedCards > 0) ...[                      const SizedBox(height: 4),
                      _buildRedCardBadge(match.awayRedCards),
                    ],
                  ],
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildRedCardBadge(int count) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: const Color(0xFFDC0000).withValues(alpha: 0.15),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 10,
            height: 12,
            decoration: BoxDecoration(
              color: const Color(0xFFDC0000),
              borderRadius: BorderRadius.circular(2),
            ),
          ),
          if (count > 1) ...[
            const SizedBox(width: 3),
            Text(
              '\u00d7$count',
              style: GoogleFonts.dmSans(
                color: const Color(0xFFDC0000),
                fontWeight: FontWeight.w700,
                fontSize: 10,
              ),
            ),
          ],
        ],
      ),
    );
  }

  /// Basketball quarter/half scoreboard — shown when periodScores is populated.
  Widget _buildPeriodScoreboard() {
    final ps = match.periodScores!;
    final periods = <String>['q1', 'q2', 'q3', 'q4'];
    final hasSubs = ps.containsKey('h1') || ps.containsKey('h2');
    final hasOt   = ps.containsKey('ot') &&
        ((ps['ot']?['home'] ?? 0) > 0 || (ps['ot']?['away'] ?? 0) > 0);

    String sc(String period, String side) {
      final v = ps[period]?[side];
      if (v == null) return '-';
      return v.toString();
    }

    Widget cell(String text, {bool bold = false, Color? color}) {
      return Expanded(
        child: Center(
          child: Text(
            text,
            style: GoogleFonts.dmSans(
              color: color ?? (bold ? Colors.white : Colors.white70),
              fontSize: bold ? 13 : 11,
              fontWeight: bold ? FontWeight.w900 : FontWeight.w600,
            ),
          ),
        ),
      );
    }

    Widget row(String label, String home, String away,
        {bool isTotal = false, bool isOt = false}) {
      final accentColor = isOt ? Colors.amber : (isTotal ? AppColors.primary : null);
      return Container(
        margin: const EdgeInsets.symmetric(vertical: 3),
        padding: const EdgeInsets.symmetric(vertical: 6, horizontal: 8),
        decoration: BoxDecoration(
          color: isTotal
              ? AppColors.primary.withValues(alpha: 0.12)
              : Colors.white.withValues(alpha: 0.03),
          borderRadius: BorderRadius.circular(8),
          border: isTotal || isOt
              ? Border.all(
                  color: (accentColor ?? AppColors.primary).withValues(alpha: 0.25))
              : null,
        ),
        child: Row(
          children: [
            SizedBox(
              width: 36,
              child: Text(
                label,
                style: GoogleFonts.dmSans(
                  color: accentColor ?? Colors.white38,
                  fontSize: 9,
                  fontWeight: FontWeight.w800,
                  letterSpacing: 0.5,
                ),
              ),
            ),
            cell(home, bold: isTotal, color: accentColor),
            Text('–', style: GoogleFonts.dmSans(color: Colors.white24, fontSize: 11)),
            cell(away, bold: isTotal, color: accentColor),
          ],
        ),
      );
    }

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.neutral800,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: Colors.white10),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header
          Row(
            children: [
              const Icon(Icons.sports_basketball, size: 14, color: Colors.orange),
              const SizedBox(width: 6),
              Text(
                'PERIOD SCORES',
                style: GoogleFonts.dmSans(
                  color: Colors.orange,
                  fontSize: 10,
                  fontWeight: FontWeight.w800,
                  letterSpacing: 1.2,
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          // Column headers
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 8),
            child: Row(
              children: [
                const SizedBox(width: 36),
                Expanded(
                  child: Center(
                    child: Text(
                      match.homeTeam.split(' ').last.toUpperCase(),
                      style: GoogleFonts.dmSans(
                        color: AppColors.primary,
                        fontSize: 9,
                        fontWeight: FontWeight.w900,
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Center(
                    child: Text(
                      match.awayTeam.split(' ').last.toUpperCase(),
                      style: GoogleFonts.dmSans(
                        color: AppColors.liveRed,
                        fontSize: 9,
                        fontWeight: FontWeight.w900,
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 6),
          // Period rows
          for (final p in periods)
            if (ps.containsKey(p))
              row(p.toUpperCase(), sc(p, 'home'), sc(p, 'away')),
          if (hasSubs) ...[
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 4),
              child: Divider(color: Colors.white10, height: 1),
            ),
            if (ps.containsKey('h1'))
              row('H1', sc('h1', 'home'), sc('h1', 'away')),
            if (ps.containsKey('h2'))
              row('H2', sc('h2', 'home'), sc('h2', 'away')),
          ],
          if (hasOt)
            row('OT', sc('ot', 'home'), sc('ot', 'away'), isOt: true),
          // Total (full game)
          row(
            'FINAL',
            match.homeScore ?? '-',
            match.awayScore ?? '-',
            isTotal: true,
          ),
        ],
      ),
    );
  }

  // Returns true when this match uses the basketball Over/Under prediction schema.
  bool get _isBasketball => match.sport.toLowerCase() == 'basketball';

  // Over / Under probabilities — parsed from ensembleWeights or rlDecision.
  // Falls back to 50/50 when not available (symbolic-only path).
  double get _probOver =>
      (match.ensembleWeights?['over'] ?? match.rlDecision?['over_prob'] ?? 0.5)
          .toDouble();
  double get _probUnder =>
      (match.ensembleWeights?['under'] ?? match.rlDecision?['under_prob'] ?? 0.5)
          .toDouble();

  Widget _buildWinProbabilitySection() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.neutral800,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: Colors.white10),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.3),
            blurRadius: 20,
            offset: const Offset(0, 10),
          ),
        ],
      ),
      child: Column(
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                _isBasketball ? "AI OVER/UNDER PROBABILITY" : "AI WIN PROBABILITY",
                style: GoogleFonts.dmSans(
                  color: Colors.white54,
                  fontSize: 10,
                  fontWeight: FontWeight.bold,
                  letterSpacing: 1.5,
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                decoration: BoxDecoration(
                  color: AppColors.primary.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(4),
                ),
                child: Text(
                  "LEO AI MODEL v1.2",
                  style: GoogleFonts.dmSans(
                    color: AppColors.primary,
                    fontSize: 10,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          if (_isBasketball) ...[
            // ── Basketball: 2-bar Over / Under ──────────────────────────
            ClipRRect(
              borderRadius: BorderRadius.circular(8),
              child: SizedBox(
                height: 28,
                child: Row(
                  children: [
                    Expanded(
                      flex: (_probOver * 100).toInt().clamp(1, 99),
                      child: Container(
                        decoration: const BoxDecoration(
                          gradient: LinearGradient(
                            colors: [Color(0xFF10B981), Color(0xFF059669)],
                          ),
                        ),
                        alignment: Alignment.centerLeft,
                        padding: const EdgeInsets.only(left: 10),
                        child: Text(
                          "OVER  ${(_probOver * 100).toInt()}%",
                          style: GoogleFonts.dmSans(
                            color: Colors.white,
                            fontSize: 11,
                            fontWeight: FontWeight.w800,
                          ),
                        ),
                      ),
                    ),
                    Expanded(
                      flex: (_probUnder * 100).toInt().clamp(1, 99),
                      child: Container(
                        decoration: const BoxDecoration(
                          gradient: LinearGradient(
                            colors: [Color(0xFFEF4444), Color(0xFFB91C1C)],
                          ),
                        ),
                        alignment: Alignment.centerRight,
                        padding: const EdgeInsets.only(right: 10),
                        child: Text(
                          "${(_probUnder * 100).toInt()}%  UNDER",
                          style: GoogleFonts.dmSans(
                            color: Colors.white,
                            fontSize: 11,
                            fontWeight: FontWeight.w800,
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 8),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  "More Points",
                  style: GoogleFonts.dmSans(color: Colors.white54, fontSize: 9, fontWeight: FontWeight.w500),
                ),
                Text(
                  "Total O/U",
                  style: GoogleFonts.dmSans(color: Colors.white38, fontSize: 9),
                ),
                Text(
                  "Fewer Points",
                  style: GoogleFonts.dmSans(color: Colors.white54, fontSize: 9, fontWeight: FontWeight.w500),
                ),
              ],
            ),
          ] else ...[
            // ── Football: 3-bar Home / Draw / Away ─────────────────────
            ClipRRect(
              borderRadius: BorderRadius.circular(8),
              child: SizedBox(
                height: 24,
                child: Row(
                  children: [
                    Expanded(
                      flex: (match.probHome * 100).toInt().clamp(1, 100),
                      child: Container(
                        color: AppColors.primary,
                        alignment: Alignment.centerLeft,
                        padding: const EdgeInsets.only(left: 8),
                        child: Text(
                          "HOME ${(match.probHome * 100).toInt()}%",
                          style: GoogleFonts.dmSans(
                            color: Colors.white,
                            fontSize: 10,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ),
                    ),
                    Expanded(
                      flex: (match.probDraw * 100).toInt().clamp(1, 100),
                      child: Container(
                        color: Colors.grey[700],
                        alignment: Alignment.center,
                        child: Text(
                          "${(match.probDraw * 100).toInt()}%",
                          style: GoogleFonts.dmSans(
                            color: Colors.white,
                            fontSize: 10,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ),
                    ),
                    Expanded(
                      flex: (match.probAway * 100).toInt().clamp(1, 100),
                      child: Container(
                        color: AppColors.liveRed,
                        alignment: Alignment.centerRight,
                        padding: const EdgeInsets.only(right: 8),
                        child: Text(
                          "${(match.probAway * 100).toInt()}% AWAY",
                          style: GoogleFonts.dmSans(
                            color: Colors.white,
                            fontSize: 10,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 8),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  match.homeTeam,
                  style: GoogleFonts.dmSans(color: Colors.white54, fontSize: 9, fontWeight: FontWeight.w500),
                ),
                Text(
                  "Draw",
                  style: GoogleFonts.dmSans(color: Colors.white54, fontSize: 9, fontWeight: FontWeight.w500),
                ),
                Text(
                  match.awayTeam,
                  style: GoogleFonts.dmSans(color: Colors.white54, fontSize: 9, fontWeight: FontWeight.w500),
                ),
              ],
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildExpertPrediction() {
    // final ruleOutput = match.ruleOutput; // Deleted as it caused indexing errors

    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [AppColors.primary, Colors.blue.shade900],
        ),
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: AppColors.primary.withValues(alpha: 0.3),
            blurRadius: 10,
            offset: const Offset(0, 5),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                _isBasketball ? Icons.sports_basketball : Icons.psychology,
                color: Colors.white,
                size: 20,
              ),
              const SizedBox(width: 8),
              Text(
                _isBasketball ? "BASKETBALL PREDICTION" : "EXPERT PREDICTION",
                style: GoogleFonts.dmSans(
                  color: Colors.white70,
                  fontSize: 12,
                  fontWeight: FontWeight.bold,
                  letterSpacing: 1.2,
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      match.chosenMarket ?? match.prediction ?? "N/A",
                      style: GoogleFonts.dmSans(
                        color: Colors.white,
                        fontSize: 22,
                        fontWeight: FontWeight.w900,
                        height: 1.1,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      "Confidence: ${(match.statisticalEdge ?? 0.0 * 100).toStringAsFixed(0)}%",
                      style: GoogleFonts.dmSans(
                        color: Colors.white60,
                        fontSize: 11,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 16),
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 12,
                  vertical: 8,
                ),
                decoration: BoxDecoration(
                  color: Colors.white24,
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: Colors.white24),
                ),
                child: Column(
                  children: [
                    Text(
                      "ODDS",
                      style: GoogleFonts.dmSans(
                        color: Colors.white70,
                        fontSize: 9,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    Text(
                      match.odds ?? "-",
                      style: GoogleFonts.dmSans(
                        color: Colors.white,
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          if (match.overrideReason != null && match.overrideReason!.isNotEmpty) ...[
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(12),
              margin: const EdgeInsets.only(bottom: 12),
              decoration: BoxDecoration(
                color: Colors.amber.withValues(alpha: 0.2),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: Colors.amber.withValues(alpha: 0.5)),
              ),
              child: Row(
                children: [
                  const Icon(Icons.warning_amber_rounded, color: Colors.amber, size: 16),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      "Rule override: ${match.overrideReason}",
                      style: GoogleFonts.dmSans(
                        color: Colors.amber,
                        fontSize: 11,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: Colors.black26,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: Colors.white10),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    const Icon(
                      Icons.analytics,
                      size: 14,
                      color: Colors.cyanAccent,
                    ),
                    const SizedBox(width: 6),
                    Text(
                      "SEMANTIC RULE ANALYSIS",
                      style: GoogleFonts.dmSans(
                        color: Colors.cyanAccent,
                        fontSize: 10,
                        fontWeight: FontWeight.bold,
                        letterSpacing: 1.0,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 4),
                Text(
                  match.ruleExplanation ?? "AI analyzing patterns...",
                  style: GoogleFonts.dmSans(
                    color: Colors.white70,
                    fontSize: 11,
                    fontStyle: FontStyle.italic,
                    height: 1.4,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 12),
          Text(
            "Pure model suggested: ${match.pureModelSuggestion ?? '-'}",
            style: GoogleFonts.dmSans(
              color: Colors.white38,
              fontSize: 10,
              fontStyle: FontStyle.italic,
            ),
          ),
        ],
      ),
    );
  }

  // â”€â”€ Expandable Match History Section â”€â”€
  Widget _buildMatchHistorySection(
    String title,
    List<MatchModel> matches,
    bool isExpanded,
    VoidCallback onToggle,
  ) {
    if (_isLoadingIndices) {
      return Container(
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          color: AppColors.neutral800,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: Colors.white10),
        ),
        child: const Center(
          child: LeoLoadingIndicator(size: 24),
        ),
      );
    }

    final visibleCount = isExpanded
        ? (matches.length > 10 ? 10 : matches.length)
        : (matches.length > 5 ? 5 : matches.length);
    final visibleMatches = matches.take(visibleCount).toList();
    final hasMore = matches.length > 5 && !isExpanded;
    final canCollapse = isExpanded;

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.neutral800,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: Colors.white10),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Section Header
          Row(
            children: [
              Icon(
                title.contains("HEAD") ? Icons.compare_arrows : Icons.history,
                size: 16,
                color: AppColors.primary,
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  title.toUpperCase(),
                  style: GoogleFonts.dmSans(
                    color: AppColors.primary,
                    fontSize: 11,
                    fontWeight: FontWeight.w800,
                    letterSpacing: 1.2,
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
              Text(
                "${matches.length} match${matches.length == 1 ? '' : 'es'}",
                style: GoogleFonts.dmSans(
                  color: AppColors.textGrey,
                  fontSize: 10,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),

          if (matches.isEmpty)
            Container(
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: Colors.white.withValues(alpha: 0.03),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: Colors.white10),
              ),
              child: Center(
                child: Text(
                  "No matches found",
                  style: GoogleFonts.dmSans(
                    color: Colors.white24,
                    fontSize: 11,
                  ),
                ),
              ),
            )
          else ...[
            // Match Cards - Responsive Layout
            LayoutBuilder(
              builder: (context, constraints) {
                final isDesktop = Responsive.isDesktop(context);
                if (isDesktop) {
                  const crossAxisCount = 3;
                  const spacing = 12.0;
                  final itemWidth = (constraints.maxWidth -
                          (spacing * (crossAxisCount - 1))) /
                      crossAxisCount;

                  return Wrap(
                    spacing: spacing,
                    runSpacing: spacing,
                    children: visibleMatches
                        .map((m) => SizedBox(
                              width: itemWidth,
                              child: MatchCard(
                                match: m,
                                showLeagueHeader: true,
                                hideLeagueInfo: false,
                              ),
                            ))
                        .toList(),
                  );
                }

                // Mobile/Tablet: Vertical List
                return Column(
                  children: visibleMatches
                      .map((m) => Padding(
                            padding: const EdgeInsets.only(bottom: 8),
                            child: MatchCard(
                              match: m,
                              showLeagueHeader: true,
                              hideLeagueInfo: false,
                            ),
                          ))
                      .toList(),
                );
              },
            ),

            const SizedBox(height: 12),

            // Expand / Collapse Button
            if (hasMore || canCollapse)
              GestureDetector(
                onTap: onToggle,
                child: Container(
                  width: double.infinity,
                  padding: const EdgeInsets.symmetric(vertical: 10),
                  decoration: BoxDecoration(
                    color: AppColors.primary.withValues(alpha: 0.08),
                    borderRadius: BorderRadius.circular(10),
                    border: Border.all(
                      color: AppColors.primary.withValues(alpha: 0.2),
                    ),
                  ),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(
                        isExpanded
                            ? Icons.keyboard_arrow_up
                            : Icons.keyboard_arrow_down,
                        size: 18,
                        color: AppColors.primary,
                      ),
                      const SizedBox(width: 6),
                      Text(
                        isExpanded ? "SHOW LESS" : "SHOW MORE",
                        style: GoogleFonts.dmSans(
                          color: AppColors.primary,
                          fontSize: 11,
                          fontWeight: FontWeight.w800,
                          letterSpacing: 0.5,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
          ],
        ],
      ),
    );
  }

  // â”€â”€ Prediction Insights Section â”€â”€
  Widget _buildPredictionInsights() {
    if (match.prediction == null || match.prediction!.isEmpty) {
      return const SizedBox.shrink();
    }

    final List<Map<String, dynamic>> insights = [];

    // xG values
    if (match.xgHome != null && match.xgAway != null) {
      insights.add({
        'icon': Icons.sports_soccer,
        'label': 'Expected Goals (xG)',
        'value':
            '${match.xgHome!.toStringAsFixed(2)}  -  ${match.xgAway!.toStringAsFixed(2)}',
        'sub': '${match.homeTeam} vs ${match.awayTeam}',
      });
    }

    // Win / O-U probabilities — sport-aware
    if (_isBasketball) {
      insights.add({
        'icon': Icons.sports_basketball,
        'label': 'Over / Under Probability',
        'value': 'OVER ${(_probOver * 100).toInt()}%  |  UNDER ${(_probUnder * 100).toInt()}%',
      });
    } else {
      insights.add({
        'icon': Icons.pie_chart_outline,
        'label': 'Win Probability',
        'value':
            'H ${(match.probHome * 100).toInt()}%  |  D ${(match.probDraw * 100).toInt()}%  |  A ${(match.probAway * 100).toInt()}%',
      });
    }

    // Odds
    if (match.odds != null && match.odds!.isNotEmpty && match.odds != '-') {
      insights.add({
        'icon': Icons.monetization_on_outlined,
        'label': 'Market Odds',
        'value': match.odds!,
      });
    }

    // Reliability
    if (match.reliabilityScore != null &&
        match.reliabilityScore! > 0) {
      insights.add({
        'icon': Icons.verified_outlined,
        'label': 'Model Reliability',
        'value': '${match.reliabilityScore!.toStringAsFixed(1)}%',
      });
    }

    // Confidence
    if (match.confidence != null && match.confidence!.isNotEmpty) {
      insights.add({
        'icon': Icons.speed,
        'label': 'Confidence Level',
        'value': match.confidence!,
      });
    }

    // Reason tags
    if (match.reasonTags != null && match.reasonTags!.isNotEmpty) {
      insights.add({
        'icon': Icons.label_outline,
        'label': 'Reason Tags',
        'value': match.reasonTags!.replaceAll('|', '  |  '),
      });
    }

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.neutral800,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: Colors.white10),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.insights, size: 16, color: AppColors.primary),
              const SizedBox(width: 8),
              Text(
                "PREDICTION DATA & INSIGHTS",
                style: GoogleFonts.dmSans(
                  color: AppColors.primary,
                  fontSize: 11,
                  fontWeight: FontWeight.w800,
                  letterSpacing: 1.2,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          ...insights.map((insight) => Padding(
                padding: const EdgeInsets.only(bottom: 10),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Icon(
                      insight['icon'] as IconData,
                      size: 16,
                      color: AppColors.textGrey.withValues(alpha: 0.7),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            insight['label'] as String,
                            style: GoogleFonts.dmSans(
                              color: Colors.white54,
                              fontSize: 10,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                          const SizedBox(height: 2),
                          Text(
                            insight['value'] as String,
                            style: GoogleFonts.dmSans(
                              color: Colors.white,
                              fontSize: 12,
                              fontWeight: FontWeight.w800,
                            ),
                          ),
                          if (insight['sub'] != null) ...[
                            const SizedBox(height: 1),
                            Text(
                              insight['sub'] as String,
                              style: GoogleFonts.dmSans(
                                color: Colors.white30,
                                fontSize: 9,
                              ),
                            ),
                          ],
                        ],
                      ),
                    ),
                  ],
                ),
              )),
          // AI Reasoning
          const SizedBox(height: 4),
          Container(
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.03),
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: Colors.white10),
            ),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Icon(
                  Icons.auto_awesome,
                  size: 14,
                  color: Colors.cyanAccent,
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    match.aiReasoningSentence,
                    style: GoogleFonts.dmSans(
                      color: Colors.white60,
                      fontSize: 10,
                      fontStyle: FontStyle.italic,
                      height: 1.4,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildStandingsSection() {
    if (_standings.isEmpty) return const SizedBox.shrink();

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.neutral800,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: Colors.white10),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                "LEAGUE STANDINGS",
                style: GoogleFonts.dmSans(
                  color: Colors.white54,
                  fontSize: 10,
                  fontWeight: FontWeight.bold,
                  letterSpacing: 1.5,
                ),
              ),
              GestureDetector(
                onTap: () {
                  Navigator.push(
                    context,
                    MaterialPageRoute(
                      builder: (context) => LeagueScreen(
                        leagueId: match.leagueId ?? match.league ?? '',
                        leagueName: match.league ?? '',
                      ),
                    ),
                  );
                },
                child: Text(
                  match.league?.toUpperCase() ?? "",
                  style: GoogleFonts.dmSans(
                    color: AppColors.primary,
                    fontSize: 9,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: SizedBox(
              width: 500, // Explicit width for horizontal scrolling
              child: Column(
                children: [
                  DefaultTextStyle(
                    style:
                        GoogleFonts.dmSans(fontSize: 10, color: Colors.white38),
                    child: const Padding(
                      padding: EdgeInsets.symmetric(vertical: 4),
                      child: Row(
                        children: [
                          SizedBox(width: 25, child: Text("#")),
                          SizedBox(width: 30), // Space for crest
                          Expanded(child: Text("TEAM")),
                          SizedBox(
                              width: 30,
                              child: Text("P", textAlign: TextAlign.center)),
                          SizedBox(
                              width: 30,
                              child: Text("W", textAlign: TextAlign.center)),
                          SizedBox(
                              width: 30,
                              child: Text("D", textAlign: TextAlign.center)),
                          SizedBox(
                              width: 30,
                              child: Text("L", textAlign: TextAlign.center)),
                          SizedBox(
                              width: 35,
                              child: Text("GF", textAlign: TextAlign.center)),
                          SizedBox(
                              width: 35,
                              child: Text("GA", textAlign: TextAlign.center)),
                          SizedBox(
                              width: 35,
                              child: Text("GD", textAlign: TextAlign.center)),
                          SizedBox(
                              width: 45,
                              child: Text("PTS", textAlign: TextAlign.center)),
                        ],
                      ),
                    ),
                  ),
                  const Divider(height: 8, color: Colors.white10),
                  ..._standings.map((s) {
                    final normalizedTableTeam = s.teamName.toLowerCase();
                    final hTeam = match.homeTeam.toLowerCase();
                    final aTeam = match.awayTeam.toLowerCase();

                    final isHome = normalizedTableTeam.contains(hTeam) ||
                        hTeam.contains(normalizedTableTeam);
                    final isAway = normalizedTableTeam.contains(aTeam) ||
                        aTeam.contains(normalizedTableTeam);
                    final isMatchTeam = isHome || isAway;

                    return Padding(
                      padding: const EdgeInsets.symmetric(vertical: 6),
                      child: Row(
                        children: [
                          // Position
                          SizedBox(
                            width: 25,
                            child: Text(
                              s.position.toString(),
                              style: TextStyle(
                                color: isMatchTeam
                                    ? AppColors.primary
                                    : Colors.white70,
                                fontSize: 11,
                                fontWeight: isMatchTeam
                                    ? FontWeight.bold
                                    : FontWeight.normal,
                              ),
                            ),
                          ),
                          // Crest
                          SizedBox(
                            width: 30,
                            child: s.teamCrestUrl != null &&
                                    s.teamCrestUrl != 'Unknown'
                                ? CachedNetworkImage(
                                    imageUrl: s.teamCrestUrl!,
                                    height: 18,
                                    width: 18,
                                    placeholder: (ctx, url) => Container(),
                                    errorWidget: (ctx, url, err) => const Icon(
                                        Icons.shield,
                                        size: 14,
                                        color: Colors.white10),
                                  )
                                : const Icon(Icons.shield,
                                    size: 14, color: Colors.white10),
                          ),
                          // Team Name
                          Expanded(
                            child: GestureDetector(
                              onTap: () {
                                Navigator.push(
                                  context,
                                  MaterialPageRoute(
                                    builder: (context) => TeamScreen(
                                      teamName: s.teamName,
                                      repository:
                                          context.read<DataRepository>(),
                                    ),
                                  ),
                                );
                              },
                              child: Text(
                                s.teamName,
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                                style: TextStyle(
                                  color: isMatchTeam
                                      ? AppColors.primary
                                      : Colors.white,
                                  fontSize: 11,
                                  fontWeight: isMatchTeam
                                      ? FontWeight.w900
                                      : FontWeight.normal,
                                ),
                              ),
                            ),
                          ),
                          // Stats
                          SizedBox(
                              width: 30,
                              child: Text(s.played.toString(),
                                  textAlign: TextAlign.center,
                                  style: const TextStyle(
                                      fontSize: 11, color: Colors.white70))),
                          SizedBox(
                              width: 30,
                              child: Text(s.wins.toString(),
                                  textAlign: TextAlign.center,
                                  style: const TextStyle(
                                      fontSize: 11, color: Colors.white70))),
                          SizedBox(
                              width: 30,
                              child: Text(s.draws.toString(),
                                  textAlign: TextAlign.center,
                                  style: const TextStyle(
                                      fontSize: 11, color: Colors.white70))),
                          SizedBox(
                              width: 30,
                              child: Text(s.losses.toString(),
                                  textAlign: TextAlign.center,
                                  style: const TextStyle(
                                      fontSize: 11, color: Colors.white70))),
                          SizedBox(
                              width: 35,
                              child: Text(s.goalsFor.toString(),
                                  textAlign: TextAlign.center,
                                  style: const TextStyle(
                                      fontSize: 11, color: Colors.white70))),
                          SizedBox(
                              width: 35,
                              child: Text(s.goalsAgainst.toString(),
                                  textAlign: TextAlign.center,
                                  style: const TextStyle(
                                      fontSize: 11, color: Colors.white70))),
                          SizedBox(
                              width: 35,
                              child: Text(
                                  (s.goalsFor - s.goalsAgainst).toString(),
                                  textAlign: TextAlign.center,
                                  style: const TextStyle(
                                      fontSize: 11, color: Colors.white70))),
                          // Points
                          SizedBox(
                            width: 45,
                            child: Text(
                              s.points.toString(),
                              textAlign: TextAlign.center,
                              style: TextStyle(
                                color: isMatchTeam
                                    ? AppColors.primary
                                    : Colors.white,
                                fontSize: 11,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                          ),
                        ],
                      ),
                    );
                  }),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  /// Returns "COUNTRY: LEAGUE" — preserves country for context.
  String _parseLeagueName(String leagueStr) {
    if (leagueStr.contains(':')) {
      final parts = leagueStr.split(':');
      if (parts.length >= 2) {
        final country = parts[0].trim().toUpperCase();
        final league = parts.sublist(1).join(':').trim().toUpperCase();
        return '$country: $league';
      }
    }
    return leagueStr.toUpperCase();
  }
}
