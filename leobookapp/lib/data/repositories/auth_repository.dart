// auth_repository.dart: Supabase authentication — Google Sign-In + Phone OTP.
// Part of LeoBook App — Repositories
//
// Classes: AuthRepository

import 'package:google_sign_in/google_sign_in.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import 'package:flutter/foundation.dart';

class AuthRepository {
  final SupabaseClient _supabase = Supabase.instance.client;

  /// Stream of Supabase Auth state changes
  Stream<AuthState> get authStateChanges => _supabase.auth.onAuthStateChange;

  /// Get current user
  User? get currentUser => _supabase.auth.currentUser;

  /// Whether a user is currently signed in
  bool get isSignedIn => currentUser != null;

  // ─── Google Sign-In ──────────────────────────────────────────────

  /// Sign in with Google via native flow + Supabase ID token exchange.
  Future<AuthResponse> signInWithGoogle() async {
    try {
      const webClientId = String.fromEnvironment('GOOGLE_WEB_CLIENT_ID');
      const iosClientId = String.fromEnvironment('GOOGLE_IOS_CLIENT_ID');

      final GoogleSignIn googleSignIn = GoogleSignIn(
        clientId: iosClientId.isEmpty ? null : iosClientId,
        serverClientId: webClientId.isEmpty ? null : webClientId,
      );

      final googleUser = await googleSignIn.signIn();
      if (googleUser == null) {
        throw 'Sign in aborted by user.';
      }

      final googleAuth = await googleUser.authentication;
      final accessToken = googleAuth.accessToken;
      final idToken = googleAuth.idToken;

      if (idToken == null) {
        throw 'No ID Token found.';
      }

      return await _supabase.auth.signInWithIdToken(
        provider: OAuthProvider.google,
        idToken: idToken,
        accessToken: accessToken,
      );
    } catch (e) {
      debugPrint('[AuthRepository] Google Sign-In error: $e');
      rethrow;
    }
  }

  // ─── Phone OTP ───────────────────────────────────────────────────

  /// Send OTP to phone number. Phone format: +234XXXXXXXXXX
  Future<void> sendPhoneOtp(String phone) async {
    try {
      await _supabase.auth.signInWithOtp(phone: phone);
    } catch (e) {
      debugPrint('[AuthRepository] Send OTP error: $e');
      rethrow;
    }
  }

  /// Verify OTP token for phone sign-in.
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
    try {
      final GoogleSignIn googleSignIn = GoogleSignIn();
      if (await googleSignIn.isSignedIn()) {
        await googleSignIn.signOut();
      }
    } catch (_) {
      // Google sign out failure is non-critical
    }
  }
}
