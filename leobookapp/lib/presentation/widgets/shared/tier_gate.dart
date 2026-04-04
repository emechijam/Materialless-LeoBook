// tier_gate.dart: Tier-based access gate widget for Pro features.
// Part of LeoBook App — Widgets
//
// Usage:
//   TierGate(
//     requirement: TierRequirement.canAutomateBetting,
//     child: AutomationScreen(),
//   )
//
// Shows a locked-feature paywall when the current user does not satisfy
// the requirement. Tapping "Upgrade" opens SubscriptionScreen.

import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:leobookapp/core/constants/app_colors.dart';
import 'package:leobookapp/data/models/user_model.dart';
import 'package:leobookapp/logic/cubit/user_cubit.dart';
import 'package:leobookapp/presentation/screens/subscription_screen.dart';

/// Describes the access requirement for a gated feature.
enum TierRequirement {
  /// Requires UserModel.canAutomateBetting == true (Pro tier).
  canAutomateBetting,

  /// Requires UserModel.canAccessChapter2 == true (Pro tier).
  canAccessChapter2,

  /// Requires any paid tier (lite or pro — not guest).
  authenticated,

  /// Requires Pro tier (isPro == true).
  pro,
}

/// Wraps [child] and enforces a [TierRequirement].
///
/// If the current user satisfies the requirement the child is rendered
/// transparently. Otherwise a paywall overlay is shown in place of the child.
class TierGate extends StatelessWidget {
  const TierGate({
    super.key,
    required this.requirement,
    required this.child,
    this.featureName,
    this.featureDescription,
  });

  final TierRequirement requirement;
  final Widget child;

  /// Short label shown in the paywall (e.g. "Betting Automation").
  final String? featureName;

  /// One-liner description for the paywall (e.g. "Automate bet placement via Chapter 2").
  final String? featureDescription;

  bool _passes(UserModel user) {
    switch (requirement) {
      case TierRequirement.canAutomateBetting:
        return user.canAutomateBetting;
      case TierRequirement.canAccessChapter2:
        return user.canAccessChapter2;
      case TierRequirement.authenticated:
        return user.isAuthenticated;
      case TierRequirement.pro:
        return user.isPro;
    }
  }

  @override
  Widget build(BuildContext context) {
    return BlocBuilder<UserCubit, UserState>(
      builder: (context, state) {
        if (_passes(state.user)) {
          return child;
        }
        return _LockedView(
          featureName: featureName ?? _defaultFeatureName(requirement),
          featureDescription:
              featureDescription ?? _defaultDescription(requirement),
        );
      },
    );
  }

  static String _defaultFeatureName(TierRequirement r) {
    switch (r) {
      case TierRequirement.canAutomateBetting:
        return 'Betting Automation';
      case TierRequirement.canAccessChapter2:
        return 'Chapter 2';
      case TierRequirement.authenticated:
        return 'This Feature';
      case TierRequirement.pro:
        return 'Pro Feature';
    }
  }

  static String _defaultDescription(TierRequirement r) {
    switch (r) {
      case TierRequirement.canAutomateBetting:
        return 'Automate bet placement and withdrawal via Chapter 2.';
      case TierRequirement.canAccessChapter2:
        return 'Access advanced booking, placement, and automation tools.';
      case TierRequirement.authenticated:
        return 'Sign in to access this feature.';
      case TierRequirement.pro:
        return 'Upgrade to Pro to unlock this feature.';
    }
  }
}

// ─── Locked Paywall View ───────────────────────────────────────────────────

class _LockedView extends StatelessWidget {
  const _LockedView({
    required this.featureName,
    required this.featureDescription,
  });

  final String featureName;
  final String featureDescription;

  @override
  Widget build(BuildContext context) {
    return Container(
      color: AppColors.neutral900,
      child: Center(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 40),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              // Lock icon
              Container(
                width: 72,
                height: 72,
                decoration: BoxDecoration(
                  color: AppColors.primary.withValues(alpha: 0.12),
                  shape: BoxShape.circle,
                ),
                child: const Icon(
                  Icons.lock_outline_rounded,
                  color: AppColors.primary,
                  size: 36,
                ),
              ),
              const SizedBox(height: 20),

              // Feature name
              Text(
                featureName,
                style: GoogleFonts.dmSans(
                  fontSize: 20,
                  fontWeight: FontWeight.w700,
                  color: Colors.white,
                ),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 8),

              // Description
              Text(
                featureDescription,
                style: GoogleFonts.dmSans(
                  fontSize: 14,
                  color: AppColors.textTertiary,
                  height: 1.5,
                ),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 28),

              // Pro badge
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  color: AppColors.warning.withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Text(
                  'Pro Feature',
                  style: GoogleFonts.dmSans(
                    fontSize: 11,
                    fontWeight: FontWeight.w700,
                    color: AppColors.warning,
                  ),
                ),
              ),
              const SizedBox(height: 20),

              // Upgrade CTA
              GestureDetector(
                onTap: () {
                  Navigator.of(context).push(
                    MaterialPageRoute(
                      builder: (_) => BlocProvider.value(
                        value: context.read<UserCubit>(),
                        child: const SubscriptionScreen(),
                      ),
                    ),
                  );
                },
                child: Container(
                  width: double.infinity,
                  constraints: const BoxConstraints(maxWidth: 320),
                  padding: const EdgeInsets.symmetric(vertical: 14),
                  decoration: BoxDecoration(
                    color: AppColors.primary,
                    borderRadius: BorderRadius.circular(12),
                  ),
                  alignment: Alignment.center,
                  child: Text(
                    'Upgrade to Pro',
                    style: GoogleFonts.dmSans(
                      fontSize: 15,
                      fontWeight: FontWeight.w700,
                      color: Colors.white,
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
