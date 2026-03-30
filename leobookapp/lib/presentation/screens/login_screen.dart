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
import 'package:leobookapp/presentation/screens/email_auth_screen.dart';
import 'package:leobookapp/presentation/screens/profile_setup_screen.dart';
import 'package:leobookapp/presentation/screens/otp_verification_screen.dart';
import 'package:leobookapp/presentation/screens/password_entry_screen.dart';

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

  void _showBiometricPrompt(BuildContext context) {
    showModalBottomSheet(
      context: context,
      backgroundColor: AppColors.neutral800,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (context) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 40, horizontal: 32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.fingerprint_rounded, size: 64, color: AppColors.primary),
            const SizedBox(height: 24),
            Text(
              'Biometric Login',
              style: GoogleFonts.lexend(
                fontSize: 24,
                fontWeight: FontWeight.bold,
                color: Colors.white,
              ),
            ),
            const SizedBox(height: 12),
            Text(
              'Sign in quickly using your device credentials.',
              textAlign: TextAlign.center,
              style: GoogleFonts.lexend(
                color: AppColors.textSecondary,
                fontSize: 14,
              ),
            ),
            const SizedBox(height: 32),
            _AuthButton(
              label: 'Sign in with Biometrics',
              icon: Icons.face_rounded,
              isLoading: false,
              onTap: () {
                Navigator.pop(context);
                context.read<UserCubit>().biometricSignIn();
              },
            ),
            const SizedBox(height: 12),
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: Text(
                'Cancel',
                style: GoogleFonts.lexend(color: AppColors.textTertiary),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _handleIdentifierCheck(BuildContext context, String title) async {
    final controller = TextEditingController();
    final isPhone = title.toLowerCase().contains('phone');

    return showModalBottomSheet(
      context: context,
      backgroundColor: AppColors.neutral800,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (context) => Padding(
        padding: EdgeInsets.only(
          bottom: MediaQuery.of(context).viewInsets.bottom,
          top: 32,
          left: 24,
          right: 24,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              title,
              style: GoogleFonts.lexend(
                fontSize: 20,
                fontWeight: FontWeight.bold,
                color: Colors.white,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              isPhone 
                ? 'Enter your phone number to continue.' 
                : 'Enter your email to continue.',
              style: GoogleFonts.lexend(color: AppColors.textSecondary, fontSize: 13),
            ),
            const SizedBox(height: 24),
            Container(
              decoration: BoxDecoration(
                color: AppColors.neutral700.withValues(alpha: 0.5),
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: Colors.white.withValues(alpha: 0.08)),
              ),
              child: TextField(
                controller: controller,
                autofocus: true,
                style: const TextStyle(color: Colors.white),
                keyboardType: isPhone ? TextInputType.phone : TextInputType.emailAddress,
                decoration: InputDecoration(
                  hintText: isPhone ? 'e.g. 8012345678' : 'e.g. user@example.com',
                  hintStyle: TextStyle(color: AppColors.textDisabled, fontSize: 14),
                  border: InputBorder.none,
                  prefixIcon: Icon(isPhone ? Icons.phone_outlined : Icons.email_outlined, color: AppColors.textTertiary, size: 20),
                  contentPadding: const EdgeInsets.symmetric(vertical: 18, horizontal: 16),
                ),
              ),
            ),
            const SizedBox(height: 24),
            ElevatedButton(
              style: ElevatedButton.styleFrom(
                backgroundColor: AppColors.primary,
                foregroundColor: Colors.black,
                padding: const EdgeInsets.symmetric(vertical: 16),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(28)),
              ),
              onPressed: () async {
                final id = controller.text.trim();
                if (id.isEmpty) return;
                
                final formattedId = isPhone 
                    ? (id.startsWith('+') ? id : '+234$id') 
                    : id;

                Navigator.pop(context);
                final exists = await context.read<UserCubit>().checkUserStatus(formattedId);
                
                if (!context.mounted) return;

                if (exists) {
                  // Existing user -> Password Screen
                  Navigator.of(context).push(
                    MaterialPageRoute(
                      builder: (_) => PasswordEntryScreen(identifier: formattedId),
                    ),
                  );
                } else {
                  // New user -> OTP / Signup flow
                  if (isPhone) {
                    context.read<UserCubit>().sendPhoneOtp(formattedId);
                    Navigator.of(context).push(
                      MaterialPageRoute(
                        builder: (_) => OtpVerificationScreen(phone: formattedId),
                      ),
                    );
                  } else {
                    // For Email, send them to the regular Email Screen but prefilled
                    // or just start the signup directly if we want velocity
                    Navigator.of(context).push(
                      MaterialPageRoute(
                        builder: (_) => const EmailAuthScreen(),
                      ),
                    );
                  }
                }
              },
              child: Text('Continue', style: GoogleFonts.lexend(fontWeight: FontWeight.bold)),
            ),
            const SizedBox(height: 32),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return BlocListener<UserCubit, UserState>(
      listener: (context, state) {
        if (state is UserAuthenticated) {
          _navigateToMain(context);
        } else if (state is UserProfileIncomplete) {
          Navigator.of(context).pushReplacement(
            MaterialPageRoute(builder: (_) => const ProfileSetupScreen()),
          );
        } else if (state is UserNeedsVerification) {
          Navigator.of(context).push(
            MaterialPageRoute(
              builder: (_) => OtpVerificationScreen(phone: state.phone),
            ),
          );
        } else if (state is UserBiometricPrompt) {
          _showBiometricPrompt(context);
        } else if (state is UserError) {
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
          child: LayoutBuilder(
            builder: (context, constraints) {
              final isDesktop = constraints.maxWidth > 1024;
              final loginContent = _buildDesktopLoginContent(context);

              if (isDesktop) {
                // Desktop: centered modal card
                return Center(
                  child: Container(
                    width: 420,
                    padding: const EdgeInsets.symmetric(vertical: 40, horizontal: 32),
                    decoration: BoxDecoration(
                      color: AppColors.neutral800,
                      borderRadius: BorderRadius.circular(20),
                      border: Border.all(
                        color: Colors.white.withValues(alpha: 0.08),
                      ),
                    ),
                    child: loginContent,
                  ),
                );
              }

              // Mobile: full screen with buttons at bottom
              return _buildMobileLoginContent(context);
            },
          ),
        ),
      ),
    );
  }

  /// Mobile: title centered vertically, buttons pinned near bottom.
  Widget _buildMobileLoginContent(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 24),
      child: Column(
        children: [
          // ── Skip button ────────────────────────────────────
          Align(
            alignment: Alignment.topRight,
            child: Padding(
              padding: const EdgeInsets.only(top: 8),
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

          // Push title to center
          const Spacer(flex: 3),

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
          Text(
            'Sign in to unlock predictions, rules, and automation.',
            textAlign: TextAlign.center,
            style: GoogleFonts.lexend(
              fontSize: 13,
              fontWeight: FontWeight.w400,
              color: AppColors.textTertiary,
              height: 1.5,
            ),
          ),

          // Push buttons to bottom
          const Spacer(flex: 5),

          // ── Auth Buttons ───────────────────────────────────
          BlocBuilder<UserCubit, UserState>(
            builder: (context, state) {
              final isLoading = state is UserLoading;
              return Column(
                children: [
                  _AuthButton(
                    label: 'Continue with Google',
                    icon: Icons.g_mobiledata_rounded,
                    isLoading: isLoading,
                    onTap: () =>
                        context.read<UserCubit>().signInWithGoogle(),
                  ),
                  const SizedBox(height: 12),
                  _AuthButton(
                    label: 'Continue with Phone',
                    icon: Icons.phone_outlined,
                    isLoading: false,
                    onTap: () => _handleIdentifierCheck(context, 'Continue with Phone'),
                  ),
                  const SizedBox(height: 12),
                  _AuthButton(
                    label: 'Continue with Email',
                    icon: Icons.email_outlined,
                    isLoading: false,
                    onTap: () => _handleIdentifierCheck(context, 'Continue with Email'),
                  ),
                ],
              );
            },
          ),

          const SizedBox(height: 24),

          // ── Terms & Privacy ────────────────────────────────
          RichText(
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

          const SizedBox(height: 16),
        ],
      ),
    );
  }

  /// Desktop modal content (compact Column).
  Widget _buildDesktopLoginContent(BuildContext context) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        // ── Skip button ────────────────────────────────────
        Align(
          alignment: Alignment.topRight,
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

        const SizedBox(height: 40),

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
        Text(
          'Sign in to unlock predictions, rules, and automation.',
          textAlign: TextAlign.center,
          style: GoogleFonts.lexend(
            fontSize: 13,
            fontWeight: FontWeight.w400,
            color: AppColors.textTertiary,
            height: 1.5,
          ),
        ),

        const SizedBox(height: 40),

        // ── Auth Buttons ───────────────────────────────────
        BlocBuilder<UserCubit, UserState>(
          builder: (context, state) {
            final isLoading = state is UserLoading;
            return Column(
              children: [
                _AuthButton(
                  label: 'Continue with Google',
                  icon: Icons.g_mobiledata_rounded,
                  isLoading: isLoading,
                  onTap: () =>
                      context.read<UserCubit>().signInWithGoogle(),
                ),
                const SizedBox(height: 12),
                _AuthButton(
                  label: 'Continue with Phone',
                  icon: Icons.phone_outlined,
                  isLoading: false,
                  onTap: () => _handleIdentifierCheck(context, 'Continue with Phone'),
                ),
                const SizedBox(height: 12),
                _AuthButton(
                  label: 'Continue with Email',
                  icon: Icons.email_outlined,
                  isLoading: false,
                  onTap: () => _handleIdentifierCheck(context, 'Continue with Email'),
                ),
              ],
            );
          },
        ),

        const SizedBox(height: 24),

        // ── Terms & Privacy ────────────────────────────────
        RichText(
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
      ],
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
