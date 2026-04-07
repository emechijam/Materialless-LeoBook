// sport_switcher.dart: Pill-chip sport selector bar.
// Part of LeoBook App — Shared Widgets
//
// Reads availableSports from HomeCubit and calls updateSport() on tap.
// Scales automatically as new sports are added to the data.

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:leobookapp/core/constants/app_colors.dart';
import 'package:leobookapp/core/constants/responsive_constants.dart';
import 'package:leobookapp/logic/cubit/home_cubit.dart';

/// Maps a sport key → (display label, icon).
/// Add entries here as new sports land in the backend — UI auto-updates.
const Map<String, ({String label, IconData icon})> _kSportMeta = {
  'ALL':        (label: 'All',        icon: Icons.all_inclusive_rounded),
  'FOOTBALL':   (label: 'Football',   icon: Icons.sports_soccer_rounded),
  'BASKETBALL': (label: 'Basketball', icon: Icons.sports_basketball_rounded),
  'TENNIS':     (label: 'Tennis',     icon: Icons.sports_tennis_rounded),
  'CRICKET':    (label: 'Cricket',    icon: Icons.sports_cricket_rounded),
  'RUGBY':      (label: 'Rugby',      icon: Icons.sports_rugby_rounded),
};

/// Horizontal pill-chip sport switcher.
/// Place inside a [BlocBuilder<HomeCubit, HomeState>] or any widget tree
/// that has [HomeCubit] in scope.
class SportSwitcher extends StatelessWidget {
  /// Horizontal padding to match surrounding content.
  final double horizontalPadding;

  const SportSwitcher({super.key, this.horizontalPadding = 16});

  @override
  Widget build(BuildContext context) {
    return BlocBuilder<HomeCubit, HomeState>(
      buildWhen: (prev, curr) {
        // Only rebuild when sport selection or available sports change.
        if (prev is HomeLoaded && curr is HomeLoaded) {
          return prev.selectedSport != curr.selectedSport ||
              prev.availableSports.length != curr.availableSports.length;
        }
        return curr is HomeLoaded;
      },
      builder: (context, state) {
        if (state is! HomeLoaded) return const SizedBox.shrink();

        final sports = state.availableSports;
        // Don't render if only 'ALL' is present (nothing to switch between).
        if (sports.length <= 1) return const SizedBox.shrink();

        final selected = state.selectedSport.toUpperCase();

        return SizedBox(
          height: Responsive.sp(context, 36),
          child: ListView.separated(
            scrollDirection: Axis.horizontal,
            padding: EdgeInsets.symmetric(horizontal: horizontalPadding),
            itemCount: sports.length,
            separatorBuilder: (_, __) =>
                SizedBox(width: Responsive.sp(context, 8)),
            itemBuilder: (context, i) {
              final key = sports[i].toUpperCase();
              final isSelected = key == selected;
              final meta = _kSportMeta[key] ??
                  (label: _toTitle(sports[i]), icon: Icons.emoji_events_rounded);

              return _SportChip(
                label: meta.label,
                icon: meta.icon,
                isSelected: isSelected,
                onTap: () {
                  HapticFeedback.selectionClick();
                  context.read<HomeCubit>().updateSport(sports[i]);
                },
              );
            },
          ),
        );
      },
    );
  }

  String _toTitle(String s) =>
      s.isEmpty ? s : s[0].toUpperCase() + s.substring(1).toLowerCase();
}

class _SportChip extends StatelessWidget {
  final String label;
  final IconData icon;
  final bool isSelected;
  final VoidCallback onTap;

  const _SportChip({
    required this.label,
    required this.icon,
    required this.isSelected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 220),
        curve: Curves.easeOutCubic,
        padding: EdgeInsets.symmetric(
          horizontal: Responsive.sp(context, 12),
          vertical: Responsive.sp(context, 6),
        ),
        decoration: BoxDecoration(
          gradient: isSelected
              ? LinearGradient(
                  colors: [
                    AppColors.primary,
                    AppColors.primary.withValues(alpha: 0.75),
                  ],
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                )
              : null,
          color: isSelected ? null : Colors.white.withValues(alpha: 0.06),
          borderRadius: BorderRadius.circular(Responsive.sp(context, 20)),
          border: Border.all(
            color: isSelected
                ? AppColors.primary.withValues(alpha: 0.0)
                : Colors.white.withValues(alpha: 0.12),
            width: 1,
          ),
          boxShadow: isSelected
              ? [
                  BoxShadow(
                    color: AppColors.primary.withValues(alpha: 0.35),
                    blurRadius: 8,
                    offset: const Offset(0, 3),
                  ),
                ]
              : null,
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              icon,
              size: Responsive.sp(context, 13),
              color: isSelected ? Colors.white : Colors.white54,
            ),
            SizedBox(width: Responsive.sp(context, 5)),
            Text(
              label,
              style: TextStyle(
                fontSize: Responsive.sp(context, 10),
                fontWeight:
                    isSelected ? FontWeight.w800 : FontWeight.w600,
                color: isSelected ? Colors.white : Colors.white54,
                letterSpacing: 0.3,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
