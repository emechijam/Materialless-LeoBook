// user_profile_screen.dart: Full user profile page.
// Part of LeoBook App — Screens
//
// Sections:
//   • Profile header (Google avatar / initials, name, email, phone, badges)
//   • Appearance (System / Light / Dark with persistence)
//   • Device fingerprint (auto-extracted, read-only, locked)
//   • Football.com vault (phone + password + withdrawal PIN, biometric-gated reveal)

import 'dart:io';

import 'package:cached_network_image/cached_network_image.dart';
import 'package:device_info_plus/device_info_plus.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:local_auth/local_auth.dart';

import 'package:leobookapp/core/constants/app_colors.dart';
import 'package:leobookapp/core/theme/theme_cubit.dart';
import 'package:leobookapp/logic/cubit/user_cubit.dart';

class UserProfileScreen extends StatefulWidget {
  const UserProfileScreen({super.key});

  @override
  State<UserProfileScreen> createState() => _UserProfileScreenState();
}

class _UserProfileScreenState extends State<UserProfileScreen> {
  static const _storage = FlutterSecureStorage();
  static const _kFbPhone = 'fb_cred_phone';
  static const _kFbPass = 'fb_cred_password';
  static const _kFbPin = 'fb_cred_pin';
  static const _kFbSaved = 'fb_creds_saved';

  // Device fingerprint
  String _deviceModel = '—';
  String _osVersion = '—';
  String _platform = '—';

  // Football.com vault state
  final _fbPhoneCtrl = TextEditingController();
  final _fbPassCtrl = TextEditingController();
  final _fbPinCtrl = TextEditingController();
  bool _fbAgreed = false;
  bool _fbSaved = false;
  bool _fbSaving = false;
  bool _fbRevealed = false;
  bool _fbRevealLoading = false;

  @override
  void initState() {
    super.initState();
    _loadDeviceInfo();
    _loadFbCredStatus();
  }

  @override
  void dispose() {
    _fbPhoneCtrl.dispose();
    _fbPassCtrl.dispose();
    _fbPinCtrl.dispose();
    super.dispose();
  }

  // ─── Device Info ────────────────────────────────────────────────

  Future<void> _loadDeviceInfo() async {
    try {
      final plugin = DeviceInfoPlugin();
      if (kIsWeb) {
        final info = await plugin.webBrowserInfo;
        setState(() {
          _platform = 'Web';
          _deviceModel = info.browserName.name;
          _osVersion = info.platform ?? '—';
        });
      } else if (Platform.isAndroid) {
        final info = await plugin.androidInfo;
        setState(() {
          _platform = 'Android';
          _deviceModel = '${info.manufacturer} ${info.model}';
          _osVersion = 'Android ${info.version.release} (SDK ${info.version.sdkInt})';
        });
      } else if (Platform.isIOS) {
        final info = await plugin.iosInfo;
        setState(() {
          _platform = 'iOS';
          _deviceModel = info.utsname.machine;
          _osVersion = '${info.systemName} ${info.systemVersion}';
        });
      } else {
        setState(() => _platform = defaultTargetPlatform.name);
      }
    } catch (_) {}
  }

  // ─── Football.com Vault ──────────────────────────────────────────

  Future<void> _loadFbCredStatus() async {
    final saved = await _storage.read(key: _kFbSaved);
    if (mounted) setState(() => _fbSaved = saved == 'true');
  }

  Future<void> _saveFbCreds() async {
    final phone = _fbPhoneCtrl.text.trim();
    final pass = _fbPassCtrl.text.trim();
    final pin = _fbPinCtrl.text.trim();

    if (phone.isEmpty || pass.isEmpty || pin.isEmpty) {
      _snack('Fill in all Football.com fields.');
      return;
    }
    if (!_fbAgreed) {
      _snack('Please agree to the terms to continue.');
      return;
    }

    setState(() => _fbSaving = true);
    await _storage.write(key: _kFbPhone, value: phone);
    await _storage.write(key: _kFbPass, value: pass);
    await _storage.write(key: _kFbPin, value: pin);
    await _storage.write(key: _kFbSaved, value: 'true');

    _fbPhoneCtrl.clear();
    _fbPassCtrl.clear();
    _fbPinCtrl.clear();

    if (mounted) {
      setState(() {
        _fbSaved = true;
        _fbSaving = false;
        _fbRevealed = false;
      });
      _snack('Credentials saved securely.', success: true);
    }
  }

