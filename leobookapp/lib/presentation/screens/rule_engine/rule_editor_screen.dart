// rule_editor_screen.dart: Full rule engine editor with weight sliders.
// Part of LeoBook App — Rule Engine Screens
//
// Classes: RuleEditorScreen, _RuleEditorScreenState

import 'package:flutter/material.dart';
import 'package:leobookapp/core/constants/app_colors.dart';
import 'package:leobookapp/core/constants/responsive_constants.dart';
import 'package:leobookapp/core/widgets/glass_container.dart';
import 'package:leobookapp/data/models/rule_config_model.dart';
import 'package:leobookapp/data/services/leo_service.dart';
import 'package:leobookapp/data/services/rl_config_service.dart';
import 'package:leobookapp/core/widgets/leo_loading_indicator.dart';

class RuleEditorScreen extends StatefulWidget {
  final RuleConfigModel? engine;
  const RuleEditorScreen({super.key, this.engine});

  @override
  State<RuleEditorScreen> createState() => _RuleEditorScreenState();
}

class _RuleEditorScreenState extends State<RuleEditorScreen> {
  late RuleConfigModel _config;
  final LeoService _service = LeoService();
  bool _isSaving = false;
  bool _isNew = false;

  late TextEditingController _nameCtrl;
  late TextEditingController _descCtrl;

  // ML filter config (synced to user_rl_config in Supabase)
  final RlConfigService _rlService = RlConfigService();
  RlConfig? _rlConfig;

  @override
  void initState() {
    super.initState();
    if (widget.engine != null) {
      _config = RuleConfigModel.fromJson(widget.engine!.toJson());
    } else {
      _isNew = true;
      _config = RuleConfigModel(
        id: 'custom_${DateTime.now().millisecondsSinceEpoch}',
        name: '',
        description: '',
        isDefault: false,
      );
    }
    _nameCtrl = TextEditingController(text: _config.name);
    _descCtrl = TextEditingController(text: _config.description);
    _loadRlConfig();
  }

  Future<void> _loadRlConfig() async {
    final cfg = await _rlService.load();
    if (mounted) setState(() => _rlConfig = cfg);
  }

  @override
  void dispose() {
    _nameCtrl.dispose();
    _descCtrl.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (_nameCtrl.text.trim().isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Engine name is required')),
      );
      return;
    }
    setState(() => _isSaving = true);
    _config.name = _nameCtrl.text.trim();
    _config.description = _descCtrl.text.trim();

