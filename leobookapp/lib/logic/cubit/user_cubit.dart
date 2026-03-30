// user_cubit.dart: Real Supabase auth state management.
// Part of LeoBook App — State Management (Cubit)
//
// Classes: UserCubit

import 'dart:async';
import 'package:bloc/bloc.dart';
import 'package:equatable/equatable.dart';
import 'package:flutter/foundation.dart';
import 'package:supabase_flutter/supabase_flutter.dart' show AuthState, AuthChangeEvent;
import 'package:local_auth/local_auth.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import '../../data/models/user_model.dart';
import '../../data/repositories/auth_repository.dart';
import '../../data/services/twilio_service.dart';

part 'user_state.dart';

class UserCubit extends Cubit<UserState> {
  final AuthRepository _authRepo;
  final LocalAuthentication _localAuth = LocalAuthentication();
  final FlutterSecureStorage _secureStorage = const FlutterSecureStorage();
  StreamSubscription<AuthState>? _authSub;

  UserCubit(this._authRepo)
      : super(const UserInitial(user: UserModel(id: 'guest'))) {
    _listenToAuthChanges();
    _restoreSession();
  }

  // ─── Auth Listeners ──────────────────────────────────────────────

  void _listenToAuthChanges() {
    _authSub = _authRepo.authStateChanges.listen((authState) {
      final event = authState.event;
      if (event == AuthChangeEvent.signedIn) {
        final user = _authRepo.currentUser;
        if (user != null) {
          _emitCorrectState(UserModel.fromSupabaseUser(user));
        }
      } else if (event == AuthChangeEvent.signedOut) {
        emit(const UserInitial(user: UserModel(id: 'guest')));
      }
    });
  }

  /// Check if there's an existing session on cold start.
  void _restoreSession() async {
    final user = _authRepo.currentUser;
    if (user != null) {
      final model = UserModel.fromSupabaseUser(user);
      
      // Check for Biometrics on cold start if previously enabled
      final hasCredentials = await _secureStorage.containsKey(key: 'leo_id');
      if (hasCredentials && model.isBiometricsEnabled) {
        emit(UserBiometricPrompt(user: model));
        return;
      }

      _emitCorrectState(model);
    }
  }

  /// Centralized state emission logic for LeoBook gating rules.
  void _emitCorrectState(UserModel model) {
    if (!model.isProfileComplete) {
      emit(UserProfileIncomplete(user: model));
    } else if (!model.isPhoneVerified) {
      emit(UserNeedsVerification(user: model, phone: model.phone ?? ''));
    } else {
      emit(UserAuthenticated(user: model));
    }
  }

  // ─── Smart Auth (Password vs OTP) ───────────────────────────────

  /// Determine if we should show the Password screen or send an OTP.
  Future<bool> checkUserStatus(String identifier) async {
    emit(UserLoading(user: state.user));
    try {
      final userData = await _authRepo.checkUserExistence(identifier);
      emit(UserInitial(user: state.user));
      return userData != null; // True if user exists (should show Password screen)
    } catch (e) {
      emit(UserInitial(user: state.user));
      return false; // Safely default to OTP/Signup flow
    }
  }

  Future<void> signInWithPassword(String identifier, String password) async {
    emit(UserLoading(user: state.user));
    try {
      final response = await _authRepo.signInWithPassword(identifier, password);
      if (response.user != null) {
        final model = UserModel.fromSupabaseUser(response.user!);
        
        // Save for biometrics if enabled
        if (model.isBiometricsEnabled) {
          await _secureStorage.write(key: 'leo_id', value: identifier);
          await _secureStorage.write(key: 'leo_pw', value: password);
        }

        _emitCorrectState(model);
      } else {
        emit(UserError(user: state.user, message: 'Invalid credentials.'));
      }
    } catch (e) {
      emit(UserError(user: state.user, message: e.toString()));
    }
  }

  // ─── Biometrics ──────────────────────────────────────────────────

