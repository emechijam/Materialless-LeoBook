import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:leobookapp/core/constants/app_colors.dart';
import 'package:leobookapp/data/repositories/auth_repository.dart';
import 'package:leobookapp/logic/cubit/user_cubit.dart';
import 'package:leobookapp/presentation/screens/main_screen.dart';
import 'package:leobookapp/presentation/screens/profile_setup_screen.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

class OtpVerificationScreen extends StatefulWidget {
  final String phone;
  final bool isPhoneChange;

  const OtpVerificationScreen({
    super.key,
    required this.phone,
    this.isPhoneChange = false,
  });

  @override
  State<OtpVerificationScreen> createState() => _OtpVerificationScreenState();
}

class _OtpVerificationScreenState extends State<OtpVerificationScreen> {
  final _otpController = TextEditingController();
  final AuthRepository _authRepo = AuthRepository();
  bool _isLoading = false;
  Timer? _resendTimer;
  int _countdown = 30;
  bool _canResend = false;
  bool _isSmsFallback = false;

  @override
  void initState() {
    super.initState();
    _startResendTimer();
  }

  @override
  void dispose() {
    _otpController.dispose();
    _resendTimer?.cancel();
    super.dispose();
  }

  void _startResendTimer() {
    setState(() {
      _countdown = 30;
      _canResend = false;
    });

    _resendTimer?.cancel();
    _resendTimer = Timer.periodic(const Duration(seconds: 1), (timer) {
      if (!mounted) {
        timer.cancel();
        return;
      }

      if (_countdown > 0) {
        setState(() => _countdown--);
      } else {
        setState(() {
          _canResend = true;
          _isSmsFallback = true;
        });
        timer.cancel();
      }
    });
  }

