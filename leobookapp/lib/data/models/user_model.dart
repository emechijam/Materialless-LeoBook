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
  final bool isSuperLeoBook; // UI-level subscription flag

  const UserModel({
    required this.id,
    this.email,
    this.phone,
    this.displayName,
    this.tier = UserTier.unregistered,
    this.isEmailVerified = false,
    this.isSuperLeoBook = false,
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
    return UserModel(
      id: user.id,
      email: user.email,
      phone: user.phone,
      displayName: meta['full_name'] as String? ??
          meta['name'] as String? ??
          user.email?.split('@').first,
      tier: UserTier.lite, // Default tier for authenticated users
      isEmailVerified: user.emailConfirmedAt != null,
    );
  }

  /// Return a copy with Super LeoBook subscription toggled.
  UserModel copyWith({bool? isSuperLeoBook, UserTier? tier}) {
    return UserModel(
      id: id,
      email: email,
      phone: phone,
      displayName: displayName,
      tier: tier ?? this.tier,
      isEmailVerified: isEmailVerified,
      isSuperLeoBook: isSuperLeoBook ?? this.isSuperLeoBook,
    );
  }
}
