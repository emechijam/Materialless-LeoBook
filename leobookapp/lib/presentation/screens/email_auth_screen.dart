// email_auth_screen.dart: Email sign-in / sign-up screen.
// Part of LeoBook App - Screens

import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:leobookapp/core/constants/app_colors.dart';
import 'package:leobookapp/logic/cubit/user_cubit.dart';
import 'package:leobookapp/presentation/screens/main_screen.dart';
import 'package:leobookapp/presentation/screens/otp_verification_screen.dart';
import 'package:leobookapp/presentation/screens/profile_setup_screen.dart';

class EmailAuthScreen extends StatefulWidget {
  final String? initialEmail;
  final bool startInSignUpMode;

  const EmailAuthScreen({
    super.key,
    this.initialEmail,
    this.startInSignUpMode = false,
  });

  @override
  State<EmailAuthScreen> createState() => _EmailAuthScreenState();
}

class _EmailAuthScreenState extends State<EmailAuthScreen> {
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();
  bool _isSignUp = false;
  bool _obscurePassword = true;

  @override
  void initState() {
    super.initState();
    _emailController.text = widget.initialEmail ?? '';
    _isSignUp = widget.startInSignUpMode;
  }

  @override
  void dispose() {
    _emailController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  String? _validatePassword(String password) {
    final missing = <String>[];
    if (password.length < 8) missing.add('at least 8 characters');
    if (!password.contains(RegExp(r'[a-z]'))) missing.add('a lowercase letter');
    if (!password.contains(RegExp(r'[A-Z]'))) {
      missing.add('an uppercase letter');
    }
    if (!password.contains(RegExp(r'[0-9]'))) missing.add('a digit');
    if (!password.contains(RegExp(r'[!@#$%^&*(),.?":{}|<>_\-+=\[\]\\\/~`]'))) {
      missing.add('a special character');
    }
    if (missing.isEmpty) return null;
    return 'Password needs: ${missing.join(', ')}';
  }

  void _submit() {
    final email = _emailController.text.trim();
    final password = _passwordController.text.trim();
    if (email.isEmpty || password.isEmpty) return;

    if (_isSignUp) {
      final error = _validatePassword(password);
      if (error != null) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(error),
            backgroundColor: AppColors.liveRed,
          ),
        );
        return;
      }
    }

    final cubit = context.read<UserCubit>();
    if (_isSignUp) {
      cubit.signUpWithEmail(email, password);
    } else {
      cubit.signInWithEmail(email, password);
    }
  }

  Future<void> _runEmailAction(
    Future<void> Function(UserCubit cubit) action,
    String successMessage,
  ) async {
    final cubit = context.read<UserCubit>();
    await action(cubit);

    if (!mounted || cubit.state is UserError) {
      return;
    }

    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(successMessage),
        backgroundColor: AppColors.primary,
      ),
    );
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

  @override
  Widget build(BuildContext context) {
    return BlocListener<UserCubit, UserState>(
      listener: (context, state) {
        if (state is UserAuthenticated) {
          _navigateToMain();
        } else if (state is UserProfileIncomplete) {
          Navigator.of(context).pushReplacement(
            PageRouteBuilder(
              pageBuilder: (_, __, ___) => const ProfileSetupScreen(),
              transitionsBuilder: (_, anim, __, child) =>
                  FadeTransition(opacity: anim, child: child),
              transitionDuration: const Duration(milliseconds: 400),
            ),
          );
        } else if (state is UserNeedsVerification) {
          Navigator.of(context).pushReplacement(
            MaterialPageRoute(
              builder: (_) => OtpVerificationScreen(phone: state.phone),
            ),
          );
        } else if (state is UserError) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text(state.message),
              backgroundColor: AppColors.liveRed,
            ),
          );
        } else if (state is UserInitial && _isSignUp) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('Check your email to confirm your account.'),
              backgroundColor: AppColors.primary,
              duration: const Duration(seconds: 4),
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
              final content = _buildForm();

              if (isDesktop) {
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
                        _buildHeader(),
                        const SizedBox(height: 16),
                        content,
                      ],
                    ),
                  ),
                );
              }

              return Column(
                children: [
                  Padding(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                    child: _buildHeader(),
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

  Widget _buildHeader() {
    return GestureDetector(
      onTap: () => Navigator.of(context).pop(),
      child: Row(
        children: [
          const Icon(Icons.arrow_back, color: Colors.white, size: 20),
          const SizedBox(width: 10),
          Text(
            _isSignUp ? 'Create Account' : 'Sign In',
            style: GoogleFonts.dmSans(
              fontSize: 17,
              fontWeight: FontWeight.w600,
              color: Colors.white,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildForm() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        const SizedBox(height: 32),
        Text(
          _isSignUp ? 'Create your account' : 'Welcome back',
          style: GoogleFonts.dmSans(
            fontSize: 20,
            fontWeight: FontWeight.w700,
            color: Colors.white,
          ),
        ),
        const SizedBox(height: 8),
        Text(
          _isSignUp
              ? 'Enter your email and choose a password.'
              : 'Sign in with your email and password.',
          style: GoogleFonts.dmSans(
            fontSize: 13,
            color: AppColors.textTertiary,
          ),
        ),
        const SizedBox(height: 32),
        _inputField(
          controller: _emailController,
          hint: 'Email address',
          icon: Icons.email_outlined,
          keyboardType: TextInputType.emailAddress,
        ),
        const SizedBox(height: 14),
        Container(
          decoration: BoxDecoration(
            color: AppColors.neutral800,
            borderRadius: BorderRadius.circular(14),
            border: Border.all(color: Colors.white.withValues(alpha: 0.08)),
          ),
          child: Row(
            children: [
              Padding(
                padding: const EdgeInsets.only(left: 16),
                child: Icon(Icons.lock_outline,
                    color: AppColors.textTertiary, size: 20),
              ),
              Expanded(
                child: TextField(
                  controller: _passwordController,
                  obscureText: _obscurePassword,
                  style: GoogleFonts.dmSans(fontSize: 15, color: Colors.white),
                  decoration: InputDecoration(
                    hintText: 'Password',
                    hintStyle: GoogleFonts.dmSans(
                      color: AppColors.textDisabled,
                      fontSize: 15,
                    ),
                    border: InputBorder.none,
                    contentPadding: const EdgeInsets.symmetric(
                        horizontal: 12, vertical: 16),
                  ),
                ),
              ),
              GestureDetector(
                onTap: () =>
                    setState(() => _obscurePassword = !_obscurePassword),
                child: Padding(
                  padding: const EdgeInsets.only(right: 16),
                  child: Icon(
                    _obscurePassword
                        ? Icons.visibility_off_outlined
                        : Icons.visibility_outlined,
                    color: AppColors.textTertiary,
                    size: 20,
                  ),
                ),
              ),
            ],
          ),
        ),
        if (!_isSignUp)
          Align(
            alignment: Alignment.centerRight,
            child: TextButton(
              onPressed: () async {
                final email = _emailController.text.trim();
                if (email.isEmpty) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text('Enter your email first.')),
                  );
                  return;
                }

                await _runEmailAction(
                  (cubit) => cubit.sendPasswordReset(email),
                  'Reset link sent to your email.',
                );
              },
              child: Text(
                'Forgot Password?',
                style: GoogleFonts.dmSans(
                    fontSize: 13, color: AppColors.textTertiary),
              ),
            ),
          ),
        const SizedBox(height: 24),
        BlocBuilder<UserCubit, UserState>(
          builder: (context, state) {
            final isLoading = state is UserLoading;
            return GestureDetector(
              onTap: isLoading ? null : _submit,
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
                          _isSignUp ? 'Create Account' : 'Sign In',
                          style: GoogleFonts.dmSans(
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
        if (!_isSignUp)
          Center(
            child: TextButton(
              onPressed: () async {
                final email = _emailController.text.trim();
                if (email.isEmpty) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text('Enter your email first.')),
                  );
                  return;
                }

                await _runEmailAction(
                  (cubit) => cubit.sendMagicLink(email),
                  'Magic link sent to your email.',
                );
              },
              child: Text(
                'Sign in with Magic Link',
                style: GoogleFonts.dmSans(
                  fontSize: 13,
                  color: AppColors.primary.withValues(alpha: 0.8),
                  fontWeight: FontWeight.w500,
                ),
              ),
            ),
          ),
        const SizedBox(height: 20),
        Center(
          child: GestureDetector(
            onTap: () => setState(() => _isSignUp = !_isSignUp),
            child: RichText(
              text: TextSpan(
                style: GoogleFonts.dmSans(fontSize: 13),
                children: [
                  TextSpan(
                    text: _isSignUp
                        ? 'Already have an account? '
                        : 'Don\'t have an account? ',
                    style: TextStyle(color: AppColors.textTertiary),
                  ),
                  TextSpan(
                    text: _isSignUp ? 'Sign In' : 'Sign Up',
                    style: const TextStyle(
                      color: AppColors.primary,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ],
    );
  }

  Widget _inputField({
    required TextEditingController controller,
    required String hint,
    required IconData icon,
    TextInputType keyboardType = TextInputType.text,
  }) {
    return Container(
      decoration: BoxDecoration(
        color: AppColors.neutral800,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: Colors.white.withValues(alpha: 0.08)),
      ),
      child: Row(
        children: [
          Padding(
            padding: const EdgeInsets.only(left: 16),
            child: Icon(icon, color: AppColors.textTertiary, size: 20),
          ),
          Expanded(
            child: TextField(
              controller: controller,
              keyboardType: keyboardType,
              style: GoogleFonts.dmSans(fontSize: 15, color: Colors.white),
              decoration: InputDecoration(
                hintText: hint,
                hintStyle: GoogleFonts.dmSans(
                  color: AppColors.textDisabled,
                  fontSize: 15,
                ),
                border: InputBorder.none,
                contentPadding:
                    const EdgeInsets.symmetric(horizontal: 12, vertical: 16),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
