// account_screen.dart: Grok-style settings/profile page.
// Part of LeoBook App — Screens
//
// Grouped sections with category headers, glass cards, version footer
// with in-app update availability check.

import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:local_auth/local_auth.dart';
import 'package:leobookapp/core/constants/app_colors.dart';
import 'package:leobookapp/core/theme/leo_typography.dart';
import 'package:leobookapp/core/services/update_service.dart';
import 'package:leobookapp/data/models/user_model.dart';
import 'package:leobookapp/logic/cubit/user_cubit.dart';
import 'package:leobookapp/presentation/screens/login_screen.dart';
import 'package:leobookapp/presentation/screens/super_leobook_screen.dart';
import 'package:leobookapp/presentation/screens/subscription_screen.dart';
import 'package:leobookapp/presentation/screens/stairway_screen.dart';
import 'package:leobookapp/presentation/screens/accuracy_dashboard_screen.dart';

class AccountScreen extends StatelessWidget {
  const AccountScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return BlocListener<UserCubit, UserState>(
      listener: (context, state) {
        // If user logs out, show login
        if (state is UserInitial && state.user.isGuest) {
          final isDesktop = MediaQuery.of(context).size.width > 1024;
          if (isDesktop) {
            // Desktop: show login as a centered modal dialog
            showDialog(
              context: context,
              barrierDismissible: false,
              barrierColor: Colors.black87,
              builder: (_) => BlocProvider.value(
                value: context.read<UserCubit>(),
                child: const LoginScreen(),
              ),
            );
          } else {
            // Mobile: navigate to full-screen login
            Navigator.of(context).pushAndRemoveUntil(
              MaterialPageRoute(builder: (_) => const LoginScreen()),
              (_) => false,
            );
          }
        }
      },
      child: Scaffold(
        backgroundColor: AppColors.neutral900,
        body: SafeArea(
          child: Column(
            children: [
              const SizedBox(height: 12),

              // ── Scrollable body ────────────────────────────────
              Expanded(
                child: SingleChildScrollView(
                  padding: const EdgeInsets.symmetric(horizontal: 16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const SizedBox(height: 8),
                      // ── Profile Card ───────────────────────────
                      _buildProfileCard(context),
                      const SizedBox(height: 16),

                      // ── Super LeoBook Upsell ──────────────────
                      _buildSuperUpsell(context),
                      const SizedBox(height: 28),

                      // ── Pro Features ───────────────────────────
                      _sectionLabel('Pro Features'),
                      const SizedBox(height: 8),
                      _glassGroup([
                        _settingsTile(
                          icon: Icons.stairs_rounded,
                          title: 'Project Stairway',
                          subtitle: 'ROI & cycle dashboard',
                          onTap: () => Navigator.of(context).push(
                            MaterialPageRoute(
                              builder: (_) => BlocProvider.value(
                                value: context.read<UserCubit>(),
                                child: const StairwayScreen(),
                              ),
                            ),
                          ),
                        ),
                        _settingsTile(
                          icon: Icons.analytics_outlined,
                          title: 'Accuracy Dashboard',
                          subtitle: 'Win rates & ROI history',
                          onTap: () => Navigator.of(context).push(
                            MaterialPageRoute(
                              builder: (_) => BlocProvider.value(
                                value: context.read<UserCubit>(),
                                child: const AccuracyDashboardScreen(),
                              ),
                            ),
                          ),
                        ),
                        _settingsTile(
                          icon: Icons.workspace_premium_rounded,
                          title: 'Manage Subscription',
                          subtitle: 'Paystack · Stripe',
                          onTap: () => Navigator.of(context).push(
                            MaterialPageRoute(
                              builder: (_) => BlocProvider.value(
                                value: context.read<UserCubit>(),
                                child: const SubscriptionScreen(),
                              ),
                            ),
                          ),
                        ),
                      ]),
                      const SizedBox(height: 28),

                      // ── General ────────────────────────────────
                      _sectionLabel('General'),
                      const SizedBox(height: 8),
                      _glassGroup([
                        _settingsTile(
                          icon: Icons.brightness_6_outlined,
                          title: 'Appearance',
                          subtitle: 'Dark',
                          onTap: () {},
                        ),
                        _settingsTile(
                          icon: Icons.notifications_outlined,
                          title: 'Notifications',
                          onTap: () {},
                        ),
                        _settingsTile(
                          icon: Icons.language,
                          title: 'Language',
                          subtitle: 'English',
                          onTap: () {},
                        ),
                        _settingsTile(
                          icon: Icons.tune_rounded,
                          title: 'Advanced',
                          onTap: () {},
                        ),
                      ]),
                      const SizedBox(height: 28),

                      // ── Data & Information ─────────────────────
                      _sectionLabel('Security'),
                      const SizedBox(height: 8),
                      _buildSecuritySection(context),
                      const SizedBox(height: 28),
                      _sectionLabel('Data & Information'),
                      const SizedBox(height: 8),
                      _glassGroup([
                        _settingsTile(
                          icon: Icons.shield_outlined,
                          title: 'Data Controls',
                          onTap: () {},
                        ),
                        _settingsTile(
                          icon: Icons.storage_outlined,
                          title: 'Cached Data',
                          onTap: () {},
                        ),
                      ]),
                      const SizedBox(height: 28),

                      // ── Legal ──────────────────────────────────
                      _glassGroup([
                        _settingsTile(
                          icon: Icons.description_outlined,
                          title: 'Open Source Licenses',
                          onTap: () => showLicensePage(
                            context: context,
                            applicationName: 'LeoBook',
                            applicationVersion: context
                                .read<UpdateCubit>()
                                .state
                                .info
                                .currentVersion,
                          ),
                        ),
                        _settingsTile(
                          icon: Icons.article_outlined,
                          title: 'Terms of Use',
                          onTap: () {},
                        ),
                        _settingsTile(
                          icon: Icons.lock_outline,
                          title: 'Privacy Policy',
                          onTap: () {},
                        ),
                      ]),
                      const SizedBox(height: 28),

                      // ── Actions ────────────────────────────────
                      _glassGroup([
                        _settingsTile(
                          icon: Icons.bug_report_outlined,
                          title: 'Report a Problem',
                          onTap: () {},
                        ),
                        _settingsTile(
                          icon: Icons.logout_rounded,
                          title: 'Sign out',
                          titleColor: AppColors.liveRed,
                          onTap: () => context.read<UserCubit>().logout(),
                        ),
                      ]),
                      const SizedBox(height: 32),

                      // ── Version Footer ─────────────────────────
                      _buildVersionFooter(context),
                      const SizedBox(height: 32),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  // ═══════════════════════════════════════════════════════════════════
  // Profile Card
  // ═══════════════════════════════════════════════════════════════════

  Widget _buildProfileCard(BuildContext context) {
    return BlocBuilder<UserCubit, UserState>(
      builder: (context, state) {
        final user = state.user;
        return Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: AppColors.neutral800,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(
              color: Colors.white.withValues(alpha: 0.06),
            ),
          ),
          child: Row(
            children: [
              CircleAvatar(
                radius: 24,
                backgroundColor: AppColors.primary.withValues(alpha: 0.15),
                child: Text(
                  (user.displayName ?? user.id)
                      .substring(
                          0, (user.displayName ?? user.id).length >= 2 ? 2 : 1)
                      .toUpperCase(),
                  style: GoogleFonts.dmSans(
                    fontSize: 16,
                    fontWeight: FontWeight.w800,
                    color: AppColors.primary,
                  ),
                ),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      user.displayName ??
                          (user.isGuest ? 'Guest' : 'LeoBook User'),
                      style: GoogleFonts.dmSans(
                        fontSize: 15,
                        fontWeight: FontWeight.w600,
                        color: Colors.white,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      user.email ?? user.phone ?? user.id,
                      style: GoogleFonts.dmSans(
                        fontSize: 12,
                        color: AppColors.textTertiary,
                      ),
                    ),
                  ],
                ),
              ),
              if (user.isSuperLeoBook)
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      colors: [AppColors.primary, AppColors.primaryLight],
                    ),
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: Text(
                    'SUPER',
                    style: GoogleFonts.dmSans(
                      fontSize: 10,
                      fontWeight: FontWeight.w800,
                      color: Colors.white,
                    ),
                  ),
                ),
            ],
          ),
        );
      },
    );
  }

  // ═══════════════════════════════════════════════════════════════════
  // Super LeoBook Upsell Card
  // ═══════════════════════════════════════════════════════════════════

  Widget _buildSuperUpsell(BuildContext context) {
    return BlocBuilder<UserCubit, UserState>(
      builder: (context, state) {
        final user = state.user;
        if (user.isSuperLeoBook) return const SizedBox.shrink();

        return GestureDetector(
          onTap: () => Navigator.of(context).push(
            MaterialPageRoute(builder: (_) => const SuperLeoBookScreen()),
          ),
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
            decoration: BoxDecoration(
              color: AppColors.neutral800,
              borderRadius: BorderRadius.circular(16),
              border: Border.all(
                color: AppColors.primary.withValues(alpha: 0.15),
              ),
            ),
            child: Row(
              children: [
                Icon(Icons.auto_awesome, color: AppColors.primary, size: 22),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Try Super LeoBook free',
                        style: GoogleFonts.dmSans(
                          fontSize: 14,
                          fontWeight: FontWeight.w600,
                          color: Colors.white,
                        ),
                      ),
                      Text(
                        'Unlimited rules, automation, priority access',
                        style: GoogleFonts.dmSans(
                          fontSize: 11,
                          color: AppColors.textTertiary,
                        ),
                      ),
                    ],
                  ),
                ),
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                  decoration: BoxDecoration(
                    color: AppColors.primary,
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: Text(
                    'Try Now',
                    style: GoogleFonts.dmSans(
                      fontSize: 11,
                      fontWeight: FontWeight.w700,
                      color: Colors.white,
                    ),
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  // ═══════════════════════════════════════════════════════════════════
  // Section Label
  // ═══════════════════════════════════════════════════════════════════

  Widget _buildSecuritySection(BuildContext context) {
    return FutureBuilder<bool>(
      future: _isBiometricAccessAvailable(),
      builder: (context, snapshot) {
        final supportsBiometrics = snapshot.data ?? false;

        return BlocBuilder<UserCubit, UserState>(
          builder: (context, state) {
            final user = state.user;
            final subtitle = user.isGuest
                ? 'Sign in to manage'
                : supportsBiometrics
                    ? (user.isBiometricsEnabled ? 'Enabled' : 'Off')
                    : 'Unavailable';

            return _glassGroup([
              _settingsTile(
                icon: Icons.fingerprint_rounded,
                title: 'App Access',
                subtitle: subtitle,
                onTap: () => _handleAppAccessTap(
                  context,
                  user,
                  supportsBiometrics: supportsBiometrics,
                ),
              ),
            ]);
          },
        );
      },
    );
  }

  Future<void> _handleAppAccessTap(
    BuildContext context,
    UserModel user, {
    required bool supportsBiometrics,
  }) async {
    if (user.isGuest) {
      _showMessage(context, 'Sign in to manage biometric app access.');
      return;
    }

    if (!supportsBiometrics) {
      await showDialog<void>(
        context: context,
        builder: (dialogContext) => AlertDialog(
          backgroundColor: AppColors.neutral800,
          title: Text(
            'App Access',
            style: GoogleFonts.dmSans(
              color: Colors.white,
              fontWeight: FontWeight.w600,
            ),
          ),
          content: Text(
            'Biometric access is not available on this device yet.',
            style: GoogleFonts.dmSans(
              color: AppColors.textTertiary,
              fontSize: 13,
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(dialogContext).pop(),
              child: Text(
                'Close',
                style: GoogleFonts.dmSans(color: AppColors.primary),
              ),
            ),
          ],
        ),
      );
      return;
    }

    final cubit = context.read<UserCubit>();
    if (user.isBiometricsEnabled) {
      final shouldDisable = await showDialog<bool>(
        context: context,
        builder: (dialogContext) => AlertDialog(
          backgroundColor: AppColors.neutral800,
          title: Text(
            'Disable App Access?',
            style: GoogleFonts.dmSans(
              color: Colors.white,
              fontWeight: FontWeight.w600,
            ),
          ),
          content: Text(
            'LeoBook will stop offering fingerprint or face sign-in on this device.',
            style: GoogleFonts.dmSans(
              color: AppColors.textTertiary,
              fontSize: 13,
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(dialogContext).pop(false),
              child: Text(
                'Cancel',
                style: GoogleFonts.dmSans(color: AppColors.textTertiary),
              ),
            ),
            TextButton(
              onPressed: () => Navigator.of(dialogContext).pop(true),
              child: Text(
                'Turn Off',
                style: GoogleFonts.dmSans(color: AppColors.liveRed),
              ),
            ),
          ],
        ),
      );

      if (shouldDisable != true) {
        return;
      }

      await cubit.enableBiometrics(false);
      if (!context.mounted) {
        return;
      }

      final latestState = cubit.state;
      if (latestState is UserError) {
        _showMessage(context, latestState.message);
        return;
      }

      _showMessage(
        context,
        'Biometric app access turned off.',
        backgroundColor: AppColors.primary,
      );
      return;
    }

    final password = await _promptForAppAccessPassword(context);
    if (!context.mounted || password == null) {
      return;
    }

    await cubit.enableBiometrics(true, password: password);
    if (!context.mounted) {
      return;
    }

    final latestState = cubit.state;
    if (latestState is UserError) {
      _showMessage(context, latestState.message);
      return;
    }

    _showMessage(
      context,
      'Biometric app access is now enabled.',
      backgroundColor: AppColors.primary,
    );
  }

  Future<String?> _promptForAppAccessPassword(BuildContext context) async {
    final controller = TextEditingController();

    final result = await showDialog<String>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        backgroundColor: AppColors.neutral800,
        title: Text(
          'Enable App Access',
          style: GoogleFonts.dmSans(
            color: Colors.white,
            fontWeight: FontWeight.w600,
          ),
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Enter your current LeoBook password to use fingerprint or face sign-in on this device.',
              style: GoogleFonts.dmSans(
                color: AppColors.textTertiary,
                fontSize: 13,
                height: 1.4,
              ),
            ),
            const SizedBox(height: 16),
            TextField(
              controller: controller,
              obscureText: true,
              style: GoogleFonts.dmSans(color: Colors.white),
              decoration: InputDecoration(
                hintText: 'Current password',
                hintStyle: GoogleFonts.dmSans(color: AppColors.textDisabled),
                filled: true,
                fillColor: AppColors.neutral900,
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide:
                      BorderSide(color: Colors.white.withValues(alpha: 0.08)),
                ),
                enabledBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide:
                      BorderSide(color: Colors.white.withValues(alpha: 0.08)),
                ),
                focusedBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: const BorderSide(color: AppColors.primary),
                ),
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(),
            child: Text(
              'Cancel',
              style: GoogleFonts.dmSans(color: AppColors.textTertiary),
            ),
          ),
          TextButton(
            onPressed: () =>
                Navigator.of(dialogContext).pop(controller.text.trim()),
            child: Text(
              'Enable',
              style: GoogleFonts.dmSans(color: AppColors.primary),
            ),
          ),
        ],
      ),
    );

    controller.dispose();

    if (!context.mounted || result == null) {
      return null;
    }

    if (result.isEmpty) {
      _showMessage(
          context, 'Enter your current password to enable biometrics.');
      return null;
    }

    return result;
  }

  Future<bool> _isBiometricAccessAvailable() async {
    final localAuth = LocalAuthentication();

    try {
      return await localAuth.isDeviceSupported() &&
          await localAuth.canCheckBiometrics;
    } catch (_) {
      return false;
    }
  }

  void _showMessage(
    BuildContext context,
    String message, {
    Color backgroundColor = AppColors.liveRed,
  }) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: backgroundColor,
      ),
    );
  }

  Widget _sectionLabel(String label) {
    return Padding(
      padding: const EdgeInsets.only(left: 4),
      child: Text(
        label,
        style: GoogleFonts.dmSans(
          fontSize: 12,
          fontWeight: FontWeight.w500,
          color: AppColors.textTertiary,
        ),
      ),
    );
  }

  // ═══════════════════════════════════════════════════════════════════
  // Glass Group
  // ═══════════════════════════════════════════════════════════════════

  Widget _glassGroup(List<Widget> children) {
    return Container(
      decoration: BoxDecoration(
        color: AppColors.neutral800,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(
          color: Colors.white.withValues(alpha: 0.06),
        ),
      ),
      child: Column(
        children: [
          for (int i = 0; i < children.length; i++) ...[
            children[i],
            if (i < children.length - 1)
              Divider(
                height: 0.5,
                thickness: 0.5,
                color: Colors.white.withValues(alpha: 0.06),
                indent: 52,
              ),
          ],
        ],
      ),
    );
  }

  // ═══════════════════════════════════════════════════════════════════
  // Settings Tile
  // ═══════════════════════════════════════════════════════════════════

  Widget _settingsTile({
    required IconData icon,
    required String title,
    String? subtitle,
    Color? titleColor,
    required VoidCallback onTap,
  }) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(14),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 13),
        child: Row(
          children: [
            Icon(icon, color: titleColor ?? AppColors.textTertiary, size: 20),
            const SizedBox(width: 14),
            Expanded(
              child: Text(
                title,
                style: GoogleFonts.dmSans(
                  fontSize: 14,
                  fontWeight: FontWeight.w400,
                  color: titleColor ?? Colors.white,
                ),
              ),
            ),
            if (subtitle != null) ...[
              Text(
                subtitle,
                style: GoogleFonts.dmSans(
                  fontSize: 12,
                  color: AppColors.textTertiary,
                ),
              ),
              const SizedBox(width: 8),
            ],
            if (titleColor == null)
              const Icon(
                Icons.arrow_forward_ios,
                size: 12,
                color: AppColors.textDisabled,
              ),
          ],
        ),
      ),
    );
  }

  // ═══════════════════════════════════════════════════════════════════
  // Version Footer with Update Check
  // ═══════════════════════════════════════════════════════════════════

  Widget _buildVersionFooter(BuildContext context) {
    return BlocBuilder<UpdateCubit, UpdateState>(
      builder: (context, updateState) {
        final info = updateState.info;
        final dlState = updateState.downloadState;
        final cubit = context.read<UpdateCubit>();
        return Center(
          child: Column(
            children: [
              Text(
                'LeoBook v${info.currentVersion.isNotEmpty ? info.currentVersion : "..."}',
                style: LeoTypography.bodySmall.copyWith(
                  color: AppColors.textDisabled,
                  fontFeatures: [const FontFeature.tabularFigures()],
                ),
              ),
              if (info.updateAvailable) ...[
                const SizedBox(height: 6),

                // ── Downloading: progress bar ──────────────────
                if (dlState == UpdateDownloadState.downloading) ...[
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 40),
                    child: Column(
                      children: [
                        ClipRRect(
                          borderRadius: BorderRadius.circular(4),
                          child: LinearProgressIndicator(
                            value: updateState.downloadProgress,
                            backgroundColor: AppColors.neutral700,
                            color: AppColors.primary,
                            minHeight: 6,
                          ),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          '${(updateState.downloadProgress * 100).toStringAsFixed(0)}%',
                          style: LeoTypography.labelSmall.copyWith(
                            color: AppColors.textTertiary,
                          ),
                        ),
                      ],
                    ),
                  ),
                ]

                // ── Installing ─────────────────────────────────
                else if (dlState == UpdateDownloadState.installing) ...[
                  Text(
                    'Installing…',
                    style: LeoTypography.bodySmall.copyWith(
                      color: AppColors.primary,
                    ),
                  ),
                ]

                // ── Error: show message + retry ────────────────
                else if (dlState == UpdateDownloadState.error) ...[
                  Text(
                    updateState.errorMessage ?? 'Update failed',
                    style: LeoTypography.labelSmall.copyWith(
                      color: AppColors.liveRed,
                    ),
                  ),
                  const SizedBox(height: 4),
                  GestureDetector(
                    onTap: () {
                      cubit.resetDownloadState();
                      cubit.downloadAndInstall();
                    },
                    child: Text(
                      'Retry',
                      style: LeoTypography.bodySmall.copyWith(
                        fontWeight: FontWeight.w600,
                        color: AppColors.primary,
                        decoration: TextDecoration.underline,
                        decorationColor: AppColors.primary,
                      ),
                    ),
                  ),
                ]

                // ── Idle: show "Update" tap target ─────────────
                else ...[
                  GestureDetector(
                    onTap: () => cubit.downloadAndInstall(),
                    child: RichText(
                      text: TextSpan(
                        style: LeoTypography.bodySmall,
                        children: [
                          TextSpan(
                            text: 'v${info.latestVersion} available — ',
                            style: TextStyle(color: AppColors.textTertiary),
                          ),
                          TextSpan(
                            text: 'Update',
                            style: TextStyle(
                              color: AppColors.primary,
                              fontWeight: FontWeight.w600,
                              decoration: TextDecoration.underline,
                              decorationColor: AppColors.primary,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ],
              ],
              const SizedBox(height: 12),
              Text(
                'A Materialless Creation',
                style: LeoTypography.labelSmall.copyWith(
                  color: AppColors.textDisabled,
                  letterSpacing: 0.5,
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}
