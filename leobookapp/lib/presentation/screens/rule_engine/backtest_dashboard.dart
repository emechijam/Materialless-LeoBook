// backtest_dashboard.dart: Rule Engine Studio — engines, stairway, RL jobs, backtests.
// Part of LeoBook App — Rule Engine Screens

import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:leobookapp/core/constants/app_colors.dart';
import 'package:leobookapp/core/widgets/leo_loading_indicator.dart';
import 'package:leobookapp/data/models/stairway_model.dart';
import 'package:leobookapp/data/models/rule_config_model.dart';
import 'package:leobookapp/data/models/user_model.dart';
import 'package:leobookapp/data/services/leo_service.dart';
import 'package:leobookapp/data/services/rl_training_jobs_service.dart';
import 'package:leobookapp/data/services/rule_engines_service.dart';
import 'package:leobookapp/data/services/user_account_snapshots_service.dart';
import 'package:leobookapp/logic/cubit/user_cubit.dart';
import 'rule_editor_screen.dart';

class BacktestDashboard extends StatefulWidget {
  const BacktestDashboard({super.key});

  @override
  State<BacktestDashboard> createState() => _BacktestDashboardState();
}

class _BacktestDashboardState extends State<BacktestDashboard> {
  final RuleEnginesService _enginesService = RuleEnginesService();
  final UserAccountSnapshotsService _snapshots = UserAccountSnapshotsService();
  final RlTrainingJobsService _rlJobs = RlTrainingJobsService();
  final LeoService _leoFile = LeoService();

  bool _isLoading = false;
  List<Map<String, dynamic>> _results = [];
  List<RuleConfigModel> _engines = [];
  RuleConfigModel? _currentConfig;
  UserStairwaySnapshot? _stairway;
  UserFbBalanceSnapshot? _fbBalance;
  List<Map<String, dynamic>> _jobRows = [];
  String? _selectedRlEngineId;

  @override
  void initState() {
    super.initState();
    _loadAll();
  }

  Future<void> _loadAll() async {
    setState(() => _isLoading = true);
    try {
      _engines = await _enginesService.loadAll();
      _currentConfig = await _enginesService.getDefaultEngine();
      final results = await Future.wait([
        _snapshots.fetchStairway(),
        _snapshots.fetchFbBalance(),
      ]);
      _stairway = results[0] as UserStairwaySnapshot?;
      _fbBalance = results[1] as UserFbBalanceSnapshot?;
      _jobRows = await _rlJobs.recentJobs(limit: 15);
      _selectedRlEngineId = _currentConfig?.id;
      if (!kIsWeb && _currentConfig != null) {
        await _refreshResults();
      }
    } catch (e) {
      debugPrint('BacktestDashboard load: $e');
    }
    if (mounted) setState(() => _isLoading = false);
  }

  Future<void> _refreshResults() async {
    if (_currentConfig == null) return;
    try {
      final results = await _leoFile.getBacktestResults(_currentConfig!.name);
      if (mounted) setState(() => _results = results);
    } catch (e) {
      debugPrint('Results: $e');
    }
  }

