// user_cubit.dart: Real Supabase auth state management.
// Part of LeoBook App - State Management (Cubit)
//
// Classes: UserCubit

import 'dart:async';
import 'package:bloc/bloc.dart';
import 'package:equatable/equatable.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:local_auth/local_auth.dart';
import 'package:supabase_flutter/supabase_flutter.dart'
    show AuthChangeEvent, AuthState, OtpType;
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

  void _restoreSession() async {
    final user = _authRepo.currentUser;
    if (user != null) {
      final model = UserModel.fromSupabaseUser(user);
      final hasCredentials = await _secureStorage.containsKey(key: 'leo_id');
      if (hasCredentials && model.isBiometricsEnabled) {
        emit(UserBiometricPrompt(user: model));
        return;
      }

      _emitCorrectState(model);
    }
  }

  void _emitCorrectState(UserModel model) {
    if (!model.isProfileComplete) {
      emit(UserProfileIncomplete(user: model));
    } else if (!model.isPhoneVerified) {
      emit(UserNeedsVerification(user: model, phone: model.phone ?? ''));
    } else {
      emit(UserAuthenticated(user: model));
    }
  }

  Future<bool> checkUserStatus(String identifier) async {
    emit(UserLoading(user: state.user));
    try {
      final userData = await _authRepo.checkUserExistence(identifier);
      emit(UserInitial(user: state.user));
      return userData?['exists'] == true;
    } catch (_) {
      emit(UserInitial(user: state.user));
      return false;
    }
  }

  Future<void> signInWithPassword(String identifier, String password) async {
    emit(UserLoading(user: state.user));
    try {
      final response = await _authRepo.signInWithPassword(identifier, password);
      if (response.user != null) {
        final model = UserModel.fromSupabaseUser(response.user!);
        if (model.isBiometricsEnabled) {
          await _secureStorage.write(key: 'leo_id', value: identifier);
          await _secureStorage.write(key: 'leo_pw', value: password);
        }
        _emitCorrectState(model);
      } else {
        emit(UserError(
          user: state.user,
          message: 'Incorrect email/phone or password.',
        ));
      }
    } catch (e) {
      emit(UserError(
        user: state.user,
        message: AuthRepository.mapAuthError(
          e,
          fallbackMessage: 'Incorrect email/phone or password.',
        ),
      ));
    }
  }

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
      emit(UserError(
        user: state.user,
        message: AuthRepository.mapAuthError(
          e,
          fallbackMessage: 'Biometric sign-in failed. Please try again.',
        ),
      ));
      emit(UserInitial(user: state.user));
    }
  }

  Future<void> enableBiometrics(bool enabled, {String? password}) async {
    final user = state.user;
    if (user.id == 'guest') return;

    try {
      if (enabled && (password == null || password.trim().isEmpty)) {
        emit(UserError(
          user: user,
          message: 'Enter your current password to enable biometrics.',
        ));
        return;
      }

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
      _emitCorrectState(updated);
    } catch (e) {
      emit(UserError(
        user: user,
        message: AuthRepository.mapAuthError(
          e,
          fallbackMessage: enabled
              ? 'Failed to enable biometrics.'
              : 'Failed to update biometrics.',
        ),
      ));
    }
  }

  Future<void> signInWithGoogle() async {
    emit(UserLoading(user: state.user));
    try {
      final response = await _authRepo.signInWithGoogle();
      if (response.user != null) {
        _emitCorrectState(UserModel.fromSupabaseUser(response.user!));
      } else if (kIsWeb) {
        emit(UserInitial(user: state.user));
      } else {
        emit(UserError(user: state.user, message: 'Google sign-in failed.'));
      }
    } catch (e) {
      emit(UserError(
        user: state.user,
        message: AuthRepository.mapAuthError(
          e,
          fallbackMessage: 'Google sign-in failed. Please try again.',
        ),
      ));
    }
  }

  Future<void> sendPhoneOtp(String phone) async {
    emit(UserLoading(user: state.user));
    try {
      await _authRepo.sendPhoneOtp(phone);
      emit(UserInitial(user: state.user));
    } catch (e) {
      emit(UserError(
        user: state.user,
        message: AuthRepository.mapAuthError(
          e,
          fallbackMessage: 'Unable to send the verification code right now.',
        ),
      ));
    }
  }

  Future<void> verifyPhoneOtp(
    String phone,
    String token, {
    bool isPhoneChange = false,
  }) async {
    emit(UserLoading(user: state.user));
    try {
      final response = await _authRepo.verifyOtp(
        phone,
        token,
        type: isPhoneChange ? OtpType.phoneChange : OtpType.sms,
      );
      if (response.user != null) {
        _emitCorrectState(UserModel.fromSupabaseUser(response.user!));
      } else {
        emit(UserError(
          user: state.user,
          message: 'Invalid verification code. Please try again.',
        ));
      }
    } catch (e) {
      emit(UserError(
        user: state.user,
        message: AuthRepository.mapAuthError(
          e,
          fallbackMessage: 'Invalid verification code. Please try again.',
        ),
      ));
    }
  }

  Future<void> signUpWithEmail(String email, String password) async {
    emit(UserLoading(user: state.user));
    try {
      final response = await _authRepo.signUpWithEmail(email, password);
      if (response.session == null) {
        emit(UserInitial(user: state.user));
      } else if (response.user != null) {
        _emitCorrectState(UserModel.fromSupabaseUser(response.user!));
      } else {
        emit(UserInitial(user: state.user));
      }
    } catch (e) {
      emit(UserError(
        user: state.user,
        message: AuthRepository.mapAuthError(
          e,
          fallbackMessage: 'Unable to create your account right now.',
        ),
      ));
    }
  }

  Future<void> signInWithEmail(String email, String password) async {
    emit(UserLoading(user: state.user));
    try {
      final response = await _authRepo.signInWithEmail(email, password);
      if (response.user != null) {
        final model = UserModel.fromSupabaseUser(response.user!);
        if (model.isProfileComplete &&
            model.isPhoneVerified &&
            model.phone != null) {
          TwilioService.sendDeviceLoginNotification(model.phone!);
        }
        _emitCorrectState(model);
      } else {
        emit(UserError(
          user: state.user,
          message: 'Incorrect email/phone or password.',
        ));
      }
    } catch (e) {
      emit(UserError(
        user: state.user,
        message: AuthRepository.mapAuthError(
          e,
          fallbackMessage: 'Incorrect email/phone or password.',
        ),
      ));
    }
  }

  Future<void> sendPasswordReset(String email) async {
    emit(UserLoading(user: state.user));
    try {
      await _authRepo.sendPasswordReset(email);
      emit(UserInitial(user: state.user));
    } catch (e) {
      emit(UserError(
        user: state.user,
        message: AuthRepository.mapAuthError(
          e,
          fallbackMessage: 'Unable to send a reset link right now.',
        ),
      ));
    }
  }

  Future<void> sendMagicLink(String email) async {
    emit(UserLoading(user: state.user));
    try {
      await _authRepo.sendMagicLink(email);
      emit(UserInitial(user: state.user));
    } catch (e) {
      emit(UserError(
        user: state.user,
        message: AuthRepository.mapAuthError(
          e,
          fallbackMessage: 'Unable to send a magic link right now.',
        ),
      ));
    }
  }

  Future<void> refreshCurrentUserState() async {
    final user = _authRepo.currentUser;
    if (user == null) {
      emit(const UserInitial(user: UserModel(id: 'guest')));
      return;
    }

    _emitCorrectState(UserModel.fromSupabaseUser(user));
  }

  void dismissBiometricPrompt() {
    emit(UserInitial(user: state.user));
  }

  void skipAsGuest() {
    emit(const UserInitial(user: UserModel(id: 'guest')));
  }

  void upgradeToSuperLeoBook() {
    final activatedAt = DateTime.now().toIso8601String();

    _authRepo.updateUserMetadata({
      'super_leobook_activated_at': activatedAt,
    }).then((_) {
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

  /// Activate a paid subscription via [provider] ('paystack' or 'stripe').
  /// [reference] is the payment provider's transaction/subscription ID.
  /// Stub: persists metadata to Supabase and upgrades tier to Pro.
  void activateSubscription({required String provider, required String reference}) {
    final now = DateTime.now();
    final expiresAt = DateTime(now.year, now.month + 1, now.day).toIso8601String();

    _authRepo.updateUserMetadata({
      'subscription_provider': provider,
      'subscription_status': 'active',
      'subscription_expires_at': expiresAt,
      'subscription_reference': reference,
    }).then((_) {
      _authRepo.triggerEmailEdgeFunction('subscription_active', {
        'provider': provider,
        'reference': reference,
        'expires_at': expiresAt,
      });
    }).catchError((e) {
      debugPrint('[UserCubit] Failed to persist subscription: $e');
    });

    final upgraded = state.user.copyWith(
      isSuperLeoBook: true,
      tier: UserTier.pro,
    );
    emit(UserAuthenticated(user: upgraded));
  }

  Future<void> logout() async {
    try {
      await _authRepo.signOut();
    } catch (e) {
      debugPrint('[UserCubit] Sign out error: $e');
    }
    emit(const UserInitial(user: UserModel(id: 'guest')));
  }

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
