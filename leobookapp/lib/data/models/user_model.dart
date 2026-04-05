// user_model.dart: User data model with tier-based access control.
// Part of LeoBook App — Data Models
//
// Classes: UserModel

import 'package:supabase_flutter/supabase_flutter.dart' show User;

enum UserTier { unregistered, lite, pro }

class UserModel {
  final String id;
  final String? email;
  final String? phone;
  final String? displayName;
  final UserTier tier;
  final bool isEmailVerified;
  final bool isPhoneVerified;
  final bool isBiometricsEnabled;
  final bool isSuperLeoBook; // UI-level subscription flag
  final bool isProfileComplete;

  /// Google profile photo URL (null for non-Google sign-ins).
  final String? avatarUrl;

  // ─── Subscription Fields ─────────────────────────────────────
  /// Payment provider: 'paystack', 'stripe', 'trial', or null
  final String? subscriptionProvider;

  /// Lifecycle status: 'active', 'expired', 'cancelled', or 'none'
  final String subscriptionStatus;

  /// UTC timestamp when the current billing period ends
  final DateTime? subscriptionExpiresAt;

  /// Payment provider's transaction/subscription reference ID
  final String? subscriptionReference;

  const UserModel({
    required this.id,
    this.email,
    this.phone,
    this.displayName,
    this.tier = UserTier.unregistered,
    this.isEmailVerified = false,
    this.isPhoneVerified = false,
    this.isBiometricsEnabled = false,
    this.isSuperLeoBook = false,
    this.isProfileComplete = false,
    this.avatarUrl,
    this.subscriptionProvider,
    this.subscriptionStatus = 'none',
    this.subscriptionExpiresAt,
    this.subscriptionReference,
  });

  // ─── Access Control ──────────────────────────────────────────────
  // Guest = unregistered. Free = signed in, not Super. Super = paid / trial flag.

  bool get isGuest => tier == UserTier.unregistered && id == 'guest';
  bool get isAuthenticated => id != 'guest';

  /// Rule Engine Studio: CRUD engines (guest: no).
  bool get canUseRuleEngine => isAuthenticated;

  /// Super LeoBook: queue RL training jobs, unlimited engines.
  bool get canTrainRl => isSuperLeoBook;

  /// Max custom engines (excluding built-in `default`). Null means unlimited.
  int? get maxCustomRuleEngines => isSuperLeoBook ? null : 5;

  bool get canCreateCustomRules => canUseRuleEngine;
  bool get canRunBacktests => canUseRuleEngine;

  /// Full Chapter 2 automation (booking, withdrawal orchestration).
  bool get canAutomateBetting => isSuperLeoBook;

  /// Chapter 2 UI (manual tools / visibility) for registered users.
  bool get canAccessChapter2Ui => isAuthenticated;

  /// Legacy: full Chapter 2 automation (maps to Super).
  bool get canAccessChapter2 => canAutomateBetting;

  /// View Project Stairway dashboard (registered).
  bool get canViewStairway => isAuthenticated;

  bool get isPro => tier == UserTier.pro || isSuperLeoBook;

  // ─── Factories ───────────────────────────────────────────────────

  factory UserModel.guest() {
    return const UserModel(id: 'guest', tier: UserTier.unregistered);
  }

  factory UserModel.lite({required String id, String? email, String? phone}) {
    return UserModel(
      id: id,
      email: email,
      phone: phone,
      tier: UserTier.lite,
      isEmailVerified: email != null,
    );
  }

  factory UserModel.pro({required String id, String? email, String? phone}) {
    return UserModel(
      id: id,
      email: email,
      phone: phone,
      tier: UserTier.pro,
      isEmailVerified: email != null,
      isSuperLeoBook: true,
    );
  }

  /// Map a Supabase [User] to [UserModel].
  factory UserModel.fromSupabaseUser(User user) {
    final meta = user.userMetadata ?? {};
    
    // Check Super LeoBook 15-day trial status
    bool isSuperLeoBook = false;
    UserTier currentTier = UserTier.lite; // Default for authenticated users
    
    if (meta['super_leobook_activated_at'] != null) {
      final activatedStr = meta['super_leobook_activated_at'].toString();
      final activatedDate = DateTime.tryParse(activatedStr);
      if (activatedDate != null) {
        final daysSinceActivation = DateTime.now().difference(activatedDate).inDays;
        if (daysSinceActivation <= 15) {
          isSuperLeoBook = true;
          currentTier = UserTier.pro;
        }
      }
    }

    final isProfileComplete = meta['profile_completed'] == true;
    final isPhoneVerified = meta['phone_verified'] == true || user.phone != null;
    final isBiometricsEnabled = meta['biometrics_enabled'] == true;

    return UserModel(
      id: user.id,
      email: user.email,
      phone: user.phone,
      displayName: meta['full_name'] as String? ??
          meta['name'] as String? ??
          meta['username'] as String? ??
          user.email?.split('@').first,
      tier: currentTier,
      isEmailVerified: user.emailConfirmedAt != null,
      isPhoneVerified: isPhoneVerified,
      isBiometricsEnabled: isBiometricsEnabled,
      isSuperLeoBook: isSuperLeoBook,
      isProfileComplete: isProfileComplete,
      avatarUrl: meta['avatar_url'] as String? ?? meta['picture'] as String?,
    );
  }

  /// Return a copy with modified fields.
  UserModel copyWith({
    bool? isSuperLeoBook,
    UserTier? tier,
    bool? isProfileComplete,
    bool? isPhoneVerified,
    bool? isBiometricsEnabled,
    String? avatarUrl,
  }) {
    return UserModel(
      id: id,
      email: email,
      phone: phone,
      displayName: displayName,
      tier: tier ?? this.tier,
      isEmailVerified: isEmailVerified,
      isPhoneVerified: isPhoneVerified ?? this.isPhoneVerified,
      isBiometricsEnabled: isBiometricsEnabled ?? this.isBiometricsEnabled,
      isSuperLeoBook: isSuperLeoBook ?? this.isSuperLeoBook,
      isProfileComplete: isProfileComplete ?? this.isProfileComplete,
      avatarUrl: avatarUrl ?? this.avatarUrl,
    );
  }
}
