// super_leobook_screen.dart: Pro subscription paywall (UI-only).
// Part of LeoBook App — Screens
//
// Grok SuperGrok-inspired layout with feature list, pricing, trial CTA.

import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:leobookapp/core/constants/app_colors.dart';
import 'package:leobookapp/logic/cubit/user_cubit.dart';

class SuperLeoBookScreen extends StatelessWidget {
  const SuperLeoBookScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return BlocListener<UserCubit, UserState>(
      listener: (context, state) {
        if (state is UserAuthenticated && state.user.isSuperLeoBook) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text(
                '🎉 Welcome to Super LeoBook!',
                style: GoogleFonts.lexend(),
              ),
              backgroundColor: AppColors.success,
            ),
          );
          Navigator.of(context).pop();
        }
      },
      child: Scaffold(
        backgroundColor: AppColors.neutral900,
        body: SafeArea(
          child: Column(
            children: [
              // ── Header ── × close + Skip ──────────────────────
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    GestureDetector(
                      onTap: () => Navigator.of(context).pop(),
                      child: const Icon(Icons.close, color: Colors.white, size: 24),
                    ),
                    GestureDetector(
                      onTap: () => Navigator.of(context).pop(),
                      child: Text(
                        'Skip',
                        style: GoogleFonts.lexend(
                          fontSize: 15,
                          fontWeight: FontWeight.w500,
                          color: AppColors.textTertiary,
                        ),
                      ),
                    ),
                  ],
                ),
              ),

              // ── Scrollable body ────────────────────────────────
              Expanded(
                child: SingleChildScrollView(
                  padding: const EdgeInsets.symmetric(horizontal: 24),
                  child: Column(
                    children: [
                      const SizedBox(height: 24),

                      // ── Title ──────────────────────────────────
                      Text(
                        'Super LeoBook',
                        style: GoogleFonts.lexend(
                          fontSize: 28,
                          fontWeight: FontWeight.w800,
                          color: Colors.white,
                        ),
                      ),
                      const SizedBox(height: 6),
                      RichText(
                        text: TextSpan(
                          style: GoogleFonts.lexend(fontSize: 15),
                          children: [
                            const TextSpan(
                              text: 'Try ',
                              style: TextStyle(color: AppColors.textTertiary),
                            ),
                            TextSpan(
                              text: 'Free',
                              style: TextStyle(
                                color: AppColors.warning,
                                fontWeight: FontWeight.w700,
                              ),
                            ),
                            const TextSpan(
                              text: ' for 12 Days',
                              style: TextStyle(color: AppColors.textTertiary),
                            ),
                          ],
                        ),
                      ),

                      const SizedBox(height: 32),

                      // ── Feature List ───────────────────────────
                      _featureCard(
                        Icons.rule_rounded,
                        'Unlimited Rules Creation',
                        'Create unlimited custom rules and RL training sessions',
                      ),
                      _featureCard(
                        Icons.flash_on_rounded,
                        'Unlimited Access During Peak Times',
                        'No throttling during high-traffic match days',
                      ),
                      _featureCard(
                        Icons.new_releases_outlined,
                        'Priority Access to New Features',
                        'Be first to try new prediction models and tools',
                      ),
                      _featureCard(
                        Icons.account_balance_wallet_outlined,
                        'Unlimited Funds Management',
                        'Full betting automation and withdrawal control',
                      ),
                      _featureCard(
                        Icons.star_outline_rounded,
                        'Early Access to Automation',
                        'Chapter 2 booking and placement before public release',
                      ),

                      const SizedBox(height: 40),
                    ],
                  ),
                ),
              ),

              // ── Bottom: Pricing + CTA ──────────────────────────
              _buildBottomSection(context),
            ],
          ),
        ),
      ),
    );
  }

  // ─── Feature Card ──────────────────────────────────────────────────

  Widget _featureCard(IconData icon, String title, String subtitle) {
    return Container(
      margin: const EdgeInsets.only(bottom: 4),
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, color: AppColors.primary, size: 22),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: GoogleFonts.lexend(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                    color: Colors.white,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  subtitle,
                  style: GoogleFonts.lexend(
                    fontSize: 12,
                    color: AppColors.textTertiary,
                    height: 1.4,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  // ─── Bottom Pricing Section ────────────────────────────────────────

  Widget _buildBottomSection(BuildContext context) {
    return Container(
      padding: const EdgeInsets.fromLTRB(24, 16, 24, 16),
      decoration: BoxDecoration(
        color: AppColors.neutral800,
        border: Border(
          top: BorderSide(color: Colors.white.withValues(alpha: 0.06)),
        ),
      ),
      child: Column(
        children: [
          // Pricing row
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            decoration: BoxDecoration(
              color: AppColors.neutral700,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: Colors.white.withValues(alpha: 0.06)),
            ),
            child: Row(
              children: [
                Text(
                  'Monthly',
                  style: GoogleFonts.lexend(
                    fontSize: 14,
                    fontWeight: FontWeight.w500,
                    color: Colors.white,
                  ),
                ),
                const SizedBox(width: 8),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                  decoration: BoxDecoration(
                    color: AppColors.success,
                    borderRadius: BorderRadius.circular(6),
                  ),
                  child: Text(
                    'FREE',
                    style: GoogleFonts.lexend(
                      fontSize: 9,
                      fontWeight: FontWeight.w800,
                      color: Colors.white,
                    ),
                  ),
                ),
                const Spacer(),
                Text(
                  '₦48,500',
                  style: GoogleFonts.lexend(
                    fontSize: 16,
                    fontWeight: FontWeight.w700,
                    color: Colors.white,
                  ),
                ),
                Text(
                  '/month',
                  style: GoogleFonts.lexend(
                    fontSize: 12,
                    color: AppColors.textTertiary,
                  ),
                ),
              ],
            ),
          ),

          const SizedBox(height: 14),

          // CTA button
          BlocBuilder<UserCubit, UserState>(
            builder: (context, state) {
              final isSuperUser = state.user.isSuperLeoBook;
              return GestureDetector(
                onTap: () {
                  if (isSuperUser) {
                    context.read<UserCubit>().cancelSuperLeoBook();
                    ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(
                        content: Text(
                          'Super LeoBook cancelled.',
                          style: GoogleFonts.lexend(),
                        ),
                      ),
                    );
                    Navigator.of(context).pop();
                  } else {
                    context.read<UserCubit>().upgradeToSuperLeoBook();
                  }
                },
                child: Container(
                  width: double.infinity,
                  padding: const EdgeInsets.symmetric(vertical: 16),
                  decoration: BoxDecoration(
                    color: isSuperUser ? AppColors.liveRed : Colors.white,
                    borderRadius: BorderRadius.circular(28),
                  ),
                  child: Center(
                    child: Text(
                      isSuperUser ? 'Cancel Subscription' : 'Start 12-day free trial',
                      style: GoogleFonts.lexend(
                        fontSize: 15,
                        fontWeight: FontWeight.w700,
                        color: isSuperUser ? Colors.white : AppColors.neutral900,
                      ),
                    ),
                  ),
                ),
              );
            },
          ),

          const SizedBox(height: 10),

          // Sub-text
          Text(
            'Renews at ₦48,500 a month, cancel anytime',
            style: GoogleFonts.lexend(
              fontSize: 11,
              color: AppColors.textDisabled,
            ),
          ),

          const SizedBox(height: 6),

          // Terms | Privacy
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Text(
                'Terms',
                style: GoogleFonts.lexend(
                  fontSize: 11,
                  color: AppColors.textTertiary,
                  decoration: TextDecoration.underline,
                  decorationColor: AppColors.textTertiary,
                ),
              ),
              Text(
                ' | ',
                style: GoogleFonts.lexend(
                  fontSize: 11,
                  color: AppColors.textDisabled,
                ),
              ),
              Text(
                'Privacy Policy',
                style: GoogleFonts.lexend(
                  fontSize: 11,
                  color: AppColors.textTertiary,
                  decoration: TextDecoration.underline,
                  decorationColor: AppColors.textTertiary,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
