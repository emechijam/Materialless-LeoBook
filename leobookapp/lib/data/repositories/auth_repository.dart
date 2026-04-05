// auth_repository.dart: Supabase authentication — Google, Phone OTP, Email.
// Part of LeoBook App — Repositories
//
// Classes: AuthRepository

import 'package:device_info_plus/device_info_plus.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:google_sign_in/google_sign_in.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import '../services/twilio_service.dart';

class AuthRepository {
  final SupabaseClient _supabase = Supabase.instance.client;
  static const String _defaultMobileAuthRedirectUrl =
      'com.materialless.leobookapp://login-callback';

  /// Stream of Supabase Auth state changes
  Stream<AuthState> get authStateChanges => _supabase.auth.onAuthStateChange;

  /// Get current user
  User? get currentUser => _supabase.auth.currentUser;

  /// Whether a user is currently signed in
  bool get isSignedIn => currentUser != null;

  /// Get current auth session
  Session? get currentSession => _supabase.auth.currentSession;

  static String mapAuthError(
    Object error, {
    String fallbackMessage = 'Something went wrong. Please try again.',
  }) {
    final statusCode =
        error is AuthException ? error.statusCode?.toString() : '';
    final code =
        error is AuthApiException ? (error.code ?? '').toLowerCase() : '';
    final message = error.toString().toLowerCase();
    final combined = '$code $statusCode $message';

    if (combined.contains('invalid_credentials') ||
        combined.contains('invalid login credentials') ||
        combined.contains('wrong password') ||
        combined.contains('invalid_grant')) {
      return 'Incorrect email/phone or password.';
    }

    if (combined.contains('user_not_found') ||
        combined.contains('sub claim in jwt does not exist') ||
        (combined.contains('jwt') && combined.contains('does not exist'))) {
      return 'Your session expired. Please sign in again.';
    }

    if (combined.contains('phone_exists') ||
        combined.contains('already been registered') ||
        (combined.contains('phone number') &&
            combined.contains('registered')) ||
        (combined.contains('duplicate') && combined.contains('phone'))) {
      return 'This phone number is already linked to another account.';
    }

    if (combined.contains('email_exists') ||
        combined.contains('user already registered') ||
        (combined.contains('already registered') &&
            combined.contains('email'))) {
      return 'An account already exists with this email.';
    }

    if (combined.contains('unsupported channel') ||
        (combined.contains('whatsapp') && combined.contains('not available'))) {
      return 'That verification channel is not available right now. Please try SMS instead.';
    }

    if ((combined.contains('sms') && combined.contains('provider')) ||
        (combined.contains('phone') && combined.contains('provider')) ||
        combined.contains('twilio') ||
        combined.contains('messagebird') ||
        combined.contains('vonage')) {
      return 'Phone verification is temporarily unavailable. Please try again shortly.';
    }

    if (combined.contains('redirect') &&
        (combined.contains('invalid') || combined.contains('not allowed'))) {
      return 'This email link is not configured correctly yet. Please try again later.';
    }

    return fallbackMessage;
  }

  String get _authRedirectUrl {
    if (kIsWeb) {
      return Uri.base.origin;
    }

    final configured = dotenv.env['AUTH_REDIRECT_URL']?.trim();
    if (configured != null && configured.isNotEmpty) {
      return configured;
    }

    return _defaultMobileAuthRedirectUrl;
  }

  // ─── Google Sign-In ──────────────────────────────────────────────

  /// Sign in with Google.
  /// Web: Uses Supabase OAuth redirect (no native google_sign_in).
  /// Mobile: Uses native google_sign_in + Supabase ID token exchange.
  Future<AuthResponse> signInWithGoogle() async {
    if (kIsWeb) {
      return _signInWithGoogleWeb();
    }
    return _signInWithGoogleNative();
  }

