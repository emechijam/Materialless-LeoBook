// login_screen.dart: Grok-inspired login/signup screen.
// Part of LeoBook App - Screens

import 'package:country_picker/country_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_svg/flutter_svg.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:leobookapp/core/constants/app_colors.dart';
import 'package:leobookapp/logic/cubit/user_cubit.dart';
import 'package:leobookapp/presentation/screens/email_otp_signup_screen.dart';
import 'package:leobookapp/presentation/screens/main_screen.dart';
import 'package:leobookapp/presentation/screens/profile_setup_screen.dart';

// ─── Validation helpers ─────────────────────────────────────────────────────

/// Returns true if [email] is a syntactically valid email address.
bool _isValidEmail(String email) {
  return RegExp(r'^[^@\s]+@[^@\s]+\.[^@\s]{2,}$').hasMatch(email.trim());
}

/// Returns true if [digits] (the part the user typed, without country code)
/// has at least 7 digits — enough to be a plausible local number.
bool _isValidPhoneDigits(String digits) {
  final onlyDigits = digits.replaceAll(RegExp(r'\D'), '');
  return onlyDigits.length >= 7;
}

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  bool _biometricSheetOpen = false;

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

  Future<void> _showBiometricPrompt(BuildContext context) async {
    if (_biometricSheetOpen) return;
    _biometricSheetOpen = true;

    await showModalBottomSheet<void>(
      context: context,
      isDismissible: false,
      enableDrag: false,
      backgroundColor: AppColors.neutral800,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (sheetContext) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 40, horizontal: 32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.fingerprint_rounded,
                size: 64, color: AppColors.primary),
            const SizedBox(height: 24),
            Text(
              'Biometric Login',
              style: GoogleFonts.dmSans(
                fontSize: 24,
                fontWeight: FontWeight.bold,
                color: Colors.white,
              ),
            ),
            const SizedBox(height: 12),
            Text(
              'Sign in quickly using your device credentials.',
              textAlign: TextAlign.center,
              style: GoogleFonts.dmSans(
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
                Navigator.pop(sheetContext);
                context.read<UserCubit>().biometricSignIn();
              },
            ),
            const SizedBox(height: 12),
            TextButton(
              onPressed: () {
                Navigator.pop(sheetContext);
                context.read<UserCubit>().dismissBiometricPrompt();
              },
              child: Text(
                'Dismiss',
                style: GoogleFonts.dmSans(color: AppColors.textTertiary),
              ),
            ),
          ],
        ),
      ),
    );

    _biometricSheetOpen = false;
  }

  Future<void> _handleIdentifierCheck(
      BuildContext context, String title) async {
    final isPhone = title.toLowerCase().contains('phone');

    return showModalBottomSheet(
      context: context,
      backgroundColor: AppColors.neutral800,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (sheetContext) => _IdentifierInputSheet(
        title: title,
        isPhone: isPhone,
        parentContext: context,
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
                    child: loginContent,
                  ),
                );
              }

              return _buildMobileLoginContent(context);
            },
          ),
        ),
      ),
    );
  }

  Widget _buildMobileLoginContent(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 24),
      child: Column(
        children: [
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
                  style: GoogleFonts.dmSans(
                    fontSize: 15,
                    fontWeight: FontWeight.w500,
                    color: AppColors.textTertiary,
                  ),
                ),
              ),
            ),
          ),
          const Spacer(flex: 3),
          Text(
            'LeoBook',
            style: GoogleFonts.dmSans(
              fontSize: 48,
              fontWeight: FontWeight.w800,
              color: Colors.white,
              letterSpacing: -1,
            ),
          ),
          const SizedBox(height: 20),
          Text(
            'Thanks for trying LeoBook.',
            style: GoogleFonts.dmSans(
              fontSize: 16,
              fontWeight: FontWeight.w400,
              color: AppColors.textSecondary,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            'Sign in to unlock predictions, rules, and automation.',
            textAlign: TextAlign.center,
            style: GoogleFonts.dmSans(
              fontSize: 13,
              fontWeight: FontWeight.w400,
              color: AppColors.textTertiary,
              height: 1.5,
            ),
          ),
          const Spacer(flex: 5),
          BlocBuilder<UserCubit, UserState>(
            builder: (context, state) {
              final isGoogleLoading = state is UserLoading && state.method == 'google';
              final isGlobalLoading = state is UserLoading;
              return Column(
                children: [
                  _AuthButton(
                    label: 'Continue with Google',
                    customIcon: SvgPicture.asset(
                      'assets/icons/google_g.svg',
                      width: 22,
                      height: 22,
                    ),
                    isLoading: isGoogleLoading,
                    onTap: () => context.read<UserCubit>().signInWithGoogle(),
                  ),
                  const SizedBox(height: 12),
                  _AuthButton(
                    label: 'Continue with Phone',
                    icon: Icons.phone_outlined,
                    isLoading: false,
                    onTap: isGlobalLoading ? () {} : () => _handleIdentifierCheck(context, 'Continue with Phone'),
                  ),
                  const SizedBox(height: 12),
                  _AuthButton(
                    label: 'Continue with Email',
                    icon: Icons.email_outlined,
                    isLoading: false,
                    onTap: isGlobalLoading ? () {} : () => _handleIdentifierCheck(context, 'Continue with Email'),
                  ),
                ],
              );
            },
          ),
          const SizedBox(height: 24),
          RichText(
            textAlign: TextAlign.center,
            text: TextSpan(
              style: GoogleFonts.dmSans(
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
          Text(
            'A Materialless Creation',
            style: GoogleFonts.dmSans(
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

  Widget _buildDesktopLoginContent(BuildContext context) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Align(
          alignment: Alignment.topRight,
          child: GestureDetector(
            onTap: () {
              context.read<UserCubit>().skipAsGuest();
              _navigateToMain(context);
            },
            child: Text(
              'Skip',
              style: GoogleFonts.dmSans(
                fontSize: 15,
                fontWeight: FontWeight.w500,
                color: AppColors.textTertiary,
              ),
            ),
          ),
        ),
        const SizedBox(height: 40),
        Text(
          'LeoBook',
          style: GoogleFonts.dmSans(
            fontSize: 48,
            fontWeight: FontWeight.w800,
            color: Colors.white,
            letterSpacing: -1,
          ),
        ),
        const SizedBox(height: 20),
        Text(
          'Thanks for trying LeoBook.',
          style: GoogleFonts.dmSans(
            fontSize: 16,
            fontWeight: FontWeight.w400,
            color: AppColors.textSecondary,
          ),
        ),
        const SizedBox(height: 8),
        Text(
          'Sign in to unlock predictions, rules, and automation.',
          textAlign: TextAlign.center,
          style: GoogleFonts.dmSans(
            fontSize: 13,
            fontWeight: FontWeight.w400,
            color: AppColors.textTertiary,
            height: 1.5,
          ),
        ),
        const SizedBox(height: 40),
        BlocBuilder<UserCubit, UserState>(
          builder: (context, state) {
            final isGoogleLoading = state is UserLoading && state.method == 'google';
            final isGlobalLoading = state is UserLoading;
            return Column(
              children: [
                _AuthButton(
                  label: 'Continue with Google',
                  customIcon: SvgPicture.asset(
                    'assets/icons/google_g.svg',
                    width: 22,
                    height: 22,
                  ),
                  isLoading: isGoogleLoading,
                  onTap: () => context.read<UserCubit>().signInWithGoogle(),
                ),
                const SizedBox(height: 12),
                _AuthButton(
                  label: 'Continue with Phone',
                  icon: Icons.phone_outlined,
                  isLoading: false,
                  onTap: isGlobalLoading ? () {} : () => _handleIdentifierCheck(context, 'Continue with Phone'),
                ),
                const SizedBox(height: 12),
                _AuthButton(
                  label: 'Continue with Email',
                  icon: Icons.email_outlined,
                  isLoading: false,
                  onTap: isGlobalLoading ? () {} : () => _handleIdentifierCheck(context, 'Continue with Email'),
                ),
              ],
            );
          },
        ),
        const SizedBox(height: 24),
        RichText(
          textAlign: TextAlign.center,
          text: TextSpan(
            style: GoogleFonts.dmSans(
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
        Text(
          'A Materialless Creation',
          style: GoogleFonts.dmSans(
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

// ─── Identifier Input Sheet (email or phone with in-sheet password reveal) ──
class _IdentifierInputSheet extends StatefulWidget {
  final String title;
  final bool isPhone;
  final BuildContext parentContext;

  const _IdentifierInputSheet({
    required this.title,
    required this.isPhone,
    required this.parentContext,
  });

  @override
  State<_IdentifierInputSheet> createState() => _IdentifierInputSheetState();
}

class _IdentifierInputSheetState extends State<_IdentifierInputSheet> {
  final _identifierController = TextEditingController();
  final _passwordController = TextEditingController();
  final _passwordFocusNode = FocusNode();
  String _countryCode = '+234';
  String _countryFlag = '🇳🇬';
  bool _isChecking = false;
  bool _isSigningIn = false;
  bool _obscurePassword = true;

  // null = not checked yet, true = existing user, false = new user
  bool? _userExists;
  String? _validationError;

  @override
  void dispose() {
    _identifierController.dispose();
    _passwordController.dispose();
    _passwordFocusNode.dispose();
    super.dispose();
  }

  void _showCountryPicker() {
    FocusScope.of(context).unfocus();
    showCountryPicker(
      context: context,
      showPhoneCode: true,
      countryListTheme: CountryListThemeData(
        backgroundColor: AppColors.neutral900,
        textStyle: const TextStyle(color: Colors.white),
        searchTextStyle: const TextStyle(color: Colors.white),
        bottomSheetHeight: 500,
        inputDecoration: InputDecoration(
          labelText: 'Search',
          labelStyle: const TextStyle(color: AppColors.textSecondary),
          hintText: 'Search for country code',
          hintStyle: const TextStyle(color: AppColors.textDisabled),
          prefixIcon: const Icon(Icons.search, color: AppColors.textSecondary),
          border: OutlineInputBorder(
            borderRadius: BorderRadius.circular(12),
            borderSide: const BorderSide(color: AppColors.neutral700),
          ),
        ),
      ),
      onSelect: (Country country) {
        setState(() {
          _countryFlag = country.flagEmoji;
          _countryCode = '+${country.phoneCode}';
        });
      },
    );
  }

  // ── Step 1: Validate format locally ────────────────────────────────────────
  String? _validateFormat(String raw) {
    if (raw.isEmpty) return 'Please enter your ${widget.isPhone ? 'phone number' : 'email address'}.';
    if (widget.isPhone) {
      if (!_isValidPhoneDigits(raw)) return 'Enter a complete phone number (at least 7 digits).';
    } else {
      if (!_isValidEmail(raw)) return 'Enter a valid email address (e.g. user@example.com).';
    }
    return null;
  }

  // ── Step 2: Check if user exists — reveals password field in-sheet ─────────
  Future<void> _onContinue() async {
    if (_isChecking || _isSigningIn) return;
    final raw = _identifierController.text.trim();

    // If password field is already revealed → sign in
    if (_userExists == true) {
      _doSignIn(raw);
      return;
    }

    // Validate format first
    final formatError = _validateFormat(raw);
    if (formatError != null) {
      setState(() => _validationError = formatError);
      return;
    }
    setState(() => _validationError = null);

    final formattedId = widget.isPhone
        ? (raw.startsWith('+') ? raw : '$_countryCode$raw')
        : raw;

    setState(() => _isChecking = true);
    final exists = await widget.parentContext.read<UserCubit>().checkUserStatus(formattedId);
    if (!mounted) return;
    setState(() {
      _isChecking = false;
      _userExists = exists;
    });

    if (!exists) {
      // New user → go to sign-up screen
      if (!mounted) return;
      Navigator.pop(context);
      if (!widget.parentContext.mounted) return;
      Navigator.of(widget.parentContext).push(
        MaterialPageRoute(
          builder: (_) => EmailOtpSignUpScreen(
            initialEmail: widget.isPhone ? '' : formattedId,
            initialPhone: widget.isPhone ? formattedId : '',
            title: 'Create your account',
          ),
        ),
      );
      return;
    }

    // Existing user → reveal password field in-sheet
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _passwordFocusNode.requestFocus();
    });
  }

  // ── Step 3: Sign in with password ──────────────────────────────────────────
  Future<void> _doSignIn(String raw) async {
    final password = _passwordController.text.trim();
    if (password.isEmpty) {
      setState(() => _validationError = 'Please enter your password.');
      return;
    }
    setState(() {
      _validationError = null;
      _isSigningIn = true;
    });

    final formattedId = widget.isPhone
        ? (raw.startsWith('+') ? raw : '$_countryCode$raw')
        : raw;

    await widget.parentContext.read<UserCubit>().signInWithPassword(formattedId, password);
    if (!mounted) return;
    setState(() => _isSigningIn = false);

    // Auth state listener on login_screen handles navigation on success.
    // If still mounted → error was shown via BlocListener, stay in sheet.
  }

  // ── Magic link (email only, existing user) ──────────────────────────────────
  Future<void> _sendMagicLink() async {
    final email = _identifierController.text.trim();
    if (!_isValidEmail(email)) return;
    Navigator.pop(context);
    if (!widget.parentContext.mounted) return;
    await widget.parentContext.read<UserCubit>().sendMagicLink(email);
    if (!widget.parentContext.mounted) return;
    ScaffoldMessenger.of(widget.parentContext).showSnackBar(
      const SnackBar(
        content: Text('Magic link sent — check your inbox.'),
        backgroundColor: AppColors.primary,
        duration: Duration(seconds: 4),
      ),
    );
  }

  // ── Forgot password ─────────────────────────────────────────────────────────
  Future<void> _forgotPassword() async {
    final raw = _identifierController.text.trim();
    if (!raw.contains('@')) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Password reset is only available for email accounts.'),
          backgroundColor: AppColors.neutral700,
        ),
      );
      return;
    }
    Navigator.pop(context);
    if (!widget.parentContext.mounted) return;
    await widget.parentContext.read<UserCubit>().sendPasswordReset(raw);
    if (!widget.parentContext.mounted) return;
    ScaffoldMessenger.of(widget.parentContext).showSnackBar(
      const SnackBar(content: Text('Password reset link sent to your email.')),
    );
  }

  @override
  Widget build(BuildContext context) {
    final passwordRevealed = _userExists == true;

    return BlocListener<UserCubit, UserState>(
      bloc: widget.parentContext.read<UserCubit>(),
      listener: (_, state) {
        if (state is UserError && mounted) {
          setState(() {
            _isSigningIn = false;
            _validationError = state.message;
          });
        }
      },
      child: Padding(
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
            // ── Header ─────────────────────────────────────────────────────
            Text(
              passwordRevealed ? 'Welcome back' : widget.title,
              style: GoogleFonts.dmSans(
                fontSize: 20,
                fontWeight: FontWeight.bold,
                color: Colors.white,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              passwordRevealed
                  ? 'Enter your password to sign in.'
                  : (widget.isPhone
                      ? "We'll check if your account exists, then sign you in."
                      : "We'll check if your account exists, then sign you in."),
              style: GoogleFonts.dmSans(color: AppColors.textSecondary, fontSize: 13),
            ),
            const SizedBox(height: 24),

            // ── Identifier field ────────────────────────────────────────────
            Container(
              decoration: BoxDecoration(
                color: AppColors.neutral700.withValues(alpha: 0.5),
                borderRadius: BorderRadius.circular(16),
                border: Border.all(
                  color: _validationError != null && !passwordRevealed
                      ? AppColors.liveRed.withValues(alpha: 0.6)
                      : Colors.white.withValues(alpha: 0.08),
                ),
              ),
              child: TextField(
                controller: _identifierController,
                autofocus: true,
                enabled: !passwordRevealed,
                style: TextStyle(
                  color: passwordRevealed ? AppColors.textSecondary : Colors.white,
                ),
                keyboardType: widget.isPhone
                    ? TextInputType.phone
                    : TextInputType.emailAddress,
                onChanged: (_) {
                  if (_validationError != null) setState(() => _validationError = null);
                },
                decoration: InputDecoration(
                  hintText: widget.isPhone ? 'e.g. 8012345678' : 'e.g. user@example.com',
                  hintStyle: const TextStyle(color: AppColors.textDisabled, fontSize: 14),
                  border: InputBorder.none,
                  prefixIcon: widget.isPhone
                      ? Padding(
                          padding: const EdgeInsets.only(left: 12, right: 8),
                          child: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              InkWell(
                                onTap: passwordRevealed ? null : _showCountryPicker,
                                child: Container(
                                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                                  decoration: BoxDecoration(
                                    color: AppColors.neutral700.withValues(alpha: 0.4),
                                    borderRadius: BorderRadius.circular(6),
                                  ),
                                  child: Row(
                                    mainAxisSize: MainAxisSize.min,
                                    children: [
                                      Text(_countryFlag, style: const TextStyle(fontSize: 16)),
                                      const SizedBox(width: 4),
                                      Text(
                                        _countryCode,
                                        style: const TextStyle(
                                          color: Colors.white,
                                          fontWeight: FontWeight.w600,
                                          fontSize: 13,
                                        ),
                                      ),
                                      const Icon(Icons.arrow_drop_down,
                                          color: AppColors.textSecondary, size: 18),
                                    ],
                                  ),
                                ),
                              ),
                              const SizedBox(width: 8),
                              Container(width: 1, height: 20, color: Colors.white12),
                            ],
                          ),
                        )
                      : const Icon(Icons.email_outlined,
                          color: AppColors.textTertiary, size: 20),
                  contentPadding:
                      const EdgeInsets.symmetric(vertical: 18, horizontal: 16),
                ),
              ),
            ),

            // ── Password field (animated reveal) ────────────────────────────
            AnimatedSize(
              duration: const Duration(milliseconds: 280),
              curve: Curves.easeInOut,
              child: passwordRevealed
                  ? Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        const SizedBox(height: 14),
                        Container(
                          decoration: BoxDecoration(
                            color: AppColors.neutral700.withValues(alpha: 0.5),
                            borderRadius: BorderRadius.circular(16),
                            border: Border.all(
                              color: _validationError != null
                                  ? AppColors.liveRed.withValues(alpha: 0.6)
                                  : Colors.white.withValues(alpha: 0.08),
                            ),
                          ),
                          child: Row(
                            children: [
                              const Padding(
                                padding: EdgeInsets.only(left: 16),
                                child: Icon(Icons.lock_outline_rounded,
                                    color: AppColors.textTertiary, size: 20),
                              ),
                              Expanded(
                                child: TextField(
                                  controller: _passwordController,
                                  focusNode: _passwordFocusNode,
                                  obscureText: _obscurePassword,
                                  style: const TextStyle(color: Colors.white),
                                  onSubmitted: (_) => _onContinue(),
                                  onChanged: (_) {
                                    if (_validationError != null) {
                                      setState(() => _validationError = null);
                                    }
                                  },
                                  decoration: InputDecoration(
                                    hintText: 'Password',
                                    hintStyle: const TextStyle(
                                        color: AppColors.textDisabled, fontSize: 14),
                                    border: InputBorder.none,
                                    contentPadding: const EdgeInsets.symmetric(
                                        vertical: 18, horizontal: 12),
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
                      ],
                    )
                  : const SizedBox.shrink(),
            ),

            // ── Validation error ────────────────────────────────────────────
            if (_validationError != null) ...[
              const SizedBox(height: 8),
              Text(
                _validationError!,
                style: GoogleFonts.dmSans(
                    color: AppColors.liveRed, fontSize: 12),
              ),
            ],

            const SizedBox(height: 24),

            // ── Primary button (Continue → Sign In) ─────────────────────────
            ElevatedButton(
              style: ElevatedButton.styleFrom(
                backgroundColor: AppColors.primary,
                foregroundColor: Colors.black,
                padding: const EdgeInsets.symmetric(vertical: 16),
                shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(28)),
              ),
              onPressed: (_isChecking || _isSigningIn) ? null : _onContinue,
              child: (_isChecking || _isSigningIn)
                  ? const SizedBox(
                      height: 18,
                      width: 18,
                      child: CircularProgressIndicator(
                          color: Colors.black, strokeWidth: 2),
                    )
                  : Text(
                      passwordRevealed ? 'Sign In' : 'Continue',
                      style: GoogleFonts.dmSans(fontWeight: FontWeight.bold),
                    ),
            ),

            // ── Forgot password / Magic link (only when password revealed) ──
            if (passwordRevealed) ...[
              const SizedBox(height: 12),
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  if (!widget.isPhone)
                    TextButton(
                      onPressed: _sendMagicLink,
                      child: Text(
                        'Send magic link instead',
                        style: GoogleFonts.dmSans(
                          fontSize: 13,
                          color: AppColors.primary.withValues(alpha: 0.85),
                        ),
                      ),
                    ),
                  if (!widget.isPhone) const SizedBox(width: 8),
                  TextButton(
                    onPressed: _forgotPassword,
                    child: Text(
                      'Forgot password?',
                      style: GoogleFonts.dmSans(
                        fontSize: 13,
                        color: AppColors.textTertiary,
                      ),
                    ),
                  ),
                ],
              ),
            ],

            const SizedBox(height: 32),
          ],
        ),
      ),
    );
  }
}



class _AuthButton extends StatelessWidget {
  final String label;
  final IconData? icon;
  final Widget? customIcon;
  final bool isLoading;
  final VoidCallback onTap;

  const _AuthButton({
    required this.label,
    this.icon,
    this.customIcon,
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
            else if (customIcon != null)
              customIcon!
            else
              Icon(icon, color: Colors.white, size: 22),
            const SizedBox(width: 10),
            Text(
              label,
              style: GoogleFonts.dmSans(
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
