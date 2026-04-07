// email_otp_signup_screen.dart: Email magic-link sign-up flow.
// Part of LeoBook App — Screens
//
// Step 1: Enter email → send magic link.
// Step 2: "Check your email" confirmation screen (no code entry).

import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:leobookapp/core/constants/app_colors.dart';
import 'package:leobookapp/logic/cubit/user_cubit.dart';
import 'package:leobookapp/presentation/screens/main_screen.dart';
import 'package:leobookapp/presentation/screens/profile_setup_screen.dart';

/// Sign-up via email magic link (Supabase magic link).
class EmailOtpSignUpScreen extends StatefulWidget {
  const EmailOtpSignUpScreen({
    super.key,
    this.initialEmail = '',
    this.initialPhone = '',
    this.title = 'Create your account',
  });

  final String initialEmail;
  final String initialPhone;
  final String title;

  @override
  State<EmailOtpSignUpScreen> createState() => _EmailOtpSignUpScreenState();
}

class _EmailOtpSignUpScreenState extends State<EmailOtpSignUpScreen> {
  final _emailController = TextEditingController();
  bool _linkSent = false;

  @override
  void initState() {
    super.initState();
    _emailController.text = widget.initialEmail;
  }

  @override
  void dispose() {
    _emailController.dispose();
    super.dispose();
  }

  Future<void> _sendMagicLink() async {
    final email = _emailController.text.trim();
    if (!_looksLikeEmail(email)) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Enter a valid email address.'),
          backgroundColor: AppColors.liveRed,
        ),
      );
      return;
    }
    await context.read<UserCubit>().sendMagicLink(email);
    if (!mounted) return;
    if (context.read<UserCubit>().state is UserError) return;
    setState(() => _linkSent = true);
  }

  bool _looksLikeEmail(String s) {
    return s.contains('@') && s.contains('.') && s.length > 5;
  }

  void _goMain() {
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

  @override
  Widget build(BuildContext context) {
    return BlocListener<UserCubit, UserState>(
      listener: (context, state) {
        if (state is UserAuthenticated) {
          _goMain();
        } else if (state is UserProfileIncomplete) {
          Navigator.of(context).pushReplacement(
            MaterialPageRoute(
              builder: (_) => ProfileSetupScreen(
                initialPhone: widget.initialPhone,
              ),
            ),
          );
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
        appBar: AppBar(
          backgroundColor: Colors.transparent,
          elevation: 0,
          leading: IconButton(
            icon: const Icon(Icons.arrow_back, color: Colors.white),
            onPressed: () {
              if (_linkSent) {
                setState(() => _linkSent = false);
              } else {
                Navigator.of(context).pop();
              }
            },
          ),
        ),
        body: SafeArea(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 24),
            child: BlocBuilder<UserCubit, UserState>(
              builder: (context, state) {
                final loading = state is UserLoading;

                if (_linkSent) {
                  return _CheckEmailView(
                    email: _emailController.text.trim(),
                    onResend: loading ? null : _sendMagicLink,
                    loading: loading,
                  );
                }

                return Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Text(
                      widget.title,
                      style: GoogleFonts.dmSans(
                        fontSize: 24,
                        fontWeight: FontWeight.bold,
                        color: Colors.white,
                      ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      'We\'ll send a magic link to your email to continue.',
                      style: GoogleFonts.dmSans(
                        color: AppColors.textSecondary,
                        fontSize: 14,
                      ),
                    ),
                    const SizedBox(height: 28),
                    TextField(
                      controller: _emailController,
                      keyboardType: TextInputType.emailAddress,
                      style: const TextStyle(color: Colors.white),
                      decoration:
                          _fieldDecoration('Email', Icons.email_outlined),
                    ),
                    const SizedBox(height: 20),
                    ElevatedButton(
                      onPressed: loading ? null : _sendMagicLink,
                      style: ElevatedButton.styleFrom(
                        backgroundColor: AppColors.primary,
                        foregroundColor: Colors.black,
                        padding: const EdgeInsets.symmetric(vertical: 16),
                      ),
                      child: loading
                          ? const SizedBox(
                              height: 18,
                              width: 18,
                              child: CircularProgressIndicator(
                                  color: Colors.black, strokeWidth: 2),
                            )
                          : Text(
                              'Send magic link',
                              style: GoogleFonts.dmSans(
                                  fontWeight: FontWeight.bold),
                            ),
                    ),
                  ],
                );
              },
            ),
          ),
        ),
      ),
    );
  }

  InputDecoration _fieldDecoration(String hint, IconData icon) {
    return InputDecoration(
      hintText: hint,
      hintStyle: const TextStyle(color: AppColors.textDisabled, fontSize: 14),
      prefixIcon: Icon(icon, color: AppColors.textTertiary, size: 20),
      filled: true,
      fillColor: AppColors.neutral700.withValues(alpha: 0.5),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(16),
        borderSide: BorderSide(color: Colors.white.withValues(alpha: 0.08)),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(16),
        borderSide: BorderSide(color: Colors.white.withValues(alpha: 0.08)),
      ),
    );
  }
}

// ─── Check Email Confirmation View ─────────────────────────────
class _CheckEmailView extends StatelessWidget {
  final String email;
  final VoidCallback? onResend;
  final bool loading;

  const _CheckEmailView({
    required this.email,
    required this.onResend,
    required this.loading,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const SizedBox(height: 32),
        Center(
          child: Container(
            width: 80,
            height: 80,
            decoration: BoxDecoration(
              color: AppColors.primary.withValues(alpha: 0.12),
              shape: BoxShape.circle,
            ),
            child: const Icon(
              Icons.mark_email_unread_outlined,
              color: AppColors.primary,
              size: 40,
            ),
          ),
        ),
        const SizedBox(height: 32),
        Text(
          'Check your email',
          textAlign: TextAlign.center,
          style: GoogleFonts.dmSans(
            fontSize: 24,
            fontWeight: FontWeight.bold,
            color: Colors.white,
          ),
        ),
        const SizedBox(height: 12),
        Text(
          'We sent a magic link to',
          textAlign: TextAlign.center,
          style: GoogleFonts.dmSans(
            color: AppColors.textSecondary,
            fontSize: 14,
          ),
        ),
        const SizedBox(height: 4),
        Text(
          email,
          textAlign: TextAlign.center,
          style: GoogleFonts.dmSans(
            color: Colors.white,
            fontSize: 15,
            fontWeight: FontWeight.w600,
          ),
        ),
        const SizedBox(height: 16),
        Text(
          'Click the link in the email to complete your registration. You can then set a password and add your phone number.',
          textAlign: TextAlign.center,
          style: GoogleFonts.dmSans(
            color: AppColors.textTertiary,
            fontSize: 13,
            height: 1.5,
          ),
        ),
        const SizedBox(height: 40),
        TextButton(
          onPressed: onResend,
          child: loading
              ? const SizedBox(
                  height: 16,
                  width: 16,
                  child: CircularProgressIndicator(
                      color: AppColors.primary, strokeWidth: 2),
                )
              : Text(
                  'Resend magic link',
                  style: GoogleFonts.dmSans(color: AppColors.textTertiary),
                ),
        ),
      ],
    );
  }
}
