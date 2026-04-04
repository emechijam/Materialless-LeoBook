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
    this.subscriptionProvider,
    this.subscriptionStatus = 'none',
    this.subscriptionExpiresAt,
    this.subscriptionReference,
  });

  // ─── Access Control ──────────────────────────────────────────────

  bool get canCreateCustomRules =>
      tier == UserTier.lite || tier == UserTier.pro;
  bool get canRunBacktests => tier == UserTier.lite || tier == UserTier.pro;
  bool get canAutomateBetting => tier == UserTier.pro;
  bool get canAccessChapter2 => tier == UserTier.pro;
  bool get isPro => tier == UserTier.pro || isSuperLeoBook;
  bool get isGuest => tier == UserTier.unregistered && id == 'guest';
  bool get isAuthenticated => id != 'guest';

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
    );
  }

  /// Return a copy with modified fields.
  UserModel copyWith({
    bool? isSuperLeoBook, 
    UserTier? tier,
    bool? isProfileComplete,
    bool? isPhoneVerified,
    bool? isBiometricsEnabled,
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
    );
  }
}