  /// Web: Supabase handles the full OAuth redirect flow.
  Future<AuthResponse> _signInWithGoogleWeb() async {
    try {
      final success = await _supabase.auth.signInWithOAuth(
        OAuthProvider.google,
        redirectTo: _authRedirectUrl,
      );
      if (!success) {
        throw 'Google OAuth redirect failed.';
      }
      // After redirect, Supabase auto-signs in via authStateChanges.
      // Return a placeholder — the real auth state comes from the listener.
      // Wait briefly for the session to populate after redirect.
      await Future.delayed(const Duration(seconds: 1));
      final session = _supabase.auth.currentSession;
      if (session != null) {
        return AuthResponse(session: session, user: session.user);
      }
      // If no session yet, the redirect hasn't completed — caller handles via listener.
      return AuthResponse(session: null, user: null);
    } catch (e) {
      debugPrint('[AuthRepository] Google OAuth (web) error: $e');
      rethrow;
    }
  }

  /// Mobile: Native in-app Google Sign-In via google_sign_in v7+ SDK.
  /// Shows the native credential-picker sheet — no Chrome / external browser.
  /// GoogleSignIn.instance.initialize() is called once at startup in main.dart.
  Future<AuthResponse> _signInWithGoogleNative() async {
    try {
      // v7+: authenticate() replaces signIn(); returns GoogleSignInAccount.
      final account = await GoogleSignIn.instance.authenticate();

      // .authentication is a synchronous property in v7 (GoogleSignInAuthentication).
      final idToken = account.authentication.idToken;
      if (idToken == null) {
        throw 'Google authentication failed — missing ID token. '
            'Ensure GOOGLE_WEB_CLIENT_ID is the Web OAuth client ID.';
      }

      // Only idToken is needed; accessToken requires authorizationClient in v7.
      final response = await _supabase.auth.signInWithIdToken(
        provider: OAuthProvider.google,
        idToken: idToken,
      );

      if (response.user != null) {
        logUserSession(response.user!, deviceInfo: await _buildDeviceInfo());
      }

      return response;
    } on Exception catch (e) {
      final msg = e.toString().toLowerCase();
      // User tapped Cancel on the picker — not an error.
      if (msg.contains('cancel') || msg.contains('sign_in_cancelled')) {
        debugPrint('[AuthRepository] Google sign-in cancelled by user.');
        return AuthResponse(session: null, user: null);
      }
      debugPrint('[AuthRepository] Google native sign-in error: $e');
      rethrow;
    }
  }

  // ─── Email Sign-Up ──────────────────────────────────────────────

  /// Create account with email + password.
  Future<AuthResponse> signUpWithEmail(String email, String password) async {
    try {
      return await _supabase.auth.signUp(
        email: email,
        password: password,
        emailRedirectTo: _authRedirectUrl,
      );
    } catch (e) {
      debugPrint('[AuthRepository] Email sign-up error: $e');
      rethrow;
    }
  }

  /// Sign in with existing email + password.
  Future<AuthResponse> signInWithEmail(String email, String password) async {
    try {
      final response = await _supabase.auth.signInWithPassword(
        email: email,
        password: password,
      );
      if (response.user != null) {
        logUserSession(response.user!, deviceInfo: await _buildDeviceInfo());
      }
      return response;
    } catch (e) {
      debugPrint('[AuthRepository] Email sign-in error: $e');
      rethrow;
    }
  }

  /// Sign in with identifier (email or phone) and password.
  Future<AuthResponse> signInWithPassword(
      String identifier, String password) async {
    try {
      final response = await _supabase.auth.signInWithPassword(
        email: identifier.contains('@') ? identifier : null,
        phone: identifier.contains('@') ? null : identifier,
        password: password,
      );
      if (response.user != null) {
        logUserSession(response.user!, deviceInfo: await _buildDeviceInfo());
      }
      return response;
    } catch (e) {
      debugPrint('[AuthRepository] Password sign-in error: $e');
      rethrow;
    }
  }

