// profile_setup_screen.dart: Post-auth complete profile setup.
// Part of LeoBook App - Screens

import 'package:country_picker/country_picker.dart';
import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:leobookapp/core/constants/app_colors.dart';
import 'package:leobookapp/core/utils/phone_utils.dart';
import 'package:leobookapp/data/repositories/auth_repository.dart';
import 'package:leobookapp/logic/cubit/user_cubit.dart';
import 'package:leobookapp/presentation/screens/login_screen.dart';
import 'package:leobookapp/presentation/screens/main_screen.dart';
import 'package:leobookapp/presentation/screens/otp_verification_screen.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

class ProfileSetupScreen extends StatefulWidget {
  const ProfileSetupScreen({super.key});

  @override
  State<ProfileSetupScreen> createState() => _ProfileSetupScreenState();
}

class _ProfileSetupScreenState extends State<ProfileSetupScreen> {
  final _formKey = GlobalKey<FormState>();
  final _usernameController = TextEditingController();
  final _passwordController = TextEditingController();
  final _confirmPasswordController = TextEditingController();
  final _emailController = TextEditingController();
  final _phoneController = TextEditingController();
  final AuthRepository _authRepo = AuthRepository();
  final FlutterSecureStorage _secureStorage = const FlutterSecureStorage();

  bool _isLoading = false;
  bool _phoneNeedsVerification = true;
  bool _obscurePassword = true;
  bool _obscureConfirmPassword = true;
  bool _acceptedTerms = false;
  bool _biometricsEnabled = false;

  String _selectedCountryCode = '+234';
  String _selectedCountryFlag = 'NG';

  @override
  void initState() {
    super.initState();
    final user = context.read<UserCubit>().state.user;
    _emailController.text = user.email ?? '';

    if (user.phone != null && user.phone!.trim().length > 5) {
      _phoneNeedsVerification = false;
      _phoneController.text = user.phone!;
    }

    _usernameController.text = user.displayName ?? '';
    _biometricsEnabled = user.isBiometricsEnabled;
  }

  @override
  void dispose() {
    _usernameController.dispose();
    _passwordController.dispose();
    _confirmPasswordController.dispose();
    _emailController.dispose();
    _phoneController.dispose();
    super.dispose();
  }

  bool _isValidPassword(String password) {
    if (password.length < 8) return false;
    if (!password.contains(RegExp(r'[A-Z]'))) return false;
    if (!password.contains(RegExp(r'[a-z]'))) return false;
    if (!password.contains(RegExp(r'[0-9]'))) return false;
    if (!password.contains(RegExp(r'[!@#\$&*~]'))) return false;
    return true;
  }