    try {
      // Save rule engine to local file
      await _service.saveEngine(_config);
      // Sync ML filter preferences to Supabase
      if (_rlConfig != null) await _rlService.save(_rlConfig!);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('${_config.name} saved!')),
        );
        Navigator.pop(context, true);
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: $e')),
        );
      }
    } finally {
      if (mounted) setState(() => _isSaving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final title = _isNew ? 'New Engine' : 'Edit: ${widget.engine?.name ?? ""}';

    return Scaffold(
      appBar: AppBar(
        title: Text(title),
        centerTitle: true,
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _isSaving ? null : _save,
        backgroundColor: AppColors.success,
        foregroundColor: Colors.white,
        icon: _isSaving
            ? const SizedBox(
                child: LeoLoadingIndicator(
                  size: 16,
                  color: Colors.white,
                ),
              )
            : const Icon(Icons.save),
        label: const Text(
          'SAVE ENGINE',
          style: TextStyle(fontWeight: FontWeight.w900, letterSpacing: 1),
        ),
      ),
      body: ListView(
        padding: EdgeInsets.symmetric(
          horizontal: Responsive.horizontalPadding(context),
          vertical: 16,
        ),
        children: [
          _buildIdentitySection(),
          const SizedBox(height: 16),
          _buildParametersSection(),
          const SizedBox(height: 16),
          _buildWeightSection('xG Weights', [
            _SliderDef('xG Advantage', _config.xgAdvantage,
                (v) => _config.xgAdvantage = v),
            _SliderDef(
                'xG Draw Signal', _config.xgDraw, (v) => _config.xgDraw = v),
          ]),
          const SizedBox(height: 16),
          _buildWeightSection('Head-to-Head', [
            _SliderDef('H2H Home Win', _config.h2hHomeWin,
                (v) => _config.h2hHomeWin = v),
            _SliderDef('H2H Away Win', _config.h2hAwayWin,
                (v) => _config.h2hAwayWin = v),
            _SliderDef('H2H Draw', _config.h2hDraw, (v) => _config.h2hDraw = v),
            _SliderDef('H2H Over 2.5', _config.h2hOver25,
                (v) => _config.h2hOver25 = v),
          ]),
          const SizedBox(height: 16),
          _buildWeightSection('League Standings', [
            _SliderDef('Top vs Bottom', _config.standingsTopBottom,
                (v) => _config.standingsTopBottom = v),
            _SliderDef('Table Advantage 8+', _config.standingsTableAdv,
                (v) => _config.standingsTableAdv = v),
            _SliderDef('Strong GD', _config.standingsGdStrong,
                (v) => _config.standingsGdStrong = v),
            _SliderDef('Weak GD', _config.standingsGdWeak,
                (v) => _config.standingsGdWeak = v),
          ]),
          const SizedBox(height: 16),
          _buildWeightSection('Recent Form', [
            _SliderDef('Scores 2+', _config.formScore2plus,
                (v) => _config.formScore2plus = v),
            _SliderDef('Scores 3+', _config.formScore3plus,
                (v) => _config.formScore3plus = v),
            _SliderDef('Concedes 2+', _config.formConcede2plus,
                (v) => _config.formConcede2plus = v),
            _SliderDef('Fails to Score', _config.formNoScore,
                (v) => _config.formNoScore = v),
            _SliderDef('Clean Sheet', _config.formCleanSheet,
                (v) => _config.formCleanSheet = v),
            _SliderDef('Beats Top Teams', _config.formVsTopWin,
                (v) => _config.formVsTopWin = v),
          ]),
          const SizedBox(height: 16),
          _buildMlFilterSection(),
          const SizedBox(height: 80), // Padding for FAB
        ],
      ),
    );
  }

  // ── Identity ──────────────────────────────────────

  Widget _buildIdentitySection() {
    return GlassContainer(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Identity',
              style: TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.w700,
                color: AppColors.textPrimary,
              ),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _nameCtrl,
              decoration: const InputDecoration(
                labelText: 'Engine Name',
                hintText: "e.g. James' Law",
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 10),
            TextField(
              controller: _descCtrl,
              decoration: const InputDecoration(
                labelText: 'Description',
                hintText: 'Conservative H2H-heavy engine for top leagues',
                border: OutlineInputBorder(),
              ),
              maxLines: 2,
            ),
          ],
        ),
      ),
    );
  }

  // ── Parameters ────────────────────────────────────

  Widget _buildParametersSection() {
    return GlassContainer(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Parameters',
              style: TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.w700,
                color: AppColors.textPrimary,
              ),
            ),
            const SizedBox(height: 12),

            // Risk Preference
            Row(
              children: [
                Icon(Icons.shield_outlined,
                    size: 18, color: AppColors.textGrey),
                const SizedBox(width: 8),
                Text('Risk Preference',
                    style: TextStyle(color: AppColors.textGrey)),
                const Spacer(),
                DropdownButton<String>(
                  value: _config.riskPreference,
                  items: const [
                    DropdownMenuItem(
                        value: 'conservative', child: Text('Conservative')),
                    DropdownMenuItem(value: 'medium', child: Text('Medium')),
                    DropdownMenuItem(
                        value: 'aggressive', child: Text('Aggressive')),
                  ],
                  onChanged: (v) {
                    if (v != null) setState(() => _config.riskPreference = v);
                  },
                ),
              ],
            ),
            const Divider(height: 24),

            // H2H Lookback
            _buildNumberRow(
              'H2H Lookback (days)',
              _config.h2hLookbackDays,
              (v) => setState(() => _config.h2hLookbackDays = v),
            ),
            const SizedBox(height: 8),

            // Min Form Matches
            _buildNumberRow(
              'Min Form Matches',
              _config.minFormMatches,
              (v) => setState(() => _config.minFormMatches = v),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildNumberRow(String label, int value, ValueChanged<int> onChanged) {
    return Row(
      children: [
        Expanded(
          child: Text(label, style: TextStyle(color: AppColors.textGrey)),
        ),
        SizedBox(
          width: 80,
          child: TextField(
            controller: TextEditingController(text: value.toString()),
            keyboardType: TextInputType.number,
            textAlign: TextAlign.center,
            decoration: const InputDecoration(
              isDense: true,
              contentPadding: EdgeInsets.symmetric(horizontal: 8, vertical: 8),
              border: OutlineInputBorder(),
            ),
            onChanged: (v) => onChanged(int.tryParse(v) ?? value),
          ),
        ),
      ],
    );
  }

  // ── Weight Sections ───────────────────────────────

  Widget _buildWeightSection(String title, List<_SliderDef> sliders) {
    return GlassContainer(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              title,
              style: TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.w700,
                color: AppColors.textPrimary,
              ),
            ),
            const SizedBox(height: 8),
            ...sliders.map(_buildSlider),
          ],
        ),
      ),
    );
  }

  Widget _buildSlider(_SliderDef def) {
    return Column(
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(
              def.label,
              style: TextStyle(
                fontSize: 13,
                color: AppColors.textGrey,
              ),
            ),
            Text(
              def.value.toStringAsFixed(1),
              style: TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.w600,
                color: AppColors.textPrimary,
              ),
            ),
          ],
        ),
        SliderTheme(
          data: SliderThemeData(
            trackHeight: 3,
            thumbShape: const RoundSliderThumbShape(enabledThumbRadius: 6),
            overlayShape: const RoundSliderOverlayShape(overlayRadius: 14),
            activeTrackColor: AppColors.success,
            inactiveTrackColor:
                AppColors.glassBorder.withValues(alpha: 0.2),
            thumbColor: AppColors.success,
          ),
          child: Slider(
            value: def.value,
            min: 0,
            max: 10,
            divisions: 20,
            onChanged: (v) => setState(() => def.setter(v)),
          ),
        ),
      ],
    );
  }

  // ── ML Filter (user_rl_config) ────────────────────

  Widget _buildMlFilterSection() {
    final cfg = _rlConfig;
    if (cfg == null) {
      return const SizedBox(
        height: 60,
        child: Center(child: LeoLoadingIndicator()),
      );
    }

    return GlassContainer(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.tune, size: 18, color: AppColors.accentPrimary),
                const SizedBox(width: 8),
                Text(
                  'ML Filter (Supabase)',
                  style: TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.w700,
                    color: AppColors.textPrimary,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 4),
            Text(
              'These thresholds filter predictions before they reach your feed.',
              style: TextStyle(fontSize: 12, color: AppColors.textGrey),
            ),
            const SizedBox(height: 16),

            // Risk appetite
            Row(
              children: [
                Icon(Icons.shield_outlined, size: 16, color: AppColors.textGrey),
                const SizedBox(width: 8),
                Text('Risk Appetite',
                    style: TextStyle(color: AppColors.textGrey)),
                const Spacer(),
                DropdownButton<String>(
                  value: cfg.riskAppetite,
                  items: const [
                    DropdownMenuItem(value: 'low',    child: Text('Low')),
                    DropdownMenuItem(value: 'medium', child: Text('Medium')),
                    DropdownMenuItem(value: 'high',   child: Text('High')),
                  ],
                  onChanged: (v) {
                    if (v != null) {
                      setState(() => _rlConfig = cfg.copyWith(riskAppetite: v));
                    }
                  },
                ),
              ],
            ),
            const Divider(height: 20),

            // Min confidence slider (0.35 – 0.90)
            _buildDoubleSliderRow(
              label: 'Min Confidence',
              value: cfg.minConfidence,
              min: 0.35,
              max: 0.90,
              divisions: 11,
              format: (v) => '${(v * 100).round()}%',
              onChanged: (v) =>
                  setState(() => _rlConfig = cfg.copyWith(minConfidence: v)),
            ),
            const SizedBox(height: 8),

            // Min odds slider (1.0 – 3.0)
            _buildDoubleSliderRow(
              label: 'Min Odds',
              value: cfg.minOdds,
              min: 1.0,
              max: 3.0,
              divisions: 20,
              format: (v) => v.toStringAsFixed(2),
              onChanged: (v) =>
                  setState(() => _rlConfig = cfg.copyWith(minOdds: v)),
            ),
            const SizedBox(height: 8),

            // Max odds slider (2.0 – 12.0)
            _buildDoubleSliderRow(
              label: 'Max Odds',
              value: cfg.maxOdds,
              min: 2.0,
              max: 12.0,
              divisions: 20,
              format: (v) => v.toStringAsFixed(2),
              onChanged: (v) =>
                  setState(() => _rlConfig = cfg.copyWith(maxOdds: v)),
            ),
            const SizedBox(height: 8),

            // Max stake % slider (1% – 20%)
            _buildDoubleSliderRow(
              label: 'Max Stake %',
              value: cfg.maxStakePct,
              min: 0.01,
              max: 0.20,
              divisions: 19,
              format: (v) => '${(v * 100).round()}%',
              onChanged: (v) =>
                  setState(() => _rlConfig = cfg.copyWith(maxStakePct: v)),
            ),
            const Divider(height: 20),

            // Enabled sports toggles
            Text('Enabled Sports',
                style: TextStyle(color: AppColors.textGrey, fontSize: 13)),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              children: ['football', 'basketball'].map((sport) {
                final enabled = cfg.enabledSports.contains(sport);
                return FilterChip(
                  label: Text(sport[0].toUpperCase() + sport.substring(1)),
                  selected: enabled,
                  onSelected: (v) {
                    final next = List<String>.from(cfg.enabledSports);
                    if (v) {
                      next.add(sport);
                    } else {
                      next.remove(sport);
                    }
                    setState(() =>
                        _rlConfig = cfg.copyWith(enabledSports: next));
                  },
                );
              }).toList(),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildDoubleSliderRow({
    required String label,
    required double value,
    required double min,
    required double max,
    required int divisions,
    required String Function(double) format,
    required ValueChanged<double> onChanged,
  }) {
    return Column(
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(label,
                style: TextStyle(fontSize: 13, color: AppColors.textGrey)),
            Text(
              format(value),
              style: TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w600,
                  color: AppColors.textPrimary),
            ),
          ],
        ),
        SliderTheme(
          data: SliderThemeData(
            trackHeight: 3,
            thumbShape: const RoundSliderThumbShape(enabledThumbRadius: 6),
            overlayShape: const RoundSliderOverlayShape(overlayRadius: 14),
            activeTrackColor: AppColors.accentPrimary,
            inactiveTrackColor: AppColors.glassBorder.withValues(alpha: 0.2),
            thumbColor: AppColors.accentPrimary,
          ),
          child: Slider(
            value: value.clamp(min, max),
            min: min,
            max: max,
            divisions: divisions,
            onChanged: onChanged,
          ),
        ),
      ],
    );
  }
}

class _SliderDef {
  final String label;
  final double value;
  final ValueChanged<double> setter;
  const _SliderDef(this.label, this.value, this.setter);
}