  /// Check whether [identifier] (email or phone) belongs to an existing user.
  ///
  /// Strategy (most reliable first):
  ///   1. Edge function 'check-user-status' — queries auth.users directly.
  ///   2. Profiles table — covers email/phone if profile row exists.
  ///   3. Returns null (unknown) on total failure — caller treats as new user.
  Future<Map<String, dynamic>?> checkUserExistence(String identifier) async {
    // ── 1. Edge function (primary) ────────────────────────────────────
    try {
      final response = await _supabase.functions
          .invoke('check-user-status', body: {'identifier': identifier})
          .timeout(const Duration(seconds: 6));
      final data = response.data;
      if (data is Map && data.containsKey('exists')) {
        debugPrint('[AuthRepository] checkUserExistence via edge fn: $data');
        return Map<String, dynamic>.from(data);
      }
    } catch (e) {
      debugPrint('[AuthRepository] checkUserExistence edge fn failed: $e');
    }

    // ── 2. Profiles table (fallback) ──────────────────────────────────
    try {
      final isEmail = identifier.contains('@');
      final List<dynamic> rows = isEmail
          ? await _supabase
              .from('profiles')
              .select('id')
              .eq('email', identifier)
              .limit(1)
          : await _supabase
              .from('profiles')
              .select('id')
              .eq('phone', identifier)
              .limit(1);
      debugPrint(
          '[AuthRepository] checkUserExistence via profiles: ${rows.isNotEmpty}');
      return {'exists': rows.isNotEmpty};
    } catch (e) {
      debugPrint('[AuthRepository] checkUserExistence profiles failed: $e');
    }

    // ── 3. Unknown — treat as new user in the caller ──────────────────
    return null;
  }

  // ─── Phone OTP (disabled) ─────────────────────────────────────────

  static const String kSmsOtpDisabledMessage =
      'SMS and WhatsApp OTP are disabled. Use email verification or sign in with email/password or Google.';

  /// SMS/WhatsApp OTP is not used (policy). Use [sendSignUpEmailOtp] for sign-up.
  Future<OtpChannel> sendOtp(
    String phone, {
    OtpChannel channel = OtpChannel.sms,
  }) async {
    debugPrint('[AuthRepository] sendOtp blocked (phone=$phone).');
    throw Exception(kSmsOtpDisabledMessage);
  }

  /// Prefer storing optional phone via profiles table; updating auth phone triggers SMS flows.
  Future<void> updatePhone(String phone) async {
    throw Exception(
      'Linking phone to Supabase Auth is disabled (avoids SMS OTP). '
      'Save phone in your profile after sign-up, or use email sign-in.',
    );
  }

  /// Verify OTP token (supports sms and phoneChange).
  Future<AuthResponse> verifyOtp(String phone, String token,
      {OtpType type = OtpType.sms}) async {
    try {
      return await _supabase.auth.verifyOTP(
        phone: phone,
        token: token,
        type: type,
      );
    } catch (e) {
      debugPrint('[AuthRepository] Verify OTP ($type) error: $e');
      rethrow;
    }
  }

  // ─── Email Actions (Triggers Designing Templates) ────────────────

  /// Email OTP for sign-up (and passwordless sign-in). Preferred for new accounts.
  Future<void> sendSignUpEmailOtp(String email) async {
    try {
      await _supabase.auth.signInWithOtp(
        email: email.trim(),
        emailRedirectTo: _authRedirectUrl,
        shouldCreateUser: true,
      );
    } catch (e) {
      debugPrint('[AuthRepository] Email sign-up OTP error: $e');
      rethrow;
    }
  }

  /// Verify email OTP (sign-up / magic link flow).
  Future<AuthResponse> verifyEmailOtpCode(String email, String token) async {
    return _supabase.auth.verifyOTP(
      email: email.trim(),
      token: token.trim(),
      type: OtpType.email,
    );
  }

  /// Send Magic Link (One-Click Log In)
  Future<void> sendMagicLink(String email) async {
    try {
      await _supabase.auth.signInWithOtp(
        email: email,
        emailRedirectTo: _authRedirectUrl,
      );
    } catch (e) {
      debugPrint('[AuthRepository] Send Magic Link error: $e');
      rethrow;
    }
  }

  /// Send Password Reset Link
  Future<void> sendPasswordReset(String email) async {
    try {
      await _supabase.auth.resetPasswordForEmail(
        email,
        redirectTo: _authRedirectUrl,
      );
    } catch (e) {
      debugPrint('[AuthRepository] Password Reset error: $e');
      rethrow;
    }
  }

  /// Reauthenticate user for sensitive actions
  Future<void> reauthenticate() async {
    try {
      await _supabase.auth.reauthenticate();
    } catch (e) {
      debugPrint('[AuthRepository] Reauth error: $e');
      rethrow;
    }
  }