  Future<void> biometricSignIn() async {
    final identifier = await _secureStorage.read(key: 'leo_id');
    final password = await _secureStorage.read(key: 'leo_pw');

    if (identifier == null || password == null) {
      emit(UserInitial(user: state.user));
      return;
    }

    try {
      final authenticated = await _localAuth.authenticate(
        localizedReason: 'Sign in to LeoBook',
        options: const AuthenticationOptions(stickyAuth: true),
      );

      if (authenticated) {
        await signInWithPassword(identifier, password);
      } else {
        emit(UserInitial(user: state.user));
      }
    } catch (e) {
      emit(UserError(user: state.user, message: 'Biometric error: $e'));
      emit(UserInitial(user: state.user));
    }
  }

  Future<void> enableBiometrics(bool enabled, {String? password}) async {
    final user = state.user;
    if (user.id == 'guest') return;

    try {
      await _authRepo.updateUserMetadata({'biometrics_enabled': enabled});
      
      if (enabled && password != null) {
        final id = user.email ?? user.phone;
        if (id != null) {
          await _secureStorage.write(key: 'leo_id', value: id);
          await _secureStorage.write(key: 'leo_pw', value: password);
        }
      } else {
        await _secureStorage.delete(key: 'leo_id');
        await _secureStorage.delete(key: 'leo_pw');
      }

      final updated = user.copyWith(isBiometricsEnabled: enabled);
      emit(UserAuthenticated(user: updated));
    } catch (e) {
      emit(UserError(user: user, message: 'Failed to update biometrics.'));
    }
  }

  // ─── Google Sign-In ──────────────────────────────────────────────

  Future<void> signInWithGoogle() async {
    emit(UserLoading(user: state.user));
    try {
      final response = await _authRepo.signInWithGoogle();
      if (response.user != null) {
        _emitCorrectState(UserModel.fromSupabaseUser(response.user!));
      } else if (kIsWeb) {
        // On web, OAuth redirects the page — session arrives via authStateChanges.
        // Reset to initial so the UI isn't stuck on loading.
        emit(UserInitial(user: state.user));
      } else {
        emit(UserError(user: state.user, message: 'Google sign-in failed.'));
      }
    } catch (e) {
      emit(UserError(
        user: state.user,
        message: e.toString(),
      ));
    }
  }

  // ─── Phone OTP ───────────────────────────────────────────────────

  Future<void> sendPhoneOtp(String phone) async {
    emit(UserLoading(user: state.user));
    try {
      await _authRepo.sendPhoneOtp(phone);
      // Stay in loading — the UI will navigate to OTP screen
      emit(UserInitial(user: state.user));
    } catch (e) {
      emit(UserError(
        user: state.user,
        message: 'Failed to send OTP: ${e.toString()}',
      ));
    }
  }

  Future<void> verifyPhoneOtp(String phone, String token) async {
    emit(UserLoading(user: state.user));
    try {
      final response = await _authRepo.verifyPhoneOtp(phone, token);
      if (response.user != null) {
        emit(UserAuthenticated(
          user: UserModel.fromSupabaseUser(response.user!),
        ));
      } else {
        emit(UserError(user: state.user, message: 'OTP verification failed.'));
      }
    } catch (e) {
      emit(UserError(
        user: state.user,
        message: 'Invalid OTP: ${e.toString()}',
      ));
    }
  }

  // ─── Email Auth ──────────────────────────────────────────────────

  Future<void> signUpWithEmail(String email, String password) async {
    emit(UserLoading(user: state.user));
    try {
      final response = await _authRepo.signUpWithEmail(email, password);
      if (response.user != null) {
        emit(UserAuthenticated(
          user: UserModel.fromSupabaseUser(response.user!),
        ));
      } else {
        // Email confirmation required — user registered but not yet verified
        emit(UserInitial(user: state.user));
      }
    } catch (e) {
      emit(UserError(
        user: state.user,
        message: 'Sign-up failed: ${e.toString()}',
      ));
    }
  }

