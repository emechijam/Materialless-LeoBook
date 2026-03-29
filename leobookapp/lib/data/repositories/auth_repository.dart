// auth_repository.dart: Supabase authentication — Google, Phone OTP, Email.
// Part of LeoBook App — Repositories
//
// Classes: AuthRepository

import 'package:flutter/foundation.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:google_sign_in/google_sign_in.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

class AuthRepository {
  final SupabaseClient _supabase = Supabase.instance.client;

  /// Stream of Supabase Auth state changes
  Stream<AuthState> get authStateChanges => _supabase.auth.onAuthStateChange;

  /// Get current user
  User? get currentUser => _supabase.auth.currentUser;

  /// Whether a user is currently signed in
  bool get isSignedIn => currentUser != null;

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
        redirectTo: kIsWeb ? Uri.base.origin : null,
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

  /// Mobile: Native google_sign_in → ID token → Supabase exchange.
  Future<AuthResponse> _signInWithGoogleNative() async {
    try {
      final webClientId = dotenv.env['GOOGLE_WEB_CLIENT_ID'] ?? '';
      final iosClientId = dotenv.env['GOOGLE_IOS_CLIENT_ID'] ?? '';

      final signIn = GoogleSignIn.instance;
      await signIn.initialize(
        clientId: iosClientId.isEmpty ? null : iosClientId,
        serverClientId: webClientId.isEmpty ? null : webClientId,
      );

      final googleUser = await signIn.authenticate();

      final googleAuth = googleUser.authentication;
      final idToken = googleAuth.idToken;

      if (idToken == null) {
        throw 'No ID Token found.';
      }

      return await _supabase.auth.signInWithIdToken(
        provider: OAuthProvider.google,
        idToken: idToken,
      );
    } catch (e) {
      debugPrint('[AuthRepository] Google Sign-In (native) error: $e');
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
      );
    } catch (e) {
      debugPrint('[AuthRepository] Email sign-up error: $e');
      rethrow;
    }
  }

  /// Sign in with existing email + password.
  Future<AuthResponse> signInWithEmail(String email, String password) async {
    try {
      return await _supabase.auth.signInWithPassword(
        email: email,
        password: password,
      );
    } catch (e) {
      debugPrint('[AuthRepository] Email sign-in error: $e');
      rethrow;
    }
  }

  // ─── Phone OTP ───────────────────────────────────────────────────

  /// Send OTP via WhatsApp. Phone format: +234XXXXXXXXXX
  Future<void> sendOtp(String phone) async {
    try {
      await _supabase.auth.signInWithOtp(
        phone: phone,
        channel: OtpChannel.whatsapp,
      );
    } catch (e) {
      debugPrint('[AuthRepository] Send OTP error: $e');
      rethrow;
    }
  }

  /// Verify OTP token for phone sign-in via SMS.
  Future<AuthResponse> verifyOtp(String phone, String token) async {
    try {
      return await _supabase.auth.verifyOTP(
        phone: phone,
        token: token,
        type: OtpType.sms,
      );
    } catch (e) {
      debugPrint('[AuthRepository] Verify OTP error: $e');
      rethrow;
    }
  }

  // (Legacy) Send simple OTP to phone number
  Future<void> sendPhoneOtp(String phone) async {
    try {
      await _supabase.auth.signInWithOtp(phone: phone);
    } catch (e) {
      debugPrint('[AuthRepository] Send OTP error: $e');
      rethrow;
    }
  }

  // (Legacy) Verify OTP token for phone sign-in
  Future<AuthResponse> verifyPhoneOtp(String phone, String token) async {
    try {
      return await _supabase.auth.verifyOTP(
        phone: phone,
        token: token,
        type: OtpType.sms,
      );
    } catch (e) {
      debugPrint('[AuthRepository] Verify OTP error: $e');
      rethrow;
    }
  }

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