  Future<void> _handleResend() async {
    if (!_canResend) return;

    setState(() => _isLoading = true);
    try {
      String channelName = 'WhatsApp';
      if (widget.isPhoneChange) {
        await _authRepo.updatePhone(widget.phone);
        channelName = 'SMS';
      } else {
        final preferredChannel =
            _isSmsFallback ? OtpChannel.sms : OtpChannel.whatsapp;
        final deliveredChannel = await _authRepo.sendOtp(
          widget.phone,
          channel: preferredChannel,
        );
        channelName = deliveredChannel == OtpChannel.sms ? 'SMS' : 'WhatsApp';
      }

      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('OTP resent via $channelName.')),
      );
      _startResendTimer();
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(AuthRepository.mapAuthError(e))),
      );
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  Future<void> _verifyOtp() async {
    final token = _otpController.text.trim();
    if (token.length != 6) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please enter the full 6-digit OTP.')),
      );
      return;
    }

    setState(() => _isLoading = true);
    try {
      final userCubit = context.read<UserCubit>();
      final supabase = Supabase.instance.client;

      await userCubit.verifyPhoneOtp(
        widget.phone,
        token,
        isPhoneChange: widget.isPhoneChange,
      );

      final userId = supabase.auth.currentUser?.id;
      if (userId != null) {
        await supabase
            .from('profiles')
            .update({'phone_verified': true}).eq('id', userId);
        await supabase.auth.updateUser(
          UserAttributes(phone: widget.phone, data: {'phone_verified': true}),
        );
        await userCubit.refreshCurrentUserState();
      }
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            AuthRepository.mapAuthError(
              e,
              fallbackMessage: 'Invalid verification code. Please try again.',
            ),
          ),
        ),
      );
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return BlocListener<UserCubit, UserState>(
      listener: (context, state) {
        if (state is UserAuthenticated) {
          Navigator.of(context).pushAndRemoveUntil(
            MaterialPageRoute(builder: (_) => const MainScreen()),
            (_) => false,
          );
        } else if (state is UserProfileIncomplete) {
          Navigator.of(context).pushAndRemoveUntil(
            MaterialPageRoute(builder: (_) => const ProfileSetupScreen()),
            (_) => false,
          );
        } else if (state is UserError) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text(state.message)),
          );
        }
      },
      child: Scaffold(
        backgroundColor: AppColors.neutral900,
        appBar: AppBar(
          title: Text(
            'Verification Code',
            style:
                GoogleFonts.dmSans(fontSize: 18, fontWeight: FontWeight.w600),
          ),
          backgroundColor: Colors.transparent,
          elevation: 0,
          leading: IconButton(
            icon: const Icon(Icons.arrow_back_ios_new_rounded, size: 20),
            onPressed: () => Navigator.pop(context),
          ),
        ),
        body: SafeArea(
          child: Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(24),
              child: Container(
                constraints: const BoxConstraints(maxWidth: 450),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(
                      Icons.mark_chat_unread_outlined,
                      size: 64,
                      color: AppColors.primary,
                    ),
                    const SizedBox(height: 24),
                    Text(
                      'Enter verification code',
                      textAlign: TextAlign.center,
                      style: GoogleFonts.dmSans(
                        fontSize: 24,
                        fontWeight: FontWeight.w700,
                        color: Colors.white,
                      ),
                    ),
                    const SizedBox(height: 12),
                    Text(
                      'We sent a 6-digit code to\n${widget.phone}',
                      textAlign: TextAlign.center,
                      style: GoogleFonts.dmSans(
                        fontSize: 14,
                        color: AppColors.textSecondary,
                        height: 1.4,
                      ),
                    ),
                    const SizedBox(height: 40),
                    Container(
                      decoration: BoxDecoration(
                        color: AppColors.neutral800,
                        borderRadius: BorderRadius.circular(16),
                        border: Border.all(
                            color: Colors.white.withValues(alpha: 0.08)),
                      ),
                      child: TextField(
                        controller: _otpController,
                        keyboardType: TextInputType.number,
                        autofocus: true,
                        inputFormatters: [
                          FilteringTextInputFormatter.digitsOnly,
                          LengthLimitingTextInputFormatter(6),
                        ],
                        textAlign: TextAlign.center,
                        style: GoogleFonts.dmSans(
                          fontSize: 28,
                          fontWeight: FontWeight.bold,
                          color: Colors.white,
                          letterSpacing: 16,
                        ),
                        decoration: InputDecoration(
                          hintText: '000000',
                          hintStyle: GoogleFonts.dmSans(
                            color: AppColors.textDisabled,
                            fontSize: 28,
                            letterSpacing: 16,
                          ),
                          border: InputBorder.none,
                          contentPadding: const EdgeInsets.symmetric(
                            horizontal: 16,
                            vertical: 24,
                          ),
                        ),
                        onChanged: (val) {
                          if (val.length == 6) {
                            _verifyOtp();
                          }
                        },
                      ),
                    ),
                    const SizedBox(height: 24),
                    ElevatedButton(
                      style: ElevatedButton.styleFrom(
                        backgroundColor: AppColors.primary,
                        foregroundColor: Colors.black,
                        padding: const EdgeInsets.symmetric(vertical: 18),
                        shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(14)),
                        disabledBackgroundColor:
                            AppColors.primary.withValues(alpha: 0.3),
                      ),
                      onPressed: _isLoading ? null : _verifyOtp,
                      child: _isLoading
                          ? const SizedBox(
                              width: 24,
                              height: 24,
                              child: CircularProgressIndicator(
                                color: Colors.black,
                                strokeWidth: 2,
                              ),
                            )
                          : Text(
                              'Verify Code',
                              style: GoogleFonts.dmSans(
                                fontSize: 16,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                    ),
                    const SizedBox(height: 32),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Text(
                          'Didn\'t receive code?',
                          style: GoogleFonts.dmSans(
                            color: AppColors.textSecondary,
                            fontSize: 14,
                          ),
                        ),
                        const SizedBox(width: 8),
                        GestureDetector(
                          onTap: _canResend ? _handleResend : null,
                          child: Text(
                            _canResend
                                ? (_isSmsFallback
                                    ? 'Send via SMS'
                                    : 'Resend via WhatsApp')
                                : 'Resend in ${_countdown}s',
                            style: GoogleFonts.dmSans(
                              color: _canResend
                                  ? AppColors.primary
                                  : AppColors.textDisabled,
                              fontSize: 14,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
