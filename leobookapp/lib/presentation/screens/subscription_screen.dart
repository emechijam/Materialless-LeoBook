// subscription_screen.dart: Paystack + Stripe subscription paywall.
// Part of LeoBook App — Screens
//
// Two-provider pricing UI: Paystack (₦48,500/mo, Nigeria) and Stripe ($45/mo, international).
// Payment integration is stubbed — replace launchPaystack / launchStripe with
// real SDK calls when provider SDKs are integrated.

import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:leobookapp/core/constants/app_colors.dart';
import 'package:leobookapp/logic/cubit/user_cubit.dart';
import 'package:leobookapp/presentation/screens/login_screen.dart';

class SubscriptionScreen extends StatefulWidget {
  const SubscriptionScreen({super.key});

  @override
  State<SubscriptionScreen> createState() => _SubscriptionScreenState();
}

class _SubscriptionScreenState extends State<SubscriptionScreen> {
  // 'paystack' or 'stripe' — default to Paystack (Nigerian users first)
  String _selectedProvider = 'paystack';
  bool _loading = false;

  static const _paystackPrice = '₦48,500';
  static const _stripePrice = '\$45';

  @override
  Widget build(BuildContext context) {
    return BlocListener<UserCubit, UserState>(
      listener: (context, state) {
        if (state is UserAuthenticated && state.user.isPro) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text(
                'Subscription activated! Welcome to Pro.',
                style: GoogleFonts.dmSans(),
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
              _buildHeader(context),
              Expanded(
                child: SingleChildScrollView(
                  padding: const EdgeInsets.symmetric(horizontal: 24),
                  child: Column(
                    children: [
                      const SizedBox(height: 24),
                      _buildTitle(),
                      const SizedBox(height: 32),
                      _buildFeatures(),
                      const SizedBox(height: 32),
                      _buildProviderSelector(),
                      const SizedBox(height: 40),
                    ],
                  ),
                ),
              ),
              _buildBottomSection(context),
            ],
          ),
        ),
      ),
    );
  }

  // ─── Header ──────────────────────────────────────────────────────────

  Widget _buildHeader(BuildContext context) {
    return Padding(
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
              style: GoogleFonts.dmSans(
                fontSize: 15,
                fontWeight: FontWeight.w500,
                color: AppColors.textTertiary,
              ),
            ),
          ),
        ],
      ),
    );
  }

  // ─── Title ───────────────────────────────────────────────────────────

  Widget _buildTitle() {
    return Column(
      children: [
        Text(
          'Go Pro',
          style: GoogleFonts.dmSans(
            fontSize: 28,
            fontWeight: FontWeight.w800,
            color: Colors.white,
          ),
        ),
        const SizedBox(height: 6),
        Text(
          'Full automation, unlimited rules, Chapter 2 access',
          textAlign: TextAlign.center,
          style: GoogleFonts.dmSans(
            fontSize: 14,
            color: AppColors.textTertiary,
            height: 1.4,
          ),
        ),
      ],
    );
  }

  // ─── Feature List ────────────────────────────────────────────────────

  Widget _buildFeatures() {
    final features = [
      (Icons.auto_awesome_rounded, 'Betting Automation', 'Chapter 2: auto-placement on Bet9ja, SportsBet'),
      (Icons.rule_rounded, 'Unlimited Custom Rules', 'Build unlimited RL rules and market strategies'),
      (Icons.show_chart_rounded, 'Project Stairway', 'Full ROI dashboard — track every cycle and stake'),
      (Icons.analytics_outlined, 'Accuracy Dashboard', 'Per-market win rates, streak data, avg odds'),
      (Icons.flash_on_rounded, 'Priority Peak Access', 'No throttling during high-traffic match days'),
    ];
    return Column(
      children: features
          .map((f) => _featureRow(f.$1, f.$2, f.$3))
          .toList(),
    );
  }

  Widget _featureRow(IconData icon, String title, String subtitle) {
    return Container(
      margin: const EdgeInsets.only(bottom: 4),
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
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
                  style: GoogleFonts.dmSans(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                    color: Colors.white,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  subtitle,
                  style: GoogleFonts.dmSans(
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

  // ─── Provider Selector ────────────────────────────────────────────────

  Widget _buildProviderSelector() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'Choose payment method',
          style: GoogleFonts.dmSans(
            fontSize: 13,
            fontWeight: FontWeight.w600,
            color: AppColors.textTertiary,
          ),
        ),
        const SizedBox(height: 10),
        _providerCard(
          provider: 'paystack',
          label: 'Paystack',
          region: 'Nigeria',
          price: _paystackPrice,
          period: '/month',
          badgeText: 'NGN',
          badgeColor: const Color(0xFF00C3F7), // Paystack brand cyan
        ),
        const SizedBox(height: 8),
        _providerCard(
          provider: 'stripe',
          label: 'Stripe',
          region: 'International',
          price: _stripePrice,
          period: '/month',
          badgeText: 'USD',
          badgeColor: const Color(0xFF635BFF), // Stripe brand purple
        ),
      ],
    );
  }

  Widget _providerCard({
    required String provider,
    required String label,
    required String region,
    required String price,
    required String period,
    required String badgeText,
    required Color badgeColor,
  }) {
    final isSelected = _selectedProvider == provider;
    return GestureDetector(
      onTap: () => setState(() => _selectedProvider = provider),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        decoration: BoxDecoration(
          color: isSelected ? AppColors.neutral700 : AppColors.neutral800,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
            color: isSelected
                ? AppColors.primary
                : Colors.white.withValues(alpha: 0.06),
            width: isSelected ? 1.5 : 1.0,
          ),
        ),
        child: Row(
          children: [
            // Selection indicator
            Container(
              width: 20,
              height: 20,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                border: Border.all(
                  color: isSelected ? AppColors.primary : AppColors.neutral400,
                  width: 2,
                ),
                color: isSelected ? AppColors.primary : Colors.transparent,
              ),
              child: isSelected
                  ? const Icon(Icons.check, size: 12, color: Colors.white)
                  : null,
            ),
            const SizedBox(width: 12),
            // Provider name + region
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Text(
                        label,
                        style: GoogleFonts.dmSans(
                          fontSize: 14,
                          fontWeight: FontWeight.w600,
                          color: Colors.white,
                        ),
                      ),
                      const SizedBox(width: 6),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                        decoration: BoxDecoration(
                          color: badgeColor.withValues(alpha: 0.15),
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: Text(
                          badgeText,
                          style: GoogleFonts.dmSans(
                            fontSize: 9,
                            fontWeight: FontWeight.w700,
                            color: badgeColor,
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 2),
                  Text(
                    region,
                    style: GoogleFonts.dmSans(
                      fontSize: 12,
                      color: AppColors.textTertiary,
                    ),
                  ),
                ],
              ),
            ),
            // Price
            Row(
              crossAxisAlignment: CrossAxisAlignment.baseline,
              textBaseline: TextBaseline.alphabetic,
              children: [
                Text(
                  price,
                  style: GoogleFonts.dmSans(
                    fontSize: 18,
                    fontWeight: FontWeight.w700,
                    color: Colors.white,
                  ),
                ),
                Text(
                  period,
                  style: GoogleFonts.dmSans(
                    fontSize: 12,
                    color: AppColors.textTertiary,
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  // ─── Bottom Section ───────────────────────────────────────────────────

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
          BlocBuilder<UserCubit, UserState>(
            builder: (context, state) {
              final isGuest = state.user.isGuest;
              final isPro = state.user.isPro;

              if (isPro) {
                return _ctaButton(
                  label: 'You\'re already Pro',
                  color: AppColors.neutral600,
                  onTap: null,
                );
              }

              return _ctaButton(
                label: _loading
                    ? 'Processing...'
                    : (isGuest
                        ? 'Sign in to Subscribe'
                        : _selectedProvider == 'paystack'
                            ? 'Subscribe with Paystack'
                            : 'Subscribe with Stripe'),
                color: _loading ? AppColors.neutral600 : AppColors.primary,
                onTap: _loading
                    ? null
                    : () => _handleSubscribe(context, state),
              );
            },
          ),
          const SizedBox(height: 10),
          Text(
            'Cancel any time • Secure payment',
            style: GoogleFonts.dmSans(
              fontSize: 11,
              color: AppColors.textTertiary,
            ),
          ),
        ],
      ),
    );
  }

  Widget _ctaButton({
    required String label,
    required Color color,
    required VoidCallback? onTap,
  }) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.symmetric(vertical: 16),
        decoration: BoxDecoration(
          color: color,
          borderRadius: BorderRadius.circular(14),
        ),
        alignment: Alignment.center,
        child: Text(
          label,
          style: GoogleFonts.dmSans(
            fontSize: 15,
            fontWeight: FontWeight.w700,
            color: Colors.white,
          ),
        ),
      ),
    );
  }

  // ─── Actions ──────────────────────────────────────────────────────────

  void _handleSubscribe(BuildContext context, UserState state) {
    if (state.user.isGuest) {
      Navigator.of(context).pop();
      Navigator.of(context).push(
        MaterialPageRoute(builder: (_) => BlocProvider.value(
          value: context.read<UserCubit>(),
          child: const LoginScreen(),
        )),
      );
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            'Sign in first to subscribe',
            style: GoogleFonts.dmSans(),
          ),
        ),
      );
      return;
    }

    setState(() => _loading = true);

    // Mock: fire stub and let the cubit emit the new state
    // Replace with real Paystack / Stripe SDK call when integrated
    context.read<UserCubit>().activateSubscription(
      provider: _selectedProvider,
      reference: 'mock_${_selectedProvider}_${DateTime.now().millisecondsSinceEpoch}',
    );

    Future.delayed(const Duration(milliseconds: 800), () {
      if (mounted) setState(() => _loading = false);
    });
  }
}
