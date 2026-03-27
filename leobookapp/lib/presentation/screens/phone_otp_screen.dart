// phone_otp_screen.dart: Phone number + OTP verification screen.
// Part of LeoBook App — Screens
//
// Two-step flow: phone input → OTP pin entry.
// Desktop: centered modal card. Mobile: full-page scaffold.

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:leobookapp/core/constants/app_colors.dart';
import 'package:leobookapp/logic/cubit/user_cubit.dart';
import 'package:leobookapp/presentation/screens/main_screen.dart';

class PhoneOtpScreen extends StatefulWidget {
  const PhoneOtpScreen({super.key});

  @override
  State<PhoneOtpScreen> createState() => _PhoneOtpScreenState();
}

class _PhoneOtpScreenState extends State<PhoneOtpScreen> {
  final _phoneController = TextEditingController();
  final _otpController = TextEditingController();
  bool _otpSent = false;
  String _phone = '';

  @override
  void dispose() {
    _phoneController.dispose();
    _otpController.dispose();
    super.dispose();
  }

  void _sendOtp() {
    final phone = _phoneController.text.trim();
    if (phone.isEmpty) return;
    // Ensure + prefix
    final formatted = phone.startsWith('+') ? phone : '+234$phone';
    setState(() {
      _phone = formatted;
    });
    context.read<UserCubit>().sendPhoneOtp(formatted);
    setState(() => _otpSent = true);
  }

  void _verifyOtp() {
    final token = _otpController.text.trim();
    if (token.length < 6) return;
    context.read<UserCubit>().verifyPhoneOtp(_phone, token);
  }

  void _navigateToMain() {
    Navigator.of(context).pushAndRemoveUntil(
      PageRouteBuilder(
        pageBuilder: (_, __, ___) => const MainScreen(),
        transitionsBuilder: (_, anim, __, child) =>
            FadeTransition(opacity: anim, child: child),
        transitionDuration: const Duration(milliseconds: 400),
      ),
      (_) => false,
    );
  }

  void _goBack() {
    if (_otpSent) {
      setState(() => _otpSent = false);
    } else {
      Navigator.of(context).pop();
    }
  }