  Future<void> _revealFbCreds() async {
    setState(() => _fbRevealLoading = true);
    final auth = LocalAuthentication();
    bool authed = false;
    try {
      final canCheck = await auth.canCheckBiometrics || await auth.isDeviceSupported();
      if (!canCheck) {
        _snack('Biometric authentication not available on this device.');
        setState(() => _fbRevealLoading = false);
        return;
      }
      authed = await auth.authenticate(
        localizedReason: 'Verify identity to view Football.com credentials',
        options: const AuthenticationOptions(biometricOnly: false),
      );
    } catch (_) {}

    if (!authed) {
      if (mounted) setState(() => _fbRevealLoading = false);
      return;
    }

    final phone = await _storage.read(key: _kFbPhone) ?? '';
    final pass = await _storage.read(key: _kFbPass) ?? '';
    final pin = await _storage.read(key: _kFbPin) ?? '';

    if (mounted) {
      _fbPhoneCtrl.text = phone;
      _fbPassCtrl.text = pass;
      _fbPinCtrl.text = pin;
      setState(() {
        _fbRevealed = true;
        _fbRevealLoading = false;
      });
    }
  }

  Future<void> _clearFbCreds() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        backgroundColor: AppColors.neutral800,
        title: Text('Clear credentials?',
            style: GoogleFonts.dmSans(color: Colors.white, fontWeight: FontWeight.w600)),
        content: Text(
          'Your Football.com credentials will be deleted from this device.',
          style: GoogleFonts.dmSans(color: AppColors.textTertiary, fontSize: 13),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: Text('Cancel', style: GoogleFonts.dmSans(color: AppColors.textTertiary)),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            child: Text('Delete', style: GoogleFonts.dmSans(color: AppColors.liveRed)),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;

    await _storage.delete(key: _kFbPhone);
    await _storage.delete(key: _kFbPass);
    await _storage.delete(key: _kFbPin);
    await _storage.delete(key: _kFbSaved);

    _fbPhoneCtrl.clear();
    _fbPassCtrl.clear();
    _fbPinCtrl.clear();
    setState(() {
      _fbSaved = false;
      _fbRevealed = false;
      _fbAgreed = false;
    });
    _snack('Credentials removed.');
  }

