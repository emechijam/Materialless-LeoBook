// secure_storage.dart: Encrypted storage for Supabase session tokens.
// Part of LeoBook App — Core Services

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

/// Custom storage for Supabase that using [FlutterSecureStorage] 
/// to encrypt and securely store auth tokens.
class SecureSupabaseStorage extends LocalStorage {
  final _storage = const FlutterSecureStorage();
  static const _tokenKey = 'supabase.auth.token';

  @override
  Future<void> initialize() async {}

  @override
  Future<String?> accessToken() async {
    return await _storage.read(key: _tokenKey);
  }

  @override
  Future<bool> hasAccessToken() async {
    final token = await accessToken();
    return token != null;
  }

  @override
  Future<void> persistSession(String session) async {
    await _storage.write(key: _tokenKey, value: session);
  }

  @override
  Future<void> removePersistedSession() async {
    await _storage.delete(key: _tokenKey);
  }
}