  @override
  Widget build(BuildContext context) {
    return BlocListener<UserCubit, UserState>(
      listener: (context, state) {
        if (state is UserAuthenticated) {
          _navigateToMain();
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
          child: LayoutBuilder(
            builder: (context, constraints) {
              final isDesktop = constraints.maxWidth > 1024;
              final content = _otpSent ? _buildOtpView() : _buildPhoneView();

              if (isDesktop) {
                // Desktop: centered modal card (same style as login modal)
                return Center(
                  child: Container(
                    width: 420,
                    padding: const EdgeInsets.symmetric(
                        vertical: 40, horizontal: 32),
                    decoration: BoxDecoration(
                      color: AppColors.neutral800,
                      borderRadius: BorderRadius.circular(20),
                      border: Border.all(
                        color: Colors.white.withValues(alpha: 0.08),
                      ),
                    ),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        // Back button row
                        GestureDetector(
                          onTap: _goBack,
                          child: Row(
                            children: [
                              const Icon(Icons.arrow_back,
                                  color: Colors.white, size: 20),
                              const SizedBox(width: 10),
                              Text(
                                _otpSent ? 'Verify OTP' : 'Phone Number',
                                style: GoogleFonts.lexend(
                                  fontSize: 17,
                                  fontWeight: FontWeight.w600,
                                  color: Colors.white,
                                ),
                              ),
                            ],
                          ),
                        ),
                        const SizedBox(height: 16),
                        content,
                      ],
                    ),
                  ),
                );
              }

              // Mobile: full page with AppBar
              return Column(
                children: [
                  // Custom AppBar row
                  Padding(
                    padding: const EdgeInsets.symmetric(
                        horizontal: 8, vertical: 4),
                    child: Row(
                      children: [
                        IconButton(
                          icon: const Icon(Icons.arrow_back,
                              color: Colors.white),
                          onPressed: _goBack,
                        ),
                        Text(
                          _otpSent ? 'Verify OTP' : 'Phone Number',
                          style: GoogleFonts.lexend(
                            fontSize: 17,
                            fontWeight: FontWeight.w600,
                            color: Colors.white,
                          ),
                        ),
                      ],
                    ),
                  ),
                  Expanded(
                    child: Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 24),
                      child: content,
                    ),
                  ),
                ],
              );
            },
          ),
        ),
      ),
    );
  }

  // ── Phone Number Input ──────────────────────────────────────────

  Widget _buildPhoneView() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        const SizedBox(height: 32),
        Text(
          'Enter your phone number',
          style: GoogleFonts.lexend(
            fontSize: 20,
            fontWeight: FontWeight.w700,
            color: Colors.white,
          ),
        ),
        const SizedBox(height: 8),
        Text(
          'We\'ll send you a verification code via SMS.',
          style: GoogleFonts.lexend(
            fontSize: 13,
            color: AppColors.textTertiary,
          ),
        ),
        const SizedBox(height: 32),

        // Phone input
        Container(
          decoration: BoxDecoration(
            color: AppColors.neutral800,
            borderRadius: BorderRadius.circular(14),
            border: Border.all(color: Colors.white.withValues(alpha: 0.08)),
          ),
          child: Row(
            children: [
              // Country code chip
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
                decoration: BoxDecoration(
                  border: Border(
                    right: BorderSide(
                      color: Colors.white.withValues(alpha: 0.08),
                    ),
                  ),
                ),
                child: Text(
                  '+234',
                  style: GoogleFonts.lexend(
                    fontSize: 15,
                    fontWeight: FontWeight.w500,
                    color: Colors.white,
                  ),
                ),
              ),
              Expanded(
                child: TextField(
                  controller: _phoneController,
                  keyboardType: TextInputType.phone,
                  inputFormatters: [FilteringTextInputFormatter.digitsOnly],
                  style: GoogleFonts.lexend(
                    fontSize: 15,
                    color: Colors.white,
                  ),
                  decoration: InputDecoration(
                    hintText: '8012345678',
                    hintStyle: GoogleFonts.lexend(
                      color: AppColors.textDisabled,
                      fontSize: 15,
                    ),
                    border: InputBorder.none,
                    contentPadding: const EdgeInsets.symmetric(horizontal: 16),
                  ),
                ),
              ),
            ],
          ),
        ),

        const SizedBox(height: 24),

        // Send OTP button
        BlocBuilder<UserCubit, UserState>(
          builder: (context, state) {
            final isLoading = state is UserLoading;
            return GestureDetector(
              onTap: isLoading ? null : _sendOtp,
              child: Container(
                width: double.infinity,
                padding: const EdgeInsets.symmetric(vertical: 16),
                decoration: BoxDecoration(
                  color: AppColors.primary,
                  borderRadius: BorderRadius.circular(28),
                ),
                child: Center(
                  child: isLoading
                      ? const SizedBox(
                          width: 20,
                          height: 20,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            color: Colors.white,
                          ),
                        )
                      : Text(
                          'Send Code',
                          style: GoogleFonts.lexend(
                            fontSize: 15,
                            fontWeight: FontWeight.w600,
                            color: Colors.white,
                          ),
                        ),
                ),
              ),
            );
          },
        ),
      ],
    );
  }

  // ── OTP Input ───────────────────────────────────────────────────

  Widget _buildOtpView() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        const SizedBox(height: 32),
        Text(
          'Enter verification code',
          style: GoogleFonts.lexend(
            fontSize: 20,
            fontWeight: FontWeight.w700,
            color: Colors.white,
          ),
        ),
        const SizedBox(height: 8),
        Text(
          'Code sent to $_phone',
          style: GoogleFonts.lexend(
            fontSize: 13,
            color: AppColors.textTertiary,
          ),
        ),
        const SizedBox(height: 32),

        // OTP input
        Container(
          decoration: BoxDecoration(
            color: AppColors.neutral800,
            borderRadius: BorderRadius.circular(14),
            border: Border.all(color: Colors.white.withValues(alpha: 0.08)),
          ),
          child: TextField(
            controller: _otpController,
            keyboardType: TextInputType.number,
            inputFormatters: [
              FilteringTextInputFormatter.digitsOnly,
              LengthLimitingTextInputFormatter(6),
            ],
            textAlign: TextAlign.center,
            style: GoogleFonts.lexend(
              fontSize: 24,
              fontWeight: FontWeight.w700,
              color: Colors.white,
              letterSpacing: 12,
            ),
            decoration: InputDecoration(
              hintText: '000000',
              hintStyle: GoogleFonts.lexend(
                color: AppColors.textDisabled,
                fontSize: 24,
                letterSpacing: 12,
              ),
              border: InputBorder.none,
              contentPadding: const EdgeInsets.symmetric(
                horizontal: 16,
                vertical: 18,
              ),
            ),
          ),
        ),

        const SizedBox(height: 24),

        // Verify button
        BlocBuilder<UserCubit, UserState>(
          builder: (context, state) {
            final isLoading = state is UserLoading;
            return GestureDetector(
              onTap: isLoading ? null : _verifyOtp,
              child: Container(
                width: double.infinity,
                padding: const EdgeInsets.symmetric(vertical: 16),
                decoration: BoxDecoration(
                  color: AppColors.primary,
                  borderRadius: BorderRadius.circular(28),
                ),
                child: Center(
                  child: isLoading
                      ? const SizedBox(
                          width: 20,
                          height: 20,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            color: Colors.white,
                          ),
                        )
                      : Text(
                          'Verify',
                          style: GoogleFonts.lexend(
                            fontSize: 15,
                            fontWeight: FontWeight.w600,
                            color: Colors.white,
                          ),
                        ),
                ),
              ),
            );
          },
        ),

        const SizedBox(height: 16),

        // Resend
        Center(
          child: GestureDetector(
            onTap: _sendOtp,
            child: Text(
              'Resend Code',
              style: GoogleFonts.lexend(
                fontSize: 13,
                fontWeight: FontWeight.w500,
                color: AppColors.primary,
              ),
            ),
          ),
        ),
      ],
    );
  }
}