  void _snack(String msg, {bool success = false}) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
      content: Text(msg),
      backgroundColor: success ? AppColors.success : AppColors.liveRed,
    ));
  }

  // ─── Build ───────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.neutral900,
      appBar: AppBar(
        backgroundColor: AppColors.neutral900,
        surfaceTintColor: Colors.transparent,
        title: Text('Profile',
            style: GoogleFonts.dmSans(fontSize: 17, fontWeight: FontWeight.w600)),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios_new_rounded, size: 19),
          onPressed: () => Navigator.of(context).pop(),
        ),
      ),
      body: BlocBuilder<UserCubit, UserState>(
        builder: (context, state) {
          final user = state.user;
          return ListView(
            padding: const EdgeInsets.symmetric(horizontal: 20),
            children: [
              const SizedBox(height: 8),
              _buildProfileHeader(user),
              const SizedBox(height: 28),
              _sectionLabel('Appearance'),
              const SizedBox(height: 8),
              _buildAppearanceCard(),
              const SizedBox(height: 28),
              _sectionLabel('Device Fingerprint'),
              const SizedBox(height: 8),
              _buildFingerprintCard(),
              const SizedBox(height: 28),
              _sectionLabel('Football.com Account'),
              const SizedBox(height: 8),
              _buildFbVaultCard(user),
              const SizedBox(height: 40),
            ],
          );
        },
      ),
    );
  }

  // ─── Profile Header ──────────────────────────────────────────────

  Widget _buildProfileHeader(user) {
    final name = user.displayName ?? (user.isGuest ? 'Guest' : 'LeoBook User');
    final initials = name.length >= 2
        ? name.substring(0, 2).toUpperCase()
        : name.substring(0, 1).toUpperCase();
    final hasAvatar = user.avatarUrl != null && (user.avatarUrl as String).isNotEmpty;

    return Column(
      children: [
        const SizedBox(height: 12),
        // Avatar
        Container(
          width: 80,
          height: 80,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: AppColors.primary.withValues(alpha: 0.15),
            border: Border.all(
              color: AppColors.primary.withValues(alpha: 0.25),
              width: 2,
            ),
          ),
          child: ClipOval(
            child: hasAvatar
                ? CachedNetworkImage(
                    imageUrl: user.avatarUrl as String,
                    fit: BoxFit.cover,
                    placeholder: (_, __) => _initialsAvatar(initials),
                    errorWidget: (_, __, ___) => _initialsAvatar(initials),
                  )
                : _initialsAvatar(initials),
          ),
        ),
        const SizedBox(height: 14),
        // Name
        Text(
          name,
          style: GoogleFonts.dmSans(
            fontSize: 20,
            fontWeight: FontWeight.w700,
            color: Colors.white,
          ),
        ),
        if (user.isSuperLeoBook) ...[
          const SizedBox(height: 6),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 3),
            decoration: BoxDecoration(
              gradient: LinearGradient(colors: [AppColors.primary, AppColors.primaryLight]),
              borderRadius: BorderRadius.circular(20),
            ),
            child: Text('SUPER',
                style: GoogleFonts.dmSans(
                    fontSize: 10, fontWeight: FontWeight.w800, color: Colors.white)),
          ),
        ],
        const SizedBox(height: 16),
        // Info chips
        if (user.email != null)
          _infoRow(
            icon: Icons.alternate_email_rounded,
            text: user.email!,
            verified: user.isEmailVerified,
          ),
        if (user.phone != null && user.phone!.isNotEmpty) ...[
          const SizedBox(height: 8),
          _infoRow(
            icon: Icons.phone_iphone_rounded,
            text: user.phone!,
            verified: user.isPhoneVerified,
          ),
        ],
        const SizedBox(height: 8),
        _infoRow(
          icon: Icons.badge_outlined,
          text: user.isGuest ? 'Guest session' : 'ID: ${user.id.substring(0, 8)}…',
        ),
      ],
    );
  }

  Widget _initialsAvatar(String initials) {
    return Center(
      child: Text(
        initials,
        style: GoogleFonts.dmSans(
          fontSize: 28,
          fontWeight: FontWeight.w800,
          color: AppColors.primary,
        ),
      ),
    );
  }

  Widget _infoRow({required IconData icon, required String text, bool? verified}) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 14, color: AppColors.textTertiary),
        const SizedBox(width: 6),
        Flexible(
          child: Text(
            text,
            style: GoogleFonts.dmSans(fontSize: 13, color: AppColors.textTertiary),
            overflow: TextOverflow.ellipsis,
          ),
        ),
        if (verified == true) ...[
          const SizedBox(width: 6),
          const Icon(Icons.verified_rounded, size: 14, color: AppColors.success),
        ],
      ],
    );
  }

  // ─── Appearance ──────────────────────────────────────────────────

  Widget _buildAppearanceCard() {
    return BlocBuilder<ThemeCubit, ThemeMode>(
      builder: (context, mode) {
        return _card(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _cardRow(
                icon: Icons.brightness_auto_rounded,
                label: 'Theme',
                trailing: _ThemeSegmentedControl(current: mode),
              ),
            ],
          ),
        );
      },
    );
  }

  // ─── Device Fingerprint ──────────────────────────────────────────

  Widget _buildFingerprintCard() {
    return _card(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.lock_rounded, size: 15, color: AppColors.textTertiary),
              const SizedBox(width: 6),
              Expanded(
                child: Text(
                  'Automatically extracted from your device. Read-only — cannot be modified.',
                  style: GoogleFonts.dmSans(
                    fontSize: 12,
                    color: AppColors.textTertiary,
                    height: 1.4,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          _fpRow('Platform', _platform),
          const Divider(height: 16, thickness: 0.5, color: Colors.white10),
          _fpRow('Device', _deviceModel),
          const Divider(height: 16, thickness: 0.5, color: Colors.white10),
          _fpRow('OS', _osVersion),
        ],
      ),
    );
  }

  Widget _fpRow(String label, String value) {
    return Row(
      children: [
        SizedBox(
          width: 70,
          child: Text(label,
              style: GoogleFonts.dmSans(fontSize: 12, color: AppColors.textTertiary)),
        ),
        Expanded(
          child: Text(
            value,
            style: GoogleFonts.dmSans(
              fontSize: 13,
              color: Colors.white,
              fontWeight: FontWeight.w500,
            ),
          ),
        ),
        const Icon(Icons.lock_outline, size: 13, color: AppColors.textDisabled),
      ],
    );
  }

  // ─── Football.com Vault ──────────────────────────────────────────

  Widget _buildFbVaultCard(user) {
    return _card(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // ── Saved status header ──
          if (_fbSaved)
            _savedBanner()
          else
            _trustBanner(),

          const SizedBox(height: 20),

          // ── Fields ──────────────────────────────────────────
          _vaultField(
            controller: _fbPhoneCtrl,
            label: 'Football.com Phone Number',
            hint: 'e.g. 08012345678',
            icon: Icons.phone_outlined,
            obscure: _fbSaved && !_fbRevealed,
            readOnly: _fbSaved && !_fbRevealed,
            keyboardType: TextInputType.phone,
          ),
          const SizedBox(height: 12),
          _vaultField(
            controller: _fbPassCtrl,
            label: 'Football.com Password',
            hint: 'Your football.com login password',
            icon: Icons.lock_outline_rounded,
            obscure: true,
            readOnly: _fbSaved && !_fbRevealed,
          ),
          const SizedBox(height: 12),
          _vaultField(
            controller: _fbPinCtrl,
            label: 'Withdrawal PIN',
            hint: '4–6 digit PIN',
            icon: Icons.pin_outlined,
            obscure: true,
            readOnly: _fbSaved && !_fbRevealed,
            keyboardType: TextInputType.number,
            inputFormatters: [
              FilteringTextInputFormatter.digitsOnly,
              LengthLimitingTextInputFormatter(6),
            ],
          ),

          const SizedBox(height: 20),

          // ── Actions ─────────────────────────────────────────
          if (!_fbSaved) ...[
            // Agree checkbox
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Checkbox(
                  value: _fbAgreed,
                  activeColor: AppColors.primary,
                  side: const BorderSide(color: AppColors.textTertiary),
                  onChanged: (v) => setState(() => _fbAgreed = v ?? false),
                  visualDensity: VisualDensity.compact,
                ),
                const SizedBox(width: 4),
                Expanded(
                  child: GestureDetector(
                    onTap: () => setState(() => _fbAgreed = !_fbAgreed),
                    child: Text(
                      'By saving these details I confirm I have read and agree to '
                      'LeoBook\'s Terms of Service and Privacy Policy, and I authorise '
                      'LeoBook to use these credentials solely for automated betting '
                      'on my behalf.',
                      style: GoogleFonts.dmSans(
                        fontSize: 12,
                        color: AppColors.textTertiary,
                        height: 1.45,
                      ),
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: (_fbSaving || !_fbAgreed) ? null : _saveFbCreds,
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppColors.primary,
                  foregroundColor: Colors.black,
                  disabledBackgroundColor: AppColors.primary.withValues(alpha: 0.25),
                  padding: const EdgeInsets.symmetric(vertical: 14),
                  shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12)),
                ),
                child: _fbSaving
                    ? const SizedBox(
                        height: 18,
                        width: 18,
                        child: CircularProgressIndicator(
                            color: Colors.black, strokeWidth: 2))
                    : Text('Save credentials securely',
                        style: GoogleFonts.dmSans(
                            fontWeight: FontWeight.bold, fontSize: 14)),
              ),
            ),
          ] else ...[
            Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: _fbRevealLoading ? null : (_fbRevealed ? null : _revealFbCreds),
                    icon: _fbRevealLoading
                        ? const SizedBox(
                            height: 14,
                            width: 14,
                            child: CircularProgressIndicator(
                                strokeWidth: 2, color: AppColors.primary))
                        : Icon(
                            _fbRevealed
                                ? Icons.visibility_off_outlined
                                : Icons.fingerprint_rounded,
                            size: 18,
                          ),
                    label: Text(
                      _fbRevealed ? 'Credentials visible' : 'View credentials',
                      style: GoogleFonts.dmSans(fontSize: 13),
                    ),
                    style: OutlinedButton.styleFrom(
                      foregroundColor: _fbRevealed ? AppColors.textTertiary : AppColors.primary,
                      side: BorderSide(
                          color: _fbRevealed
                              ? AppColors.textTertiary.withValues(alpha: 0.4)
                              : AppColors.primary.withValues(alpha: 0.5)),
                      padding: const EdgeInsets.symmetric(vertical: 12),
                      shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(10)),
                    ),
                  ),
                ),
                const SizedBox(width: 10),
                OutlinedButton(
                  onPressed: _clearFbCreds,
                  style: OutlinedButton.styleFrom(
                    foregroundColor: AppColors.liveRed,
                    side: BorderSide(
                        color: AppColors.liveRed.withValues(alpha: 0.4)),
                    padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 14),
                    shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(10)),
                  ),
                  child: const Icon(Icons.delete_outline_rounded, size: 18),
                ),
              ],
            ),
            if (_fbRevealed) ...[
              const SizedBox(height: 12),
              SizedBox(
                width: double.infinity,
                child: ElevatedButton(
                  onPressed: _fbSaving ? null : _saveFbCreds,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppColors.primary,
                    foregroundColor: Colors.black,
                    padding: const EdgeInsets.symmetric(vertical: 14),
                    shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12)),
                  ),
                  child: Text('Update credentials',
                      style: GoogleFonts.dmSans(
                          fontWeight: FontWeight.bold, fontSize: 14)),
                ),
              ),
            ],
          ],
        ],
      ),
    );
  }

  Widget _trustBanner() {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.primary.withValues(alpha: 0.06),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: AppColors.primary.withValues(alpha: 0.15)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.shield_outlined,
                  size: 16, color: AppColors.primary.withValues(alpha: 0.9)),
              const SizedBox(width: 8),
              Text('Trust & Security',
                  style: GoogleFonts.dmSans(
                    fontSize: 13,
                    fontWeight: FontWeight.w600,
                    color: Colors.white,
                  )),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            'Your Football.com credentials are stored exclusively on this device using '
            'hardware-backed encrypted storage. LeoBook never transmits them to any '
            'server. They are used only when you authorise an automated action — '
            'such as booking a bet or initiating a withdrawal to your registered '
            'bank account on Football.com. Credentials are only revealed after '
            'successful biometric verification.',
            style: GoogleFonts.dmSans(
              fontSize: 12,
              color: AppColors.textTertiary,
              height: 1.5,
            ),
          ),
        ],
      ),
    );
  }

  Widget _savedBanner() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: AppColors.success.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: AppColors.success.withValues(alpha: 0.2)),
      ),
      child: Row(
        children: [
          const Icon(Icons.verified_user_rounded,
              size: 16, color: AppColors.success),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              'Credentials saved on this device. Tap "View credentials" and verify '
              'with biometrics to inspect or update them.',
              style: GoogleFonts.dmSans(
                  fontSize: 12, color: AppColors.textSecondary, height: 1.4),
            ),
          ),
        ],
      ),
    );
  }

  Widget _vaultField({
    required TextEditingController controller,
    required String label,
    required String hint,
    required IconData icon,
    bool obscure = false,
    bool readOnly = false,
    TextInputType? keyboardType,
    List<TextInputFormatter>? inputFormatters,
  }) {
    return TextField(
      controller: controller,
      obscureText: obscure,
      readOnly: readOnly,
      keyboardType: keyboardType,
      inputFormatters: inputFormatters,
      style: TextStyle(
        color: readOnly ? AppColors.textTertiary : Colors.white,
        fontSize: 14,
      ),
      decoration: InputDecoration(
        labelText: label,
        labelStyle:
            GoogleFonts.dmSans(fontSize: 12, color: AppColors.textTertiary),
        hintText: hint,
        hintStyle:
            const TextStyle(color: AppColors.textDisabled, fontSize: 13),
        prefixIcon: Icon(icon, color: AppColors.textTertiary, size: 18),
        suffixIcon: readOnly
            ? const Icon(Icons.lock_rounded,
                size: 15, color: AppColors.textDisabled)
            : null,
        filled: true,
        fillColor: readOnly
            ? AppColors.neutral700.withValues(alpha: 0.25)
            : AppColors.neutral800,
        contentPadding:
            const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: BorderSide.none,
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: AppColors.primary, width: 1.5),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide:
              BorderSide(color: Colors.white.withValues(alpha: 0.06)),
        ),
      ),
    );
  }

  // ─── Shared helpers ──────────────────────────────────────────────

  Widget _card({required Widget child}) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.neutral800,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: Colors.white.withValues(alpha: 0.06)),
      ),
      child: child,
    );
  }

  Widget _cardRow({
    required IconData icon,
    required String label,
    required Widget trailing,
  }) {
    return Row(
      children: [
        Icon(icon, size: 18, color: AppColors.textTertiary),
        const SizedBox(width: 10),
        Expanded(
          child: Text(label,
              style: GoogleFonts.dmSans(fontSize: 14, color: Colors.white)),
        ),
        trailing,
      ],
    );
  }

  Widget _sectionLabel(String text) => Padding(
        padding: const EdgeInsets.only(left: 2),
        child: Text(
          text,
          style: GoogleFonts.dmSans(
            fontSize: 12,
            fontWeight: FontWeight.w500,
            color: AppColors.textTertiary,
          ),
        ),
      );
}