  Future<void> _runBacktest() async {
    if (_currentConfig == null) return;
    setState(() => _isLoading = true);
    try {
      await _leoFile.triggerBacktest(_currentConfig!);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text(
              'Backtest triggered. Run Leo.py with --rule-engine --backtest locally for full CSV output.',
            ),
          ),
        );
      }
      await Future<void>.delayed(const Duration(seconds: 2));
      await _refreshResults();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
      }
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  Future<void> _openEditor(RuleConfigModel? engine) async {
    final changed = await Navigator.push<bool>(
      context,
      MaterialPageRoute(builder: (_) => RuleEditorScreen(engine: engine)),
    );
    if (changed == true) await _loadAll();
  }

  Future<void> _enqueueRl(UserModel user) async {
    if (!user.canTrainRl) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('RL training is included with Super LeoBook.')),
      );
      return;
    }
    final eid = _selectedRlEngineId ?? _currentConfig?.id ?? 'default';
    try {
      await _rlJobs.enqueue(ruleEngineId: eid, trainSeason: 'current', phase: 1);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Training job queued. Worker will pick it up.')),
        );
      }
      _jobRows = await _rlJobs.recentJobs(limit: 15);
      if (mounted) setState(() {});
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
      }
    }
  }

  int _customCount() => _enginesService.countCustomEnginesSync(_engines);

  Future<void> _newEngine(UserModel user) async {
    final maxC = user.maxCustomRuleEngines;
    if (maxC != null && _customCount() >= maxC) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Free plan allows up to $maxC custom engines. Upgrade to Super for unlimited.')),
      );
      return;
    }
    await _openEditor(null);
  }

  @override
  Widget build(BuildContext context) {
    final isDesktop = MediaQuery.of(context).size.width > 1024;
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return BlocBuilder<UserCubit, UserState>(
      builder: (context, ustate) {
        final user = ustate.user;
        return Scaffold(
          backgroundColor: isDark ? AppColors.neutral900 : Colors.white,
          body: _isLoading && _engines.isEmpty
              ? const LeoLoadingIndicator(label: 'Loading Rule Engine Studio…')
              : CustomScrollView(
                  slivers: [
                    _buildSliverAppBar(isDesktop, isDark),
                    SliverPadding(
                      padding: EdgeInsets.all(isDesktop ? 32 : 16),
                      sliver: SliverToBoxAdapter(
                        child: Center(
                          child: ConstrainedBox(
                            constraints: const BoxConstraints(maxWidth: 1000),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                if (isDesktop) ...[
                                  Row(
                                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                    children: [
                                      const Text(
                                        'RULE ENGINE STUDIO',
                                        style: TextStyle(
                                          fontSize: 24,
                                          fontWeight: FontWeight.w900,
                                          color: Colors.white,
                                          letterSpacing: -1,
                                          fontStyle: FontStyle.italic,
                                        ),
                                      ),
                                      Wrap(
                                        spacing: 8,
                                        children: [
                                          _hdrBtn(Icons.add, 'NEW', () => _newEngine(user)),
                                          _hdrBtn(Icons.edit_outlined, 'EDIT', () async {
                                            if (_currentConfig != null) {
                                              await _openEditor(_currentConfig);
                                            }
                                          }),
                                          _hdrBtn(Icons.refresh, 'REFRESH', _loadAll),
                                        ],
                                      ),
                                    ],
                                  ),
                                  const SizedBox(height: 24),
                                ],
                                _stairwayCard(),
                                const SizedBox(height: 12),
                                _fbBalanceCard(),
                                const SizedBox(height: 20),
                                _enginesSection(user),
                                const SizedBox(height: 20),
                                _rlSection(user),
                                const SizedBox(height: 24),
                                _buildSummaryCard(isDesktop),
                                const SizedBox(height: 24),
                                const Text(
                                  'HISTORICAL RESULTS',
                                  style: TextStyle(
                                    fontSize: 12,
                                    fontWeight: FontWeight.w900,
                                    color: AppColors.textGrey,
                                    letterSpacing: 2,
                                  ),
                                ),
                                const SizedBox(height: 16),
                                if (isDesktop) _buildResultsGrid() else _buildResultsList(),
                              ],
                            ),
                          ),
                        ),
                      ),
                    ),
                    const SliverToBoxAdapter(child: SizedBox(height: 80)),
                  ],
                ),
          floatingActionButtonLocation: FloatingActionButtonLocation.endFloat,
          floatingActionButton: Padding(
            padding: const EdgeInsets.only(bottom: 112),
            child: FloatingActionButton.extended(
              onPressed: kIsWeb || _currentConfig == null ? null : _runBacktest,
              backgroundColor: AppColors.primary,
              foregroundColor: Colors.white,
              elevation: 4,
              label: const Text(
                'TRIGGER BACKTEST',
                style: TextStyle(fontWeight: FontWeight.w900, letterSpacing: 1),
              ),
              icon: const Icon(Icons.play_arrow_rounded),
            ),
          ),
        );
      },
    );
  }

  Widget _hdrBtn(IconData icon, String label, VoidCallback onTap) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(12),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
        decoration: BoxDecoration(
          color: AppColors.surfaceDark,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: Colors.white10),
        ),
        child: Row(
          children: [
            Icon(icon, color: Colors.white70, size: 18),
            const SizedBox(width: 8),
            Text(
              label,
              style: const TextStyle(
                fontSize: 10,
                fontWeight: FontWeight.w900,
                color: Colors.white70,
                letterSpacing: 1,
              ),
            ),
          ],
        ),
      ),
    );
  }

  // 4x per step over 7 steps: totalMultiplier = 4^7 = 16384
  static const double _stairSeed = 1000;
  static const double _stairMultiplier = 16384; // 4^7

  static String _fmtAmount(double v) {
    if (v >= 1000000) return '${(v / 1000000).toStringAsFixed(1)}M';
    if (v >= 1000) return '${(v / 1000).toStringAsFixed(0)}K';
    return v.toStringAsFixed(0);
  }

  Widget _stairwayCard() {
    final s = _stairway;
    final step = s?.currentStep ?? 1;
    final project = StairwayProject(
      seedAmount: _stairSeed,
      targetMultiplier: _stairMultiplier,
      stepCount: 7,
      currentStep: step,
      cycleCount: s?.cycleCount ?? 0,
      lastResult: s?.lastResult,
    );
    final active = project.activeStep;

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AppColors.surfaceDark,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: Colors.white10),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // ── Header ──────────────────────────────────────────────
          Row(
            children: [
              Icon(Icons.stairs_rounded,
                  color: AppColors.primary.withValues(alpha: 0.9)),
              const SizedBox(width: 8),
              const Text(
                'PROJECT STAIRWAY',
                style: TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w900,
                  color: AppColors.textGrey,
                  letterSpacing: 1.5,
                ),
              ),
              const Spacer(),
              Text(
                project.progressLabel,
                style: const TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w700,
                  color: AppColors.textGrey,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),

          if (s == null) ...[
            const Text(
              'No stairway sync yet. Run Leo with --user-id after placing bets.',
              style: TextStyle(fontSize: 13, color: AppColors.textGrey),
            ),
          ] else ...[
            // ── Progress bar ─────────────────────────────────────
            ClipRRect(
              borderRadius: BorderRadius.circular(4),
              child: LinearProgressIndicator(
                value: project.progressPct,
                backgroundColor: Colors.white10,
                color: AppColors.primary,
                minHeight: 6,
              ),
            ),
            const SizedBox(height: 14),

            // ── Current step seed → target ────────────────────────
            Row(
              children: [
                Text(
                  '₦${_fmtAmount(active.seedAmount)}',
                  style: const TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.w900,
                    color: Colors.white,
                  ),
                ),
                const Padding(
                  padding: EdgeInsets.symmetric(horizontal: 8),
                  child: Icon(Icons.arrow_forward,
                      size: 16, color: AppColors.textGrey),
                ),
                Text(
                  '₦${_fmtAmount(active.targetAmount)}',
                  style: const TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.w900,
                    color: AppColors.success,
                  ),
                ),
                const Spacer(),
                Text(
                  'Cycles: ${s.cycleCount}',
                  style: const TextStyle(
                      fontSize: 12, color: AppColors.textGrey),
                ),
              ],
            ),

            // ── Last result + week stats ──────────────────────────
            const SizedBox(height: 6),
            Text(
              'This week: ${s.weekCyclesCompleted} completed'
              '${s.lastResult != null ? ' · Last: ${s.lastResult}' : ''}',
              style: const TextStyle(fontSize: 12, color: AppColors.textGrey),
            ),
            const SizedBox(height: 14),

            // ── Step dots ────────────────────────────────────────
            Row(
              children: project.steps.map((st) {
                final Color col = st.isCompleted
                    ? AppColors.success
                    : st.isActive
                        ? AppColors.primary
                        : Colors.white10;
                return Expanded(
                  child: Container(
                    margin: const EdgeInsets.symmetric(horizontal: 2),
                    height: 5,
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(3),
                      color: col,
                    ),
                  ),
                );
              }).toList(),
            ),
          ],
        ],
      ),
    );
  }

  Widget _fbBalanceCard() {
    final bal = _fbBalance;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
      decoration: BoxDecoration(
        color: AppColors.surfaceDark,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: Colors.white10),
      ),
      child: Row(
        children: [
          Icon(Icons.account_balance_wallet_outlined,
              color: AppColors.primary.withValues(alpha: 0.9), size: 20),
          const SizedBox(width: 10),
          Expanded(
            child: bal == null
                ? const Text(
                    'Football.com balance not synced yet',
                    style: TextStyle(fontSize: 13, color: AppColors.textGrey),
                  )
                : Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        '${bal.currency} ${bal.balance.toStringAsFixed(2)}',
                        style: const TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.w800,
                          color: Colors.white,
                        ),
                      ),
                      if (bal.capturedAt != null)
                        Text(
                          'Updated: ${bal.capturedAt!.substring(0, 16).replaceFirst('T', ' ')}',
                          style: const TextStyle(fontSize: 11, color: AppColors.textGrey),
                        ),
                    ],
                  ),
          ),
          IconButton(
            icon: const Icon(Icons.refresh, size: 18),
            tooltip: 'Refresh balance from Supabase',
            onPressed: () async {
              final fresh = await _snapshots.fetchFbBalance();
              if (mounted) setState(() => _fbBalance = fresh);
            },
          ),
        ],
      ),
    );
  }

  Widget _enginesSection(UserModel user) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            const Text(
              'YOUR ENGINES',
              style: TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w900,
                color: AppColors.textGrey,
                letterSpacing: 2,
              ),
            ),
            TextButton.icon(
              onPressed: () => _newEngine(user),
              icon: const Icon(Icons.add, size: 18),
              label: const Text('New engine'),
            ),
          ],
        ),
        const SizedBox(height: 8),
        if (_engines.isEmpty)
          const Text('No engines yet.', style: TextStyle(color: AppColors.textGrey))
        else
          ..._engines.map((e) {
            final isDef = e.isDefault;
            return Card(
              color: AppColors.neutral900.withValues(alpha: 0.6),
              child: ListTile(
                title: Text(e.name, style: const TextStyle(fontWeight: FontWeight.bold)),
                subtitle: Text(
                  e.description.isEmpty ? e.id : e.description,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
                trailing: Wrap(
                  spacing: 4,
                  children: [
                    if (isDef)
                      const Chip(
                        label: Text('DEFAULT', style: TextStyle(fontSize: 10)),
                        visualDensity: VisualDensity.compact,
                      ),
                    IconButton(
                      icon: const Icon(Icons.edit, size: 20),
                      onPressed: () => _openEditor(e),
                    ),
                    if (e.id != 'default')
                      IconButton(
                        icon: const Icon(Icons.delete_outline, size: 20),
                        onPressed: () async {
                          await _enginesService.deleteEngine(e.id);
                          await _loadAll();
                        },
                      ),
                  ],
                ),
                onTap: () async {
                  await _enginesService.setDefaultEngine(e.id);
                  await _loadAll();
                },
              ),
            );
          }),
      ],
    );
  }

  Widget _rlSection(UserModel user) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'RL TRAINING',
          style: TextStyle(
            fontSize: 12,
            fontWeight: FontWeight.w900,
            color: AppColors.textGrey,
            letterSpacing: 2,
          ),
        ),
        const SizedBox(height: 8),
        Row(
          children: [
            Expanded(
              child: DropdownButtonFormField<String>(
                value: _engines.isEmpty
                    ? null
                    : (_selectedRlEngineId ?? _engines.first.id),
                decoration: const InputDecoration(
                  labelText: 'Engine for expert signal',
                  border: OutlineInputBorder(),
                  isDense: true,
                ),
                items: _engines
                    .map((e) => DropdownMenuItem(value: e.id, child: Text(e.name)))
                    .toList(),
                onChanged: _engines.isEmpty ? null : (v) => setState(() => _selectedRlEngineId = v),
              ),
            ),
            const SizedBox(width: 12),
            FilledButton.icon(
              onPressed: () => _enqueueRl(user),
              icon: const Icon(Icons.model_training),
              label: const Text('Queue job'),
            ),
          ],
        ),
        const SizedBox(height: 12),
        if (_jobRows.isEmpty)
          const Text('No jobs yet.', style: TextStyle(color: AppColors.textGrey, fontSize: 12))
        else
          ..._jobRows.take(5).map(
                (j) => ListTile(
                  dense: true,
                  title: Text(
                    '${j['status']} · ${j['rule_engine_id']}',
                    style: const TextStyle(fontSize: 13),
                  ),
                  subtitle: Text(
                    '${j['requested_at'] ?? ''}',
                    style: const TextStyle(fontSize: 11),
                  ),
                ),
              ),
      ],
    );
  }

  Widget _buildSliverAppBar(bool isDesktop, bool isDark) {
    if (isDesktop) return const SliverToBoxAdapter(child: SizedBox.shrink());

    return SliverAppBar(
      expandedHeight: 120,
      floating: false,
      pinned: true,
      backgroundColor: isDark ? AppColors.neutral900 : Colors.white,
      surfaceTintColor: Colors.transparent,
      actions: [
        IconButton(icon: const Icon(Icons.add), onPressed: () => _newEngine(context.read<UserCubit>().state.user)),
        IconButton(icon: const Icon(Icons.refresh), onPressed: _loadAll),
      ],
      flexibleSpace: FlexibleSpaceBar(
        titlePadding: const EdgeInsets.only(left: 16, bottom: 16),
        title: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'RULE ENGINE STUDIO',
              style: TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w900,
                color: AppColors.primary.withValues(alpha: 0.8),
                letterSpacing: 2,
              ),
            ),
            const Text(
              'Engines · Stairway · RL',
              style: TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.w900,
                color: Colors.white,
              ),
            ),
          ],
        ),
        background: Container(
          decoration: BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topCenter,
              end: Alignment.bottomCenter,
              colors: [
                AppColors.primary.withValues(alpha: 0.15),
                AppColors.neutral900,
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildSummaryCard(bool isDesktop) {
    int total = _results.length;
    int correct = _results.where((r) => r['outcome_correct'] == 'True').length;

    return Container(
      padding: EdgeInsets.all(isDesktop ? 32 : 16),
      decoration: BoxDecoration(
        color: AppColors.surfaceDark,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: Colors.white10),
      ),
      child: Column(
        children: [
          Row(
            children: [
              const Icon(Icons.analytics_outlined, color: AppColors.primary, size: 20),
              const SizedBox(width: 8),
              Text(
                'CONFIG: ${_currentConfig?.name.toUpperCase() ?? 'DEFAULT'}',
                style: const TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w900,
                  color: AppColors.textGrey,
                  letterSpacing: 1.5,
                ),
              ),
            ],
          ),
          const SizedBox(height: 24),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceAround,
            children: [
              _statItem('TOTAL MATCHES', '$total'),
              _statItem(
                'WIN RATE',
                total == 0 ? 'N/A' : '${(correct / total * 100).toStringAsFixed(1)}%',
              ),
              _statItem('PROFIT/LOSS', 'N/A'),
            ],
          ),
        ],
      ),
    );
  }

  Widget _statItem(String label, String value) {
    final isPrimary = label == 'WIN RATE';
    return Column(
      children: [
        Text(
          value,
          style: TextStyle(
            fontSize: isPrimary ? 32 : 24,
            fontWeight: FontWeight.w900,
            color: isPrimary ? AppColors.success : Colors.white,
            fontStyle: FontStyle.italic,
          ),
        ),
        Text(
          label,
          style: const TextStyle(
            color: AppColors.textGrey,
            fontSize: 10,
            fontWeight: FontWeight.w900,
            letterSpacing: 1,
          ),
        ),
      ],
    );
  }

  Widget _buildResultsGrid() {
    if (_results.isEmpty) {
      return const Center(
        child: Text(
          'No local backtest CSV yet. Desktop + Leo.py produce backtest files.',
          style: TextStyle(color: AppColors.textGrey),
        ),
      );
    }
    return GridView.builder(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
        crossAxisCount: 3,
        crossAxisSpacing: 16,
        mainAxisSpacing: 16,
        childAspectRatio: 2.2,
      ),
      itemCount: _results.length,
      itemBuilder: (context, index) {
        final row = _results[index];
        final isWin = row['outcome_correct'] == 'True';
        return Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: AppColors.neutral900.withValues(alpha: 0.5),
            borderRadius: BorderRadius.circular(16),
            border: Border.all(
              color: isWin ? AppColors.success.withValues(alpha: 0.2) : Colors.white10,
            ),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'MATCH #${index + 1}',
                style: const TextStyle(fontSize: 9, fontWeight: FontWeight.w900, color: AppColors.textGrey),
              ),
              const Spacer(),
              Text(
                '${row['home_team']} VS ${row['away_team']}'.toUpperCase(),
                style: const TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: Colors.white),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _buildResultsList() {
    if (_results.isEmpty) {
      return const Text(
        'No local backtest rows. Use desktop workflow with Leo.py for CSV output.',
        style: TextStyle(color: AppColors.textGrey),
      );
    }
    return ListView.builder(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      itemCount: _results.length,
      itemBuilder: (context, index) {
        final row = _results[index];
        final isWin = row['outcome_correct'] == 'True';
        return Card(
          margin: const EdgeInsets.only(bottom: 12),
          color: AppColors.surfaceDark,
          child: ListTile(
            title: Text('${row['home_team']} vs ${row['away_team']}'),
            trailing: Icon(
              isWin ? Icons.check_circle : Icons.cancel,
              color: isWin ? AppColors.success : AppColors.liveRed,
            ),
          ),
        );
      },
    );
  }
}
