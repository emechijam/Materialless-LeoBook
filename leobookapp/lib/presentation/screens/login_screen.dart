// login_screen.dart: Grok-inspired login/signup screen.
// Part of LeoBook App — Screens
//
// Features: Skip, Continue with Google, Continue with Phone,
// Terms/Privacy links, "A Materialless Creation" signature.

import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:leobookapp/core/constants/app_colors.dart';
import 'package:leobookapp/logic/cubit/user_cubit.dart';
import 'package:leobookapp/presentation/screens/main_screen.dart';
import 'package:leobookapp/presentation/screens/phone_otp_screen.dart';

class LoginScreen extends StatelessWidget {
  const LoginScreen({super.key});

  void _navigateToMain(BuildContext context) {
    Navigator.of(context).pushReplacement(
      PageRouteBuilder(
        pageBuilder: (_, __, ___) => const MainScreen(),
        transitionsBuilder: (_, anim, __, child) =>
            FadeTransition(opacity: anim, child: child),
        transitionDuration: const Duration(milliseconds: 400),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return BlocListener<UserCubit, UserState>(
      listener: (context, state) {
        if (state is UserAuthenticated) {
          _navigateToMain(context);
        }
        if (state is UserError) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text(state.message),
              backgroundColor: AppColors.liveRed,
            ),
          );
        }
      },
      child: Scaffold(
        backgroundColor: AppColors.neutral900,
        body: SafeArea(
          child: Column(
            children: [
              // ── Skip button ────────────────────────────────────
              Align(
                alignment: Alignment.topRight,
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: GestureDetector(
                    onTap: () {
                      context.read<UserCubit>().skipAsGuest();
                      _navigateToMain(context);
                    },
                    child: Text(
                      'Skip',
                      style: GoogleFonts.lexend(
                        fontSize: 15,
                        fontWeight: FontWeight.w500,
                        color: AppColors.textTertiary,
                      ),
                    ),
                  ),
                ),
              ),

              const Spacer(flex: 2),

              // ── Logo / Title ───────────────────────────────────
              Text(
                'LeoBook',
                style: GoogleFonts.lexend(
                  fontSize: 48,
                  fontWeight: FontWeight.w800,
                  color: Colors.white,
                  letterSpacing: -1,
                ),
              ),
              const SizedBox(height: 20),

              // ── Subtitle ──────────────────────────────────────
              Text(
                'Thanks for trying LeoBook.',
                style: GoogleFonts.lexend(
                  fontSize: 16,
                  fontWeight: FontWeight.w400,
                  color: AppColors.textSecondary,
                ),
              ),
              const SizedBox(height: 8),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 48),
                child: Text(
                  'Sign in to unlock predictions, rules, and automation.',
                  textAlign: TextAlign.center,
                  style: GoogleFonts.lexend(
                    fontSize: 13,
                    fontWeight: FontWeight.w400,
                    color: AppColors.textTertiary,
                    height: 1.5,
                  ),
                ),
              ),

              const Spacer(flex: 3),

              // ── Auth Buttons ───────────────────────────────────
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 24),
                child: BlocBuilder<UserCubit, UserState>(
                  builder: (context, state) {
                    final isLoading = state is UserLoading;
                    return Column(
                      children: [
                        // Continue with Google
                        _AuthButton(
                          label: 'Continue with Google',
                          icon: Icons.g_mobiledata_rounded,
                          isLoading: isLoading,
                          onTap: () =>
                              context.read<UserCubit>().signInWithGoogle(),
                        ),
                        const SizedBox(height: 12),

                        // Continue with Phone
                        _AuthButton(
                          label: 'Continue with Phone',
                          icon: Icons.phone_outlined,
                          isLoading: false,
                          onTap: () {
                            Navigator.of(context).push(
                              MaterialPageRoute(
                                builder: (_) => const PhoneOtpScreen(),
                              ),
                            );
                          },
                        ),
                      ],
                    );
                  },
                ),
              ),

              const SizedBox(height: 24),

              // ── Terms & Privacy ────────────────────────────────
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 32),
                child: RichText(
                  textAlign: TextAlign.center,
                  text: TextSpan(
                    style: GoogleFonts.lexend(
                      fontSize: 11,
                      color: AppColors.textDisabled,
                    ),
                    children: [
                      const TextSpan(text: 'By continuing you agree to '),
                      TextSpan(
                        text: 'Terms',
                        style: TextStyle(
                          color: AppColors.textTertiary,
                          decoration: TextDecoration.underline,
                          decorationColor: AppColors.textTertiary,
                        ),
                      ),
                      const TextSpan(text: ' and '),
                      TextSpan(
                        text: 'Privacy Policy',
                        style: TextStyle(
                          color: AppColors.textTertiary,
                          decoration: TextDecoration.underline,
                          decorationColor: AppColors.textTertiary,
                        ),
                      ),
                    ],
                  ),
                ),
              ),

              const SizedBox(height: 32),

              // ── Materialless Creation ──────────────────────────
              Text(
                'A Materialless Creation',
                style: GoogleFonts.lexend(
                  fontSize: 11,
                  fontWeight: FontWeight.w400,
                  color: AppColors.textDisabled,
                  letterSpacing: 0.5,
                ),
              ),

              const SizedBox(height: 32),
            ],
          ),
        ),
      ),
    );
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// Auth Button (glass-style, Grok-inspired)
// ═══════════════════════════════════════════════════════════════════════════

class _AuthButton extends StatelessWidget {
  final String label;
  final IconData icon;
  final bool isLoading;
  final VoidCallback onTap;

  const _AuthButton({
    required this.label,
    required this.icon,
    required this.isLoading,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: isLoading ? null : onTap,
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.symmetric(vertical: 14),
        decoration: BoxDecoration(
          color: AppColors.neutral700,
          borderRadius: BorderRadius.circular(28),
          border: Border.all(
            color: Colors.white.withValues(alpha: 0.08),
          ),
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            if (isLoading)
              const SizedBox(
                width: 18,
                height: 18,
                child: CircularProgressIndicator(
                  strokeWidth: 2,
                  color: Colors.white54,
                ),
              )
            else
              Icon(icon, color: Colors.white, size: 22),
            const SizedBox(width: 10),
            Text(
              label,
              style: GoogleFonts.lexend(
                fontSize: 14,
                fontWeight: FontWeight.w500,
                color: Colors.white,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