  Future<void> signInWithEmail(String email, String password) async {
    emit(UserLoading(user: state.user));
    try {
      final response = await _authRepo.signInWithEmail(email, password);
      if (response.user != null) {
        final model = UserModel.fromSupabaseUser(response.user!);
        if (model.isProfileComplete) {
          // Send notification if phone exists
          if (model.phone != null) {
            TwilioService.sendDeviceLoginNotification(model.phone!);
          }
          emit(UserAuthenticated(user: model));
        } else {
          emit(UserProfileIncomplete(user: model));
        }
      } else {
        emit(UserError(user: state.user, message: 'Email sign-in failed.'));
      }
    } catch (e) {
      emit(UserError(user: state.user, message: e.toString()));
    }
  }

  Future<void> sendPasswordReset(String email) async {
    try {
      await _authRepo.sendPasswordReset(email);
    } catch (e) {
      emit(UserError(user: state.user, message: 'Reset failed: $e'));
    }
  }

  Future<void> sendMagicLink(String email) async {
    emit(UserLoading(user: state.user));
    try {
      await _authRepo.sendMagicLink(email);
      emit(UserInitial(user: state.user));
    } catch (e) {
      emit(UserError(user: state.user, message: 'Magic link failed: $e'));
    }
  }

  // ─── Skip (Guest) ───────────────────────────────────────────────

  void skipAsGuest() {
    emit(const UserInitial(user: UserModel(id: 'guest')));
  }

  // ─── Super LeoBook (Subscription toggle with persistence) ───────

  void upgradeToSuperLeoBook() {
    final activatedAt = DateTime.now().toIso8601String();
    
    // Save to Supabase metadata in background so it persists across sessions
    _authRepo.updateUserMetadata({
      'super_leobook_activated_at': activatedAt,
    }).then((_) {
      // TRIGGER EMAIL: Super LeoBook Activated
      _authRepo.triggerEmailEdgeFunction('subscription_active', {
        'activation_date': activatedAt,
      });
    }).catchError((e) {
      debugPrint('[UserCubit] Failed to persist Super LeoBook activation: $e');
    });

    final upgraded = state.user.copyWith(
      isSuperLeoBook: true,
      tier: UserTier.pro,
    );
    emit(UserAuthenticated(user: upgraded));
  }

  void cancelSuperLeoBook() {
    // Clear from Supabase metadata
    _authRepo.updateUserMetadata({
      'super_leobook_activated_at': null,
    }).catchError((e) {
      debugPrint('[UserCubit] Failed to clear Super LeoBook activation: $e');
      throw e;
    });

    final downgraded = state.user.copyWith(
      isSuperLeoBook: false,
      tier: UserTier.lite,
    );
    emit(UserAuthenticated(user: downgraded));
  }

  // ─── Logout ──────────────────────────────────────────────────────

  Future<void> logout() async {
    try {
      await _authRepo.signOut();
    } catch (e) {
      debugPrint('[UserCubit] Sign out error: $e');
    }
    emit(const UserInitial(user: UserModel(id: 'guest')));
  }

  // ─── Legacy (test helpers) ───────────────────────────────────────

  void loginAsLite() {
    emit(UserAuthenticated(
      user: UserModel.lite(id: 'demo_lite', email: 'lite@leobook.com'),
    ));
  }

  void loginAsPro() {
    emit(UserAuthenticated(
      user: UserModel.pro(id: 'demo_pro', email: 'pro@leobook.com'),
    ));
  }

  void toggleTier(UserTier tier) {
    if (tier == UserTier.lite) {
      loginAsLite();
    } else if (tier == UserTier.pro) {
      loginAsPro();
    } else {
      logout();
    }
  }

  @override
  Future<void> close() {
    _authSub?.cancel();
    return super.close();
  }
}