// ─── Theme Segmented Control ─────────────────────────────────────────────────

class _ThemeSegmentedControl extends StatelessWidget {
  final ThemeMode current;
  const _ThemeSegmentedControl({required this.current});

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: AppColors.neutral700.withValues(alpha: 0.5),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          _seg(context, ThemeMode.system, Icons.brightness_auto_rounded, 'Auto'),
          _seg(context, ThemeMode.light, Icons.light_mode_outlined, 'Light'),
          _seg(context, ThemeMode.dark, Icons.dark_mode_outlined, 'Dark'),
        ],
      ),
    );
  }

  Widget _seg(BuildContext ctx, ThemeMode mode, IconData icon, String label) {
    final selected = current == mode;
    return GestureDetector(
      onTap: () {
        final cubit = ctx.read<ThemeCubit>();
        if (mode == ThemeMode.system) cubit.setSystem();
        if (mode == ThemeMode.light) cubit.setLight();
        if (mode == ThemeMode.dark) cubit.setDark();
      },
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 180),
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
        decoration: BoxDecoration(
          color: selected
              ? AppColors.primary.withValues(alpha: 0.2)
              : Colors.transparent,
          borderRadius: BorderRadius.circular(7),
          border: selected
              ? Border.all(color: AppColors.primary.withValues(alpha: 0.4))
              : null,
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 14,
                color: selected ? AppColors.primary : AppColors.textTertiary),
            const SizedBox(width: 4),
            Text(
              label,
              style: GoogleFonts.dmSans(
                fontSize: 12,
                fontWeight: selected ? FontWeight.w600 : FontWeight.w400,
                color: selected ? AppColors.primary : AppColors.textTertiary,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