  void _showMessage(String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(message)),
    );
  }

  void _goToLogin() {
    Navigator.of(context).pushAndRemoveUntil(
      MaterialPageRoute(builder: (_) => const LoginScreen()),
      (_) => false,
    );
  }

  Future<void> _sendPhoneOtp() async {
    if (_phoneController.text.isEmpty) {
      _showMessage('Please enter your phone number');
      return;
    }

    setState(() => _isLoading = true);
    try {
      final formattedPhone = toE164(_selectedCountryCode, _phoneController.text);
      await _authRepo.updatePhone(formattedPhone);

      if (!mounted) return;
      Navigator.of(context).push(
        MaterialPageRoute(
          builder: (_) => OtpVerificationScreen(
            phone: formattedPhone,
            isPhoneChange: true,
          ),
        ),
      );
    } catch (e) {
      if (!mounted) return;
      _showMessage(AuthRepository.mapAuthError(e));
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  Future<void> _completeProfile() async {
    if (!_formKey.currentState!.validate()) return;

    if (!_acceptedTerms) {
      _showMessage('Please accept the Terms and Privacy Policy');
      return;
    }

    if (_phoneNeedsVerification) {
      _showMessage('Please verify your phone number using the button below first');
      return;
    }

    setState(() => _isLoading = true);
    try {
      final supabase = Supabase.instance.client;
      final userCubit = context.read<UserCubit>();
      final currentUser = supabase.auth.currentUser;
      final currentSession = _authRepo.currentSession;
      final password = _passwordController.text.trim();

      if (currentUser == null || currentSession == null) {
        _showMessage('Your session expired. Please sign in again.');
        _goToLogin();
        return;
      }

      await supabase.auth.updateUser(
        UserAttributes(
          password: password,
          data: {
            'full_name': _usernameController.text.trim(),
            'username': _usernameController.text.trim(),
            'profile_completed': true,
            'biometrics_enabled': _biometricsEnabled,
            'phone_verified': true,
          },
        ),
      );

      await supabase.from('profiles').upsert({
        'id': currentUser.id,
        'email': currentUser.email,
        'phone': supabase.auth.currentUser?.phone ?? _phoneController.text.trim(),
        'full_name': _usernameController.text.trim(),
        'phone_verified': true,
      });

      if (_biometricsEnabled) {
        final identifier = _emailController.text.trim().isNotEmpty
            ? _emailController.text.trim()
            : (supabase.auth.currentUser?.phone ?? _phoneController.text.trim());
        if (identifier.isNotEmpty) {
          await _secureStorage.write(key: 'leo_id', value: identifier);
          await _secureStorage.write(key: 'leo_pw', value: password);
        }
      } else {
        await _secureStorage.delete(key: 'leo_id');
        await _secureStorage.delete(key: 'leo_pw');
      }

      await supabase.auth.refreshSession();
      await userCubit.refreshCurrentUserState();
    } catch (e) {
      if (!mounted) return;
      final message = AuthRepository.mapAuthError(
        e,
        fallbackMessage: 'Unable to save your profile right now.',
      );
      _showMessage(message);
      if (message == 'Your session expired. Please sign in again.') {
        _goToLogin();
      }
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  void _showCountryPicker() {
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
          _selectedCountryFlag = country.flagEmoji;
          _selectedCountryCode = '+${country.phoneCode}';
        });
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final formContent = Form(
      key: _formKey,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            'Just one last step!',
            style: GoogleFonts.dmSans(
              fontSize: 26,
              color: Colors.white,
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 10),
          Text(
            'To secure your LeoBook account, please complete your profile details.',
            style: GoogleFonts.dmSans(
              color: AppColors.textSecondary,
              fontSize: 14,
              height: 1.4,
            ),
          ),
          const SizedBox(height: 32),
          TextFormField(
            controller: _usernameController,
            style: const TextStyle(color: Colors.white),
            decoration: _inputDecoration(
              'Full Name',
              prefixIcon: Icons.person_outline_rounded,
            ),
            validator: (v) => v!.isEmpty ? 'Please enter your name' : null,
          ),
          const SizedBox(height: 16),
          TextFormField(
            controller: _emailController,
            style: const TextStyle(color: AppColors.textSecondary),
            enabled: false,
            decoration: _inputDecoration(
              'Email Address',
              prefixIcon: Icons.alternate_email_rounded,
            ),
          ),
          const SizedBox(height: 16),
          TextFormField(
            controller: _phoneController,
            style: const TextStyle(color: Colors.white),
            keyboardType: TextInputType.phone,
            decoration: _inputDecoration(
              '80XXXXXXXX',
            ).copyWith(
              prefixIcon: Padding(
                padding: const EdgeInsets.only(left: 14, right: 8),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(
                      Icons.phone_iphone_rounded,
                      color: AppColors.textSecondary,
                      size: 22,
                    ),
                    const SizedBox(width: 8),
                    InkWell(
                      onTap: () {
                        FocusScope.of(context).unfocus();
                        _showCountryPicker();
                      },
                      child: Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                        decoration: BoxDecoration(
                          color: AppColors.neutral700.withValues(alpha: 0.4),
                          borderRadius: BorderRadius.circular(6),
                        ),
                        child: Row(
                          children: [
                            Text(_selectedCountryFlag, style: const TextStyle(fontSize: 18)),
                            const SizedBox(width: 4),
                            Text(
                              _selectedCountryCode,
                              style: const TextStyle(
                                color: Colors.white,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                            const Icon(Icons.arrow_drop_down, color: AppColors.textSecondary),
                          ],
                        ),
                      ),
                    ),
                    const SizedBox(width: 10),
                    Container(width: 1, height: 24, color: Colors.white12),
                  ],
                ),
              ),
            ),
            validator: (v) => v!.isEmpty ? 'Phone number required' : null,
          ),
          const SizedBox(height: 16),
          TextFormField(
            controller: _passwordController,
            style: const TextStyle(color: Colors.white),
            obscureText: _obscurePassword,
            decoration: _inputDecoration(
              'Set a Secure Password',
              prefixIcon: Icons.lock_outline_rounded,
              suffixIcon: IconButton(
                icon: Icon(
                  _obscurePassword ? Icons.visibility_off_rounded : Icons.visibility_rounded,
                  color: AppColors.textSecondary,
                  size: 20,
                ),
                onPressed: () => setState(() => _obscurePassword = !_obscurePassword),
              ),
            ),
            validator: (v) {
              if (v!.isEmpty) return 'Password required';
              if (!_isValidPassword(v)) return 'Must include uppercase, number & symbol';
              return null;
            },
          ),
          const SizedBox(height: 16),
          TextFormField(
            controller: _confirmPasswordController,
            style: const TextStyle(color: Colors.white),
            obscureText: _obscureConfirmPassword,
            decoration: _inputDecoration(
              'Confirm Password',
              prefixIcon: Icons.lock_reset_rounded,
              suffixIcon: IconButton(
                icon: Icon(
                  _obscureConfirmPassword ? Icons.visibility_off_rounded : Icons.visibility_rounded,
                  color: AppColors.textSecondary,
                  size: 20,
                ),
                onPressed: () => setState(
                  () => _obscureConfirmPassword = !_obscureConfirmPassword,
                ),
              ),
            ),
            validator: (v) => v != _passwordController.text ? 'Passwords do not match' : null,
          ),
          const SizedBox(height: 16),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            decoration: BoxDecoration(
              color: AppColors.neutral800,
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: Colors.white.withValues(alpha: 0.05)),
            ),
            child: SwitchListTile(
              title: Text(
                'Enable Biometric Login',
                style: GoogleFonts.dmSans(
                  fontSize: 14,
                  fontWeight: FontWeight.w500,
                  color: Colors.white,
                ),
              ),
              subtitle: Text(
                'Sign in faster using your fingerprint or face.',
                style: GoogleFonts.dmSans(
                  fontSize: 12,
                  color: AppColors.textTertiary,
                ),
              ),
              value: _biometricsEnabled,
              activeColor: AppColors.primary,
              secondary: const Icon(Icons.fingerprint_rounded, color: AppColors.primary),
              onChanged: (v) => setState(() => _biometricsEnabled = v),
              contentPadding: EdgeInsets.zero,
            ),
          ),
          const SizedBox(height: 24),
          ElevatedButton(
            style: ElevatedButton.styleFrom(
              backgroundColor: AppColors.neutral800,
              foregroundColor: Colors.white,
              padding: const EdgeInsets.symmetric(vertical: 14),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
              side: const BorderSide(color: Colors.white10),
            ),
            onPressed: _isLoading ? null : _sendPhoneOtp,
            child: _isLoading
                ? const SizedBox(
                    height: 18,
                    width: 18,
                    child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                  )
                : Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      const Icon(Icons.forum_outlined, color: Color(0xFF25D366), size: 20),
                      const SizedBox(width: 8),
                      Text(
                        'Send WhatsApp OTP',
                        style: GoogleFonts.dmSans(fontWeight: FontWeight.w500),
                      ),
                    ],
                  ),
          ),
          const SizedBox(height: 32),
          Row(
            children: [
              Checkbox(
                value: _acceptedTerms,
                activeColor: AppColors.primary,
                side: const BorderSide(color: AppColors.textSecondary),
                onChanged: (v) => setState(() => _acceptedTerms = v ?? false),
              ),
              Expanded(
                child: RichText(
                  text: TextSpan(
                    style: GoogleFonts.dmSans(
                      color: AppColors.textSecondary,
                      fontSize: 12,
                    ),
                    children: [
                      const TextSpan(text: 'I agree to the '),
                      TextSpan(
                        text: 'Terms of Service',
                        style: const TextStyle(
                          color: AppColors.primary,
                          fontWeight: FontWeight.bold,
                        ),
                        recognizer: TapGestureRecognizer()..onTap = () {},
                      ),
                      const TextSpan(text: ' and '),
                      TextSpan(
                        text: 'Privacy Policy',
                        style: const TextStyle(
                          color: AppColors.primary,
                          fontWeight: FontWeight.bold,
                        ),
                        recognizer: TapGestureRecognizer()..onTap = () {},
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 24),
          ElevatedButton(
            style: ElevatedButton.styleFrom(
              backgroundColor: AppColors.primary,
              foregroundColor: Colors.black,
              disabledBackgroundColor: AppColors.primary.withValues(alpha: 0.3),
              padding: const EdgeInsets.symmetric(vertical: 18),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
            ),
            onPressed: (_isLoading || !_acceptedTerms) ? null : _completeProfile,
            child: _isLoading
                ? const SizedBox(
                    height: 20,
                    width: 20,
                    child: CircularProgressIndicator(color: Colors.black, strokeWidth: 2),
                  )
                : Text(
                    'Save & Finish',
                    style: GoogleFonts.dmSans(fontSize: 16, fontWeight: FontWeight.bold),
                  ),
          ),
        ],
      ),
    );

    return BlocListener<UserCubit, UserState>(
      listener: (context, state) {
        if (state is UserAuthenticated) {
          Navigator.of(context).pushAndRemoveUntil(
            MaterialPageRoute(builder: (_) => const MainScreen()),
            (_) => false,
          );
        } else if (state is UserError) {
          _showMessage(state.message);
        }
      },
      child: PopScope(
        canPop: false,
        onPopInvokedWithResult: (didPop, _) {
          if (!didPop) {
            _goToLogin();
          }
        },
        child: Scaffold(
          backgroundColor: AppColors.neutral900,
          appBar: AppBar(
            title: Text(
              'Complete Profile',
              style: GoogleFonts.dmSans(fontSize: 18, fontWeight: FontWeight.w600),
            ),
            backgroundColor: Colors.transparent,
            elevation: 0,
            leading: IconButton(
              icon: const Icon(Icons.arrow_back_ios_new_rounded, size: 20),
              onPressed: _goToLogin,
            ),
          ),
          body: SafeArea(
            child: Center(
              child: SingleChildScrollView(
                padding: const EdgeInsets.all(24),
                child: Container(
                  constraints: const BoxConstraints(maxWidth: 450),
                  child: formContent,
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }

  InputDecoration _inputDecoration(
    String hint, {
    IconData? prefixIcon,
    Widget? suffixIcon,
  }) {
    return InputDecoration(
      hintText: hint,
      prefixIcon: prefixIcon != null
          ? Icon(prefixIcon, color: AppColors.textSecondary, size: 22)
          : null,
      suffixIcon: suffixIcon,
      hintStyle: const TextStyle(color: AppColors.textDisabled, fontSize: 14),
      filled: true,
      fillColor: AppColors.neutral800,
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: BorderSide.none,
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: BorderSide(color: Colors.white.withValues(alpha: 0.05)),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: const BorderSide(color: AppColors.primary, width: 1.5),
      ),
    );
  }
}