  /// Trigger custom Supabase Edge Function for premium emails
  Future<void> triggerEmailEdgeFunction(
      String template, Map<String, dynamic> data) async {
    try {
      await _supabase.functions.invoke(
        'trigger-email',
        body: {
          'template': template,
          'email': currentUser?.email,
          'data': data,
        },
      );
    } catch (e) {
      debugPrint('[AuthRepository] Edge Function trigger error: $e');
      // Non-critical, do not rethrow but log it
    }
  }

  /// Log session info and send security alert.
  Future<void> logUserSession(
    User user, {
    Map<String, dynamic>? deviceInfo,
  }) async {
    try {
      final email = user.email;
      final phone = user.phone ?? user.userMetadata?['phone'] as String?;

      if (phone != null) {
        TwilioService.sendDeviceLoginNotification(phone);
      }

      if (email != null) {
        await triggerEmailEdgeFunction('login_alert', {
          'identifier': email,
          'device': deviceInfo ?? <String, dynamic>{},
          'phone': phone,
          'logged_in_at': DateTime.now().toIso8601String(),
        });
      }
    } catch (e) {
      debugPrint('[AuthRepository] Log session error: $e');
    }
  }

  Future<Map<String, dynamic>> _buildDeviceInfo() async {
    final plugin = DeviceInfoPlugin();

    try {
      if (kIsWeb) {
        final info = await plugin.webBrowserInfo;
        return {
          'platform': 'web',
          'browser': info.browserName.name,
          'userAgent': info.userAgent,
          'device': info.platform,
        };
      }

      switch (defaultTargetPlatform) {
        case TargetPlatform.android:
          final info = await plugin.androidInfo;
          return {
            'platform': 'android',
            'device': info.device,
            'model': info.model,
            'manufacturer': info.manufacturer,
            'androidVersion': info.version.release,
          };
        case TargetPlatform.iOS:
          final info = await plugin.iosInfo;
          return {
            'platform': 'ios',
            'device': info.utsname.machine,
            'model': info.model,
            'systemVersion': info.systemVersion,
            'name': info.name,
          };
        case TargetPlatform.windows:
          final info = await plugin.windowsInfo;
          return {
            'platform': 'windows',
            'device': info.computerName,
            'model': info.productName,
            'buildNumber': info.buildNumber,
          };
        case TargetPlatform.macOS:
          final info = await plugin.macOsInfo;
          return {
            'platform': 'macos',
            'device': info.computerName,
            'model': info.model,
            'osRelease': info.osRelease,
          };
        case TargetPlatform.linux:
          final info = await plugin.linuxInfo;
          return {
            'platform': 'linux',
            'device': info.prettyName,
            'model': info.variant ?? info.name,
            'version': info.version,
          };
        case TargetPlatform.fuchsia:
          return {'platform': 'fuchsia'};
      }
    } catch (e) {
      debugPrint('[AuthRepository] Device info error: $e');
    }

    return {'platform': 'unknown'};
  }

  // ─── Legacy (Aliases for UserCubit) ─────────────────────────────

  Future<OtpChannel> sendPhoneOtp(String phone) async => sendOtp(phone);
  Future<AuthResponse> verifyPhoneOtp(String phone, String token) async =>
      verifyOtp(phone, token);

  // ─── Sign Out ────────────────────────────────────────────────────

  /// Sign out from both Supabase and Google.
  Future<void> signOut() async {
    await _supabase.auth.signOut();
    if (!kIsWeb) {
      try {
        await GoogleSignIn.instance.signOut();
      } catch (_) {
        // Google sign out failure is non-critical
      }
    }
  }
  // ─── Update User Metadata ────────────────────────────────────────

  /// Update user metadata (e.g. Super LeoBook activation, profile data).
  Future<UserResponse> updateUserMetadata(Map<String, dynamic> data) async {
    try {
      return await _supabase.auth.updateUser(
        UserAttributes(data: data),
      );
    } catch (e) {
      debugPrint('[AuthRepository] Update metadata error: $e');
      rethrow;
    }
  }

}
